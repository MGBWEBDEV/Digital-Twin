# Rig I/O firmware (WP09a)

> **Status: approved by researcher 2026-11-26, compile-checked, not uploaded.** Written by Claude Code on 2026-11-26. The protocol and safety design are D49 (approved). The firmware compiles for the Metro ESP32-S2 with Arduino core 3.3.12 (`espressif32@8.0.0`) and core 2.0.17 (`espressif32@6.9.0`). Those builds used a scratch copy with a test-only `rig_config.h` (reviewed = 1, ceiling 15 000 ms, sensor −1), not the repository file. It has not run on a board. The cut-off logic (`lib/rig_core`) is also tested on the host. Uploading needs the researcher's approval (AGENTS.md; protocol section 6.1).

## What it is

This is the ESP32 firmware of the rig. It acts as a serial I/O server (D21) for the two pumps and the level sensor, and it enforces the safety cut-off (D27, D38, D45). It contains no controller logic (D30). The controller runs on the host and talks to the firmware through `src/shared/rig_environment.py`.

It is derived from the bundled StepExample (`references/LabAutomationKits/Electronics/Firmware/StepExample`, upstream commit `a22a6b9`, D32).

| Kept from StepExample | Changed |
|---|---|
| Board `adafruit_metro_esp32s2`, Arduino framework (`platformio.ini`); platform pinned to `espressif32@6.9.0` (Arduino core 2.0.17), on which unmodified StepExample builds (researcher decision 2026-11-26, for compatibility with the firmware the rig runs now) | The timed `kStep` is removed. Instead the host sends a per-run **limit** (`kSetLimit`) and ON/OFF commands for **both** pumps (`kSetPumps`) |
| CmdMessenger on `Serial`, 115 200 baud, separators `,` `;` `/` | Arguments are sent as text, so the host needs only pyserial, not PyCmdMessenger |
| Driver pins and `analogWrite` calls of `DF4MotorDriver` (channel 1: PWM 8, DIR 9; channel 2: PWM 16, DIR 21) | Speed and direction are fixed in `include/rig_config.h` (D20), not sent with each command |
| Watchdog identifier reply | Added: sensor report (`kSensor`), cut-off report (`kCutoff`), start-up message (`kStarted`), configuration report (`kInfo`) |
| — | All driver outputs are set OFF first thing in `setup()`. StepExample only set the pin modes |

`lib/CmdMessenger/` holds byte-identical copies of `CmdMessenger.h`, `CmdMessenger.cpp` and `LICENSE.md` (MIT) from StepExample. The examples and `library.json` were not copied. `library.json` lists dependencies (PID, a thermocouple library) that this firmware does not need.

## Cut-off and limit rules

These rules are in `lib/rig_core/rig_core.c`. It is plain C so the same file is tested on the host. The rules are identical to `src/shared/cutoff.py` (D38):

1. For each pump, a timer counts continuous ON time from the moment the firmware receives the ON command. Only an OFF → ON change of the commanded state starts the timer.
2. When the timer reaches the limit, the pump is switched OFF and `kCutoff` is sent once. The pump stays OFF while the command stays ON. Only OFF and then ON again starts a new timer. A repeated ON without an OFF in between changes nothing.
3. No pump can be switched ON before a limit has been set. After start-up the limit is 0, which means "not set".
4. A limit must satisfy 0 < limit ≤ `CUTOFF_CEILING_MS`, the compiled-in ceiling.
5. The limit can only be changed while both pumps are commanded OFF.
6. `kStop` switches both pumps OFF and clears the trips. The limit is kept.

Example with test numbers: with a 10 s limit, a pump commanded ON at 1.000 s is still ON at 10.999 s and is OFF at 11.000 s. A second ON command at 12 s, without an OFF in between, leaves it OFF.

The loop applies the cut-off before and after reading serial input, and the output is switched OFF before the report is sent.

## Messages

Each message is `id,arg,...;`. The firmware ends each message with CR LF. The IDs are listed in the same order in `src/shared/rig_protocol.py`, and a unit test checks that they match.

| ID | Name | Direction | Arguments | Reply |
|---|---|---|---|---|
| 0 | kWatchdog | both | (reply: device identifier) | kWatchdog |
| 1 | kStarted | fw → host | name, version | — |
| 2 | kError | fw → host | code: `unknown_command`, `bad_argument`, `limit_not_positive`, `limit_above_ceiling`, `pumps_on`, `no_limit` | — |
| 3 | kGetInfo | host → fw | — | kInfo |
| 4 | kInfo | fw → host | name, version, ceiling_ms, ch1 PWM pin, ch1 DIR pin, ch1 speed, ch1 DIR level, the same for ch2, sensor pin | — |
| 5 | kSetLimit | host → fw | limit_ms | kLimitSet or kError |
| 6 | kLimitSet | fw → host | limit_ms | — |
| 7 | kSetPumps | host → fw | on_ch1 (0/1), on_ch2 (0/1) | kPumps or kError |
| 8 | kPumps | fw → host | cmd1, eff1, cmd2, eff2, fw_ms | — |
| 9 | kStop | host → fw | — | kPumps |
| 10 | kGetState | host → fw | — | kState |
| 11 | kState | fw → host | cmd1, eff1, trip1, cmd2, eff2, trip2, limit_ms, sensor, fw_ms | — |
| 12 | kGetSensor | host → fw | — | kSensor |
| 13 | kSensor | fw → host | raw level 0/1 (−1 = not wired), fw_ms; also sent on every change | — |
| 14 | kCutoff | fw → host | channel (1/2), on_ms, fw_ms | — |

`fw_ms` is the firmware's `millis()`. The host adds its own timestamp to every message it logs.

## Before a build that is uploaded

`include/rig_config.h` holds every rig-specific value. The build **stops with an `#error`** until:

1. pins, channel assignment (P17), speed and direction (P19) are checked against the rig (`design/physical_system.md` section 10);
2. `CUTOFF_CEILING_MS` is set to the largest T_max of the approved session plan (D45). This is a safety limit, so it is never a placeholder (D34). The first session (cut-off check, WP04) needs a conservative ceiling chosen by the researcher before WP04 values exist (open, see D49);
3. `SENSOR_PIN` is set once the sensor is wired (D19), or left at −1. With −1, only runs that do not need the sensor can start (the cut-off check);
4. `RIG_CONFIG_REVIEWED` is set to 1.

Then build with `pio run` in this directory. After the researcher approves, upload with `pio run --target upload`. Record the firmware version, the SHA-256 of the built image, the `rig_config.h` values and the PlatformIO platform version in the session log (protocol sections 6.1 and 16).

## Host side

- `src/shared/rig_protocol.py`: message IDs, encoding and decoding.
- `src/shared/rig_environment.py`: `RigEnvironment`, the same `Environment` interface as the simulation. It maps intake and outtake to channels, normalizes the sensor (P18), paces real time, sets the per-run limit at `start()`, and logs every message. It marks the run invalid and sends `kStop` on any of these: firmware restart, firmware error, protocol error, lost link, missing acknowledgement, researcher Ctrl-C, or a cut-off that has not arrived 500 ms after the limit (a host check that detects a firmware fault; it does not replace the firmware cut-off).
- `src/shared/run_rig.py`: runs one run from an approved session plan and writes `run.json`, `calls.csv`, `events.csv` and `manual.csv` (readings entered by the researcher). Requires `pip install pyserial`.

Rig configuration file (`--rig-config`). The values come from the rig check, not from placeholders:

```json
{"intake_channel": 1, "sensor_wet_level": 1}
```

`sensor_wet_level` is `null` while the sensor is not wired.

Session plan file (`--session-plan`). It is written per session and approved in writing (protocol section 7.1). The structure is shown below; every value is an example only:

```json
{
  "session_id": "<id>", "approved_by": "<researcher>", "approved_on": "<date>",
  "firmware_ceiling_ms": 15000,
  "runs": [
    {"label": "CC1", "purpose": "cutoff_check",
     "controller": "src/shared/tests/doubles/double_never_off.py",
     "controller_sha256": "<sha256>", "scenario_id": "S2",
     "v0_plan_ml": 5, "v0_band_ml": 1, "start_sensor": null,
     "t_max_ms": 10000, "dt_call_ms": 100, "t_end_ms": 15000, "settle_ms": 10000},
    {"label": "CC2", "purpose": "cutoff_check",
     "controller": "src/shared/tests/doubles/double_on_15s.py", "...": "...",
     "t_max_ms": 15000, "t_end_ms": 20000}
  ]
}
```

The runner refuses a run, before any pump is switched ON, if any of these holds:

- the plan has no approval;
- the label is missing from the plan;
- the controller hash differs from the plan;
- the controller fails the D37 static check;
- the plan ceiling is not its largest T_max;
- the firmware reports a different ceiling;
- a `cutoff_check` run uses something other than a test double;
- a `reference` or `fault` run uses placeholder parameters, or differs from its scenario (V0, band, D45 T_max, R01, R08, R09, start sensor state);
- the start reading is outside the band;
- the firmware's sensor state does not match the plan;
- the researcher does not type `RUN`.

## Tests

- `src/esp32/test/native/test_rig_core.c`: 55 hand-written checks of the cut-off and limit rules, including `millis()` wrap-around. `src/shared/tests/test_rig_firmware_and_adapter.py` compiles and runs it with the host C compiler (it is skipped if none is installed).
- The same Python file tests the message format, that the message IDs match the `main.cpp` enum, that the copied CmdMessenger files are unchanged, and the adapter and runner. These run against a labelled fake firmware (`src/shared/tests/fake_rig.py`), not against hardware.

## Not verified and known limits

- Compiled but never run on a board. Arduino core 3.x changed `analogWriteResolution` to a per-pin call. `main.cpp` selects the right form by core version. Unmodified StepExample (one-argument form) builds only on core 2.x, so the rig's existing build used a 2.x core. The core's library sources show that a duty of 4095 at 12 bits gives full ON on both 2.0.17 and 3.3.12 (`ledcWrite`). StepExample's 4096 is passed to the hardware unchanged on 2.0.17; what the hardware does with it was not checked (P19, D32).
- Build sizes (test config): core 3.3.12 RAM 15.5 %, flash 22.4 %; core 2.0.17 RAM 8.5 %, flash 19.3 %. Only the unchanged CmdMessenger library gives compiler warnings (always-true comparisons, a switch fall-through).
- If the host stops reading while the firmware is sending, a USB-CDC write could block and delay the cut-off check by the write timeout. This has not been measured. The cut-off check (protocol 7.4) and the host's missing-cut-off check bound the effect but do not remove it. Messages are sent only on events and replies to keep traffic low.
- The sensor is not debounced. A noisy input would send many `kSensor` messages.
- Pin levels between power-on and `setup()` depend on the hardware, not on this firmware.
- A reset method that reverses the intake pump (D46 (1), still TBD) is not supported. It would be a later, separately approved change.
