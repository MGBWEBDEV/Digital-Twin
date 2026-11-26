# Walkthrough: from the bare rig to the first calibration, validation and test run

Written 26 November 2026 for the researcher. It describes the whole path in the order you will do it, and what happens at each step. All numbers marked "example" are invented to show the arithmetic. They are not measurements and must never be used on the rig.

## Where things stand today

- **The computer side is built and tested.** The basic simulation model, the program that runs a controller, the program that judges a run, and the tools that drive the real rig all exist. Their 224 automatic tests pass on this computer (checked today).
- **The new board program (firmware) compiles but has never run on the board.** The board still runs the original example program with your one-line pump change.
- **Nothing has been measured yet.** Every number in the models is a stand-in until you measure the rig.
- **The level sensor is mounted but not wired.**
- **No controller has been generated yet.** The controllers come from ChatGPT, outside this project folder.

## The whole path in one list

1. Look at the rig and write down what you see. No power is needed.
2. Wire the level sensor. You can start the first session without it.
3. Set up the computer: Python tools, the board build tool, and serial port access.
4. Fill in the board settings and build the firmware for the first session.
5. Upload the firmware and check that the board answers.
6. Write and approve the plan for the first session.
7. **First session (start-up):** check your reading precision, check for leaks, time the communication, prove that the safety timer works, and get a first rough pump rate.
8. **Second session (calibration):** rebuild the firmware with a longer limit, then measure the pump rate, the repeatability, the water hidden in the tube, the settling time and the sensor.
9. Turn the measurements into final numbers.
10. **Validation, first part:** put the measured numbers into the models and check the models' arithmetic.
11. Generate the controllers in ChatGPT and choose the reference controller and the faulty ones. This can start today.
12. **First test run on the real tank:** run the reference controller on the rig, judge the run, and compare it with the models. This is also the second part of the validation.

Who does what:

- **You** do everything physical: you inspect the rig, wire it, read the syringe, approve every plan and every upload, and watch every pumping action.
- **The agent** drafts plans, edits settings files, builds the firmware, runs the analysis and keeps the records.
- **ChatGPT**, in separate fresh chats, writes the controllers. The agent never writes or fixes a controller.

---

## Step 1. Look at the rig and write things down (no power)

This step replaces guesses with facts. Several later safety limits depend on it, so nothing pumps until it is done. Write the answers down and give them to the agent, which records them in the project files.

1. **Board.** Read the model printed on the board. The firmware assumes an Adafruit Metro ESP32-S2. Check that the motor driver wires go to these board pins:
   - driver channel 1: speed pin 8, direction pin 9;
   - driver channel 2: speed pin 16, direction pin 21.

   These pin numbers were read from the original example program, so they have not been checked on the rig yet.
2. **Motor driver.** Read its make and model, and note what powers it (power supply, voltage).
3. **Pumps.** Trace which pump is on channel 1 and which is on channel 2. The software currently assumes that the filling pump (intake) is on channel 1 and the emptying pump (outtake) is on channel 2. Read the pump model and voltage if they are printed on the pump.
4. **Syringe.** Note the full capacity, the spacing between graduation marks, which way up it stands, and where each tube connects. Note how much water the emptying pump can never remove (the water left below its tube).
5. **Tubing and water.** Note the tube lengths, whether you can see water inside them, and where the water comes from and goes to.
6. **Sensor.** Note its type, the number of wires, its height on the syringe in millilitres, and whether it has an indicator light.
7. **Safety.** Note where the electronics sit relative to the water, and check for leaks. **Choose a safe line below the top of the syringe and mark it.** Going above this line counts as "overflow" in the tests. Example: on a 60 millilitre syringe you might mark 50 millilitres.
8. **Decide how you will empty the intake tube between runs.** Every run must start with the intake tube empty, so that each run starts the same way. You planned to pump or drain for a fixed time. Write down how you will do it. If it means running the intake pump backwards, say so, because that would be a reset-only exception.
9. **Estimate the fastest the intake pump could possibly fill,** in millilitres per second, and say where the figure comes from: the pump's data sheet or something you saw the rig do before. This figure sizes the first safety limit in Step 4, so it should be on the high side.

## Step 2. Wire the level sensor

The sensor is only needed for the sensor measurements and the sensor tests. The whole first session works without it, so you can do this step later.

The sensor is a ZCT-YOF07. It is a flexible strip that sticks to the outside of the syringe and senses the water through the plastic wall. It has three wires: ground, supply and signal. According to its datasheet, the signal is **low when water is present and high when there is none**.

- Switch off the power before wiring. The datasheet warns that wiring it live, or swapping the wires, can damage it.
- Connect its supply wire to the board's **3.3 volt** pin, not 5 volts. The board's inputs only accept 3.3 volts, and the sensor works from 2.5 volts upwards.
- Stick it flat against the syringe at the chosen height. Keep tubes, wires and hands away from it during runs, because it senses anything that holds water near it.
- For the signal, use a board pin that the firmware does not use. The firmware currently uses pins 8, 9, 16, 21, 10 and 11 for the motor driver, so pins 9 and 10 are not free yet as far as the firmware is concerned. If they really have nothing attached on the rig, pin 10 can be freed with a small firmware change (it belongs to an unused driver channel). Pin 9 is supposed to set the intake pump's direction, so if nothing is attached to it, that wiring needs tracing first.
- Tell the agent the pin. Until then the firmware reports "not wired", and the tools refuse anything that needs the sensor.

## Step 3. Set up the computer

Run these commands from the project folder.

1. **Create a separate Python environment and install the two tools.** PlatformIO builds and uploads the firmware. pyserial lets the Python programs talk to the board.

   ```bash
   cd ~/Documents/ChatGPT/Digital_Twins
   python3 -m venv .venv
   source .venv/bin/activate
   pip install platformio pyserial
   ```

   Run `source .venv/bin/activate` again in every new terminal before using the tools. Git ignores the `.venv` folder.

2. **Allow your user to open the serial port.** On Linux the board appears as a file such as `/dev/ttyACM0`, and normally only members of the `dialout` group may open it.

   ```bash
   sudo usermod -aG dialout $USER
   ```

   Log out and back in afterwards. If the board is still not accessible, PlatformIO's documentation describes an extra "udev rules" file to install.

3. **Find the board's port.** Plug the board in with the USB cable and run `ls /dev/ttyACM*`. Unplug it and run the command again. The name that disappeared is the board.

4. **Check that the software works on your machine.**

   ```bash
   python3 -m unittest discover -s src -t src
   ```

   It should end with `Ran 224 tests` and `OK`. These tests use a fake board and never touch the hardware.

5. **What PlatformIO will download.** The firmware build is pinned to the same older board toolchain that the original example program needs, so that the new firmware matches what the rig runs now. The first build downloads it, which takes a few minutes.

## Step 4. Fill in the board settings and build the firmware

### What the new firmware does, in plain words

The board does not decide anything. It waits for commands from the computer, switches each pump on or off, and reports the sensor. It also has its own safety stopwatch, which works like this:

- As soon as a pump is switched on, the board starts timing it.
- When the time limit is reached, the board switches the pump off **by itself** and reports a "cut-off" message. The pump stays off even if the computer keeps asking for it to be on.
- No pump can be switched on until a time limit has been set.
- The time limit can only be changed while both pumps are off.
- On power-up everything is switched off first.

There are two limits:

- **The per-run limit.** The computer sends it before each run. It depends on how full the syringe is at the start.
- **The hard maximum (the "ceiling").** It is built into the firmware itself. The per-run limit can never exceed it, and changing it means building and uploading the firmware again. This protects the rig even if the computer sends a wrong number.

Example: with a 10 second limit, a pump switched on at 1.000 seconds is still running at 10.999 seconds and is off at 11.000 seconds.

### The settings file

Every rig-specific value is in one file, `src/esp32/include/rig_config.h`:

- the pins of each driver channel (from Step 1);
- the speed and direction of each pump. Speed is fixed at full and direction is fixed, as in the original example. Check that the direction actually pumps the right way;
- the sensor pin, or −1 if the sensor is not wired;
- **the hard maximum in milliseconds;**
- a "reviewed" switch.

The build deliberately refuses to run until the "reviewed" switch is set to 1 and the hard maximum is filled in. This stops anyone from uploading unchecked values by accident. The agent can make the edits with you, but you confirm every value.

### Choosing the first hard maximum

At this point nobody knows the pump rate, so the first limit is sized from your "fastest possible" estimate in Step 1. The rule is: the start level, plus one graduation of reading margin, plus the fastest rate times the limit, must stay at least five graduations below the top of the syringe.

Example: you say the pump cannot exceed 5 millilitres per second. The syringe holds 60 millilitres, the graduations are 1 millilitre apart, and the start level is 5 millilitres. Then the limit is at most (60 − 5 − 5 − 1) ÷ 5 = 9.8 seconds. You choose something comfortably shorter, for example 3 seconds.

### Build

```bash
cd src/esp32
pio run
sha256sum .pio/build/adafruit_metro_esp32s2/firmware.bin
```

`pio run` compiles the firmware without touching the board. The second command gives the fingerprint of the built program. Copy it into the session log so that every result can be traced to the exact firmware that produced it.

## Step 5. Upload the firmware and check that the board answers

Uploading is your decision. Write down that you approve it, with the date and the firmware fingerprint.

1. **Switch off the pump power supply** (the motor driver's power), but leave the board on USB. Between power-up and the moment the firmware starts, the pin levels depend on the hardware. With the pump power off, nothing can move during this window.
2. Upload:

   ```bash
   pio run --target upload
   ```

   If the upload cannot find the board: hold the board's BOOT button (often labelled "0"), press and release RESET, release BOOT, and try again. Press RESET once more after the upload. The port name can change after this.
3. **The old program is replaced.** The unmodified original example is kept in the `references` folder, but your one-line change for the second pump would have to be made again if you ever wanted to go back.
4. **First contact.** Open the serial monitor and press RESET on the board:

   ```bash
   pio device monitor -b 115200
   ```

   You should see a start-up line beginning with `1,` followed by the firmware name and version. Close the monitor with Ctrl-C, because only one program can use the port at a time. Do not type commands into the monitor. The run tools ask the board for its settings themselves, record them, and refuse to run if the hard maximum does not match the plan.
5. Switch the pump power back on only when the session starts.

## Step 6. Write and approve the plan for the first session

Nothing runs on the rig unless it is in a written plan that you have approved. The plan lists every action in order, with every number: start level, allowed start range, time limit, and the fastest-rate figure with its source. The agent drafts it, and you read it and record your approval (your name and the date go into the file). The tools check that approval is recorded and refuse any action that is not in the plan.

The agent also prepares two small files:

- **The rig settings file** says which driver channel is the intake and what the sensor reports when wet. It is empty for the sensor while the sensor is not wired.
- **The session log** records the date, the firmware fingerprint and settings, the toolchain version, the computer and port, your inspection notes, any stops and any surprises.

## Step 7. First session: start-up

### Before every session

- Both pumps are off.
- There are no leaks, the electronics are dry, there is enough water in the source container, and the outlet tube is in the destination container.
- The hard maximum in the firmware matches the plan.

### How every pumping action goes

This is the same in every session.

1. **Reset.** Bring the syringe near the planned start level. Empty the intake tube with the method from Step 1. Wait until the water settles, then read the level last.
2. **Start.** The tool connects to the board and checks the plan, its approval, the hard maximum and the sensor. It shows what it is about to do and asks for your settled start reading. If the reading is outside the planned range, it refuses, and you reset again.
3. **Confirm.** You type `RUN`. Nothing moves before that.
4. **Pumping.** You only watch. Ctrl-C switches both pumps off at once and marks the action invalid.
5. **End.** The tool waits and asks for your settled end reading, any higher level you saw, and any oddities (a strange pump sound, a drip, a sensor light that disagrees).
6. **Files.** Everything is saved: every command, every board message with both the computer's and the board's clock, and your readings.

### Stop the whole session if any of these happens

Switch both pumps off, and cut the driver power if needed. Then review before running anything else.

- The level gets close to the top of the syringe.
- There is a leak, a spill, or water near the electronics.
- The board restarts or the connection drops during an action.
- The safety stopwatch does not switch a pump off when it should have.

### What the first session contains, and why

1. **Reading precision.** With the pumps off, read the same level five times, looking away and moving your head between readings. Do this at a low level and at a high level. This shows how precisely you can read the syringe, and every later tolerance is built on that figure.
2. **Hold test.** Read the level, wait ten minutes, and read again. Any change means a leak or water siphoning through a tube.
3. **Communication timing.** With the pumps off, the computer asks the board for its state 200 times and times each answer. This shows how long a command takes to reach the board.
4. **Safety timer check, part 1.** A deliberately broken test program switches the intake on and never off. The board's stopwatch must stop the pump at the limit (3 seconds in the example). You should hear the pump stop, the log should show one cut-off message, and the level should rise by roughly "rate × 3 seconds".
5. **Safety timer check, part 2.** A test program that switches the pump off by itself after 2 seconds, before the limit. No cut-off message should appear. These test programs are labelled helpers, not controllers under test.
6. **One more timed fill** at the full limit. Together with part 1, this gives a first, cautious upper estimate of the pump rate. That estimate sizes the next session's limit.

### The commands

The plan and settings file names below are examples. The agent tells you the real ones.

```bash
source .venv/bin/activate
# Measurements (reading precision, hold test, timing, timed fills):
PYTHONPATH=src python3 -m shared.run_calibration --plan PLAN.json --action LABEL \
    --rig-config RIG.json --port /dev/ttyACM0 --out experiments/data
# Safety timer check:
PYTHONPATH=src python3 -m shared.run_rig --session-plan PLAN.json --run LABEL \
    --rig-config RIG.json --port /dev/ttyACM0 --out experiments/logs
```

Measurement data go to `experiments/data` and are never judged as test results. The safety timer check goes to `experiments/logs`. After the session the data and the session log are committed to Git.

## Step 8. Second session: calibration

The first session gave a cautious pump rate, so the hard maximum can now be raised safely. That needs a new firmware build, a new fingerprint and a new upload approval.

Example: the 3 second fills ended 3.0 millilitres higher and your reading precision is half a millilitre. The cautious rate is then (3.0 + 1.0) ÷ 3 = 1.33 millilitres per second. With a safe line at 50 millilitres, the longest fill allowed is (50 − 2 − 5 − 1) ÷ 1.33 = 31.5 seconds. That is enough for fills of 10 and 20 seconds.

The calibration session contains:

1. **Timed fills from an empty tube.** Two durations, one twice the other (for example 10 and 20 seconds), five fills each. The board's stopwatch times every fill exactly. A straight line through "water gained" against "time" gives the **pump rate** and a fixed **offset** (water lost or gained at start and stop). If the five repeats of each duration agree within one graduation, the rig counts as consistent.
2. **Fills with the tube already full.** Five fills of the longer duration without emptying the tube first. Comparing these with the empty-tube fills shows how much water hides in the tube at the start, and how much trickles in after the pump stops.
3. **Settling readings.** In three of the fills, you read the level at about 2, 5, 10, 20 and 30 seconds after the stop (the tool shows the time). This tells you how long to wait before a reading counts as settled.
4. **Sensor, if wired.**
   - Fill in short pulses (for example half a second each). After each pulse, wait, read the level and note the sensor state, until the sensor first reports wet. Do this five times. This gives the level at which the sensor switches.
   - Fill continuously until the sensor reports wet. The tool switches off immediately. Do this five times. This shows how late the sensor reacts.

The emptying pump is not used in calibration. Running it near the bottom of the syringe is not yet known to be safe.

## Step 9. Turn the measurements into final numbers

The agent runs the analysis tool on the saved measurement folders, together with a small file holding your own numbers from Step 1: capacity, graduation spacing, safe line, water the emptying pump cannot remove, standard start level, and how often the controller is called.

```bash
PYTHONPATH=src python3 -m characterization.analysis --inputs INPUTS.json \
    experiments/data/<first session> experiments/data/<second session>
```

It gives:

- your reading precision;
- the pump rate, its offset and its run-to-run spread;
- a cautious highest rate, used for safety limits;
- the settling time;
- the sensor switch level and the sensor delay;
- which small real-world effects are big enough to matter at this rig's precision (water in the tube, trickle after stop, sensor delay, communication delay);
- all the final tolerances and limits the tests need;
- warnings where a rule cannot be met.

An effect is only added to the detailed model if it is bigger than what you can read **and** bigger than the uncertainty of its own estimate, so that noise is not modelled. If no effect is big enough, that is itself a finding ("the basic model is enough at this rig's precision"), and you decide what to do next.

Example: five 20 second fills from 5 millilitres end at 24.5, 25.0, 24.5, 25.0 and 25.0, and five 10 second fills end at 14.5 or 15.0. The line through them gives about 1.0 millilitre per second with an offset of about −0.4 millilitres, and the repeats agree within one graduation.

The tool decides nothing on its own. Every warning comes to you.

## Step 10. Validation, first part: check the models' arithmetic

The measured numbers replace every stand-in value in the models, the tests and the plans. Then:

1. **The expected answers are worked out again by hand** with the real numbers, before the models are run. Example of such a check: start at 5 millilitres, a controller that never stops, a 48.5 second limit and 1 millilitre per second. The basic model must end at exactly 53.5 millilitres.
2. **You recheck at least four of these by hand for each model:** one at a boundary, one where the safety timer fires, one involving the sensor, and one full run. So far all such checks were computed by the agent, not by a person.
3. The models are run, and every volume must match exactly. Any difference is treated as a model error or a hand-calculation error and is fixed before any controller uses the model.
4. The detailed model (the second model) is finished with only the effects that passed Step 9.

This only proves that the models compute what their equations say. It does **not** prove that they behave like the real tank. That proof comes from comparing them with real runs that were never used to set the numbers (Step 12).

## Step 11. Get the controllers (can start today)

This needs neither the rig nor any measurement. The controllers receive the real numbers only when they are started.

1. **Ten fresh ChatGPT chats.** Memory, personalisation and custom instructions are off. Upload no files and switch off web search and code tools. In each chat, paste the prompt from `experiments/prompts/controller_prompt_v1.md` exactly, as the only message. Do not send follow-up messages and do not regenerate.
2. **Save each full answer**, with the date and time and the model name and version exactly as the app shows them. Copy the single block of code unchanged into its own file. An answer with no code block, or more than one, counts as unusable.
3. **Review all ten before running any of them.** For each one, write down every place where it does something different from the required behaviour.
4. **Choose by rule, not by results.**
   - The **reference controller** is the first one that passes the automatic rule check and has no defect. It must then pass all ten tests on the basic model.
   - The **faulty controllers** are the first two with a usable defect of two different kinds.
   - This choice is committed to Git before anything is run, so nobody can pick faults that happen to suit a model. If there are not enough natural faults, you make them by hand in copies of the reference controller, from a list that is already fixed.

## Step 12. First test run on the real tank

### Preparation

- **A third firmware build.** Its hard maximum is set to the longest per-run limit in the plan, computed from the measured numbers. This needs a new upload approval.
- **The per-run limit.** It is set so that even a controller that never switches off stops below the top of the syringe, but it may pass the safe line. Passing the safe line is exactly the "overflow" failure the tests must be able to see on the real tank.

  Example: start at 5 millilitres, start range of 1 millilitre, syringe 60 millilitres, a margin of 5 millilitres below the top, half a millilitre of trickle after stop, and a cautious rate of 1 millilitre per second. That gives a limit of 48.5 seconds. A runaway controller ends near 53.5 millilitres: above the 50 millilitre safe line (a failure), but still 6.5 millilitres below the top.
- **The session plan** lists the reference controller on the ten test runs, each with its start level, limit, and the controller file's fingerprint. You approve it.

### One run, step by step: "fill until the sensor is wet"

1. **Reset.** Bring the level to about 5 millilitres, empty the intake tube, wait for it to settle, and read it. The tool checks that your reading is in range and that the board reports the sensor as dry.
2. You type `RUN`.
3. The computer starts the controller and tells it the task and the known numbers: the sensor level, the pump rate and the deadline. It never tells it the water level. From then on the computer calls the controller at a fixed interval and gives it only the time and the sensor state. The controller answers each time with "intake on or off, outtake on or off".
4. The controller switches the intake on. The water rises, the sensor turns wet, and the controller should switch the intake off at its next call.
5. The run continues until its planned end time. Then the computer switches both pumps off.
6. You wait for the level to settle and enter the end reading, any higher level you saw, and any oddities.
7. The run is saved in its own folder: every controller call, every board message and your readings.

### Judging the run

```bash
PYTHONPATH=src python3 -m testing.evaluator experiments/logs/<run folder>
```

The judging program reads only the saved files. It does not know which environment produced them. It gives each check, and the run as a whole, one of four outcomes:

- **pass**;
- **fail**;
- **undetermined**: the evidence cannot settle it, for example a value you cannot see on the real tank;
- **invalid**: the run itself went wrong, for example the connection dropped. An invalid run is repeated and never counted.

If a reading lands within the reading margin of the limit that decides the check, the run is repeated until there are five. If all five agree, that is the verdict. If they do not agree, the check is undetermined.

### Validation, second part: the same run in the models

The same controller is now run in both models, with the **start level you actually measured** on the rig. Then two comparisons are made:

1. **How close is each model?** Predicted end level minus measured end level, and predicted minus real moment the sensor turned wet. Example: the model predicts 24.0 millilitres, you read 24.5, so the model is 0.5 millilitres low. That is within the "twice the reading precision" margin, so it counts as within what you can observe.
2. **Do the verdicts agree?** If the real tank passed and a model failed, that is a false alarm. If the tank failed and a model passed, that is a missed failure. This is the research question, and it gets its real answer when the faulty controllers are run the same way after the reference controller's ten runs.

The reference controller's real runs are never used to adjust model numbers. If that ever happens, it is recorded, and those runs no longer count as validation.

---

## Checklist: what each stage waits for

| Stage | Waits for | Who |
|---|---|---|
| Computer setup | Nothing | You (with the agent) |
| Controller generation | Nothing | You, in ChatGPT |
| First firmware build | Rig inspection, safe line marked, your fastest-rate estimate and its source | You, then the agent |
| Upload | Your written approval with the fingerprint | You |
| First session | Approved plan, intake-tube emptying method | Agent drafts, you approve and run |
| Second session | First session's results, new build and upload, sensor wired (for the sensor part) | Same |
| Final numbers and model checks | Both sessions; your hand rechecks | Agent, then you |
| First test run | Final numbers, reference controller chosen, third build and upload, approved plan | Same |
