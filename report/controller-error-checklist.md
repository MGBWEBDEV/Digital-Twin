# Water tank controller error checklist

Use one copy for each controller and test condition. Tick a box when you have reviewed the evidence. Write **pass**, **fail**, **undetermined** or **not applicable** beside each check. A tick means the review is complete.

**Reviewer** __________  **Date** __________  **Controller version** __________  
**Task and starting condition** __________  **Rig run ID** __________  
**Model 1 run ID** __________  **Model 2 run ID** __________

### 1. Confirm that the runs can be compared

- [ ] Verify that all three runs used the same controller file, requested task, timing rules and acceptance limits. Check that each model started at the measured rig volume, with the same tube condition and pump time limit.
- [ ] Record the approved timing tolerance ___ s, volume tolerance ___ mL and safe mark ___ mL. Label simulation verdicts provisional while any parameter is a placeholder. Physical runs require reviewed values and an approved session plan.
- [ ] Check the run record for setup errors, lost communication or a manual abort. Mark an invalid run and record the reason. Exclude it from scoring. A controller crash in an otherwise valid run counts as a failure.

### 2. Check what the controller commanded

Read the time-stamped sensor input and both pump commands together. Apply the rows for the requested task. Measure response time from the first wet reading **received by the controller**.

| Reviewed | Task or condition | What to check |
|---|---|---|
| ☐ | Timed fill (FR01) | The intake starts by the allowed start time, runs once and stays on for the requested duration within the timing tolerance. |
| ☐ | Fill until wet, initially dry (FR03) | The intake starts on time and runs once. When the sensor first reports wet, the controller switches the intake off within the response limit. |
| ☐ | Fill above the sensor, initially dry (FR09) | The intake starts on time and stays on when the sensor first reports wet. Calculate the extra pumping time by subtracting the sensor-level volume from the target volume and dividing by the calibrated intake rate. Compare that time with the interval from the wet reading to the OFF command. |
| ☐ | Sensor already wet at the start (FR03 or FR09) | Both pumps stay off throughout. Even a single ON command fails this check. |
| ☐ | Sensor stays dry (FR03 or FR09) | Once the sensor deadline expires, the controller switches the intake off within the allowed response time. |
| ☐ | Every run (FR08) | The outtake stays off. After the intake stops, neither pump restarts. If the independent safety timer stops a pump, record a safety failure even if the final level is safe. |

### 3. Check what happened to the water

- [ ] Record the settled start ___ mL and end ___ mL, with reading uncertainty ___ mL. For a timed fill, compare **end minus start** with the volume predicted by the pump calibration. For a fill until wet, compare the end level with the measured sensor level. For a fill to a target, compare it with the requested target. Apply the volume check for the scenario being scored.
- [ ] If the sensor was already wet and the pumps should have stayed off, check whether the change in volume stayed within the allowed tolerance.
- [ ] Check the final and peak levels against the safe mark. If the outtake stayed off throughout, the protocol allows the settled final reading to represent the peak. If the level could have fallen and the peak cannot be established, mark the peak check undetermined. In simulation, also inspect the overflow record.
- [ ] Record the distance to the deciding volume limit and to the safe mark. If a deciding physical reading lies within the protocol’s near-limit window, use five fully reset rig runs in total. If their verdicts differ, mark that check undetermined.

### 4. Trace a failure to its cause

- [ ] Identify the **first** violated requirement. Record its ID ___, the triggering input and time ___, the expected command or volume ___, and what was observed ___.
- [ ] Trace the command back to the controller file and line. Record how the triggering input reaches that line and what it does. If the stop command was timely but the settled volume was too high, inspect sensor reporting delay, water movement after switch-off and measurement uncertainty before attributing the excess to controller code.
- [ ] Record the supported cause or mark it unresolved. For a confirmed controller defect, record its origin as generated or deliberately injected. Label defects discovered during runs as found after selection. The study selects its two fault types from code review before running the candidate controllers.

### 5. Record what each model detected

- [ ] Assign a verdict to each valid run. Any failed applicable check makes the run fail. If none failed and an applicable check remains undecided, mark the run undetermined. Otherwise it passes.
- [ ] Compare each model with the rig using the table. Where both fail, record both failed requirement IDs so the reader can see whether they identified the same problem.

| Rig verdict | Model passes | Model fails |
|---|---|---|
| Pass | Agreement on pass | False alarm |
| Fail | Missed failure | Agreement on failure |

- [ ] List an undetermined rig verdict separately from detection counts. With a determined rig verdict and an undetermined model verdict, record *model inconclusive*. If a known faulty controller passes on the rig, record *fault not triggered* for that run.

**Model 1 comparison** __________  **Model 2 comparison** __________  
**Failed requirement IDs by environment** __________  
**Evidence location and unresolved questions** __________

Project references: [Functional requirements](../design/functional_requirements.md) · [Experimental protocol, sections 10–15](../experiments/experimental_protocol.md)
