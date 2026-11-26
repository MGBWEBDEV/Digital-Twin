"""Run one controller run on the physical rig and write its run files
(WP09a; protocol sections 6-8 and 16; D27, D45, D46; D49).

PHYSICAL ACTUATION. Use only with an uploaded, approved firmware and a
written session plan approved by the researcher (protocol section 7.1).

Gates before any pump is switched ON:
1. The session plan file records who approved it and when; the run label is
   in it; the controller file has the planned SHA-256 and passes the D37
   static check.
2. The plan's ceiling equals its largest T_max (D45) and equals the ceiling
   the firmware reports; the run's T_max is not above it.
3. Purposes: `reference` and `fault` runs must match the scenario and the
   parameter set exactly (V0, R14 band, D45 T_max, R01, R08, R09, start
   sensor state) and no parameter may be a placeholder (D34). `cutoff_check`
   runs (protocol section 7.4) use the plan's values as given and only test
   doubles from src/shared/tests/doubles/.
4. The researcher enters the settled start reading; it must be within the
   planned V0 +/- band (D46 (1)); the firmware's sensor state must match the
   plan; the researcher types RUN.

During the run, Ctrl-C stops the pumps and invalidates the run (a second
Ctrl-C aborts the program). After the settle time the researcher enters the
end reading (and a peak if one was visibly higher, D41 (8)).

In run.json, `v0_ml` is the PLANNED start volume (the rig is not given a
volume; the evaluator compares it with the scenario) and the settled start
reading is in manual.csv and `v0_start_reading_ml`.

Usage (from the repository root, after `pip install pyserial`):
    PYTHONPATH=src python3 -m shared.run_rig --session-plan PLAN.json --run LABEL \
        --rig-config RIG.json --port /dev/ttyACM0 --out experiments/logs
"""

import argparse
import csv
import datetime
import hashlib
import json
import math
import os
import signal
import sys
import time

from shared import harness
from shared.controller_check import check_file, load_controller_class
from shared.rig_environment import RigConfig, RigEnvironment, RigError, SerialLink
from shared.run_files import write_run_files
from shared.run_scenario import (REPO, ConfigurationError, _relative, generation_id, ms,
                                 planned_t_max_ms, provenance, t_max_inputs)

RIG_PURPOSES = ("reference", "fault", "cutoff_check")
DOUBLES_DIR = os.path.join(REPO, "src", "shared", "tests", "doubles")
ENTRY_KEYS = ("label", "purpose", "controller", "controller_sha256", "scenario_id",
              "v0_plan_ml", "v0_band_ml", "start_sensor", "t_max_ms", "dt_call_ms",
              "t_end_ms", "settle_ms")


def _sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def load_plan(path):
    with open(path, encoding="utf-8") as fh:
        plan = json.load(fh)
    return plan, _sha256(path)


def _resolve(path):
    return path if os.path.isabs(path) else os.path.join(REPO, path)


def check_plan(plan, label, firmware_ceiling_ms, scenarios, params, placeholders):
    """Return (entry, problems). problems empty means the run may start."""
    problems = []
    if not str(plan.get("approved_by") or "").strip() or not str(plan.get("approved_on") or "").strip():
        problems.append("session plan has no researcher approval (approved_by, approved_on)")
    runs = plan.get("runs") or []
    entries = [r for r in runs if r.get("label") == label]
    if len(entries) != 1:
        return None, problems + [f"run {label!r} is not exactly once in the session plan"]
    entry = entries[0]
    missing = [k for k in ENTRY_KEYS if k not in entry]
    if missing:
        return entry, problems + [f"plan entry lacks {missing}"]

    t_maxes = [r.get("t_max_ms") for r in runs]
    if not all(isinstance(t, int) and t > 0 for t in t_maxes):
        problems.append("every plan entry needs a positive integer t_max_ms")
    elif plan.get("firmware_ceiling_ms") != max(t_maxes):
        problems.append(f"plan ceiling {plan.get('firmware_ceiling_ms')} != largest "
                        f"T_max of the plan {max(t_maxes)} (D45)")
    if plan.get("firmware_ceiling_ms") != firmware_ceiling_ms:
        problems.append(f"firmware ceiling {firmware_ceiling_ms} != plan ceiling "
                        f"{plan.get('firmware_ceiling_ms')} (protocol 6.1 (3))")

    purpose = entry["purpose"]
    if purpose not in RIG_PURPOSES:
        problems.append(f"purpose {purpose!r} is not a rig controller run {RIG_PURPOSES}")
    if entry["scenario_id"] not in scenarios:
        return entry, problems + [f"unknown scenario {entry['scenario_id']!r}"]
    if entry["start_sensor"] not in ("wet", "dry", None):
        problems.append("start_sensor must be 'wet', 'dry' or null")
    controller = os.path.abspath(_resolve(entry["controller"]))
    if not os.path.isfile(controller):
        return entry, problems + [f"controller file not found: {entry['controller']}"]
    if _sha256(controller) != entry["controller_sha256"]:
        problems.append("controller SHA-256 differs from the session plan")
    in_doubles = os.path.dirname(controller) == DOUBLES_DIR

    if purpose == "cutoff_check":
        if not in_doubles:
            problems.append("a cut-off check runs only test doubles from "
                            "src/shared/tests/doubles/ (protocol 7.4)")
        return entry, problems

    if entry["start_sensor"] is None:
        problems.append("reference and fault runs need the sensor (start_sensor)")
    if in_doubles:
        problems.append("a test double is never a reference or fault controller (D29)")
    if placeholders:
        problems.append(f"placeholder parameters {placeholders} may not be used for a "
                        "physical run (D34); set the final values first")
        return entry, problems
    case = scenarios[entry["scenario_id"]]
    expected = {
        "v0_plan_ml": case.v0_ml, "v0_band_ml": params["R14"],
        "t_max_ms": planned_t_max_ms(case, params), "dt_call_ms": ms(params["R01"]),
        "t_end_ms": ms(params["R08"]), "settle_ms": ms(params["R09"]),
        "start_sensor": "wet" if case.v0_ml >= params["P05"] else "dry",
    }
    for key, value in expected.items():
        got = entry[key]
        same = got == value if isinstance(value, str) else (
            got is not None and math.isclose(float(got), float(value), abs_tol=1e-9))
        if not same:
            problems.append(f"plan {key} {got!r} != scenario/parameter value {value!r}")
    return entry, problems


def _ask_float(ask, prompt, allow_blank=False):
    while True:
        text = ask(prompt).strip()
        if allow_blank and not text:
            return None
        try:
            return float(text)
        except ValueError:
            print("Enter a number in mL.")


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def run_rig(plan_path, label, link, rig_config, out_dir, *, ask=input,
            clock_ns=time.monotonic_ns, sleep=time.sleep, port=None,
            install_signal_handler=True, run_id=None, scenarios=None, parameters=None):
    """Execute one planned rig run; return the run directory (or raise)."""
    from testing import parameters as testing_parameters
    from testing.scenarios import SCENARIO_RUNS

    scenarios = SCENARIO_RUNS if scenarios is None else scenarios
    params_table = testing_parameters.PARAMETERS if parameters is None else parameters
    params = testing_parameters.values(params_table)
    placeholders = testing_parameters.placeholder_ids(params_table)
    plan, plan_sha = load_plan(plan_path)

    # Run settings are filled in once the plan entry is known (below).
    env = RigEnvironment(link, rig_config, settle_ms=0, start_sensor_wet=None,
                         allow_unwired_sensor=True, clock_ns=clock_ns, sleep=sleep)
    try:
        info = env.connect()
        entry, problems = check_plan(plan, label, info["ceiling_ms"], scenarios, params,
                                     placeholders)
        controller_path = os.path.abspath(_resolve(entry["controller"])) if entry else None
        if not problems:
            check = check_file(controller_path)
            if not check.ok:
                problems.append("controller fails the D37 static check; not run on the rig")
        if problems:
            raise ConfigurationError("run refused:\n  - " + "\n  - ".join(problems))
    except RigError as exc:
        raise ConfigurationError(f"rig not ready: {exc}") from None

    case = scenarios[entry["scenario_id"]]
    start_wet = {"wet": True, "dry": False, None: None}[entry["start_sensor"]]
    env.settle_ms = entry["settle_ms"]
    env.start_sensor_wet = start_wet
    env.allow_unwired_sensor = entry["start_sensor"] is None
    request = harness.Request(task=case.task, parameter=case.parameter,
                              v_sensor_ml=params["P05"], q_in_ml_per_s=params["P06"],
                              t_deadline_s=params["R06"])
    run_plan = harness.RunPlan(scenario_id=case.run_case, v0_ml=entry["v0_plan_ml"],
                               request=request, sensor_override=case.sensor_override,
                               dt_call_ms=entry["dt_call_ms"], t_end_ms=entry["t_end_ms"],
                               t_max_ms=entry["t_max_ms"])

    now = datetime.datetime.now(datetime.timezone.utc)
    run_id = run_id or f"{now:%Y%m%dT%H%M%SZ}_rig_{case.run_case}_{entry['controller_sha256'][:8]}"
    run_dir = os.path.join(out_dir, run_id)
    if os.path.exists(run_dir):
        raise ConfigurationError(f"run directory exists: {run_dir}")

    print(f"Run {label}: {entry['purpose']} {case.run_case}, controller "
          f"{entry['controller']}, planned V0 {entry['v0_plan_ml']} mL "
          f"+/- {entry['v0_band_ml']}, T_max {entry['t_max_ms']} ms, "
          f"T_end {entry['t_end_ms']} ms, sensor at start {entry['start_sensor']}.")
    v0_read = _ask_float(ask, "Settled START reading V0 (mL): ")
    v0_unc = _ask_float(ask, "Reading uncertainty (mL): ")
    if abs(v0_read - float(entry["v0_plan_ml"])) > float(entry["v0_band_ml"]) + 1e-9:
        raise ConfigurationError(f"V0 {v0_read} mL outside {entry['v0_plan_ml']} +/- "
                                 f"{entry['v0_band_ml']} mL: redo the reset (protocol 6.2 (4))")
    start_time = _now_iso()
    if ask("Pumps will be switched by the controller. Type RUN to start: ").strip() != "RUN":
        raise ConfigurationError("not confirmed; nothing was run")

    controller_class = load_controller_class(controller_path)
    previous = None
    if install_signal_handler:
        def on_interrupt(signum, frame):
            env.request_stop("researcher interrupt (Ctrl-C)")
            signal.signal(signal.SIGINT, signal.default_int_handler)
        previous = signal.signal(signal.SIGINT, on_interrupt)
    try:
        record = harness.run_controller(controller_class, env, run_plan)
    except RigError as exc:
        env.stop_pumps("start refused")
        raise ConfigurationError(f"run not started: {exc}") from None
    except BaseException:
        env.stop_pumps("exception")
        raise
    finally:
        if install_signal_handler:
            signal.signal(signal.SIGINT, previous)

    if not env.run_valid:
        print("RUN INVALID: see events.csv. Stop the session and review (protocol 6.4).")
    v_end = _ask_float(ask, "Settled END reading (mL, blank if not readable): ", allow_blank=True)
    end_time = _now_iso()
    v_end_unc = _ask_float(ask, "Reading uncertainty (mL): ") if v_end is not None else None
    v_peak = _ask_float(ask, "Higher settled PEAK reading (mL, blank if none): ",
                        allow_blank=True)
    note = ask("Anomalies (sound, drips, indicator differs; blank if none): ").strip()

    difference = (harness.replay(controller_class, request, record.calls)
                  if record.end_reason == harness.END_NORMAL else None)
    events = list(env.events) + record.events
    if difference is not None:
        events.append((difference["t_ms"] or 0, harness.SOURCE, "replay_differs",
                       str(difference)))
    if entry["purpose"] == "cutoff_check":
        t_max_rule = {"rule": "session plan test limit (protocol 7.4)",
                      "inputs": {"t_max_ms": entry["t_max_ms"]}}
    else:
        t_max_rule = {"rule": "D45, protocol section 8", "inputs": t_max_inputs(case, params)}
    run = {
        "run_id": run_id,
        "date_utc": now.isoformat(timespec="seconds"),
        **provenance(),
        "controller": {"file": _relative(controller_path), "sha256": entry["controller_sha256"],
                       "generation_id": generation_id(controller_path),
                       "rule_check": check.as_dict()},
        "environment": "rig",
        "model": None,
        "rig": {"firmware": info, "port": port, "adapter_config": rig_config.as_dict()},
        "session_plan": {"file": _relative(os.path.abspath(plan_path)), "sha256": plan_sha,
                         "session_id": plan.get("session_id"),
                         "approved_by": plan.get("approved_by"),
                         "approved_on": plan.get("approved_on"), "entry": entry},
        "scenario_id": case.run_case,
        "purpose": entry["purpose"],
        "paired_with": None,
        "v0_plan_ml": entry["v0_plan_ml"],
        "v0_ml": entry["v0_plan_ml"],
        "v0_start_reading_ml": v0_read,
        "t_max_s": entry["t_max_ms"] / 1000,
        "t_max_rule": t_max_rule,
        "sensor_override": case.sensor_override,
        "request": request.as_dict(),
        "parameters": params,
        "placeholder_parameters": bool(placeholders),
        "dt_call_ms": entry["dt_call_ms"],
        "dt_sim_ms": None,
        "t_end_ms": entry["t_end_ms"],
        "settle_ms": entry["settle_ms"],
        "end_reason": record.end_reason,
        "controller_error": record.error,
        "determinism_replay": {"checked": record.end_reason == harness.END_NORMAL,
                               "identical": difference is None,
                               "first_difference": difference},
    }
    write_run_files(run_dir, run, record.calls, events)
    rows = [("start", start_time, v0_read, v0_unc, "")]
    if v_end is not None:
        rows.append(("end", end_time, v_end, v_end_unc, note))
    if v_peak is not None:
        rows.append(("peak", end_time, v_peak, v_end_unc, ""))
    with open(os.path.join(run_dir, "manual.csv"), "x", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(("point", "time", "volume_ml", "uncertainty_ml", "note"))
        for point, t, v, u, n in rows:
            writer.writerow((point, t, repr(v), "" if u is None else repr(u), n))
    return run_dir


def load_rig_config(path):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return RigConfig(**data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--session-plan", required=True, help="approved session plan (JSON)")
    parser.add_argument("--run", required=True, help="run label in the session plan")
    parser.add_argument("--rig-config", required=True,
                        help="adapter settings (JSON): intake_channel, sensor_wet_level")
    parser.add_argument("--port", required=True, help="serial port of the ESP32")
    parser.add_argument("--out", required=True, help="parent directory for run directories")
    args = parser.parse_args(argv)
    config = load_rig_config(args.rig_config)
    link = SerialLink(args.port)
    try:
        print(run_rig(args.session_plan, args.run, link, config, args.out, port=args.port))
    except ConfigurationError as exc:
        print(exc, file=sys.stderr)
        return 2
    finally:
        link.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
