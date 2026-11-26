"""Run one WP04 calibration action on the rig (experiments/physical_characterization.md
sections 3-7; D50).

PHYSICAL ACTUATION for every action except `readings`. Use only with an
uploaded, approved firmware and a calibration plan approved by the researcher.

Actions (`kind` in the plan):
  readings         M1, M2: the researcher enters settled readings; no pumping
  timed_fill       M3, M4, M5: intake ON with limit = duration; the firmware
                   cut-off ends the fill; settled end reading (optionally a
                   series of readings with elapsed times, for the settling time)
  latency          M6: round trips of a state request; pumps OFF
  sensor_steps     M7: short firmware-timed pulses; reading and sensor state
                   after each; stops at the first wet state
  sensor_crossing  M8: intake ON until the first wet report (host switches
                   OFF), limit = max_ms; settled end reading

Gates before any pump switches ON: plan approval recorded; label once in the
plan; plan ceiling = largest limit in the plan = firmware ceiling; the
planned end V0 + band + q_hi x (longest possible ON time) <= safe mark - 2
graduations, with q_hi and its source from the plan; settled start reading
within the planned band; sensor wired for sensor actions; the researcher
types RUN.

Output: experiments/data/<session_id>/<label>/calibration.json and events.csv.
Calibration data are never scored and never written to experiments/logs.

Usage (from the repository root, after `pip install pyserial`):
    PYTHONPATH=src python3 -m shared.run_calibration --plan PLAN.json --action LABEL \
        --rig-config RIG.json --port /dev/ttyACM0 --out experiments/data
"""

import argparse
import datetime
import hashlib
import json
import os
import sys
import time
from types import SimpleNamespace

from shared.rig_environment import RigEnvironment, RigError, SerialLink
from shared.run_files import EVENT_COLUMNS, _write_csv
from shared.run_scenario import ConfigurationError, _relative, provenance

KINDS = ("readings", "timed_fill", "latency", "sensor_steps", "sensor_crossing")
PUMPING = ("timed_fill", "sensor_steps", "sensor_crossing")
SENSOR_KINDS = ("sensor_steps", "sensor_crossing")
# Measurement IDs of experiments/physical_characterization.md section 4, by kind.
MEASURES = {"readings": ("M1", "M2"), "timed_fill": ("M3", "M4", "M5"), "latency": ("M6",),
            "sensor_steps": ("M7",), "sensor_crossing": ("M8",)}
POLL_MS = 5


def limit_ms(action):
    """Cut-off limit the action sets (None if it does not pump)."""
    return {"timed_fill": action.get("duration_ms"), "sensor_steps": action.get("pulse_ms"),
            "sensor_crossing": action.get("max_ms")}.get(action["kind"])


def max_on_ms(action):
    """Longest total ON time the action can produce."""
    if action["kind"] == "sensor_steps":
        return action["pulse_ms"] * action["max_pulses"]
    return limit_ms(action)


def check_plan(plan, label, firmware_ceiling_ms=None):
    """Return (action, problems). firmware_ceiling_ms None: not checked (readings)."""
    problems = []
    if not str(plan.get("approved_by") or "").strip() or not str(plan.get("approved_on") or "").strip():
        problems.append("calibration plan has no researcher approval (approved_by, approved_on)")
    actions = plan.get("actions") or []
    found = [a for a in actions if a.get("label") == label]
    if len(found) != 1:
        return None, problems + [f"action {label!r} is not exactly once in the plan"]
    action = found[0]
    kind = action.get("kind")
    if kind not in KINDS:
        return action, problems + [f"unknown kind {kind!r}"]
    if action.get("measure") not in MEASURES.get(kind, ()):
        problems.append(f"measure must be one of {MEASURES[kind]} for kind {kind!r}")
    required = {"readings": ("count",), "latency": ("count",),
                "timed_fill": ("duration_ms", "tube", "v0_plan_ml", "v0_band_ml"),
                "sensor_steps": ("pulse_ms", "max_pulses", "settle_ms", "v0_plan_ml",
                                 "v0_band_ml"),
                "sensor_crossing": ("max_ms", "v0_plan_ml", "v0_band_ml")}[kind]
    missing = [k for k in required if k not in action]
    if missing:
        return action, problems + [f"action lacks {missing}"]
    if kind == "timed_fill" and action["tube"] not in ("empty", "primed"):
        problems.append("tube must be 'empty' or 'primed'")
    if kind not in PUMPING:
        return action, problems

    limits = [limit_ms(a) for a in actions if a.get("kind") in PUMPING]
    if not all(isinstance(x, int) and not isinstance(x, bool) and x > 0 for x in limits):
        return action, problems + ["every pumping action needs a positive integer limit in ms"]
    if plan.get("firmware_ceiling_ms") != max(limits):
        problems.append(f"plan ceiling {plan.get('firmware_ceiling_ms')} != largest limit of "
                        f"the plan {max(limits)}")
    if firmware_ceiling_ms is not None and plan.get("firmware_ceiling_ms") != firmware_ceiling_ms:
        problems.append(f"firmware ceiling {firmware_ceiling_ms} != plan ceiling "
                        f"{plan.get('firmware_ceiling_ms')}")
    for key in ("graduation_ml", "safe_mark_ml", "q_hi_ml_per_s"):
        if not isinstance(plan.get(key), (int, float)) or plan.get(key) <= 0:
            problems.append(f"plan needs a positive {key} (researcher or measured value)")
    if not str(plan.get("q_hi_source") or "").strip():
        problems.append("plan needs q_hi_source (where the rate bound comes from)")
    if problems:
        return action, problems
    worst = (float(action["v0_plan_ml"]) + float(action["v0_band_ml"])
             + plan["q_hi_ml_per_s"] * max_on_ms(action) / 1000)
    allowed = plan["safe_mark_ml"] - 2 * plan["graduation_ml"]
    if worst > allowed + 1e-9:
        problems.append(f"planned worst end {worst:.2f} mL > safe mark - 2 graduations "
                        f"{allowed:.2f} mL (physical_characterization.md section 6)")
    return action, problems


def _ask_float(ask, prompt, allow_blank=False):
    while True:
        text = ask(prompt).strip()
        if allow_blank and not text:
            return None
        try:
            return float(text)
        except ValueError:
            print("Enter a number in mL.")


class _Session:
    """Shared steps of the pumping actions."""

    def __init__(self, env, ask, clock_ns):
        self.env, self.ask, self.clock_ns = env, ask, clock_ns

    def start_reading(self, action):
        v0 = _ask_float(self.ask, "Settled START reading (mL): ")
        u = _ask_float(self.ask, "Reading uncertainty (mL): ")
        if abs(v0 - float(action["v0_plan_ml"])) > float(action["v0_band_ml"]) + 1e-9:
            raise ConfigurationError(f"start {v0} mL outside {action['v0_plan_ml']} +/- "
                                     f"{action['v0_band_ml']} mL: redo the reset")
        if self.ask("The intake will be switched ON. Type RUN to start: ").strip() != "RUN":
            raise ConfigurationError("not confirmed; nothing was run")
        return {"volume_ml": v0, "uncertainty_ml": u}

    def wait_cutoff(self, limit):
        env = self.env
        deadline = env.now_ms() + limit + env.config.cutoff_grace_ms + 100   # from the ON command
        while env.run_valid and not env.cutoff_seen("intake") and env.now_ms() <= deadline:
            env.advance_to(env.now_ms() + POLL_MS)
        return env.cutoff_seen("intake")

    def wait(self, ms):
        self.env.advance_to(self.env.now_ms() + ms)

    def end_reading(self, series):
        """Settled end reading; with series=True, readings with elapsed times."""
        t_off = self.clock_ns()
        readings = []
        if series:
            print("Enter readings as the level settles; blank when it has stopped changing.")
            while True:
                elapsed = (self.clock_ns() - t_off) / 1e9
                v = _ask_float(self.ask, f"[{elapsed:6.1f} s after OFF] reading (mL), blank "
                                         "to finish: ", allow_blank=True)
                if v is None:
                    break
                readings.append({"elapsed_s": round((self.clock_ns() - t_off) / 1e9, 3),
                                 "volume_ml": v})
            end = readings[-1]["volume_ml"] if readings else None
        else:
            end = _ask_float(self.ask, "Settled END reading (mL, blank if not readable): ",
                             allow_blank=True)
        u = _ask_float(self.ask, "Reading uncertainty (mL): ") if end is not None else None
        return {"volume_ml": end, "uncertainty_ml": u, "series": readings}


def _cutoff_events(env):
    out = []
    for t, _src, event, detail in env.events:
        if event == "cutoff":
            fields = dict(f.split("=", 1) for f in detail.split())
            out.append({"t_ms": t, "on_ms": int(fields["on_ms"]), "fw_ms": int(fields["fw_ms"])})
    return out


def run_action(plan_path, label, link, rig_config, out_dir, *, ask=input,
               clock_ns=time.monotonic_ns, sleep=time.sleep, port=None, run_id=None):
    """Execute one planned calibration action; return its output directory."""
    with open(plan_path, "rb") as fh:
        raw = fh.read()
    plan, plan_sha = json.loads(raw), hashlib.sha256(raw).hexdigest()

    action, problems = check_plan(plan, label)
    if problems:
        raise ConfigurationError("action refused:\n  - " + "\n  - ".join(problems))
    kind = action["kind"]
    env, info = None, None
    if kind != "readings":
        sensor = kind in SENSOR_KINDS          # sensor actions start dry and need the sensor
        env = RigEnvironment(link, rig_config, settle_ms=0,
                             start_sensor_wet=False if sensor else None,
                             allow_unwired_sensor=not sensor,
                             clock_ns=clock_ns, sleep=sleep)
        try:
            info = env.connect()
        except RigError as exc:
            raise ConfigurationError(f"rig not ready: {exc}") from None
        _, problems = check_plan(plan, label, info["ceiling_ms"])
        if kind in SENSOR_KINDS and (info["sensor_pin"] < 0 or rig_config.sensor_wet_level is None):
            problems.append("sensor action needs the sensor wired (firmware SENSOR_PIN, "
                            "rig config sensor_wet_level)")
        if problems:
            raise ConfigurationError("action refused:\n  - " + "\n  - ".join(problems))

    out = os.path.join(out_dir, str(plan.get("session_id")), run_id or label)
    if os.path.exists(out):
        raise ConfigurationError(f"output directory exists: {out}")
    print(f"Action {label}: {kind} {json.dumps(action)}")

    record = {"label": label, "kind": kind, "action": action,
              "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
              **provenance(),
              "plan": {"file": _relative(os.path.abspath(plan_path)), "sha256": plan_sha,
                       "session_id": plan.get("session_id"),
                       "approved_by": plan.get("approved_by"),
                       "approved_on": plan.get("approved_on"),
                       "q_hi_ml_per_s": plan.get("q_hi_ml_per_s"),
                       "q_hi_source": plan.get("q_hi_source")},
              "rig": None if env is None else {"firmware": info, "port": port,
                                               "adapter_config": rig_config.as_dict()},
              "purpose": "calibration", "valid": True}
    s = None if env is None else _Session(env, ask, clock_ns)

    if kind == "readings":
        t0 = clock_ns()
        readings = []
        for i in range(action["count"]):
            v = _ask_float(ask, f"Reading {i + 1}/{action['count']} (mL): ")
            readings.append({"elapsed_s": round((clock_ns() - t0) / 1e9, 3), "volume_ml": v})
        record["readings"] = readings
        record["uncertainty_ml"] = _ask_float(ask, "Reading uncertainty (mL): ")
        record["note"] = ask("Note (blank if none): ").strip()

    elif kind == "latency":
        env.start(SimpleNamespace(t_max_ms=info["ceiling_ms"]))   # pumps OFF, limit valid
        record["round_trips_ms"] = [round(env.round_trip_ms(), 3)
                                    for _ in range(action["count"])]

    else:
        try:
            record["start"] = s.start_reading(action)
            limit = limit_ms(action)
            env.start(SimpleNamespace(t_max_ms=limit))
            if kind == "timed_fill":
                env.command(True, False)
                record["cutoff_seen"] = s.wait_cutoff(limit)
                env.command(False, False)
                env.finish()
                record["end"] = s.end_reading(series=bool(action.get("settle_readings")))
            elif kind == "sensor_steps":
                steps = []
                for i in range(action["max_pulses"]):
                    env.command(True, False)
                    cut = s.wait_cutoff(limit)
                    env.command(False, False)
                    s.wait(action["settle_ms"])
                    v = _ask_float(ask, f"Pulse {i + 1}: settled reading (mL): ")
                    wet = env.sensor()
                    steps.append({"pulse": i + 1, "cutoff_seen": cut, "volume_ml": v,
                                  "sensor_wet": wet})
                    print(f"  sensor {'WET' if wet else 'dry'}")
                    if wet or not env.run_valid:
                        break
                env.finish()
                record["steps"] = steps
            else:  # sensor_crossing
                env.command(True, False)
                wet_ms = None
                while env.run_valid and not env.cutoff_seen("intake"):
                    if env.sensor():
                        wet_ms = env.now_ms()
                        break
                    env.advance_to(env.now_ms() + POLL_MS)
                env.command(False, False)
                off_ms = env.now_ms()
                env.finish()
                edges = [t for t, _s, e, d in env.events if e == "sensor_edge" and "wet=True" in d]
                record["crossing"] = {"wet_seen_ms": wet_ms, "off_ms": off_ms,
                                      "wet_edge_ms": edges[0] if edges else None,
                                      "cutoff_seen": env.cutoff_seen("intake")}
                record["end"] = s.end_reading(series=False)
        except RigError as exc:
            env.stop_pumps("start refused")
            raise ConfigurationError(f"action not started: {exc}") from None
        except BaseException:
            env.stop_pumps("exception")
            raise
        record["cutoffs"] = _cutoff_events(env)
        record["note"] = ask("Anomalies (blank if none): ").strip()

    if env is not None:
        record["valid"] = env.run_valid
        if not env.run_valid:
            print("ACTION INVALID: see events.csv. Stop the session and review.")
    os.makedirs(out, exist_ok=False)
    with open(os.path.join(out, "calibration.json"), "x", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2)
        fh.write("\n")
    if env is not None:
        _write_csv(os.path.join(out, "events.csv"), EVENT_COLUMNS,
                   sorted(env.events, key=lambda e: e[0]))
    return out


def main(argv=None):
    from shared.run_rig import load_rig_config
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--plan", required=True, help="approved calibration plan (JSON)")
    parser.add_argument("--action", required=True, help="action label in the plan")
    parser.add_argument("--rig-config", help="adapter settings (JSON); not for readings")
    parser.add_argument("--port", help="serial port of the ESP32; not for readings")
    parser.add_argument("--out", required=True, help="parent directory, e.g. experiments/data")
    args = parser.parse_args(argv)
    with open(args.plan, encoding="utf-8") as fh:
        kind = next((a.get("kind") for a in json.load(fh).get("actions", [])
                     if a.get("label") == args.action), None)
    link = config = None
    if kind != "readings":
        if not args.rig_config or not args.port:
            parser.error("--rig-config and --port are needed for rig actions")
        config, link = load_rig_config(args.rig_config), SerialLink(args.port)
    try:
        print(run_action(args.plan, args.action, link, config, args.out, port=args.port))
    except ConfigurationError as exc:
        print(exc, file=sys.stderr)
        return 2
    finally:
        if link is not None:
            link.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
