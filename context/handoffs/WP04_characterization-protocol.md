# Atomic handoff — WP04 (provisional): characterization protocol, calibration tool, analysis rules

- Agent / model version if known: Claude Code, model Claude Opus 5.5 (`claude-opus-5-5`), 2026-11-26.
- Status: Approved by researcher 2026-11-26 (agent's recommended settings). **Provisional: protocol and tools only; no measurement made, no hardware used.** D50 approved.
- Scope completed (researcher request 2026-11-26: "finish everything that doesn't require the physical tank"):
  1. `experiments/physical_characterization.md`:
     - prerequisites and gates;
     - staged sessions A/B/C, which size each firmware ceiling from evidence already in hand and so answer D49 (7);
     - measurements M1–M8, with procedure, repeats and the parameter each one feeds;
     - analysis rules 1–10;
     - the D24 inclusion test with an added uncertainty condition;
     - final-value derivation per protocol section 3;
     - safety, tools, calibration plan format, and outputs for other WPs.

     Section 9 (data) is empty.
  2. `src/shared/run_calibration.py`: runs one action from an approved calibration plan. The action kinds are `readings` (M1, M2; no rig), `timed_fill` (M3/M4/M5; the firmware cut-off times the fill), `latency` (M6), `sensor_steps` (M7) and `sensor_crossing` (M8).
     - Gates: approval recorded, ceiling consistency (plan, firmware, largest limit), the worst-end check against the safe mark minus 2 graduations using the plan's q_hi and its source, the start band, sensor wiring for sensor actions, and a typed RUN.
     - Output goes to `experiments/data/<session>/<label>/`.
  3. `src/characterization/analysis.py`: rules 1–10 as functions, `summarize()` over the calibration records and a CLI. Arithmetic uses exact fractions. Rules that cannot be met are returned as flags.
  4. Test double `src/shared/tests/doubles/double_on_2s.py` (cut-off check step 2 with a short Session A limit). Fake firmware extended with `kGetState` and a timed wet sensor. `RigEnvironment` gained `round_trip_ms()` and `cutoff_seen()`.
- Created or modified paths: new `experiments/physical_characterization.md`, `src/shared/run_calibration.py`, `src/characterization/{__init__,analysis}.py`, `src/characterization/tests/{__init__,test_analysis}.py`, `src/shared/tests/test_rig_calibration.py`, `src/shared/tests/doubles/double_on_2s.py`; modified `src/shared/rig_environment.py`, `src/shared/tests/fake_rig.py`, `src/shared/tests/doubles/README.md`, `design/physical_system.md` (status note U24, U28, P16), `experiments/experimental_protocol.md` (section 16 status note, section 18 rows), `context/decisions.md` (D50), `context/project_status.md`, this handoff.
- Checks performed and actual results:
  - `python3 -m unittest discover -s src -t src`: **224 tests, OK**.
  - Analysis: 13 tests on **synthetic data, labelled as such**, with every expected value worked out by hand first (in the test file docstring), for example Q = 2500/2500 = 1.0 mL/s, b = −0.3 mL, Q_in,hi = 1.1, V_ro 0.6, V_p 0.9, V_sensor 23.25, T_max(5 mL) = 44.0 s, R06 30 s, R08 50 s. All matched on the first run. Three flag cases are covered (target not above the sensor, R06 too close to T_max, FR09 fill reaching T_max).
  - Calibration tool: 10 tests against the fake firmware:
    - a firmware-timed fill was ON for exactly 3000 ms;
    - settling series, readings without the rig, latency, sensor steps stopping at the first wet state (three 500 ms pulses) and a sensor crossing switched OFF within 10 ms of the wet edge;
    - five refusal cases, firmware ceiling mismatch and start band, each with no `kSetPumps` sent;
    - the worst-end boundary (28.0 s allowed, 28.1 s refused).
  - **Defect found and fixed:** `wait_cutoff` used an absolute deadline, so from the second pulse of `sensor_steps` on, the host switched OFF immediately. On the rig, later pulses would have delivered nothing. The deadline is now counted from the ON command.
- Decisions (proposed vs approved), decision IDs: D50 **proposed** (staged sessions; u_read, consistency, Q_in,hi rules; D24 inclusion with uncertainty condition; final-value details; M4 separation, no outtake in WP04; tool gates).
- Assumptions / changes from previous artifacts:
  - D24 is narrowed by the uncertainty condition (D50 (5)). As worded, D24 would include a 2.5 ms latency because it exceeds the 1 ms log resolution, even though its volume effect is invisible.
  - Q_out is not measured in WP04 (U30, X5); P07 stays a placeholder for the models.
  - The "early feasibility check" (roadmap) is the inclusion table after Session B.
  - The reset method (U10, U11, R13) remains open; M4 depends on it.
- Blockers / outstanding questions: rig check and safe mark; q_bound with its source for Session A; WP09a review and upload; sensor wiring for M7/M8; reset method.
- Downstream dependencies: final WP05 section 7 (inclusion), WP08 final values, `src/testing/parameters.py` and `src/model_1/parameters.py` (by ID), WP11, Session C plan and ceiling.
- Prompt/log reference or commit identifier if available: researcher prompts of 2026-11-26 ("lets finish everything that doesnt require the physial tank"). Base commit `6fe786a`; changes uncommitted.
- Next suggested atomic task (do not execute): researcher review of D50 and this protocol; then the rig check and a Session A plan for approval.
