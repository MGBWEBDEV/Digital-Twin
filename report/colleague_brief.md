# Can a simulated tank detect the same controller errors as a real tank?
**MSc Software Design research project · IT University of Copenhagen · 26 November 2026**

Consider a program that should stop a pump when water reaches a sensor. If the program stops the pump late, would testing it on a simulated tank reveal the problem? We will study that question on one ESP32-controlled tank, using two simulation models and two types of error in AI-generated controller code.

**Where we are now.** We have defined the controller requirements, built the basic simulation and implemented a common way to run tests and judge their outcomes. The basic model still uses provisional values. Both physical pumps have run previously. The level sensor still needs wiring and verification, and the new firmware has been compiled but has yet to run on the tank. Physical measurements and comparative results are still ahead.

## Your research guide

### Phase 1 · Prepare the comparison now

1. **Define what counts as a failure.** Write down the requirement you are checking and what observation would settle it. For a fill that should stop when the water reaches the sensor, the event log tells you when the controller requested a stop. The settled water level tells you how much water actually reached the tank. Keep both observations. A timely stop command can still leave too much water in the tank.

2. **Check the expected answers on paper.** The three calculations below use provisional numbers for checking the software. They are not measurements or settings for a physical run. Reproduce the arithmetic independently and record any disagreement before using these answers to assess the software.

   | Situation | How to work out what should happen |
   |---|---|
   | The controller leaves the pump on. The basic model assumes water enters the tank immediately. | Start with 5 mL. At 1 mL per second, the pump adds 48.5 mL before the independent timer stops it. The tank ends at **53.5 mL**. That exceeds the example’s 50 mL safe mark even though the timer worked. |
   | The controller requests a stop 24 seconds after it first sees the wet sensor. The inlet tube starts empty. | In the proposed model, the controller first sees “wet” at 21.2 seconds, so it requests a stop at 45.2 seconds. The pump starts moving water at 0.02 seconds and stops at 45.22 seconds, giving 45.2 seconds of flow. At 1 mL per second that moves 45.2 mL. Of that, 2 mL fills the tube, and another 0.5 mL reaches the tank after stopping. The tank ends at **5 + 45.2 − 2 + 0.5 = 48.7 mL**. The pump stopped before its timer expired. |
   | The controller again leaves the pump on, now with the tube and after-stop flow included. | The timer allows 48.5 seconds of pumping. Starting with an empty tube, the tank ends at **5 + 48.5 − 2 + 0.5 = 52 mL**. If the tube already held water, all the pumped water would reach the tank and the answer would be **54 mL**. Both exceed the 50 mL mark. This is why we reset the tube to the same state before comparing runs. |

3. **Decide how each reading will be used before collecting it.** With the project lead, label the planned runs either *calibration* (used to estimate model inputs) or *validation* (saved to check predictions later). Prepare one row per run with its identifier, purpose, starting water level, tube condition, pump duration and settled final level. Use the same identifier in the event log so a reading can be traced to its pump commands.

### Phase 2 · Measure the tank and check the models

4. **Confirm the physical session is ready.** The measurement procedure is drafted and awaits review. Before any pumping, confirm that the session plan, firmware and pump time limit have researcher approval and follow the plan’s start-up and cut-off checks. Before sensor tests, verify that the sensor has been wired and that its reported state changes when water reaches it.

5. **Measure how much water reaches the tank.** During the approved calibration runs, record the settled levels before and after each fill. Subtract the starting level from the final level to get the water delivered. Compare repeated fills of the same duration to see how much the readings vary. Compare shorter and longer fills to estimate the intake rate. Finally, compare equal-duration fills starting with an empty tube and a full tube. That last comparison tells you whether filling the tube changes delivery by an amount the tank scale can resolve.

6. **Test the models on the saved runs.** Once both models are available and their settings are fixed, give each the same controller, starting conditions and timing as the corresponding physical run. Record each predicted final level beside the measured level. Subtract measured volume from predicted volume. A positive answer means the model predicted too much water. Also compare when the sensor first reported wet. Keep the differences and reading uncertainty together so the team can judge which differences the equipment could actually resolve.

### Phase 3 · Decide whether extra detail helps detect errors

7. **Compare verdicts for each selected error.** Once the team has selected the two error types and collected the approved comparison runs, make one row per controller and test condition. Enter the physical verdict, Model 1 verdict and Model 2 verdict using the same requirement. If the tank exceeded the safe mark and a model predicted a pass, record a missed failure. If the tank passed and a model predicted a failure, record a false alarm. If the physical evidence cannot settle the requirement, record the comparison as inconclusive.

8. **Hand back the conclusion with the evidence.** For each error type, identify which model agreed with the tank, how close the result was to the relevant limit and which run supports that conclusion. If the models predicted different volumes but reached the same verdict, report that explicitly. That distinction tells us whether the extra detail changed our ability to catch this error.
