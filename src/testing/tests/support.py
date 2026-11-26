"""Test-only helpers: run-file writer, hand-written log builder and a stub plant.

Nothing here is a controller, a model or the harness:
- Intake commands are fixed, hand-derived schedules (lists of ON intervals),
  not decisions computed from the sensor. No controller is generated (D29).
- `StubTankSystem` is a test double with the `TankSystem` method names
  (`design/software_architecture.md` section 8). It only adds a constant rate
  while the intake is on and reports wet at a fixed level. It has no capacity,
  spill, dead volume, outtake or Model 2 effect and is not Model 1 (WP10).
- `simulate` is a minimal loop in the D38 call order with the D38 cut-off,
  only so that the evaluator can be exercised on complete run files. Its
  cut-off limit per planned V0 (D45) is a literal hand calculation.
"""

import csv
import json
import os

from testing.parameters import values
from testing.scenarios import SCENARIO_RUNS

DT_CALL_MS = 100
DT_SIM_MS = 10
T_END_MS = 60_000
SETTLE_MS = 10_000
# D45 per-run cut-off by planned V0, worked out by hand (protocol section 8):
# floor((60 - 5 - (V0 + 1) - 0.5) / 1.0) to 0.1 s.
T_MAX_MS = {5.0: 48_500, 30.0: 23_500}


def run_json(case_id, environment="stub", **overrides):
    case = SCENARIO_RUNS[case_id]
    p = values()
    run = {
        "run_id": f"test-{case_id}",
        "environment": environment,
        "scenario_id": case_id,
        "purpose": "reference",
        "v0_ml": case.v0_ml,
        "t_max_s": T_MAX_MS[case.v0_ml] / 1000,
        "request": {"task": case.task, "parameter": case.parameter,
                    "v_sensor_ml": p["P05"], "q_in_ml_per_s": p["P06"],
                    "t_deadline_s": p["R06"]},
        "parameters": dict(p),
        "dt_call_ms": DT_CALL_MS,
        "dt_sim_ms": DT_SIM_MS,
        "end_reason": "normal",
    }
    run.update(overrides)
    return run


def write_run(run_dir, run, calls, events=(), truth=None, manual=None):
    """Write a run directory. calls: (t_ms, sensor_env, sensor_given, intake,
    outtake); events: (t_ms, source, event, detail); truth: (t_ms, volume_ml,
    overflow, spill_ml); manual: {point: volume_ml}."""
    os.makedirs(run_dir, exist_ok=True)
    with open(os.path.join(run_dir, "run.json"), "w", encoding="utf-8") as fh:
        json.dump(run, fh, indent=2)
    _write_csv(os.path.join(run_dir, "calls.csv"),
               ["t_ms", "sensor_env", "sensor_given", "intake", "outtake"],
               [(t, int(se), int(sg), int(i), int(o)) for t, se, sg, i, o in calls])
    _write_csv(os.path.join(run_dir, "events.csv"),
               ["t_ms", "source", "event", "detail"], list(events))
    if truth is not None:
        _write_csv(os.path.join(run_dir, "truth.csv"),
                   ["t_ms", "volume_ml", "intake_flowing", "outtake_flowing",
                    "overflow", "spill_ml", "shortfall_ml"],
                   [(t, f"{v:.6f}", "", "", int(ov), sp, 0) for t, v, ov, sp in truth])
    if manual is not None:
        _write_csv(os.path.join(run_dir, "manual.csv"),
                   ["point", "time", "volume_ml", "uncertainty_ml", "note"],
                   [(pt, "", v, 0.5, "") for pt, v in manual.items()])


def _write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def intake_from(intervals):
    """Hand-written command schedule: intake ON for t in [on, off) of any interval
    (off None = until the end of the run)."""
    def on(t_ms):
        return any(a <= t_ms and (b is None or t_ms < b) for a, b in intervals)
    return on


def hand_calls(intervals, wet_from_ms=None, override_dry=False, outtake_at=(),
               t_end_ms=T_END_MS):
    """Hand-written call log: sensor_env wet from `wet_from_ms` on (None: never)."""
    on = intake_from(intervals)
    rows = []
    for t in range(0, t_end_ms + 1, DT_CALL_MS):
        s_env = wet_from_ms is not None and t >= wet_from_ms
        s_given = False if override_dry else s_env
        rows.append((t, s_env, s_given, on(t), t in outtake_at))
    return rows


def hand_truth(v0, v_end, peak=None, settled=True, overflow=False, spill=0.0):
    """Hand-written truth log with only the key rows."""
    rows = [(0, v0, False, 0.0)]
    if peak is not None:
        rows.append((30_000, peak, overflow, spill))
    end_t = T_END_MS + SETTLE_MS if settled else T_END_MS
    rows.append((end_t, v_end, overflow, spill))
    return rows


class StubTankSystem:
    """Test double; see module docstring. Volume = V0 + rate * (intake ON time)."""

    def __init__(self, rate_ml_per_s=1.0, sensor_level_ml=24.0):
        self.rate = rate_ml_per_s
        self.level = sensor_level_ml
        self.reset(0.0)

    def reset(self, v0_ml):
        self.v0 = v0_ml
        self.on_ms = 0          # integer, so volumes stay exact at call times

    def step(self, dt_ms, intake_on, outtake_on):
        if outtake_on:
            raise AssertionError("stub plant has no outtake")
        if intake_on:
            self.on_ms += dt_ms

    def volume(self):
        return self.v0 + self.rate * self.on_ms / 1000

    def sensor_wet(self):
        return self.volume() >= self.level

    def truth(self):
        return {"volume_ml": self.volume(), "overflow": False, "spill_ml": 0.0}


def simulate(run_dir, scenario_id, intervals, plant=None):
    """Run a fixed intake schedule against the stub plant and write run files."""
    case = SCENARIO_RUNS[scenario_id]
    plant = plant or StubTankSystem()
    plant.reset(case.v0_ml)
    command = intake_from(intervals)
    cutoff_ms = T_MAX_MS[case.v0_ml]
    calls, events, truth = [], [], [(0, plant.volume(), False, 0.0)]
    t, on_timer, forced_off, prev_cmd = 0, 0, False, False

    def advance(until, intake_cmd):
        nonlocal t, on_timer, forced_off
        while t < until:
            effective = intake_cmd and not forced_off
            if effective and on_timer >= cutoff_ms:
                forced_off, effective = True, False
                events.append((t, "simulation", "cutoff", "intake"))
            plant.step(DT_SIM_MS, effective, False)
            on_timer += DT_SIM_MS if effective else 0
            t += DT_SIM_MS
            truth.append((t, plant.volume(), False, 0.0))

    for k in range(T_END_MS // DT_CALL_MS + 1):
        t_call = k * DT_CALL_MS
        s_env = plant.sensor_wet()
        s_given = False if case.sensor_override == "dry" else s_env
        intake = command(t_call)
        if intake and not prev_cmd:          # new ON edge restarts the cut-off timer
            on_timer, forced_off = 0, False
        prev_cmd = intake
        calls.append((t_call, s_env, s_given, intake, False))
        if t_call < T_END_MS:
            advance(t_call + DT_CALL_MS, intake)
    advance(T_END_MS + SETTLE_MS, False)     # finish(): pumps OFF, settle R09
    write_run(run_dir, run_json(scenario_id), calls, events, truth)
