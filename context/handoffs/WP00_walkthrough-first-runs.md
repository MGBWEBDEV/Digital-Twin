# Project communication subtask — walkthrough to the first runs

- Agent / model version: Claude Code, Claude Opus 5.5 (`claude-opus-5-5`), 2026-11-26.
- Status: ready for review.
- Request: researcher asked for a walkthrough of the whole process, from rig and computer setup before the firmware upload to the first calibration, validation and test run, in natural simple language without abbreviations or document IDs.
- Changed paths: new `report/walkthrough_first_runs.md`; this handoff; one change-log line in `context/project_status.md`. No design, protocol, code, decision or approval changed.
- Sources: `design/physical_system.md` sections 10 and 12, `experiments/physical_characterization.md`, `experiments/experimental_protocol.md` sections 6–16, `src/esp32/README.md`, `src/esp32/include/rig_config.h`, `src/esp32/platformio.ini`, usage lines of `shared.run_rig`, `shared.run_calibration`, `characterization.analysis`, `testing.evaluator`, and `src/testing/scenarios`.
- Checks: `python3 -m unittest discover -s src -t src` ran 224 tests, OK (no hardware). Example arithmetic rechecked against the source documents (first limit 9.8 s, cautious rate 1.33 mL/s, longest second-session fill 31.5 s, per-run limit 48.5 s, runaway end 53.5 mL). pyserial and PlatformIO are not installed on this machine; the setup commands were not run.
- Additions beyond the source documents (to review): keep the pump power off during upload (the firmware README notes pin levels before start-up depend on the hardware); the BOOT/RESET tip for the ESP32-S2 upload; the `dialout` group step for Linux serial access; a repository-local `.venv` (already git-ignored); not typing commands into the serial monitor.
- Blockers: none for the document. Rig steps remain blocked by the rig check, safe mark, intake-tube emptying method, fastest-rate estimate and upload approval.
- Next suggested task (do not execute): researcher rig check (walkthrough step 1).
