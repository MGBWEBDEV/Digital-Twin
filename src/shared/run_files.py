"""Run-file writer (logger; `design/software_architecture.md` section 7, D11).

Writes one run directory: run.json, calls.csv, events.csv and, for
simulations, truth.csv. Column and key names are those the evaluator reads
(`src/testing/README.md`, D41 (6)). The writer refuses to write into an
existing directory, so raw files are never edited after the run.

Booleans are written as 0/1. Volumes come from the environment's truth rows
as floats (exact fractions are converted only here, D40 (1)); `repr` keeps
every digit of the float.
"""

import csv
import json
import os

CALL_COLUMNS = ("t_ms", "sensor_env", "sensor_given", "intake", "outtake")
EVENT_COLUMNS = ("t_ms", "source", "event", "detail")
TRUTH_REQUIRED = ("t_ms", "volume_ml", "intake_flowing", "outtake_flowing",
                  "overflow", "spill_ml", "shortfall_ml")


def _cell(value):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, float):
        return repr(value)
    return value


def _write_csv(path, header, rows):
    with open(path, "x", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        for row in rows:
            writer.writerow([_cell(v) for v in row])


def truth_columns(truth_rows):
    """Required columns first, then any extra columns in the order given (D40 (5))."""
    if not truth_rows:
        raise ValueError("no truth rows")
    keys = list(truth_rows[0])
    missing = [c for c in TRUTH_REQUIRED if c not in keys]
    if missing:
        raise ValueError(f"truth rows lack columns {missing}")
    return list(TRUTH_REQUIRED) + [k for k in keys if k not in TRUTH_REQUIRED]


def write_run_files(run_dir, run, calls, events, truth_rows=None):
    """Create run_dir and write the run files. Returns run_dir.

    run: dict for run.json; calls: (t_ms, sensor_env, sensor_given, intake,
    outtake); events: (t_ms, source, event, detail), sorted here by time
    (stable, so events at the same time keep their order); truth_rows: list
    of dicts from the simulation environment, or None (rig).
    """
    os.makedirs(run_dir, exist_ok=False)
    with open(os.path.join(run_dir, "run.json"), "x", encoding="utf-8") as fh:
        json.dump(run, fh, indent=2)
        fh.write("\n")
    _write_csv(os.path.join(run_dir, "calls.csv"), CALL_COLUMNS, calls)
    _write_csv(os.path.join(run_dir, "events.csv"), EVENT_COLUMNS,
               sorted(events, key=lambda e: e[0]))
    if truth_rows is not None:
        columns = truth_columns(truth_rows)
        _write_csv(os.path.join(run_dir, "truth.csv"), columns,
                   [[row[c] for c in columns] for row in truth_rows])
    return run_dir
