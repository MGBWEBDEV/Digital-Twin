"""Evaluator for controller runs (WP12, test-first part).

Reads one run directory (`design/software_architecture.md` section 7), judges
it against the WP03 checks (`design/functional_requirements.md` sections 5-6)
and infers the WP06 end state (`design/controller_behavior.md` section 6).

Independence: this module imports only the standard library and the
`testing` package. It never imports controllers or model packages, and it
runs only after a run has finished.

Results per check: "pass", "fail", "undetermined" (WP03 section 6) or
"not_applicable" (the check's condition does not arise in this run, e.g.
FR03-L2 when the sensor input never becomes wet). Overall verdict: "invalid"
(the run is not scored), else "fail" if any check fails, else "undetermined"
if any check is undetermined, else "pass". A run that the harness ended with
"controller_error" (the controller raised an error or gave a wrong answer)
fails with the single check "controller_error" unless the setup was invalid
(D42 (1)). Every scored run also gets the check "determinism_replay" (D42 (3)).

Run purposes (`experiments/experimental_protocol.md` section 4): only
reference, fault, pool and paired runs are scored; pool verdicts are marked
exploratory. A paired run may start from the measured rig V0 within the
planned V0 +/- R14 (D46). The recorded per-run cut-off `t_max_s` must equal
the evaluator's own D45 calculation from the planned V0.

Usage: PYTHONPATH=src python3 -m testing.evaluator <run_dir> [<run_dir> ...]
writes <run_dir>/verdict.json and prints the overall verdict.
"""

import json
import math
import os
import sys
from fractions import Fraction

from testing import parameters as parameters_module
from testing.runfiles import RunFileError, read_run
from testing.scenarios import SCENARIO_RUNS

EVALUATOR_VERSION = "0.4.0"

PASS = "pass"
FAIL = "fail"
UNDETERMINED = "undetermined"
NOT_APPLICABLE = "not_applicable"
CONTROLLER_ERROR = "controller_error"   # end reason written by the harness (D42)

VOLUME_EPS_ML = 1e-9      # floating-point guard for volume comparisons only
SIMULATED = ("model_1", "model_2", "stub")
SCORED_PURPOSES = ("reference", "fault", "pool", "paired")


def ms(seconds):
    return int(round(seconds * 1000))


def fmt_s(t_ms):
    return "none" if t_ms is None else f"{t_ms / 1000:.3f} s"


def fmt_ml(v):
    return "none" if v is None else f"{v:.3f} mL"


# ---------------------------------------------------------------------------
# Facts derived from the call log (WP06 section 6)
# ---------------------------------------------------------------------------

def intake_intervals(calls):
    """ON intervals as (t_on_ms, t_off_ms or None). WP03 section 3: from the
    first call returning ON to the first later call returning OFF."""
    intervals, start = [], None
    for c in calls:
        if c.intake and start is None:
            start = c.t_ms
        elif not c.intake and start is not None:
            intervals.append((start, c.t_ms))
            start = None
    if start is not None:
        intervals.append((start, None))
    return intervals


def first_wet_input(calls):
    """t_w: time of the first call whose (given) sensor input is wet."""
    for c in calls:
        if c.sensor_given:
            return c.t_ms
    return None


def call_at(calls, t_ms):
    for c in calls:
        if c.t_ms == t_ms:
            return c
    return None


def last_call_at_or_before(calls, t_ms):
    found = None
    for c in calls:
        if c.t_ms <= t_ms:
            found = c
        else:
            break
    return found


# ---------------------------------------------------------------------------
# Run validity (WP06 X8; consistency of the harness log with the scenario)
# ---------------------------------------------------------------------------

def _close(a, b):
    try:
        return abs(float(a) - float(b)) <= 1e-9
    except (TypeError, ValueError):
        return False


def expected_t_max_ms(v0_plan_ml, p):
    """D45, computed here independently of the harness:
    T_max = floor((P01 - R12 - (V0_plan + R14) - P13) / Q_in,hi) to 0.1 s,
    with decimal values taken exactly as written. None if not positive."""
    x = {k: Fraction(str(v)) for k, v in p.items() if k in ("P01", "R12", "R14", "P13",
                                                              "Q_in,hi")}
    room = x["P01"] - x["R12"] - (Fraction(str(v0_plan_ml)) + x["R14"]) - x["P13"]
    tenths = math.floor(room / x["Q_in,hi"] * 10)
    return tenths * 100 if tenths > 0 else None


def validity_problems(files, case, p):
    """Return a list of reasons why the run cannot be scored (empty if valid)."""
    run, calls = files.run, files.calls
    problems = []
    env = run["environment"]

    crashed = run["end_reason"] == CONTROLLER_ERROR
    if run["end_reason"] not in ("normal", CONTROLLER_ERROR):
        problems.append(f"end_reason is {run['end_reason']!r}")
    if crashed and not any(e.event == CONTROLLER_ERROR for e in files.events):
        problems.append("end_reason is 'controller_error' but events.csv has no "
                        "controller_error event")
    for e in files.events:
        if e.event == "run_invalidated":
            problems.append(f"run_invalidated event at {fmt_s(e.t_ms)}: {e.detail}")

    # Parameters recorded in run.json must equal the evaluator's set.
    recorded = run["parameters"]
    for pid, value in p.items():
        if pid not in recorded:
            problems.append(f"parameter {pid} not recorded in run.json")
        elif not _close(recorded[pid], value):
            problems.append(f"parameter {pid}: run {recorded[pid]} != evaluator {value}")

    # The request given to the controller must match the scenario and R07.
    req = run["request"]
    expected_req = {"task": case.task, "parameter": case.parameter,
                    "v_sensor_ml": p["P05"], "q_in_ml_per_s": p["P06"],
                    "t_deadline_s": p["R06"]}
    for key, value in expected_req.items():
        got = req.get(key)
        ok = got == value if key == "task" else _close(got, value)
        if not ok:
            problems.append(f"request {key}: run {got!r} != scenario {value!r}")

    # Call timing (WP07 section 5).
    dt = ms(p["R01"])
    t_end = ms(p["R08"])
    if run["dt_call_ms"] != dt:
        problems.append(f"dt_call_ms {run['dt_call_ms']} != R01 {dt}")
    times = [c.t_ms for c in calls]
    if any(b <= a for a, b in zip(times, times[1:])):
        problems.append("call times not strictly increasing")
    if times and not 0 <= times[0] < dt:
        problems.append(f"first call at {fmt_s(times[0])}, expected t = 0")
    if times and times[-1] < t_end and not crashed:   # a crash ends the log early (D42)
        problems.append(f"call log ends at {fmt_s(times[-1])}, before T_end {fmt_s(t_end)}")
    if env in SIMULATED and times != [k * dt for k in range(len(times))]:
        problems.append("simulated call times are not k * dt_call")

    # Sensor override must be exactly as the scenario defines (D29).
    for c in calls:
        expected_given = False if case.sensor_override == "dry" else c.sensor_env
        if c.sensor_given != expected_given:
            problems.append(f"sensor_given at {fmt_s(c.t_ms)} inconsistent with "
                            f"scenario override {case.sensor_override!r}")
            break

    # Purpose (protocol section 4): only scored purposes are judged.
    purpose = run["purpose"]
    if purpose not in SCORED_PURPOSES:
        problems.append(f"purpose {purpose!r} is not scored by the evaluator")

    # Start volume (D41 (5), D46 (3)): the scenario V0, or for a paired run the
    # measured rig V0, which must lie within the planned V0 +/- R14.
    try:
        v0_run = float(run["v0_ml"])
    except (TypeError, ValueError):
        v0_run = None
        problems.append(f"v0_ml {run['v0_ml']!r} is not a number")
    if v0_run is not None:
        if purpose == "paired":
            if abs(v0_run - case.v0_ml) > p["R14"] + VOLUME_EPS_ML:
                problems.append(f"paired V0 {fmt_ml(v0_run)} outside scenario V0 "
                                f"{fmt_ml(case.v0_ml)} +/- R14 {fmt_ml(p['R14'])}")
        elif not _close(v0_run, case.v0_ml):
            problems.append(f"run V0 {fmt_ml(v0_run)} != scenario V0 {fmt_ml(case.v0_ml)}")

    # Per-run cut-off (D45) from the PLANNED V0, also for paired runs.
    expected_t_max = expected_t_max_ms(case.v0_ml, p)
    try:
        t_max_run = ms(float(run["t_max_s"]))
    except (TypeError, ValueError):
        t_max_run = None
    if expected_t_max is None or t_max_run != expected_t_max:
        problems.append(f"t_max_s {run['t_max_s']!r} != D45 value "
                        f"{fmt_s(expected_t_max)} for planned V0 {fmt_ml(case.v0_ml)}")

    # Model start volume must equal the run's start volume.
    if files.truth is not None:
        first = files.truth[0]
        if first.t_ms != 0:
            problems.append("truth.csv does not start at t = 0")
        elif v0_run is not None and abs(first.volume_ml - v0_run) > 1e-6:
            problems.append(f"truth V0 {fmt_ml(first.volume_ml)} != run V0 "
                            f"{fmt_ml(v0_run)}")
    return problems


# ---------------------------------------------------------------------------
# Physical observations (models: truth.csv; rig: manual.csv)
# ---------------------------------------------------------------------------

def physical_observations(files, p):
    obs = {"source": None, "v0": None, "v_end": None, "v_peak": None,
           "overflow": None, "notes": []}
    if files.truth is not None:
        truth = files.truth
        obs["source"] = "truth.csv"
        obs["v0"] = truth[0].volume_ml
        settled_at = ms(p["R08"]) + ms(p["R09"])
        if truth[-1].t_ms >= settled_at:
            obs["v_end"] = truth[-1].volume_ml
        else:
            obs["notes"].append(
                f"truth.csv ends at {fmt_s(truth[-1].t_ms)}, before T_end + settling "
                f"{fmt_s(settled_at)}: V_end undetermined")
        obs["v_peak"] = max(r.volume_ml for r in truth)
        obs["overflow"] = any(r.overflow for r in truth) or max(r.spill_ml for r in truth) > 0
    else:
        manual = files.manual or {}
        obs["source"] = "manual.csv"
        obs["v0"] = manual.get("start")
        obs["v_end"] = manual.get("end")
        obs["v_peak"] = manual.get("peak")
        for point in ("start", "end"):
            if point not in manual:
                obs["notes"].append(f"no settled rig reading for {point!r}")
    obs["notes"].extend(files.notes)
    return obs


# ---------------------------------------------------------------------------
# Checks (WP03 section 5)
# ---------------------------------------------------------------------------

def check(cid, result, evidence):
    return {"id": cid, "result": result, "evidence": evidence}


def single_interval_check(cid, intervals, t_start):
    if not intervals:
        return check(cid, FAIL, "no intake ON interval")
    if len(intervals) > 1:
        return check(cid, FAIL, f"{len(intervals)} intake ON intervals, starts at "
                     + ", ".join(fmt_s(on) for on, _ in intervals))
    on = intervals[0][0]
    if on > t_start:
        return check(cid, FAIL, f"intake ON at {fmt_s(on)}, after t_start {fmt_s(t_start)}")
    return check(cid, PASS, f"one interval, ON at {fmt_s(on)}")


def no_on_check(cid, calls):
    on = [c.t_ms for c in calls if c.intake or c.outtake]
    if on:
        return check(cid, FAIL, f"ON command at {len(on)} call(s), first at {fmt_s(on[0])}")
    return check(cid, PASS, "no ON command for either pump")


def volume_window_check(cid, value, low, high, label):
    if value is None:
        return check(cid, UNDETERMINED, f"{label} not available")
    ok = low - VOLUME_EPS_ML <= value <= high + VOLUME_EPS_ML
    return check(cid, PASS if ok else FAIL,
                 f"{label} = {fmt_ml(value)}, accepted [{fmt_ml(low)}, {fmt_ml(high)}]")


def checks_fr01(calls, intervals, obs, case, p):
    t_start, eps_t, eps_v = ms(p["R02"]), ms(p["R03"]), p["R05"]
    t_fill = ms(case.parameter)
    out = [single_interval_check("FR01-L1", intervals, t_start)]

    if not intervals:
        out.append(check("FR01-L2", FAIL, "no intake ON interval"))
    else:
        on, off = intervals[0]
        if off is None:
            out.append(check("FR01-L2", FAIL,
                             f"intake ON at {fmt_s(on)} never switched OFF before T_end"))
        else:
            length = off - on
            ok = abs(length - t_fill) <= eps_t
            out.append(check("FR01-L2", PASS if ok else FAIL,
                             f"ON interval {fmt_s(length)}, requested {fmt_s(t_fill)} "
                             f"± {fmt_s(eps_t)}"))

    expected = p["P06"] * case.parameter   # placeholder calibration Q_in * T_fill
    if obs["v0"] is None or obs["v_end"] is None:
        out.append(check("FR01-P1", UNDETERMINED, "V0 or V_end not available"))
    else:
        delivered = obs["v_end"] - obs["v0"]
        out.append(volume_window_check("FR01-P1", delivered, expected - eps_v,
                                       expected + eps_v, "V_end - V0"))
    return out


def checks_fr03(calls, intervals, t_w, obs, case_a, p):
    t_start, t_resp, eps_v = ms(p["R02"]), ms(p["R04"]), p["R05"]
    if not case_a:
        return [no_on_check("FR03-L3", calls), _unchanged_check("FR03-P2", obs, eps_v)]

    out = [single_interval_check("FR03-L1", intervals, t_start)]
    if t_w is None:
        out.append(check("FR03-L2", NOT_APPLICABLE,
                         "sensor input never wet; FR08-L2 applies"))
    else:
        limit = t_w + t_resp
        window = [c for c in calls if t_w <= c.t_ms <= limit]
        off = next((c.t_ms for c in window if not c.intake), None)
        if off is not None:
            out.append(check("FR03-L2", PASS,
                             f"t_w = {fmt_s(t_w)}; intake OFF at {fmt_s(off)} "
                             f"<= {fmt_s(limit)}"))
        else:
            later = next((c.t_ms for c in calls if c.t_ms > limit and not c.intake), None)
            out.append(check("FR03-L2", FAIL,
                             f"t_w = {fmt_s(t_w)}; intake still ON at {fmt_s(limit)}; "
                             f"first OFF {fmt_s(later)}"))
    v_s = p["P05"]
    out.append(volume_window_check("FR03-P1", obs["v_end"], v_s - eps_v, v_s + eps_v, "V_end"))
    return out


def checks_fr09(calls, intervals, t_w, obs, case, case_a, p):
    t_start, eps_t, eps_v = ms(p["R02"]), ms(p["R03"]), p["R05"]
    if not case_a:
        return [no_on_check("FR09-L3", calls), _unchanged_check("FR09-P2", obs, eps_v)]

    l1 = single_interval_check("FR09-L1", intervals, t_start)
    if l1["result"] == PASS:
        if t_w is None:
            l1["evidence"] += "; sensor input never wet, 'still ON at t_w' not evaluable"
        elif not call_at(calls, t_w).intake:
            l1 = check("FR09-L1", FAIL, f"intake OFF at t_w = {fmt_s(t_w)} "
                       "(stopped at the sensor)")
        else:
            l1["evidence"] += f"; still ON at t_w = {fmt_s(t_w)}"
    out = [l1]

    v_target = case.parameter
    t_extra = ms((v_target - p["P05"]) / p["P06"])
    if t_w is None:
        out.append(check("FR09-L2", NOT_APPLICABLE, "sensor input never wet; FR08-L2 applies"))
    elif not intervals or intervals[0][1] is None:
        out.append(check("FR09-L2", FAIL, "intake not switched OFF before T_end"))
    else:
        t_off = intervals[0][1]
        diff = (t_off - t_w) - t_extra
        out.append(check("FR09-L2", PASS if abs(diff) <= eps_t else FAIL,
                         f"t_w = {fmt_s(t_w)}, t_off = {fmt_s(t_off)}, t_off - t_w = "
                         f"{fmt_s(t_off - t_w)}, T_extra = {fmt_s(t_extra)} ± {fmt_s(eps_t)}"))
    out.append(volume_window_check("FR09-P1", obs["v_end"], v_target - eps_v,
                                   v_target + eps_v, "V_end"))
    return out


def _unchanged_check(cid, obs, eps_v):
    if obs["v0"] is None or obs["v_end"] is None:
        return check(cid, UNDETERMINED, "V0 or V_end not available")
    return volume_window_check(cid, obs["v_end"] - obs["v0"], -eps_v, eps_v, "V_end - V0")


def checks_fr08(files, calls, intervals, obs, case, p):
    t_deadline, t_resp = ms(p["R06"]), ms(p["R04"])
    safe = p["P04"]
    out = []

    outtake = [c.t_ms for c in calls if c.outtake]
    out.append(check("FR08-L1", FAIL if outtake else PASS,
                     f"outtake ON at {len(outtake)} call(s), first at {fmt_s(outtake[0])}"
                     if outtake else "outtake never ON"))

    wet_by_deadline = any(c.sensor_given for c in calls if c.t_ms <= t_deadline)
    if case.task == "FR01" or wet_by_deadline:
        out.append(check("FR08-L2", NOT_APPLICABLE,
                         "FR01 run" if case.task == "FR01"
                         else "sensor input wet by T_deadline"))
    else:
        limit = t_deadline + t_resp
        c = last_call_at_or_before(calls, limit)
        ok = c is not None and not c.intake
        out.append(check("FR08-L2", PASS if ok else FAIL,
                         f"sensor input dry until T_deadline {fmt_s(t_deadline)}; intake "
                         f"{'OFF' if ok else 'ON'} at the call at {fmt_s(c.t_ms if c else None)} "
                         f"(limit {fmt_s(limit)})"))

    if not intervals or intervals[0][1] is None:
        out.append(check("FR08-L3", PASS, "no completed intake ON interval; nothing after it"))
    else:
        t_off = intervals[0][1]
        bad = [c.t_ms for c in calls if c.t_ms >= t_off and (c.intake or c.outtake)]
        out.append(check("FR08-L3", FAIL if bad else PASS,
                         f"pump ON again at {fmt_s(bad[0])} after OFF at {fmt_s(t_off)}"
                         if bad else f"both pumps OFF from {fmt_s(t_off)} to T_end"))

    cutoffs = [e for e in files.events if e.event == "cutoff"]
    out.append(check("FR08-L4", FAIL if cutoffs else PASS,
                     "cut-off at " + ", ".join(f"{fmt_s(e.t_ms)} ({e.detail})" for e in cutoffs)
                     if cutoffs else "no cut-off event"))

    out.append(volume_window_check("FR08-P1", obs["v_end"], float("-inf"), safe, "V_end"))

    if files.truth is not None:
        ok = obs["v_peak"] <= safe + VOLUME_EPS_ML and not obs["overflow"]
        out.append(check("FR08-P2", PASS if ok else FAIL,
                         f"V_peak = {fmt_ml(obs['v_peak'])} (safe mark {fmt_ml(safe)}), "
                         f"computed overflow {'yes' if obs['overflow'] else 'no'}"))
    elif obs["v_peak"] is None:
        if outtake or obs["v_end"] is None:
            out.append(check("FR08-P2", UNDETERMINED,
                             "rig: peak not readable as a settled level (D24)"))
        else:
            # D41: with only the intake running the level never falls, so the
            # settled end reading is the highest settled level.
            out.append(volume_window_check(
                "FR08-P2", obs["v_end"], float("-inf"), safe,
                "V_peak taken as settled V_end (outtake never ON, D41)"))
    else:
        out.append(volume_window_check("FR08-P2", obs["v_peak"], float("-inf"), safe,
                                       "V_peak (rig reading)"))
    return out


# ---------------------------------------------------------------------------
# End-state inference (WP06 section 6)
# ---------------------------------------------------------------------------

def infer_end_state(calls, intervals, t_w, case, p):
    """Return a WP06 terminal state, or a label outside WP06 when the log
    matches none: NO_START, NOT_STOPPED, UNEXPECTED_STOP."""
    first_wet = calls[0].sensor_given
    sensor_task = case.task in ("FR03", "FR09")
    if not intervals:
        return "DONE_SKIPPED" if sensor_task and first_wet else "NO_START"
    on, off = intervals[0]
    if off is None:
        return "NOT_STOPPED"
    if sensor_task and off >= ms(p["R06"]) and (t_w is None or t_w > off):
        return "DONE_TIMEOUT"
    eps_t, t_resp = ms(p["R03"]), ms(p["R04"])
    if case.task == "FR01":
        matches = abs((off - on) - ms(case.parameter)) <= eps_t
    elif case.task == "FR03":
        matches = t_w is not None and t_w <= off <= t_w + t_resp
    else:
        t_extra = ms((case.parameter - p["P05"]) / p["P06"])
        matches = t_w is not None and abs((off - t_w) - t_extra) <= eps_t
    return "DONE_COMPLETE" if matches else "UNEXPECTED_STOP"


# ---------------------------------------------------------------------------
# Top level
# ---------------------------------------------------------------------------

def evaluate_files(files, params=None, scenarios=None):
    """Judge already-read run files. Returns the verdict as a dict."""
    param_set = parameters_module.PARAMETERS if params is None else params
    p = parameters_module.values(param_set)
    scenarios = SCENARIO_RUNS if scenarios is None else scenarios
    run = files.run

    verdict = {
        "run_id": run["run_id"],
        "scenario_id": run["scenario_id"],
        "environment": run["environment"],
        "purpose": run["purpose"],
        "exploratory": run["purpose"] == "pool",      # protocol section 4
        "evaluator_version": EVALUATOR_VERSION,
        "parameters": p,
        "provisional": bool(parameters_module.placeholder_ids(param_set)),
        "placeholder_ids": parameters_module.placeholder_ids(param_set),
    }

    case = scenarios.get(run["scenario_id"])
    if case is None:
        return dict(verdict, overall="invalid",
                    invalid_reasons=[f"unknown scenario {run['scenario_id']!r}"], checks=[])

    problems = validity_problems(files, case, p)
    obs = physical_observations(files, p)
    if case.task == "FR01" and obs["v0"] is not None:
        if obs["v0"] + p["P06"] * case.parameter > p["P04"] - p["R05"] + VOLUME_EPS_ML:
            problems.append("FR01 precondition V0 + Q_in * T_fill <= safe mark - eps_V "
                            "not met")
    if problems:
        return dict(verdict, overall="invalid", invalid_reasons=problems, checks=[])

    calls = files.calls
    intervals = intake_intervals(calls)
    t_w = first_wet_input(calls)

    if run["end_reason"] == CONTROLLER_ERROR:
        return controller_error_verdict(verdict, files, intervals, t_w, obs)

    case_a = not calls[0].sensor_given      # case selection by the first input

    checks = []
    if "FR01" in case.groups:
        checks += checks_fr01(calls, intervals, obs, case, p)
    if "FR03" in case.groups:
        checks += checks_fr03(calls, intervals, t_w, obs, case_a, p)
    if "FR09" in case.groups:
        checks += checks_fr09(calls, intervals, t_w, obs, case, case_a, p)
    for cid in case.extra_checks:
        if cid != "FR03-L1":
            raise ValueError(f"unsupported extra check {cid!r}")
        checks.append(single_interval_check(cid, intervals, ms(p["R02"])))
    if "FR08" in case.groups:
        checks += checks_fr08(files, calls, intervals, obs, case, p)
    checks.append(determinism_check(files))

    results = {c["result"] for c in checks}
    if FAIL in results:
        overall = FAIL
    elif UNDETERMINED in results:
        overall = UNDETERMINED
    else:
        overall = PASS

    safe = p["P04"]
    margins = {
        "v_end_to_safe_mark_ml": None if obs["v_end"] is None else safe - obs["v_end"],
        "v_peak_to_safe_mark_ml": None if obs["v_peak"] is None else safe - obs["v_peak"],
    }
    if case.task == "FR09":
        margins["target_to_safe_mark_ml"] = safe - case.parameter

    return dict(
        verdict,
        overall=overall,
        invalid_reasons=[],
        case=("A" if case_a else "B") if case.task in ("FR03", "FR09") else None,
        checks=checks,
        inferred_end_state=infer_end_state(calls, intervals, t_w, case, p),
        observations={
            "t_w_ms": t_w,
            "intake_intervals_ms": [list(iv) for iv in intervals],
            "extra_on_edges": max(0, len(intervals) - 1),
            "cutoff_events_ms": [e.t_ms for e in files.events if e.event == "cutoff"],
            "late_call_events_ms": [e.t_ms for e in files.events if e.event == "late_call"],
            "volume_source": obs["source"],
            "v0_ml": obs["v0"],
            "v_end_ml": obs["v_end"],
            "v_peak_ml": obs["v_peak"],
            "computed_overflow": obs["overflow"],
            "notes": obs["notes"],
        },
        margins=margins,
    )


def determinism_check(files):
    """D42 (3), researcher 2026-11-25: after the run the harness gives a new
    controller instance the recorded inputs; any different answer (event
    `replay_differs`) fails the run. Logs without a recorded replay
    (hand-written logs) make the check not applicable."""
    cid = "determinism_replay"
    differs = [e for e in files.events if e.event == "replay_differs"]
    if differs:
        return check(cid, FAIL, f"replay of the recorded inputs gave a different answer: "
                                f"{differs[0].detail}")
    replay = files.run.get("determinism_replay") or {}
    if replay.get("checked") and replay.get("identical"):
        return check(cid, PASS, "replay of the recorded inputs gave identical answers")
    if replay.get("checked"):
        return check(cid, FAIL, f"run.json records a replay difference: "
                                f"{replay.get('first_difference')}")
    return check(cid, NOT_APPLICABLE, "no replay recorded in run.json")


def controller_error_verdict(verdict, files, intervals, t_w, obs):
    """A controller that raised an error or answered with something other than
    two booleans fails the run (D42 (1), researcher 2026-11-25). The harness
    stopped calling it at that point and switched both pumps OFF, so the WP03
    checks are not computed on the shortened log; the error is reported as
    evidence instead."""
    e = next(e for e in files.events if e.event == CONTROLLER_ERROR)
    calls = files.calls
    return dict(
        verdict,
        overall=FAIL,
        invalid_reasons=[],
        case=None,
        checks=[check(CONTROLLER_ERROR, FAIL,
                      f"controller error at {fmt_s(e.t_ms)}: {e.detail}; "
                      f"{len(calls)} call(s) completed before it; the harness then "
                      "switched both pumps OFF")],
        inferred_end_state="CONTROLLER_ERROR",
        observations={
            "controller_error_ms": e.t_ms,
            "controller_error": e.detail,
            "calls_completed": len(calls),
            "t_w_ms": t_w,
            "intake_intervals_ms": [list(iv) for iv in intervals],
            "cutoff_events_ms": [x.t_ms for x in files.events if x.event == "cutoff"],
            "volume_source": obs["source"],
            "v0_ml": obs["v0"],
            "v_end_ml": obs["v_end"],
            "v_peak_ml": obs["v_peak"],
            "computed_overflow": obs["overflow"],
            "notes": obs["notes"],
        },
        margins={},
    )


def evaluate_run(run_dir, params=None, scenarios=None):
    """Read a run directory and return its verdict (does not write it)."""
    return evaluate_files(read_run(run_dir), params, scenarios)


def write_verdict(run_dir, verdict):
    path = os.path.join(run_dir, "verdict.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(verdict, fh, indent=2, sort_keys=False)
        fh.write("\n")
    return path


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("usage: python3 -m testing.evaluator <run_dir> [<run_dir> ...]", file=sys.stderr)
        return 2
    status = 0
    for run_dir in argv:
        try:
            verdict = evaluate_run(run_dir)
        except RunFileError as exc:
            print(f"{run_dir}: ERROR {exc}", file=sys.stderr)
            status = 1
            continue
        write_verdict(run_dir, verdict)
        failed = [c["id"] for c in verdict["checks"] if c["result"] == FAIL]
        print(f"{run_dir}: {verdict['overall']}" + (f" ({', '.join(failed)})" if failed else ""))
    return status


if __name__ == "__main__":
    sys.exit(main())
