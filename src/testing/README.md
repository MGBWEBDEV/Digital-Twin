# Evaluator (WP12, test-first part)

> Status: approved by researcher 2026-11-25 (Claude Code). Provisional: all parameter values are placeholders (D34). Evaluator conventions: D41 (approved). Version 0.4.0 (2026-11-26, D45/D46 follow-up: `purpose`, `v0_ml`, `t_max_s`; D48 approved by researcher 2026-11-26).

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
  "scenario_id": "S2", "purpose": "reference | fault | pool | paired",
  "v0_ml": 5.0, "t_max_s": 48.5,
  "request": {"task": "FR03", "parameter": 0.0, "v_sensor_ml": 24.0,
              "q_in_ml_per_s": 1.0, "t_deadline_s": 30.0},
  "parameters": {"R01": 0.1, "R02": 0.5, "…": "every ID in parameters.py"},
  "dt_call_ms": 100, "end_reason": "normal | invalid | controller_error"
}
```

Other keys (date, commit, controller hash, `dt_sim_ms`, `v0_plan_ml`, `paired_with`, `t_max_rule`, …) are kept by the harness and ignored here.

- `purpose` (protocol section 4): only `reference`, `fault`, `pool` and `paired` runs are scored; any other purpose makes the run invalid. Verdicts of `pool` runs carry `exploratory: true`.
- `v0_ml`: start volume given to the environment. It must equal the scenario V0, except for a `paired` run, where it is the measured rig V0 and must lie within the scenario V0 ± R14 (D46). For models, the first `truth.csv` volume must equal `v0_ml` (D41 (5)).
- `t_max_s`: per-run cut-off (D45). The evaluator recomputes it from its own parameters and the scenario's planned V0, also for paired runs: ⌊(P01 − R12 − (V0 + R14) − P13) / Q_in,hi⌋ to 0.1 s (48.5 s from 5 mL, 23.5 s from 30 mL with placeholders). A different value makes the run invalid, so a setup error is never blamed on the controller.

- `calls.csv`: `t_ms, sensor_env, sensor_given, intake, outtake` (booleans 0/1 or true/false).
- `events.csv`: `t_ms, source, event, detail`. Event names read: `cutoff` (FR08-L4), `run_invalidated` (run not scored), `controller_error` (run fails, D42), `replay_differs` (run fails, D42), `late_call` (reported only). `run.json` key `determinism_replay` (`checked`, `identical`, `first_difference`) is read for the check `determinism_replay`.
- `truth.csv` (models): at least `t_ms, volume_ml, intake_flowing, outtake_flowing, overflow, spill_ml, shortfall_ml`; extra columns are ignored. First row at t = 0; last row at or after T_end + R09 (otherwise V_end is undetermined).
- `manual.csv` (rig): `point, time, volume_ml, uncertainty_ml, note`; points `start`, `end` and optionally `peak`.

## Results

Per check: `pass`, `fail`, `undetermined`, `not_applicable`. Overall: `invalid` (not scored; reasons listed), else `fail` if any check fails, else `undetermined` if any check is undetermined, else `pass`. A run with end reason `controller_error` (the controller raised an error or answered with something other than two booleans) fails with the single check `controller_error`, whose evidence gives the time and the error; its `calls.csv` may be empty (D42 (1)). Every scored run also gets the check `determinism_replay`: fail if the harness's replay of the recorded inputs gave a different answer, pass if it gave identical answers, not applicable if no replay is recorded (D42 (3)). Every verdict carries `provisional: true` while any parameter is a placeholder. S4 scores FR08 and FR03-L1. On the rig, FR08-P2 uses the settled end reading as the peak when the outtake never ran; otherwise it needs a `peak` reading (D41).
