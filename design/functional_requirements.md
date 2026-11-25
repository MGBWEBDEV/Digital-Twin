# Functional requirements for the water-tank controller test suite

> **Status: Provisional WP03 draft (D23, D26).** Drafted with ChatGPT before WP01; adopted by the researcher as the WP03 starting point on 2026-11-25. The FR numbering in this file is authoritative. Selected set (D26): FR01, FR03, FR09 and FR08; FR02 and FR04–FR07 are deferred (see the end of this file). Still to be aligned with WP01/WP02 and reviewed before approval. All numerical values remain TBD.

The suite evaluates AI-generated controller code (host-side Python driving the ESP32 rig; see D21) against the same behavioral specification on two simulation models. The generation prompt describes the task, hardware interface and applicable limits. The suite defines expected behavior before generation. A controller can pass every scenario. Each failure needs evidence linking the observed behavior to a requirement.

## Hardware and observations

- The graduated syringe serves as the tank. Read its markings to measure volume on the rig, after the water has settled (D24). In simulation, record the model's tank volume and identify it as simulated.
- The controller commands two peristaltic pumps independently through the ESP32. The intake adds water and the outtake removes it. Each accepts ON and OFF commands; speed and direction are fixed per pump (D20). The controller has no direct flow reading. In the selected set the controller only fills; emptying between runs is done by the researcher or a fixed reset procedure that is not under test (D26).
- The level sensor supplies one Boolean input. It is installed but not yet wired (D19). Active means the water has reached the sensor level. Electrical polarity, pin assignments and switching levels are TBD. Sensor deactivation indicates a threshold crossing and can occur while water remains in the syringe.
- A safe-limit mark below the physical capacity defines the safe maximum on the rig. On the rig, exceeding it is judged visually from the settled level; real overflow is only computed in the models (D24).
- For FR09, establish the duration-to-volume relationship of the intake using timed runs and syringe readings (WP04). Calibration data and valid operating ranges are TBD. Keep measured or simulated volume available to the test observer only.

## Tasks and acceptance criteria

Start each scenario with recorded volume, sensor state and both pumps OFF. A logical check uses the input seen by the controller and its timestamped output commands. A physical check uses independent water-volume observations. Apply FR08 throughout every task.

| ID | Controller task | Logical acceptance | Physical acceptance |
|---|---|---|---|
| FR01 | Fill for a specified time | Only intake turns ON. Its ON interval matches the requested duration within the timing tolerance, then it stays OFF. | End volume exceeds start volume by a measurable amount. |
| FR03 | Fill until the sensor is active | If initially active, issue no ON command. Otherwise run only intake and switch it OFF within the response limit after activation. | Starting below the level, water reaches the calibrated activation range and stays within the safe maximum. With the target already met, volume stays within measurement tolerance of its initial value. |
| FR09 | Fill to a specified target volume above the sensor level, using the sensor as reference (provisional, added by D26) | Known to the controller: sensor level and intake calibration. If the sensor is initially active the level is unknown, so issue no ON command and end the operation reporting that the precondition failed. Otherwise run only intake; after activation, the additional ON duration corresponds to the remaining volume to the target within the timing tolerance; then intake stays OFF. | Settled end volume is within volume tolerance of the target and at or below the safe maximum. |
| FR08 | Bound pump operation and prevent overflow | Only the pump required by the current phase may run. If the expected sensor transition never arrives, stop by the safety deadline and end the operation without starting the next phase. | Water stays at or below the safe maximum throughout the run. Check peak volume, including water delivered after an OFF command. |

## Test scenarios

| Scenario | Setup and stimulus | Checks to score |
|---|---|---|
| Timed fill | From a volume with enough headroom, run a timed fill request. | FR01, FR08. Compare the ON interval with the requested time and record the signed volume change. |
| Threshold crossing | Start below the activation level. Let the water cross the sensor naturally. | FR03, FR08. Record the sensor edge, OFF command, settled volume and margin to the safe mark. |
| Target already met | Request FR03 filling, and separately FR09 filling, with the sensor already active. | FR03, FR09. Check the entire command trace for even a brief ON pulse and compare initial and final volume. |
| Missing transition | In simulation hold the sensor inactive during filling. On the rig, disconnect the sensor and start low enough that the safety deadline stops the intake below the safe mark (researcher approval required). | FR08. Score shutdown timing and peak volume independently. An on-time shutdown can still permit overflow. |
| Target at varied margins | Run FR09 with several targets, from far below to close to the safe mark. Use the same starting state for each. | FR09, FR08. Record settled volume and margin to the safe mark for each target; this provides the margin analysis of D25. |

## Parameters and verdicts

Record the following before scoring dependent checks. All unconfirmed values are **TBD**.

| Parameter group | Values to establish |
|---|---|
| Tank and sensing | Capacity, safe-limit mark, syringe graduation and reading uncertainty, activation range |
| Task inputs | Starting volumes, pump durations, FR09 target volumes and their margins to the safe mark, observation period after completion |
| Safety net (D27) | Firmware maximum ON time per pump, derived from intake calibration and syringe capacity; identical in both simulation adapters. A cut-off is scored as an FR08 failure |
| Timing and measurement | Safety timeout, maximum response delay (on the rig including host–ESP32 serial latency), timing and volume tolerances, settling time before visual readings |
| Simulation | Model versions, intake calibration, included and excluded Model 2 effects (D24), assumptions |

For each run, retain the prompt and controller version, model or rig identifier, scenario parameters, timestamped sensor inputs and pump commands, volume observations with units, and termination reason. Compare the same controller and scenarios across both models with the same acceptance criteria. Record each model's actual sensor transition time so its controller response delay can be evaluated independently.

Score each logical and physical check as pass, fail or undetermined. Use undetermined when a required value is TBD or observation resolution cannot establish the result. A scenario passes only when all applicable checks pass. Any failed check makes the scenario fail. Preserve other undetermined checks in the report.

## Mapping a failure to controller logic

For each failure, record the requirement ID, triggering input, expected command, observed command and measured consequence. For example, an intake ON pulse when the sensor was already active violates FR03 even if the syringe shows no measurable change. Inspect the generated code for the start-condition check and confirm the suspected cause by replaying the same input. If the controller stopped within the response limit but the volume exceeded the maximum, record a physical FR08 failure and investigate delivered volume, stopping delay and available headroom. Keep the cause open until the evidence identifies it.

## Deferred requirements (D26)

Not part of the selected set. Kept for reference; FR07 is the first reserve if time allows. IDs are not reused.

| ID | Controller task | Logical acceptance | Physical acceptance | Reason deferred |
|---|---|---|---|---|
| FR02 | Drain for a specified time | Only outtake turns ON. Its ON interval matches the requested duration within the timing tolerance, then it stays OFF. | End volume is measurably below start volume. | Mirror of FR01 |
| FR04 | Drain until the sensor is inactive | If initially inactive, issue no ON command. Otherwise run only outtake and switch it OFF within the response limit after deactivation. | Starting above the level, water falls through the calibrated deactivation range. With the target already met, volume stays within measurement tolerance of its initial value. | Only task where the sensor switch-off level matters; dropping it simplifies Model 2 |
| FR05 | Add and then remove a specified volume | Command intake followed by outtake. Stop each pump before starting the next phase. | Read volume before transfer, between phases and after transfer. For each leg, the absolute difference between the measured transfer and its target must be within volume tolerance. | Covered more cleanly by FR09 |
| FR06 | Fill, wait, then drain | Execute the three phases in order. Both pumps stay OFF throughout the specified wait, whose duration must meet timing tolerance. | Volume rises, remains stable within measurement tolerance during the wait, then falls. | Sequence logic only; models necessarily agree |
| FR07 | Repeat a fill-and-drain cycle | Complete exactly the requested cycle count, in order. After the final cycle both pumps stay OFF until a new request. | Check the specified fill and drain outcomes separately in every cycle. | Sequence logic only; first reserve because it tends to provoke typical AI faults (cycle miscounting) |

Deferred scenarios: timed drain, threshold crossing while draining, target already met for draining, missing transition while draining, close to maximum (replaced by "target at varied margins"), volume transfer, ordered sequence, cycle count.
