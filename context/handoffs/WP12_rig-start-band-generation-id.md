# Atomic handoff — WP12 follow-up: rig start-reading band and controller generation ID

- Agent / model version if known: Claude Code, model Claude Opus 5.5 (`claude-opus-5-5`), 2026-11-26.
- Status: Approved by researcher 2026-11-26.
- Scope completed: the two items left open in `context/handoffs/WP10_WP12_per-run-cutoff.md`.
  1. Evaluator 0.5.0: a rig run is **invalid** if the settled start reading in `manual.csv` lies outside the planned V0 ± R14 (D46 (1)). Example: S2 planned at 5 mL with R14 = 1 mL; 6.0 is accepted, 6.5 and 3.9 are invalid. A missing start reading still makes the physical checks undetermined, as before.
  2. `run.json` records `controller.generation_id` (protocol section 16) in `shared.run_scenario` and `shared.run_rig`. It is the file name without `.py` for files in `src/shared/controllers/` (`G03`, `G01_inj-I-S`), and null for anything else (test doubles).
- Created or modified paths: `src/testing/evaluator.py` (version, check, docstring), `src/testing/README.md` (version line), `src/testing/tests/test_handwritten_logs.py` (one test), `src/shared/run_scenario.py` (`generation_id`, `CONTROLLERS_DIR`), `src/shared/run_rig.py`, `src/shared/tests/test_rig_firmware_and_adapter.py` (two assertions, one test), this handoff.
- Checks performed and actual results: full suite 224 tests OK. The new evaluator test uses hand values (band edges above); generation ID tested for a generated, an injected and a test-double path.
- Decisions: none new; implements approved D46 (1) and protocol section 16.
- Assumptions: the band check uses the scenario's planned V0 and the evaluator's own R14, the same as for paired runs.
- Blockers / outstanding questions: none. Model 2 verification (WP11) and closed-loop runs with the clean-room controller (WP09b) remain.
- Downstream dependencies: WP13/WP15 rig runs; generation ID links run files to `experiments/prompts/generations/Gnn.md`.
- Prompt/log reference: researcher prompt of 2026-11-26 ("lets finish everything that doesnt require the physial tank"). Changes uncommitted.
- Next suggested atomic task (do not execute): none in WP12 until WP11 or WP09b exist.
