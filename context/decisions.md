# Decision register

Status meanings: CONFIRMED = researcher-stated fact or scope; PROPOSED = design suggestion awaiting approval; OPEN = unresolved; APPROVED = explicitly reviewed and accepted by researcher. No implementation or experimental findings have been approved by this scaffold. Append changes with date, rationale, owner and source artifact; do not silently revise confirmed facts.

Rules: new entries take the next free ID and are appended by the agent or person owning the current task. A later entry that refines or supersedes an earlier one names it explicitly (e.g. "refines D03"); the earlier row then gets a short cross-reference note, never a rewritten text. The "Recorded" column gives the date and source; WP00 entries come from the ChatGPT-generated scaffold, whose exact date is not recorded.

| ID | Status | Decision / fact | Basis / implications | Recorded |
|---|---|---|---|---|
| D01 | CONFIRMED | Small ITU research project, preparatory to industrial thesis | Scope: 2 simulation models, 2 error types | WP00 |
| D02 | CONFIRMED | ESP32, one intake and one outtake peristaltic pump, discrete threshold sensor, graduated syringe | Researcher hardware description; physical inspection pending. Refined by D18, D19 | WP00 |
| D03 | CONFIRMED | ON/OFF pump control and duration only; no direct flow measurement; Boolean sensor not numerical volume | Controller cannot directly observe actual water volume. Driver supports PWM speed/direction; see D20 | WP00 |
| D04 | CONFIRMED | AI-generated modelling and coding | Researcher responsible for requirements, independent checks, physical measurements and review | WP00 |
| D05 | CONFIRMED | Physical system is reference, simulated state logs initially sufficient | Do not assume continuous physical volume logging | WP00 |
| D06 | CONFIRMED | Base and extended model, shared controller logic physical/simulated | Compare the same controller and acceptance criteria. Controller location: D21 | WP00 |
| D07 | PROPOSED | Common hardware interface and compatible clock, hidden simulation volume for logger/evaluator only | Final architecture WP07; information parity required | WP00 |
| D08 | PROPOSED | Model 1 volume balance; Model 2 candidate time-dependent transfer equation | Exact fidelity distinction requires WP04–05; equations may be equivalent | WP00 |
| D09 | PROPOSED | Small task suite, common logical/physical criteria, separate mathematical verification and empirical validation | WP03/WP08 | WP00 |
| D10 | PROPOSED | Natural AI faults first within a fixed budget; isolated injection fallback | Finalize WP08; document origin and selection | WP00 |
| D11 | PROPOSED | Structured CSV/JSON logs; no GUI required initially | WP07/WP08 | WP00 |
| D12 | OPEN | Hardware capacity, thresholds, polarity, flow/transfer, timing, uncertainty, wiring, safe operating limits | WP01/WP04; no invented values | WP00 |
| D13 | OPEN | Final two-model differences and parameters | WP04/WP05 | WP00 |
| D14 | OPEN | Final tasks, tolerances, validation metrics, generation budget and selection protocol | WP03/WP08 | WP00 |
| D15 | OPEN | Final two selected error types | WP14 following protocol | WP00 |
| D16 | OPEN | Exact firmware/toolchain, hardware interface implementation | WP01/WP07/WP09. Controller location and language resolved by D21; firmware changes and serial protocol remain open | WP00 |
| D17 | PROPOSED | Claude Code and Codex share a canonical instruction file, Git and task handoffs; manual coordination | WP00 scaffold; researcher chooses agent per task | WP00 |
| D18 | CONFIRMED | The rig has two pumps wired to the motor driver used by the StepExample base firmware: one intake, one outtake. Both have been run successfully. The firmware was modified from StepExample to drive the second pump (researcher recalls changing the pump identifier, e.g. A→B) | Researcher statement. Modified firmware not yet in the repository; exact code, pins, driver channels and board model remain OPEN until it is added (StepExample targets an Adafruit Metro ESP32-S2, not yet confirmed for the rig). WP01 | 2026-11-25, researcher (via Claude Code session) |
| D19 | CONFIRMED | The water-level sensor is physically installed but not wired to the ESP32 | Researcher statement. Sensor type, pin, polarity and threshold OPEN. Sensor-dependent rig tests (FR03, FR04, threshold scenarios) are blocked until it is wired and read by the firmware; design and simulation may proceed. WP01/WP04 | 2026-11-25, researcher (via Claude Code session) |
| D20 | PROPOSED | Each pump runs at one fixed speed (PWM value) and one fixed direction for the whole study; the controller issues ON/OFF only | Reconciles D03 with the PWM/direction-capable driver (StepExample `kStep` carries speed and direction). Values used so far are unknown; record them in WP01/WP04. Speed is a plant parameter, not a controller decision | 2026-11-25, Claude Code review of WP00 |
| D21 | APPROVED | The controller runs on the host PC in Python. The ESP32 firmware acts as a serial I/O server (StepExample pattern): it switches pumps and reports the sensor state. The same Python controller source runs against a serial hardware adapter and both simulation adapters | Rationale: the learning outcome is digital-twin design (D22); embedded realism is secondary, and a host controller makes same-source execution in simulation straightforward. Alternative considered: C++ scan-cycle controller on the ESP32, compiled natively for simulation. Implications: serial latency becomes part of rig response timing and must be characterized (WP04) and accounted for in models or tolerances; firmware must be extended to report the sensor and to switch both pumps through the protocol; command/sensor logging happens on the host. Affects WP01, WP06, WP07, WP09 | 2026-11-25, researcher (via Claude Code session) |
| D22 | CONFIRMED | Primary learning outcome of the project is learning how to design a digital twin (modelling and validation method); realism of the embedded implementation is secondary | Researcher statement. Use when trading off scope and effort | 2026-11-25, researcher (via Claude Code session) |
| D23 | APPROVED | The ChatGPT-drafted `functional_requirements.md` is adopted as the provisional WP03 draft and moved to `design/functional_requirements.md`; its FR numbering (FR05 volume transfer, FR06 fill/wait/drain, FR07 repeat) is authoritative | Removes the second requirements source. The master-context candidate list was renumbered to match. Reduction to a small subset is still pending (WP03) | 2026-11-25, researcher (via Claude Code session) |

## Decision entry template

- ID and date:
- Status:
- Decision and rationale:
- Evidence or artifact:
- Alternatives considered:
- Affected WPs:
- Researcher approval (if given):
