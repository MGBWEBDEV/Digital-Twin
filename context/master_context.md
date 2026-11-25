# Master project context

## Research overview
**Title:** Digital Twin Simulations for Testing Controller Code Generated with AI.
**Academic context:** MSc Software Design research project, IT University of Copenhagen. Technical and methodological foundation for a later industrial water-tank/PLC thesis, not the thesis itself.
**Research question:** How accurate does a digital twin need to be in order to reliably detect errors or unintended behavior introduced by AI-generated control code?

Investigate the relationship between physical model fidelity, complexity, accuracy and behavioral error detection. We are not primarily measuring AI coding ability. Scope: one simplified ESP32 system, two simulation fidelity levels, a small set of requirements, two selected controller error types, reusable test framework. All modelling and coding will be AI-generated and researcher-reviewed. No industrial-scale validation or assumed results. Distinguish simulations from a fully connected digital twin (dynamic data exchange with its physical counterpart). Primary learning outcome: how to design a digital twin; embedded realism is secondary (D22).

## Physical system definition
Confirmed by researcher: ESP32 microcontroller; one intake and one outtake peristaltic pump; a discrete threshold water-level sensor; a graduated syringe as tank, allowing visually observed volume in mL. Pumps have ON/OFF control only, with timed operation; no variable speed or direct measured flow input. Sensor does not report continuous volume. Actual volume cannot be read directly by the controller; the researcher can observe syringe graduations. Do not assume exact sensor polarity, wiring or plumbing beyond the stated intake/outtake roles.

Rig status (2026-11-25, D18–D20): both pumps are wired to the driver used by the StepExample base firmware and have run; the modified firmware is not yet in the repository. The driver accepts PWM speed and direction; the study proposes one fixed speed and direction per pump so that control remains ON/OFF. The level sensor is installed but not wired.

Primary boundary: monitored syringe tank. Intake adds water and outtake removes water. The host controller issues pump commands and receives threshold feedback through the ESP32 (D21). Reservoirs, tubing and supporting components initially abstracted, subject to physical inspection. Water conservation is the relevant physical mechanism.

| Symbol | Meaning | Unit/type |
|---|---|---|
| V | Actual or simulated tank water volume | mL |
| C | Physical capacity | mL, TBD |
| V_sensor | Sensor threshold expressed as volume | mL, TBD |
| u_in, u_out | Commanded pump activation | Boolean 0/1 |
| S | Sensor indication | Boolean, normalized |
| t, Δt | Elapsed time, time interval | seconds |
| V_in, V_out | Actual water entering/leaving in interval | mL |
| Q_in, Q_out | Average transfer-rate parameters if used | mL/s, TBD |

Controller inputs: Boolean sensor state, clock/timers, task configuration and commands. Controller outputs: intake/outtake ON/OFF. Researcher observations: visual volume, timestamped sensor and command logs, pump durations. Simulator may expose volume and transfer to independent logger/evaluator, never directly to controller unless an equivalent physical interface exists. Commanded states are not independently measured actuator states; label them appropriately.

Unknowns: capacity, operational safety limits, sensor polarity and activation/deactivation thresholds, transfer versus duration, repeatability, measurement uncertainty, timing/response characteristics, wiring and relevant plumbing. No assumed numerical values. Direct flow measurement unavailable; if needed average flow can be estimated from manually measured volume change divided by elapsed time. Decide later from measurements, not beforehand.

## Modelling layers
- Physical model: real entities, relevant physical states, mechanisms, exclusions and constraints.
- Conceptual model: components, boundary, water movement, signals, inputs/outputs and relationships; implementation-independent.
- Mathematical model: equations, state updates, assumptions and parameters.
- Structural software model: classes, responsibilities, interfaces and relationships.
- Behavioral controller model: tasks, states, actions, transitions, timing and exceptions; implementation-independent specification, not generated code.
- Implementation: map physical equations to simulated classes, controller decisions to shared controller logic and evaluation rules to an independent test runner.

## Proof-of-concept mathematical foundation
Both models represent conservation of water volume over an interval:

`V(t+1) = V(t) + V_in − V_out` (discrete step index; volumes per step).

Model 1: basic volume-balance model; limited parameters, simplified water transfer, pump commands, Boolean sensor, time. Document its assumptions and how commands influence transfer.

Model 2: extended representation, candidate time-dependent formulation:

`V(t+Δt) = V(t) + (u_in Q_in − u_out Q_out) Δt`

For constant states/rates over the interval. If multiple pump changes occur, split the interval or integrate appropriately. Transfer rates may be estimated from experiments or replaced by calibrated duration-to-transfer relationships. Candidate extensions include distinct pump characteristics, measured sensor behavior or physical response timing; only adopt if justified. The exact fidelity difference is TBD; a fixed per-step amount and constant rate times step can be mathematically equivalent. More parameters do not guarantee improved accuracy/detection. Hold other factors constant.

Ideal normalized sensor candidate: `S = true` when `V >= V_sensor`, otherwise false; confirm physical behavior, hysteresis or timing if relevant. Both models expose the same controller-facing sensor interface. Distinguish physical capacity C from permitted operational limit. Do not silently clamp away overflow/underflow attempts; record relevant boundary events and account for actual water loss or unavailable transfer in mass balance. Avoid unsafe physical experiments.

## Software design
Same controller source should execute against the real ESP32 adapter and both simulated adapters. The controller is Python on the host PC; the ESP32 firmware is a serial I/O server for pumps and sensor (D21). Serial latency is part of rig timing and must be characterized. Candidate components (not mandated): Controller, WaterTank, Pump (two instances), WaterLevelSensor, HardwareInterface, Clock, Simulation, DataLogger, TestRunner, TestEvaluator. Controller issues commands; physics calculates state updates; evaluation checks independent requirements. Candidate mapping: tank update -> conservation; pump calculation -> transferred volume; sensor -> threshold; clock/simulation -> time updates. Document units, step size, event ordering, controller frequency and sensor timing. Simulated vs wall-clock time must be compatible at interface. Avoid unnecessary dependencies and GUI.

## Candidate functional requirements
Provisional WP03 draft: `design/functional_requirements.md` (D23); its numbering is authoritative. FR01 timed intake; FR02 timed outtake; FR03 fill until sensor activates; FR04 drain until sensor deactivates; FR05 add then remove a specified volume (return to initial) within tolerance, if feasible with available calibration and interface; FR06 fill/wait/drain sequence; FR07 repeat fill-and-drain cycle; FR08 safety/operational constraints, bounded execution and completion. Select a small subset. For each specify initial condition, task, expected actions, physical outcome, completion/timeout, tolerances, acceptance criteria. Requirements describe what to achieve; do not prescribe unnecessary algorithms. No direct actual-volume feedback to controller. Numerical thresholds and tolerances TBD; no unsafe test on hardware.

## Verification and validation
1. Mathematical verification: independently check simulation implementation against its stated equations; conservation, direction when transfer is feasible, no transfer with pumps off under no-leak assumptions, boundaries and sensor rule; use independent hand-calculated cases and account for losses. Passing proves mathematical consistency, not physical accuracy.
2. Physical validation: execute safe, equivalent reference actions on physical tank and both models, e.g., timed intake, read initial/final syringe volumes, record commands and sensor transitions. Separate calibration and held-out validation data; compare physical and simulated volumes at corresponding measurement points and sensor timing if observable. Repeat enough to establish variability; protocol and metrics TBD.
3. Controller logical checks: correct actions, order, conditions, durations, sensor response, termination.
4. Controller physical outcome checks: independent specification, e.g., `abs(V_final - V_target) <= epsilon`, maximum operational volume, expected direction, return to initial volume. Same oracles in both models; physical evidence is needed to establish actual failures. No circular validation with same AI-generated implementation/assumptions.

## Controller error methodology
Define functional specification and acceptance criteria before generation. Prompt AI for a correct implementation with interface, hardware limitations, task requirements and relevant known parameters. Document prompt, model/version if known, generated code, modifications and generation budget. Execute predefined scenarios, record behavior, map requirement violation to responsible controller logic through root-cause analysis. Distinguish defect (cause in code), failure (observed violation), detection (test outcome), diagnosis (root cause). Candidate faults: wrong condition/actuator, missing stop/timeout, inappropriate timing, wrong sequence, incorrect assumptions about physical behavior. Select two types only using predefined procedure; if no suitable natural faults within budget, use controlled isolated fault injection into validated reference controller. Document origin explicitly. Do not assume a fault occurs naturally or automatically maps to a physical failure. Keep a correct/reference implementation to test false alarms; run same code and scenario in both models with equivalent initial conditions, same timing policy and acceptance criteria. Physical evidence may come from safe characterization, bounded physical reference tests or another independently justified reference; no unsafe faulty controller runs. Classify as inconclusive if ground truth insufficient. An untriggered fault is not a missed error. Avoid choosing faults only because Model 2 detects them; predefine selection and evaluation, document exploratory vs confirmatory results.

## Logging and outcomes
Common logs: test/run ID, controller version, model/environment, timestamp (units), commands, sensor indication, operation status, relevant events. Simulation: modeled volume, transfer, boundary events, extended states. Physical: manually observed initial/final/intermediate volume if feasible, timestamps, reading uncertainty, conditions; separate manual and automatic logs. CSV/JSON adequate. Logger independent of controller where feasible. Raw data preserved; separate calibration and validation data.

Validation metrics candidates: absolute volume discrepancy `abs(V_physical - V_simulated)`, final volume discrepancy, sensor transition timing discrepancy, consistency of repeated observations. Final metrics/tolerances TBD. Controller outcomes based on independently established behavior: correct accepted (true negative), correct rejected (false alarm), incorrect rejected (detected), incorrect accepted (missed), insufficient evidence (inconclusive). Compare paired outcomes; no broad claims from two faults. Model 2 may improve accuracy without improving detection, detect additional failures, produce false alarms, or perform equivalently/worse. All are possible outcomes.

## AI and research traceability
All models/code AI-generated. Researcher specifies tasks, acceptance criteria, approves design/safety and checks implementation, collects physical evidence, interprets findings. Record relevant prompts, model/version, generated artifacts, revisions and validation; use Git for provenance. Approved files and measurements are authoritative; conflict with source draft must be flagged. No invented citations. Existing research draft/PoC should be added to references, and bibliographic details verified separately.

## Report integration
4.1 Physical and Conceptual Model; 4.2 Functional Requirements; 4.3 Software Architecture and Controller Behavior; 4.4 Mathematical Modelling and Implementation; 4.5 Model Verification and Physical Validation; 4.6 Controller Error Testing; 4.7 Results and Discussion. Preserve scope; do not duplicate PoC unnecessarily. Subsequent thesis is separate.
