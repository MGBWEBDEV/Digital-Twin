# Functional requirements for the water-tank controller test suite

> **Status: Provisional WP03 draft (D23).** Drafted with ChatGPT before WP01; adopted by the researcher as the WP03 starting point on 2026-11-25. The FR numbering in this file is authoritative. Still to be reduced to a small subset, aligned with WP01/WP02 and reviewed before approval. All numerical values remain TBD.

The suite evaluates AI-generated controller code (host-side Python driving the ESP32 rig; see D21) against the same behavioral specification on two simulation models. The generation prompt describes the task, hardware interface and applicable limits. The suite defines expected behavior before generation. A controller can pass every scenario. Each failure needs evidence linking the observed behavior to a requirement.

## Hardware and observations

- The graduated syringe serves as the tank. Read its markings to measure volume on the rig. In simulation, record the model's tank volume and identify it as simulated.
- The controller commands two peristaltic pumps independently through the ESP32. The intake adds water and the outtake removes it. Each accepts ON and OFF commands; speed and direction are fixed per pump (proposed D20). The controller has no direct flow reading.
- The level sensor supplies one Boolean input. It is installed but not yet wired (D19). Active means the water has reached the sensor level. Electrical polarity, pin assignments and switching levels on filling and draining are TBD. Sensor deactivation indicates a threshold crossing and can occur while water remains in the syringe.
- For a volume-target task, establish the duration-to-volume relationship separately for each pump using timed runs and syringe readings. Calibration data and valid operating ranges are TBD. Keep measured or simulated volume available to the test observer only.

## Tasks and acceptance criteria

Start each scenario with recorded volume, sensor state and both pumps OFF. A logical check uses the input seen by the controller and its timestamped output commands. A physical check uses independent water-volume observations. Apply FR08 throughout every task.

| ID | Controller task | Logical acceptance | Physical acceptance |
|---|---|---|---|
| FR01 | Fill for a specified time | Only intake turns ON. Its ON interval matches the requested duration within the timing tolerance, then it stays OFF. | End volume exceeds start volume by a measurable amount. |
| FR02 | Drain for a specified time | Only outtake turns ON. Its ON interval matches the requested duration within the timing tolerance, then it stays OFF. | End volume is measurably below start volume. |
| FR03 | Fill until the sensor is active | If initially active, issue no ON command. Otherwise run only intake and switch it OFF within the response limit after activation. | Starting below the level, water reaches the calibrated activation range and stays within the safe maximum. With the target already met, volume stays within measurement tolerance of its initial value. |
| FR04 | Drain until the sensor is inactive | If initially inactive, issue no ON command. Otherwise run only outtake and switch it OFF within the response limit after deactivation. | Starting above the level, water falls through the calibrated deactivation range. With the target already met, volume stays within measurement tolerance of its initial value. |
| FR05 | Add and then remove a specified volume | Command intake followed by outtake. Stop each pump before starting the next phase. | Read volume before transfer, between phases and after transfer. For each leg, the absolute difference between the measured transfer and its target must be within volume tolerance. |
| FR06 | Fill, wait, then drain | Execute the three phases in order. Both pumps stay OFF throughout the specified wait, whose duration must meet timing tolerance. | Volume rises, remains stable within measurement tolerance during the wait, then falls. |
| FR07 | Repeat a fill-and-drain cycle | Complete exactly the requested cycle count, in order. After the final cycle both pumps stay OFF until a new request. | Check the specified fill and drain outcomes separately in every cycle. |
| FR08 | Bound pump operation and prevent overflow | Only the pump required by the current phase may run. If the expected sensor transition never arrives, stop by the safety deadline and end the operation without starting the next phase. | Water stays at or below the safe maximum throughout the run. Check peak volume, including water delivered after an OFF command. |

## Test scenarios

| Scenario | Setup and stimulus | Checks to score |
|---|---|---|
| Timed actuation | From a volume with enough headroom and water, run separate timed fill and drain requests. | FR01, FR02, FR08. Compare ON intervals with requested times and record signed volume changes. |
| Threshold crossing | Start below the activation level for filling and above the deactivation level for draining. Let the water cross the sensor naturally. | FR03, FR04, FR08. Record the sensor edge, OFF command, volume at crossing and final volume. |
| Target already met | Request filling with the sensor active. Separately request draining with it inactive. | FR03, FR04. Check the entire command trace for even a brief ON pulse and compare initial and final volume. |
| Missing transition | In simulation hold the sensor inactive during filling, then active during a separate draining run. | FR08. Score shutdown timing and peak volume independently. An on-time shutdown can still permit overflow. |
| Close to maximum | Start just below the sensor activation level with limited headroom. Use a physically consistent starting state. | FR03, FR08. Check response delay and peak volume during and after shutdown. |
| Volume transfer | Choose feasible addition and removal targets. Record volume at all three phase boundaries. | FR05, FR08. Equal errors in addition and removal can cancel in the final reading. |
| Ordered sequence | Request fill, a specified wait and drain. | FR06, FR08. Check phase order, wait duration and volume during each phase. |
| Cycle count | Run once with a single cycle, then with a specified count greater than one. | FR07, FR08. Count completed pump pairs and check each cycle's volume changes and final shutdown. |

## Parameters and verdicts

Record the following before scoring dependent checks. All unconfirmed values are **TBD**.

| Parameter group | Values to establish |
|---|---|
| Tank and sensing | Capacity, safe maximum, syringe graduation and reading uncertainty, activation and deactivation ranges |
| Task inputs | Starting volumes, pump durations, volume targets, wait duration, repeat count and observation period after completion |
| Timing and measurement | Safety timeout, maximum response delay (on the rig including host–ESP32 serial latency), timing and volume tolerances, observation frequency and means of capturing peak volume on the rig |
| Simulation | Model versions, per-pump calibration, assumptions and confirmed differences in fidelity |

For each run, retain the prompt and controller version, model or rig identifier, scenario parameters, timestamped sensor inputs and pump commands, volume observations with units, and termination reason. Compare the same controller and scenarios across both models with the same acceptance criteria. Record each model's actual sensor transition time so its controller response delay can be evaluated independently.

Score each logical and physical check as pass, fail or undetermined. Use undetermined when a required value is TBD or observation resolution cannot establish the result. A scenario passes only when all applicable checks pass. Any failed check makes the scenario fail. Preserve other undetermined checks in the report.

## Mapping a failure to controller logic

For each failure, record the requirement ID, triggering input, expected command, observed command and measured consequence. For example, an intake ON pulse when the sensor was already active violates FR03 even if the syringe shows no measurable change. Inspect the generated code for the start-condition check and confirm the suspected cause by replaying the same input. If the controller stopped within the response limit but the volume exceeded the maximum, record a physical FR08 failure and investigate delivered volume, stopping delay and available headroom. Keep the cause open until the evidence identifies it.
