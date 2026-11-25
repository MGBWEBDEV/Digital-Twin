# Evaluator (WP12, test-first part)

> Status: approved by researcher 2026-11-25 (Claude Code). Provisional: all parameter values are placeholders (D34). Evaluator conventions: D41 (approved).

Judges one finished run from its run files against the WP03 checks (`design/functional_requirements.md` section 5) and infers the WP06 end state (`design/controller_behavior.md` section 6). Standard library only; imports no controller and no model package.

```
PYTHONPATH=src python3 -m testing.evaluator experiments/logs/<run_id> [...]   # writes verdict.json
python3 -m unittest discover -s src -t src                                       # all tests
```

| File | Content |
|---|---|
| `evaluator.py` | Validity checks, WP03 checks by ID, end-state inference, `verdict.json`, command line |
| `runfiles.py` | Readers and format validation for the run files |
| `parameters.py` | R/P values used by the evaluator, by ID (placeholders) |
| `scenarios/` | S1–S5 as ten run cases (`S1-10`, `S1-20`, `S2`, `S3-FR03`, `S3-FR09-40`, `S4`, `S5-30` … `S5-48`) |
| `tests/` | Stub-plant oracle tests (WP03 section 9), hand-written logs, independence checks |

## Run files expected (architecture section 7; key names fixed by D41)

`run.json` must contain at least:

```json
{
  "run_id": "…", "environment": "model_1 | model_2 | rig",
  "scenario_id": "S2",
  "request": {"task": "FR03", "parameter": 0.0, "v_sensor_ml": 24.0,
              "q_in_ml_per_s": 1.0, "t_deadline_s": 30.0},
  "parameters": {"R01": 0.1, "R02": 0.5, "…": "every ID in parameters.py"},
  "dt_call_ms": 100, "end_reason": "normal | invalid"
}
```

Other keys (date, commit, controller hash, `dt_sim_ms`, …) are kept by the harness and ignored here.

- `calls.csv`: `t_ms, sensor_env, sensor_given, intake, outtake` (booleans 0/1 or true/false).
- `events.csv`: `t_ms, source, event, detail`. Event names read: `cutoff` (FR08-L4), `run_invalidated` (run not scored), `late_call` (reported only).
- `truth.csv` (models): at least `t_ms, volume_ml, intake_flowing, outtake_flowing, overflow, spill_ml, shortfall_ml`; extra columns are ignored. First row at t = 0; last row at or after T_end + R09 (otherwise V_end is undetermined).
- `manual.csv` (rig): `point, time, volume_ml, uncertainty_ml, note`; points `start`, `end` and optionally `peak`.

## Results

Per check: `pass`, `fail`, `undetermined`, `not_applicable`. Overall: `invalid` (not scored; reasons listed), else `fail` if any check fails, else `undetermined` if any check is undetermined, else `pass`. Every verdict carries `provisional: true` while any parameter is a placeholder. S4 scores FR08 and FR03-L1. On the rig, FR08-P2 uses the settled end reading as the peak when the outtake never ran; otherwise it needs a `peak` reading (D41).
