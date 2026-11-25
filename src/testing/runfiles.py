"""Readers for the run files of `design/software_architecture.md` section 7.

Only parsing and format validation happen here; no verdicts. A file that
cannot be parsed raises RunFileError: a broken log is a tooling fault, not a
controller verdict. Booleans are accepted as 0/1 or true/false.
"""

import csv
import json
import os
from dataclasses import dataclass, field
from typing import List, Optional


class RunFileError(Exception):
    """A run file is missing or malformed."""


CALL_COLUMNS = ("t_ms", "sensor_env", "sensor_given", "intake", "outtake")
EVENT_COLUMNS = ("t_ms", "source", "event", "detail")
TRUTH_COLUMNS = ("t_ms", "volume_ml", "intake_flowing", "outtake_flowing",
                 "overflow", "spill_ml", "shortfall_ml")
MANUAL_COLUMNS = ("point", "time", "volume_ml", "uncertainty_ml", "note")


@dataclass(frozen=True)
class Call:
    t_ms: int
    sensor_env: bool
    sensor_given: bool
    intake: bool
    outtake: bool


@dataclass(frozen=True)
class Event:
    t_ms: int
    source: str
    event: str
    detail: str


@dataclass(frozen=True)
class TruthRow:
    t_ms: int
    volume_ml: float
    overflow: bool
    spill_ml: float


@dataclass
class RunFiles:
    run: dict
    calls: List[Call]
    events: List[Event]
    truth: Optional[List[TruthRow]] = None      # models only
    manual: Optional[dict] = None               # rig only: point -> volume_ml
    notes: List[str] = field(default_factory=list)


def parse_bool(text, where):
    t = text.strip().lower()
    if t in ("1", "true"):
        return True
    if t in ("0", "false"):
        return False
    raise RunFileError(f"{where}: not a boolean: {text!r}")


def parse_int(text, where):
    try:
        return int(text.strip())
    except ValueError:
        raise RunFileError(f"{where}: not an integer: {text!r}") from None


def parse_float(text, where):
    try:
        return float(text.strip())
    except ValueError:
        raise RunFileError(f"{where}: not a number: {text!r}") from None


def _read_csv(path, required):
    if not os.path.isfile(path):
        raise RunFileError(f"missing file: {path}")
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        missing = [c for c in required if c not in header]
        if missing:
            raise RunFileError(f"{path}: missing columns {missing}")
        return [(i + 2, row) for i, row in enumerate(reader)]


def read_calls(path):
    calls = []
    for line, row in _read_csv(path, CALL_COLUMNS):
        w = f"{os.path.basename(path)} line {line}"
        calls.append(Call(
            parse_int(row["t_ms"], w),
            parse_bool(row["sensor_env"], w),
            parse_bool(row["sensor_given"], w),
            parse_bool(row["intake"], w),
            parse_bool(row["outtake"], w),
        ))
    if not calls:
        raise RunFileError(f"{path}: no calls")
    return calls


def read_events(path):
    events = []
    for line, row in _read_csv(path, EVENT_COLUMNS):
        w = f"{os.path.basename(path)} line {line}"
        events.append(Event(parse_int(row["t_ms"], w), row["source"].strip(),
                            row["event"].strip(), (row["detail"] or "").strip()))
    return events


def read_truth(path):
    rows = []
    for line, row in _read_csv(path, TRUTH_COLUMNS):
        w = f"{os.path.basename(path)} line {line}"
        rows.append(TruthRow(
            parse_int(row["t_ms"], w),
            parse_float(row["volume_ml"], w),
            parse_bool(row["overflow"], w),
            parse_float(row["spill_ml"], w),
        ))
    if not rows:
        raise RunFileError(f"{path}: no rows")
    for a, b in zip(rows, rows[1:]):
        if b.t_ms <= a.t_ms:
            raise RunFileError(f"{path}: t_ms not increasing at {b.t_ms}")
    return rows


def read_manual(path):
    """Return {point: volume_ml}. Rows with an empty volume are skipped."""
    readings = {}
    for line, row in _read_csv(path, MANUAL_COLUMNS):
        w = f"{os.path.basename(path)} line {line}"
        point = row["point"].strip()
        if not (row["volume_ml"] or "").strip():
            continue
        if point in readings:
            raise RunFileError(f"{w}: duplicate point {point!r}")
        readings[point] = parse_float(row["volume_ml"], w)
    return readings


def read_run(run_dir):
    """Read every run file needed for evaluation from one run directory."""
    run_path = os.path.join(run_dir, "run.json")
    if not os.path.isfile(run_path):
        raise RunFileError(f"missing file: {run_path}")
    with open(run_path, encoding="utf-8") as fh:
        try:
            run = json.load(fh)
        except json.JSONDecodeError as exc:
            raise RunFileError(f"{run_path}: {exc}") from None
    for key in ("run_id", "environment", "scenario_id", "request",
                "parameters", "dt_call_ms", "end_reason"):
        if key not in run:
            raise RunFileError(f"{run_path}: missing key {key!r}")

    files = RunFiles(run=run,
                     calls=read_calls(os.path.join(run_dir, "calls.csv")),
                     events=read_events(os.path.join(run_dir, "events.csv")))
    if run["environment"] == "rig":
        manual = os.path.join(run_dir, "manual.csv")
        if os.path.isfile(manual):
            files.manual = read_manual(manual)
        else:
            files.manual = {}
            files.notes.append("manual.csv missing: physical checks undetermined")
    else:
        files.truth = read_truth(os.path.join(run_dir, "truth.csv"))
    return files
