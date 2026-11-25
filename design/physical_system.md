# Physical system definition (WP01)

> **Status: Approved by researcher 2026-11-25 (agent-completed by Claude Code).** Approval covers the document's structure and content; items marked "derived from code", TBD or placeholder (section 12) remain unverified until the rig check and WP04. Describes the real rig from confirmed researcher statements (D02, D03, D18–D20, D32) and from the bundled StepExample code, which D32 makes the rig firmware baseline. No measurements were taken and no hardware was inspected by the agent. Every detail read from code is labelled "derived from code" and must be checked on the rig (checklist in section 10). Placeholder values for design and simulation work are in section 12 (D34); they are not facts. No equations beyond the shared conservation principle; no downstream design.

## 1. Evidence labels

| Label | Meaning |
|---|---|
| **Confirmed** | Stated by the researcher and recorded as CONFIRMED/APPROVED in `context/decisions.md` |
| **Derived from code** | Read from the bundled StepExample (`references/LabAutomationKits/Electronics/Firmware/StepExample/`, upstream commit `a22a6b98…`). Applies to the rig only as far as D32 holds; to be checked on the rig |
| **Assumed** | Working assumption stated by the agent; must be confirmed or replaced before it is used for a result |
| **Planned** | Required by an approved decision but not yet present on the rig |
| **TBD** | Unknown; no value is assumed |

Code paths below are relative to the StepExample directory.

## 2. System overview

A graduated syringe serves as a small water tank. An intake peristaltic pump adds water and an outtake peristaltic pump removes it (Confirmed, D02). Both pumps are wired to a motor driver controlled by an ESP32 board, and both have run (Confirmed, D18). The ESP32 runs StepExample with one pump identifier changed (Confirmed, D32); it executes timed pump commands received over a serial link and has no control logic of its own (Confirmed, D30). A discrete threshold water-level sensor is installed at the syringe but not wired (Confirmed, D19). The study's controller will run in Python on a host PC (Approved, D21). The researcher observes the volume by reading the syringe graduations (Confirmed, D02, D24).

## 3. Components

| ID | Component | Role | Known | Status / source | Open (see section 9) |
|---|---|---|---|---|---|
| C1 | Graduated syringe | Tank; volume read visually in mL | Graduated; volume readable by eye | Confirmed (D02) | Capacity C, graduation interval, reading uncertainty, orientation and mounting, which end is open, positions of inlet and outlet connections, dead volume (U01–U05) |
| C2 | Intake peristaltic pump | Adds water to the syringe | Peristaltic; wired to the driver; has run | Confirmed (D02, D18) | Model, supply voltage, driver channel, flow at the fixed speed (U07–U09) |
| C3 | Outtake peristaltic pump | Removes water from the syringe | Peristaltic; wired to the driver; has run | Confirmed (D02, D18) | As C2 (U07–U09) |
| C4 | Tubing | Connects source → C2 → C1 and C1 → C3 → destination | Implied by the pump roles | Assumed (routing not documented) | Lengths, inner diameter, routing, whether tubes stay primed between runs (U10, U11) |
| C5 | Water source for intake | Supplies water | Must exist for the intake to work | Assumed | Container, level, open or closed (U12) |
| C6 | Water destination for outtake | Receives removed water | Must exist for the outtake to work | Assumed | Container; whether it is the same as C5 (closed loop) (U12) |
| C7 | Water-level sensor | Discrete threshold indication at one level | Installed at the syringe; not wired | Confirmed (D02, D19) | Type, output kind, supply, mounting height, level as volume V_sensor, polarity, hysteresis, response time, any indicator visible to the researcher (U13–U19) |
| C8 | Motor driver | Powers the pumps from PWM and direction inputs | Both pumps wired to it; library `DF4MotorDriver` defines four PWM/DIR channel pairs | Confirmed (D18); channel count derived from code | Manufacturer and model, which pump is on which channel, power supply (U06, U20, U21) |
| C9 | ESP32 board | Runs the I/O firmware | ESP32 (D02); `platformio.ini` targets `adafruit_metro_esp32s2` | Board family Confirmed; model derived from code | Exact board model (U22) |
| C10 | Firmware | Serial command server; timed pump steps | StepExample with one identifier change A → B (D32) | Confirmed (D32); behaviour derived from code | Exact location of the change; toolchain and core version (U23, U24) |
| C11 | Host PC and serial link | Runs the controller (D21), adapter and logs | StepExample host script uses USB serial at 115200 baud via PyCmdMessenger | Controller location Approved (D21); link settings derived from code | Operating system, Python version, cable/port (U25) |
| C12 | Power supply for driver and pumps | Electrical energy for the pumps | Must exist | Assumed | Type, voltage, current limit (U21) |
| C13 | Safe-limit mark | Visual maximum on the syringe, below capacity | Required by D24 | Planned | Position and value (U26) |

The ESP32's logic supply and the USB connection are not modelled; they are listed only through C9 and C11.

## 4. System boundary

**Inside the physical system under study:** the water in the syringe (C1), the water delivered by the intake (C2 with its tubing) and removed by the outtake (C3 with its tubing), and the sensor's response to the water level (C7). This is the part the simulation models represent (WP02 refines this).

**Inside the rig but treated as I/O path, not as physics:** motor driver (C8), ESP32 firmware (C10), serial link (C11). Their effect on the study is timing (command and report latency, D21) and the safety cut-off (D27); their internals are not modelled.

**Outside the boundary:** water source and destination (C5, C6), power supply (C12), host PC hardware, the researcher, and the environment (room temperature, evaporation). Assumed to be stable during a run; source level effects on flow are not modelled unless WP04 data require it (D24).

The physical mechanism shared by both models is conservation of water volume in the syringe: the change in volume over an interval equals water delivered by the intake minus water removed by the outtake, minus any loss (Confirmed principle, master context). Leakage and evaporation are assumed negligible (Assumed; check visually for leaks, U27).

## 5. Physical states and variables

Symbols follow `context/master_context.md`.

| Quantity | Symbol | Physical meaning | Who can know it on the rig |
|---|---|---|---|
| Tank volume | V | Water in the syringe (mL) | Researcher, by settled visual reading only |
| Capacity | C | Volume at which the syringe overflows (mL, TBD) | Researcher (from syringe markings) |
| Safe limit | — | Marked volume below C used as the rig's overflow criterion (D24; TBD) | Researcher |
| Sensor level | V_sensor | Volume at which the sensor switches (mL, TBD) | Researcher (WP04 measurement) |
| Sensor state | S | Wet/dry at the sensor position | Planned to be reported by firmware; controller receives the normalized value (wet = True, D29) |
| Commanded pump state | u_in, u_out | ON/OFF as commanded | Host logs; firmware state record |
| Actual pump running | — | Whether the rotor actually turns | Researcher (by sight or sound); not measured electronically |
| Water delivered / removed | V_in, V_out | Water entering/leaving in an interval (mL) | Researcher, as difference of settled readings |
| Tubing fill state | — | Whether intake/outtake tubes are full of water (priming, D24 candidate) | Researcher, by sight if tubing is transparent (TBD, U11) |
| Time | t | Host clock for the controller and logs; ESP32 `millis()` for step timing | Host logs; firmware internal |

Commanded state is not a measured actuator state. In StepExample the reported pump state (`kGetStateResult`) is the record of the last command written to the pump object, not a reading from the driver (derived from code: `src/main.cpp`, `receiveStep()` copies the step fields into `pumpA`).

Two clocks exist on the rig: the host clock (controller, logs) and the ESP32 millisecond counter that ends each step. Their offset is not known to the host except through message timing (relevant to D21 latency, WP04).

## 6. Inputs, outputs and observations

### 6.1 Controller-accessible signals (D21, D29)

| Direction | Signal | Rig status |
|---|---|---|
| In | Current time (from the harness) | Available on host |
| In | Normalized sensor value (wet = True) | **Not available yet**: sensor not wired (D19) and StepExample reads no sensor; planned in WP09a |
| Out | Intake ON/OFF | Possible through `kStep` today, one pump per build (see 6.4) |
| Out | Outtake ON/OFF | As above |

The controller has no access to volume, flow, or pump speed and direction (D03, D07, D20).

### 6.2 Researcher observations

- Settled syringe readings before and after a run, and at intermediate points where the protocol allows (D24). Reading uncertainty TBD (U03).
- Host-side logs of commands, firmware replies and timestamps (planned; StepExample's host script logs to the console only).
- Visual or audible confirmation that a pump runs; whether the sensor has an indicator light is TBD (U19).

### 6.3 Simulation-only quantities

Modelled volume, transferred volume per step and boundary events (e.g. computed overflow) exist only in the models and go to the logger/evaluator, never to the controller (D07).

### 6.4 Firmware command interface as bundled (derived from code)

Serial over USB, 115200 baud, CmdMessenger framing (field separator `,`, command separator `;`, escape `/`) (`src/main.cpp`, `src/driver.py`).

| Command | Direction | Payload | Behaviour |
|---|---|---|---|
| `kStep` | host → ESP32 | `bool stateA, uint16 speedA, bool dirA, unsigned long time` (ms) | If no step is running: sets pump A ON (speed, direction) or OFF, starts a timer of `time` ms, replies `kAcknowledge "Step"`. If a step is running: replies `kError "Busy"` and changes nothing |
| `kStepDone` | ESP32 → host | none | Sent when the step time expires; at that moment **all** pumps are stopped (`stopPumps()`) |
| `kStop` | host → ESP32 | none | Stops all pumps immediately, ends the step, replies `kAcknowledge "Stopped"` |
| `kGetState` | host → ESP32 | none | Replies `kGetStateResult`: pump A record (state, speed, dir) |
| `kGetLastStep` | host → ESP32 | none | Replies `kGetLastStepResult`: step running, done, time, and pump A fields |
| `kWatchdog` | host → ESP32 | none | Replies with the device identifier string |
| — | ESP32 → host at start-up | — | `kAcknowledge "Arduino has started!"` |

Behaviour that matters for the study (derived from code):

- **Self-expiring ON.** Every ON command carries a duration; the firmware stops the pumps when it expires, even if the host is silent or disconnected. The limit is chosen by the host per command, so it is not yet the host-independent maximum ON time required by D27 (planned in WP09a).
- **One pump per build.** Only pump A is driven by `kStep`; the rig change (D32) made the second pump run instead. Where exactly the identifier was changed is unknown (U23). As a consequence one build drives only one pump, the state report may still be labelled "A" whichever channel is driven, and there is no command to switch the two pumps independently. WP09a must drive both from one firmware (D32).
- **No independent OFF during a step.** A new `kStep` (including an OFF step) is rejected while a step runs; only `kStop` ends it early, and it stops all pumps. An OFF step also occupies the timer for its duration.
- **No sensor input.** StepExample reads no sensor and has no command to report one (planned in WP09a, D21).
- **Start-up state.** `setupPumps()` configures the PWM and direction pins as outputs and writes nothing; pumps are expected to be off after `setup()` (Assumed from code). The pin levels between reset and `setup()`, and whether opening the serial port resets the board, are TBD (U28). Relevant to power-on safety (WP06, WP09a).

### 6.5 Pin and channel assignments (derived from code, to be checked on the rig)

From `lib/DF4MotorDriver/df4MotorDriver.h` and `df4MotorDriver.cpp`. Numbers are the pin numbers used in code (on ESP32 Arduino cores these are GPIO numbers); the board's header labels for them are to be checked.

| Driver channel | PWM pin | DIR pin | Code function | Rig pump |
|---|---|---|---|---|
| 1 | 8 | 9 | `StartPumpA` / `StopPumpA` | TBD (U20) |
| 2 | 16 | 21 | `StartPumpB` / `StopPumpB` | TBD (U20) |
| 3 | 10 | 13 | `StartPumpC` / `StopPumpC` | Not used (assumed) |
| 4 | 11 | 12 | none (pins only configured) | Not used (assumed) |

Sensor pin: none in code; TBD (U15).

### 6.6 Speed and direction (D20, D32)

Each pump runs at one fixed speed and direction for the whole study (Approved, D20). The values actually used so far are probably those of the unmodified host script `src/driver.py` (Derived from code, assuming that script was used, D32):

| Parameter | Value in host script | Notes |
|---|---|---|
| Speed | `speedA = 4096` | PWM resolution set to 12 bits (`analogWriteResolution(12)`), nominal range 0–4095. `map(speed, 0, 4096, 0, 4096)` leaves the value unchanged. How the ESP32 Arduino core treats 4096 (one above the nominal maximum) depends on the core version, which `platformio.ini` does not pin (U24); intended as full speed, to be checked |
| Direction | `dirA = True` | Writes the DIR pin high. Which physical flow direction this gives depends on wiring; it must move water into the syringe for the intake and out of it for the outtake (check on rig) |
| Step duration | `stepTime = 50000` ms | Example value in `main()`; `set_state()` default is also 50000 ms with speed 0 |
| PWM frequency | not set in code | Core default; TBD (U24) |

Stopping a pump sets its PWM to 0 and leaves the direction pin unchanged (derived from code).

## 7. Constraints

### 7.1 Actuators

- ON/OFF only for the controller; speed and direction fixed (D03, D20). Speed is a plant parameter, not a controller decision.
- No flow measurement (D03). Flow at the fixed speed is obtained only from timed runs and settled readings (WP04).
- A stopped peristaltic pump is expected to block flow through its tube, so no water should pass while it is OFF (Assumed general property of peristaltic pumps; check for siphoning on the rig, U27).
- Delays between command and water arriving (tube priming) and water still arriving after OFF (run-on) are candidate effects for Model 2 (D24), not assumed values.

### 7.2 Sensor

- Boolean at one level; no continuous volume (D03).
- Not wired (D19); everything else (type, output, threshold, polarity, hysteresis, response time) TBD. If the sensor gives an analog output, the switching threshold becomes a firmware setting that must be fixed and recorded (U14).
- The controller receives a normalized value (wet = True); normalization is the adapter's job (D29).

### 7.3 Operation and safety

- Overflow must never be caused on the rig. On the rig, "overflow" means a settled level above the safe-limit mark (D24); real overflow is only computed in the models.
- An independent firmware maximum ON time, sized so that starting level + intake rate × maximum time stays below capacity, is planned (D27; value from WP04 calibration, conservative before then).
- Water and electronics share the rig; the location of the board and driver relative to possible spills is TBD (U29).
- The controller under test only fills; emptying between runs is done by the researcher or a fixed reset procedure (D26).
- Every physical run needs researcher approval (AGENTS.md, D27).
- The outtake running with an empty syringe, and either pump running dry, have not been characterised; avoid until checked (U30).

## 8. Gaps between the rig baseline and the approved design

These are facts about StepExample relative to approved decisions. They are inputs for WP09a/WP07, not design choices.

| Needed by | Gap in StepExample |
|---|---|
| D21, D29 | No sensor reading or report |
| D18, D21 | One pump per build; no independent ON/OFF per pump |
| D27 | ON time limited per command by the host, not by a fixed firmware maximum; cut-off not logged as such |
| D21 | No host-side log file of commands, replies and timestamps |
| D20 | Speed and direction sent by the host with every step; must be fixed values, not controller outputs |

## 9. Unknowns register

"Rig check" = visual inspection or reading of markings, no powered run. "WP04" = needs a researcher-approved measurement.

| ID | Unknown | Why it matters | Resolved by |
|---|---|---|---|
| U01 | Syringe nominal capacity C | Safety limit, cut-off sizing (D27) | Rig check |
| U02 | Graduation interval | Reading resolution; D24 inclusion rule | Rig check |
| U03 | Reading uncertainty of a settled level | Tolerances, D24, D27 | WP04 |
| U04 | Syringe orientation, open end, plunger fixed or not | Where the level is read; whether capacity is fixed | Rig check |
| U05 | Positions of inlet/outlet connections; dead volume the outtake cannot remove | Reset procedure; lower limit | Rig check |
| U06 | Motor driver manufacturer and model | Electrical limits; documentation | Rig check |
| U07 | Pump models and rated voltage | Flow range; safe operation | Rig check |
| U08 | Intake and outtake flow at the fixed speed | Calibration for FR09 and models | WP04 |
| U09 | Run-to-run variability of delivered volume | Tolerances, D27 consistency rule | WP04 |
| U10 | Tubing lengths, inner diameter, routing, transparency | Priming volume (D24 candidate) | Rig check |
| U11 | Whether tubes stay primed between runs | Priming effect, initial conditions | Rig check, then WP04 |
| U12 | Water source and destination; same container or not | Initial conditions; stable supply | Rig check |
| U13 | Sensor type and model | Behaviour, wiring | Rig check |
| U14 | Sensor output kind (digital or analog) and supply voltage | Wiring; whether a threshold is set in firmware | Rig check |
| U15 | Sensor pin on the ESP32 | Firmware (WP09a) | After wiring (D19) |
| U16 | Sensor mounting height; level as volume V_sensor | FR03, FR09 | Rig check (height), WP04 (volume) |
| U17 | Sensor electrical polarity | Adapter normalization (D29) | After wiring, WP09a |
| U18 | Sensor hysteresis and response time | D24 candidate effect | WP04 |
| U19 | Visible sensor indicator (e.g. a light) | Researcher observation of the sensor | Rig check |
| U20 | Which pump is on driver channel 1 and which on channel 2 | Correct actuator mapping | Rig check (trace wires) |
| U21 | Pump/driver power supply and its limits | Electrical safety | Rig check |
| U22 | Exact ESP32 board model | Pins, upload target | Rig check |
| U23 | Exact location of the A → B change in the rig firmware | Which channel the current build drives | Researcher memory, or WP09a replaces it |
| U24 | Toolchain and ESP32 Arduino core version; PWM frequency; handling of speed 4096 | Reproducibility; actual pump speed | WP09a (pin versions) |
| U25 | Host operating system, Python version, serial port | Reproducibility; latency | Rig check |
| U26 | Position and value of the safe-limit mark | Overflow criterion on the rig (D24) | Researcher marks it; recorded before WP04 runs |
| U27 | Leaks, evaporation, siphoning with pumps OFF | Validity of the conservation assumption | Rig check, then WP04 |
| U28 | Pin levels between reset and `setup()`; reset on serial port opening | Power-on safety | WP09a (check), WP06 |
| U29 | Location of electronics relative to possible spills | Electrical safety | Rig check |
| U30 | Effects of running a pump dry or the outtake on an empty syringe | Safe operating limits | Pump documentation (U07); avoid until known |
| U31 | Host–ESP32 command and report latency | Rig response timing (D21) | WP04 |

## 10. Rig checklist for the researcher

Visual checks only; no powered run is needed. Results go into this file (replace TBD) and, where a decision is affected, into `context/decisions.md`.

1. Board: read the model printed on the ESP32 board (U22). Confirm the driver's PWM/DIR wires go to the pins in section 6.5 (U20, U22).
2. Driver: read the manufacturer and model (U06); note its power supply (U21).
3. Pumps: trace which pump (intake/outtake) is on driver channel 1 and which on channel 2 (U20); read pump model and voltage if marked (U07).
4. Syringe: capacity, graduation interval, orientation, where the tubes connect (U01, U02, U04, U05).
5. Tubing and water: lengths, diameter if known, transparency, source and destination containers (U10, U12).
6. Sensor: type, number of wires, height on the syringe in mL, any indicator light (U13, U14, U16, U19).
7. Safety: location of electronics relative to water; any visible leak (U27, U29). Choose and mark the safe-limit level (U26).
8. Firmware: if remembered, where the A → B change was made (U23).

## 11. Wording of D05 (proposed D33)

D05 ("physical system is reference, simulated state logs initially sufficient") was flagged as ambiguous in the WP00 review. Proposed clarification, recorded as D33 (PROPOSED): the rig is the reference for validation and for controller verdicts (D25, D27); on the rig, volume is observed only as manual settled readings at discrete points, with no continuous volume log; continuous volume traces exist only in simulation logs and go to the logger/evaluator, never to the controller (D07); no extra volume instrumentation is added to the rig unless a later decision requires it.

## 12. Placeholder values (D34)

At the researcher's request (2026-11-25), the unknowns needed by later design and simulation work get **placeholder values** so that work can proceed before the rig check and WP04. Rules (D34):

- A placeholder is **not** a measurement or a hardware fact. It is a round number chosen by the agent to be plausible for a small syringe rig, or taken from a researcher example where noted.
- Placeholders may be used in design documents, simulation code and tests of the software itself. Anything produced with them is labelled provisional.
- Placeholders are **never** used for a physical run, a firmware safety limit uploaded to the board, or a reported result.
- Each placeholder is replaced by the rig check or by WP04 measurement; the "Replaced by" column says which. Code and documents refer to the ID (P01…) so that every use can be found and updated.

| ID | Quantity | Placeholder | Unit | Basis of the placeholder | Replaces | Replaced by |
|---|---|---|---|---|---|---|
| P01 | Syringe capacity C | 60 | mL | Common large syringe size | U01 | Rig check |
| P02 | Graduation interval | 1 | mL | Typical for that size | U02 | Rig check |
| P03 | Reading uncertainty (settled level) | ±0.5 | mL | Half a graduation | U03 | WP04 |
| P04 | Safe-limit mark | 50 | mL | About 83 % of P01, leaving headroom | U26 | Researcher marks it |
| P05 | Sensor level V_sensor | 24 | mL | 40 % of P01, from the researcher's "sensor at 40 %" example (D26) | U16 | Rig check (height), WP04 (volume) |
| P06 | Intake flow at fixed speed Q_in | 1.0 | mL/s | Round value | U08 | WP04 |
| P07 | Outtake flow at fixed speed Q_out | 1.0 | mL/s | Round value | U08 | WP04 |
| P08 | Run-to-run spread of delivered volume | ±0.5 | mL | Same as P03 | U09 | WP04 |
| P09 | Dead volume the outtake cannot remove | 0 | mL | Ignored until known | U05 | Rig check |
| P10 | Standard starting volume | 5 | mL | Well below P05 | — | WP08 |
| P11 | Firmware maximum ON time (simulation only) | 45 | s | (P04 − P10) / P06, per the D27 rule, using the safe mark instead of capacity for extra margin | — | WP04 calibration (D27) |
| P12 | Tube priming delay (Model 2 candidate) | 2 | s | Round value | U10, U11 | WP04 (D24 inclusion rule) |
| P13 | Run-on volume after OFF (Model 2 candidate) | 0.5 | mL | Round value | — | WP04 (D24) |
| P14 | Sensor response delay (Model 2 candidate) | 0.1 | s | Round value | U18 | WP04 (D24) |
| P15 | Host–ESP32 command or report latency, each way | 0.02 | s | Round value; expected negligible (D24) | U31 | WP04 |
| P16 | Host log timestamp resolution | 0.001 | s | Millisecond timestamps | — | WP09a |
| P17 | Pump on driver channel 1 / channel 2 | intake / outtake | — | Arbitrary; channel 1 is StepExample's pump A | U20 | Rig check |
| P18 | Sensor output kind and polarity | digital; logic HIGH = wet | — | Arbitrary; hidden from the controller by normalization (D29) | U14, U17 | Rig check, WP09a |
| P19 | Pump speed and direction | 4095 (full scale, 12-bit); DIR high | — | Host-script values (D32), clipped to the nominal 12-bit maximum | U24 | Rig check, WP09a |

Not given placeholders (stay TBD because nothing downstream needs a number yet): U04, U06, U07, U12, U13, U15, U19, U21–U23, U25, U27–U30.
