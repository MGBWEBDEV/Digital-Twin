# Atomic handoff — WP09a (rig I/O firmware, host adapter, rig runner)

- Agent / model version if known: Claude Code, model Claude Opus 5.5 (`claude-opus-5-5`), 2026-11-26.
- Status: Approved by researcher 2026-11-26 (agent's recommended settings). Compile-checked for the ESP32-S2 (two Arduino cores), **not uploaded**; no hardware touched. D49 approved.
- Scope completed:
  1. **Firmware** `src/esp32/`, derived from StepExample (D32). One firmware switches both driver channels with `kSetPumps`. The timed `kStep` is replaced by a per-run `kSetLimit` and a compiled-in ceiling (D45). The cut-off follows D38 exactly: continuous ON time from the ON edge, latched OFF until the command goes OFF, reported once with `kCutoff`. The sensor is reported raw on change and on request (−1 = not wired). The start-up message `kStarted` lets the host detect a restart (WP06 X8). All driver outputs are set OFF first in `setup()`. Speed and direction are fixed (D20). The cut-off and limit rules are in a plain-C core (`lib/rig_core`) so the same file is tested on the host. All rig values are in `include/rig_config.h`, which stops the build until `RIG_CONFIG_REVIEWED` = 1 and `CUTOFF_CEILING_MS` > 0. It has no placeholder ceiling (D34).
  2. **Host adapter** `src/shared/rig_protocol.py` (message format, pyserial only) and `src/shared/rig_environment.py` (`RigEnvironment`, the same `Environment` interface; the harness is unchanged). It maps channels (P17), normalizes the sensor (P18), paces with the monotonic clock, sends commands only on change, refuses a limit above the firmware ceiling, and checks the start sensor state. It logs commands, acks, edges, cut-offs and firmware messages with host ms and firmware ms. It marks the run invalid and sends `kStop` on: firmware restart, firmware error, protocol error, lost link, missing ack, Ctrl-C, or a cut-off missing 500 ms after the limit.
  3. **Rig runner** `src/shared/run_rig.py`. It runs one labelled run from an approved session-plan JSON and refuses before any pump switches ON when gates fail (list in `src/esp32/README.md`). It asks for the start reading (band check, D46 (1)) and a typed RUN, then for the end and peak readings after settling. It writes `run.json`, `calls.csv`, `events.csv` and `manual.csv` in the format the evaluator reads, and runs the D37 static check and the determinism replay as the simulation runner does.
  4. Test doubles `double_never_off.py` and `double_on_15s.py` for the cut-off check (protocol 7.4), labelled in the doubles README.
- Created or modified paths (compile check later changed `src/esp32/src/main.cpp`, `platformio.ini` comment and `README.md`):
  - New: `src/esp32/` (`platformio.ini`, `README.md`, `.gitignore`, `include/rig_config.h`, `src/main.cpp`, `lib/rig_core/rig_core.{h,c}`, `lib/CmdMessenger/{CmdMessenger.h,CmdMessenger.cpp,LICENSE.md}` byte-identical copies, `test/native/test_rig_core.c`); `src/shared/rig_protocol.py`, `rig_environment.py`, `run_rig.py`; `src/shared/tests/fake_rig.py` (labelled fake firmware), `test_rig_firmware_and_adapter.py`, `doubles/double_never_off.py`, `doubles/double_on_15s.py`; this handoff.
  - Modified: `src/shared/tests/doubles/README.md` (two rows, rig-use note); `design/software_architecture.md` (section 12 status note, section 13 open point); `experiments/experimental_protocol.md` (section 8 "Consequences" sentence); `context/decisions.md` (D49 proposed, note on D16); `context/project_status.md` (WP09a row, next task, change log).
- Checks performed and actual results:
  - `python3 -m unittest discover -s src -t src`: **199 tests, OK** (167 before, 32 new).
  - The native C test of `rig_core` was compiled with `gcc -std=c99 -Wall -Wextra -Werror -pedantic`: **55 checks, 0 failures**. The expected values were written by hand from D38/D45 (limit, ceiling, no ON before a limit, no limit change while ON, repeated ON, new edge, independent channels, stop, `millis()` wrap-around).
  - Message IDs in Python match the `main.cpp` enum (parsed in a test). The CmdMessenger copies match the reference by SHA-256.
  - Adapter and runner were tested against the fake firmware with a fake clock:
    - the never-OFF double is cut off at 10 000 ms (event within 5 ms; fake hardware ON for exactly 10 000 ms on channel 1 only);
    - OFF at 15 s gives no cut-off;
    - channel swap works;
    - a missing cut-off is detected at 10 500–10 510 ms and stopped;
    - restart, error, lost link, missing ack and Ctrl-C each invalidate the run and stop the pumps;
    - each refusal case sends no `kSetPumps`;
    - a reference run is refused with the placeholder parameter set;
    - with a test copy of the parameters marked final, a reference S2 run produces run files that `testing.runfiles.read_run` reads.
  - One defect was found and fixed during testing: a lost link was logged on every poll (51 events). It is now logged once.
  - **Compile check (researcher request, same day):** PlatformIO Core 6.2.0 in a scratchpad venv. The builds used a scratch copy of `src/esp32` with a test-only `rig_config.h` (reviewed = 1, ceiling 15 000 ms, sensor −1); the repository file is unchanged.
    1. The unchanged copy stops at both `#error` gates, as intended.
    2. On `espressif32@8.0.0` (Arduino core 3.3.12) the first build **failed**: core 3.x changed `analogWriteResolution` to `(pin, bits)`. `main.cpp` now chooses the call by `ESP_ARDUINO_VERSION_MAJOR`. After that it builds, with no warnings from new code (RAM 15.5 %, flash 22.4 %).
    3. On `espressif32@6.9.0` (core 2.0.17) it builds (RAM 8.5 %, flash 19.3 %).
    4. Core sources read: a duty of 4095 at 12 bits gives full ON on both cores. Unmodified StepExample builds only on core 2.x.
  - **Not done:** upload and any hardware run; pyserial is not installed (the tests do not need it).
- Decisions (proposed vs approved), decision IDs: D49 **proposed** (protocol, limit rules, config header gate, host safeguards, session-plan runner, rig `v0_ml` convention, open first ceiling). It would settle the protocol part of D16. It implements D45's "set limit" and ceiling and D27 (1) on the rig.
- Assumptions / changes from previous artifacts:
  - The firmware works in driver channels. Intake/outtake is a host setting (`intake_channel`), so P17 can change without re-flashing.
  - For rig runs, `v0_ml` in `run.json` is the planned V0, because the evaluator compares it with the scenario for non-paired runs. The measured reading is `v0_start_reading_ml` and in `manual.csv`. D48 (3) describes `v0_ml` as "start volume actually used", which reads naturally for models; this rig convention is part of D49 (6).
  - Cut-off-check runs take R01, T_end, R09, V0 and band from the session plan, not from the placeholder set, so that no placeholder reaches a physical run (D34). The request given to the test double still carries placeholder values. Test doubles ignore it.
  - P16 (host timestamp resolution): the adapter logs integer ms from `time.monotonic_ns()`, so the resolution is 1 ms. `design/physical_system.md` is not edited.
  - Timeouts (1 s ack, 500 ms cut-off grace, 2 ms poll) are software choices, not rig values.
- Blockers / outstanding questions:
  1. First conservative ceiling before WP04 (D49 (7)): the researcher must choose it, with an upper bound on the real intake rate from somewhere other than P06.
  2. Platform version: pinned to `espressif32@6.9.0` (core 2.0.17) by researcher decision 2026-11-26 (D49 (8)), for compatibility with the firmware the rig runs now. Unmodified StepExample builds with it, and so does this firmware from the pinned `platformio.ini`. The exact version of the rig's current build is still unknown; if the build machine is available, `pio pkg list` there would show it.
  3. Rig check (section 10 of `design/physical_system.md`) still needed for pins, channel assignment, speed/direction, sensor pin and polarity; sensor not wired (D19).
  4. Serial write blocking on USB-CDC and its effect on cut-off timing is unmeasured; the cut-off check should note the observed `fw_ms` of `kCutoff` against the limit.
  5. Reset method (D46 (1)) not supported if it reverses a pump.
- Downstream dependencies: WP04 (can use the firmware for timed pumping: set the limit to the wanted duration and let the cut-off end it; calibration tooling itself is WP04); WP09b (reference controller runs through `shared.run_rig`); WP13/WP15 (rig run files, `manual.csv`, session plans); protocol section 7.4 (cut-off check uses the two new doubles).
- Prompt/log reference or commit identifier if available: researcher prompt of 2026-11-26 ("Execute WP09a only: rig I/O firmware starting from the bundled StepExample, with a per-run 'set limit' command and a compiled-in ceiling. Do not upload to hardware …"). Base commit `6fe786a`; changes uncommitted. Codex's uncommitted WP07 figure files, handoffs and status-file lines were left untouched.
- Next suggested atomic task (do not execute): researcher review of WP09a and D49; then the rig check and sensor wiring before the first session plan (cut-off check).

## Addendum 2026-11-26 (same session, later requests)

- The compile check and the platform pin are described above (D49 (8)).
- WP04 tooling (handoff `WP04_characterization-protocol.md`) added two read-only helpers to `RigEnvironment`, `round_trip_ms()` and `cutoff_seen()`, and the test double `double_on_2s.py`. The staged sessions of proposed D50 (1) answer the open first-ceiling question D49 (7).
- `run.json` of rig runs now also records `controller.generation_id` (WP12 follow-up).
