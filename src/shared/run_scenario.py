"""Run a controller file on one scenario case and write the run files
(WP12 remainder; `design/software_architecture.md` sections 3-7).

Steps for one run:
1. D37 static rule check of the controller file; on a violation the
   controller is not loaded or run, and only the record of the check is
   written (end_reason "rule_violation").
2. Plan from the scenario definition (`testing.scenarios`, data only) and the
   planned parameter set (`testing.parameters`, placeholders, D34). The
   environment's own parameter values must agree with the plan for every ID
   both define; otherwise the run is refused (a setup error, not a verdict).
3. Fresh module load and controller instance (D36); harness call loop (D38).
4. Determinism replay on a second instance (D37).
5. run.json, calls.csv, events.csv, truth.csv written once.

Only Model 1 exists so far (WP10); Model 2 (WP11) and the rig (WP09a) plug
in through ENVIRONMENTS.

Usage (from the repository root):
    PYTHONPATH=src python3 -m shared.run_scenario --controller FILE \
        --case S2 [--case S4 ... | --all] --out experiments/logs
"""

import argparse
import datetime
import os
import platform
import subprocess
import sys

from shared import harness
from shared.controller_check import check_file, load_controller_class
from shared.run_files import write_run_files
from shared.simulation_environment import SimulationEnvironment

HARNESS_VERSION = "0.1.0"
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ConfigurationError(Exception):
    """The run setup is inconsistent; nothing was run."""


# ---------------------------------------------------------------------------
# Environments
# ---------------------------------------------------------------------------

def model_1_environment():
    """Model 1 simulation environment and its parameter values by ID."""
    from model_1 import MODEL_1_SIMULATION_PARAMETERS, Model1Parameters, build_model_1
    mp = Model1Parameters()
    sp = MODEL_1_SIMULATION_PARAMETERS
    env = SimulationEnvironment(build_model_1(mp), sp)
    by_id = {
        "P01": mp.capacity_ml, "P05": mp.sensor_level_ml, "P06": mp.q_in_ml_per_s,
        "P07": mp.q_out_ml_per_s, "P09": mp.dead_volume_ml,
        "P11": sp.max_on_ms / 1000, "R09": sp.settle_ms / 1000,
    }
    info = {"name": "model_1", "version": "WP10 provisional (placeholders, D34)",
            "dt_sim_ms": sp.step_ms, "settle_ms": sp.settle_ms,
            "command_delay_ms": sp.command_delay_ms,
            "report_delay_ms": sp.report_delay_ms}
    return env, by_id, info


ENVIRONMENTS = {"model_1": model_1_environment}


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------

def ms(seconds):
    return int(round(seconds * 1000))


def plan_for_case(case, p):
    """RunPlan from a scenario run case and the planned parameter values {ID: value}."""
    request = harness.Request(task=case.task, parameter=case.parameter,
                              v_sensor_ml=p["P05"], q_in_ml_per_s=p["P06"],
                              t_deadline_s=p["R06"])
    return harness.RunPlan(scenario_id=case.run_case, v0_ml=case.v0_ml, request=request,
                           sensor_override=case.sensor_override,
                           dt_call_ms=ms(p["R01"]), t_end_ms=ms(p["R08"]))


def merged_parameters(plan_values, env_values):
    """Planned values plus the environment's own; refuse on any disagreement."""
    clashes = [f"{pid}: plan {plan_values[pid]} != environment {v}"
               for pid, v in env_values.items()
               if pid in plan_values and abs(float(plan_values[pid]) - float(v)) > 1e-12]
    if clashes:
        raise ConfigurationError("parameter mismatch: " + "; ".join(clashes))
    return dict(plan_values, **env_values)


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------

def _git(*args):
    try:
        out = subprocess.run(["git", *args], cwd=REPO, capture_output=True,
                             text=True, timeout=10, check=True)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def provenance():
    status = _git("status", "--porcelain")
    return {"git_commit": _git("rev-parse", "HEAD"),
            "git_dirty": None if status is None else bool(status),
            "python_version": platform.python_version(),
            "harness_version": HARNESS_VERSION}


def _relative(path):
    path = os.path.abspath(path)
    return os.path.relpath(path, REPO) if path.startswith(REPO + os.sep) else path


# ---------------------------------------------------------------------------
# One run
# ---------------------------------------------------------------------------

def run_case(controller_path, case_id, out_dir, environment="model_1", run_id=None,
             scenarios=None, plan_values=None):
    """Run one scenario case; write its run directory under out_dir; return its path."""
    from testing.parameters import values
    from testing.scenarios import SCENARIO_RUNS

    scenarios = SCENARIO_RUNS if scenarios is None else scenarios
    plan_values = values() if plan_values is None else dict(plan_values)
    if case_id not in scenarios:
        raise ConfigurationError(f"unknown scenario case {case_id!r}")
    if environment not in ENVIRONMENTS:
        raise ConfigurationError(f"unknown environment {environment!r}")
    case = scenarios[case_id]

    check = check_file(controller_path)
    env, env_values, env_info = ENVIRONMENTS[environment]()
    parameters = merged_parameters(plan_values, env_values)
    plan = plan_for_case(case, plan_values)

    now = datetime.datetime.now(datetime.timezone.utc)
    run_id = run_id or f"{now:%Y%m%dT%H%M%SZ}_{environment}_{case_id}_{check.sha256[:8]}"
    run_dir = os.path.join(out_dir, run_id)
    if os.path.exists(run_dir):
        raise ConfigurationError(f"run directory exists: {run_dir}")

    run = {
        "run_id": run_id,
        "date_utc": now.isoformat(timespec="seconds"),
        **provenance(),
        "controller": {"file": _relative(controller_path), "sha256": check.sha256,
                       "rule_check": check.as_dict()},
        "environment": environment,
        "model": env_info,
        "scenario_id": case_id,
        "v0_ml": case.v0_ml,
        "sensor_override": case.sensor_override,
        "request": plan.request.as_dict(),
        "parameters": parameters,
        "placeholder_parameters": True,      # D34: every value is a placeholder
        "dt_call_ms": plan.dt_call_ms,
        "dt_sim_ms": env_info.get("dt_sim_ms"),
        "t_end_ms": plan.t_end_ms,
        "settle_ms": env_info.get("settle_ms"),
    }

    if not check.ok:
        run.update(end_reason=harness.END_RULE_VIOLATION, determinism_replay=None)
        events = [(0, harness.SOURCE, "rule_violation",
                   "; ".join(f"line {f.line}: {f.rule}: {f.detail}" for f in check.violations))]
        return write_run_files(run_dir, run, [], events)

    controller_class = load_controller_class(controller_path)
    record = harness.run_controller(controller_class, env, plan)

    difference = (harness.replay(controller_class, plan.request, record.calls)
                  if record.end_reason == harness.END_NORMAL else None)
    events = list(env.events) + record.events
    if difference is not None:
        events.append((difference["t_ms"] or 0, harness.SOURCE, "replay_differs",
                       str(difference)))
    run.update(end_reason=record.end_reason, controller_error=record.error,
               determinism_replay={"checked": record.end_reason == harness.END_NORMAL,
                                   "identical": difference is None,
                                   "first_difference": difference})
    return write_run_files(run_dir, run, record.calls, events,
                           getattr(env, "truth_rows", None))


def main(argv=None):
    from testing.scenarios import SCENARIO_RUNS

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--controller", required=True, help="controller file (D37)")
    parser.add_argument("--environment", default="model_1", choices=sorted(ENVIRONMENTS))
    parser.add_argument("--case", action="append", default=[], help="scenario run case")
    parser.add_argument("--all", action="store_true", help="all ten scenario run cases")
    parser.add_argument("--out", required=True, help="parent directory for run directories")
    args = parser.parse_args(argv)
    cases = list(SCENARIO_RUNS) if args.all else args.case
    if not cases:
        parser.error("give --case or --all")
    for case_id in cases:
        print(run_case(args.controller, case_id, args.out, args.environment))
    return 0


if __name__ == "__main__":
    sys.exit(main())
