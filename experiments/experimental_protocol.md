# Experimental protocol (WP08, provisional)

> **Status: Provisional, approved by researcher 2026-11-26 (agent-completed by Claude Code); final version after WP04.** Written before WP04, as the roadmap allows (D28). It fixes procedures and rules. Numerical values are placeholders (D34) or rules that turn WP04 results into values. The final version follows WP04 and replaces every placeholder with a measured or derived value. Decisions D43–D47 (`context/decisions.md`) approved by researcher 2026-11-26; D43 with ChatGPT as the generating AI.
>
> Inputs: `design/functional_requirements.md` (WP03), `design/mathematical_models.md` (WP05, provisional), `design/controller_behavior.md` (WP06), `design/software_architecture.md` (WP07), `design/physical_system.md` (WP01), `src/testing/README.md` (WP12), decisions D10, D14, D24–D29, D33–D42.
>
> **Not for the generation session (D29).** This document contains scenarios, tolerances, fault types and injection rules. It must never be shown to the session that generates controllers. The only text that goes to that session is `experiments/prompts/controller_prompt_v1.md`.

## 1. In plain terms

The study tests AI-written controllers on three "tanks": the real rig, Model 1 and Model 2. Each controller gets the same tasks (S1–S5). The same evaluator judges every run. The research question is whether each model gives the same pass/fail verdict as the rig (D25). This protocol fixes, before any experiment:

- how controllers are obtained (sections 13–15);
- how a run is prepared, executed and recorded on the rig and in the models (sections 5–9, 16);
- how results are judged and compared (sections 10–12);
- what is still missing before each step can start (section 18).

Example of a complete chain: an AI generation G03 turns out to forget the 30 s deadline. It is selected as a "missing stop" fault from its code, before anything is run. It then runs scenario S4 on the rig, in Model 1 and in Model 2. Every environment logs a `cutoff` event and FR08 fails. All three verdicts are "fail", so both models agree with the rig on this run.

## 2. Scope and prerequisites

| Prerequisite | Needed for | Status 2026-11-26 |
|---|---|---|
| Rig checklist (`design/physical_system.md` section 10): capacity P01, graduation P02, safe mark P04 | Cut-off sizing, any rig run | Pending (researcher) |
| Sensor wired and read by the firmware (D19) | Rig FR03/FR09 runs, WP04 sensor measurements | Pending (researcher) |
| WP09a rig firmware and adapter, approved and uploaded | Every rig run in this protocol | Pending |
| WP04 characterization | Final parameter values (section 3), Model 2 inclusion, cut-off value | Pending; blocked by the two rows above |
| WP11 Model 2 | Model 2 runs | Pending; needs WP04 and final WP05 |
| Approval of D43 (AI family and generation procedure) | Generating the controller pool | Approved 2026-11-26 (ChatGPT) |
| WP10 Model 1, WP12 evaluator and harness | Simulation runs and evaluation | Approved (provisional) |

Controller generation (section 13) needs no rig and no WP04 values. The prompt contains no numbers; the known parameters are passed to the constructor at run time. Generation can therefore start now.

## 3. Parameters and how their final values are set

Existing IDs keep their meaning (`design/functional_requirements.md` section 4; `design/physical_system.md` section 12). This section adds the **rule** that turns WP04 evidence into the final value. New IDs R12–R16 are introduced here. All current numbers are placeholders (D34).

| ID | Quantity | Placeholder | Final value rule (applied after WP04) |
|---|---|---|---|
| R01 | Call period Δt_c | 0.1 s | Kept (D38) unless WP09a shows that the rig cannot call every 0.1 s without frequent late calls (more than 1 % of calls late) |
| R02 | Start limit t_start | 0.5 s | 5 × R01 |
| R03 | Timing tolerance ε_t | 0.2 s | 2 × R01 |
| R04 | Response limit t_resp | 0.1 s | 1 × R01 |
| R05 | Volume tolerance ε_V | 2 mL | 2 × u_read + s_run, rounded up to a whole graduation. u_read is the WP04 reading uncertainty (P03). s_run is half the range of the 5 repeated timed fills (P08) |
| R06 | Sensor-wait deadline T_deadline | 30 s | 1.5 × (V_sensor − P10) / Q_in, rounded up to a multiple of 5 s; must be at least 5 s below T_max of the S2/S4 start volume (section 8) |
| R07 | Known parameters given to the controller | V_sensor = P05, Q_in = P06, T_deadline = R06 | V_sensor = WP04 measured rising switch volume; Q_in = WP04 fitted intake rate; T_deadline = R06 (D46) |
| R08 | Observation time T_end | 60 s | At least the largest per-run T_max + 5 s (section 8) |
| R09 | Settling time | 10 s | WP04 time from intake OFF until the reading stops changing (including run-on), rounded up to 5 s; at least 10 s |
| R10 | FR01 durations | 10 s, 20 s | Two durations, so that a proportional and an offset calibration can be told apart (WP05 section 6.1); P10 + Q_in × duration ≤ P04 − R05 |
| R11 | FR09 targets | 30, 40, 45, 48 mL | P04 − 20, −10, −5, −2 mL from the marked safe mark; every target must be above V_sensor |
| P10 | Standard start volume (S1, S2, S4, S5) | 5 mL | Lowest level that can be read reliably, at least 2 graduations above the dead volume P09, and well below V_sensor |
| R12 | Capacity headroom for the cut-off | 5 mL | At least 5 graduations; never less than 2 × R05 |
| R13 | Reset tube-emptying time | TBD | Set after the rig check (U10, U11) by the reset method (section 6.2) |
| R14 | Start-volume band on the rig | ±1 mL | 2 × u_read |
| R15 | Repeats near a limit | 5 runs in total | Fixed by D27; not a placeholder |
| R16 | Near-limit window w | 1 mL | Range (max − min) of the 5 repeated settled readings in WP04, but not less than u_read |
| — | S3 start volume | 30 mL | V_sensor + 6 mL, and at least 3 graduations above the sensor so that the sensor is reliably wet at the first call |
| P11 | Cut-off maximum ON time | 45 s (single value) | Replaced by the per-run rule of section 8 (D45) |

FR01-P1 compares the delivered volume with the calibration in the form WP04 actually fits: Q_in × T, or Q_in × T + b if an offset qualifies under D24 (WP05 section 10).

## 4. Environments and run purposes

Every run directory records a `purpose` in `run.json`. The purpose decides how a run may be used. Data from one purpose is never reused for another without a recorded reason (section 9).

| Purpose | Environment | What it is for | Scored by the evaluator |
|---|---|---|---|
| `verification` | Model 1, Model 2 | Mathematical verification against hand calculations (section 5) | No; unit tests |
| `cutoff_check` | Rig | Proves the firmware cut-off works before any controller runs (section 7.4) | No |
| `calibration` | Rig | WP04 characterization; fits parameters | No |
| `reference` | Rig, Model 1, Model 2 | The reference controller on S1–S5. Gives rig verdicts for false-alarm counting and the held-out data for model accuracy (WP13) | Yes |
| `fault` | Rig, Model 1, Model 2 | A selected faulty controller on its triggering scenarios (section 15) | Yes |
| `pool` | Model 1, Model 2 | Every usable generation on all ten scenario runs, after selection. Exploratory only | Yes (reported as exploratory) |
| `paired` | Model 1, Model 2 | Re-run of a rig run with the measured rig start volume (section 10) | Yes |

## 5. Mathematical verification

Mathematical verification shows that a model computes what its equations say. It does not show that the equations describe the rig (master context; AGENTS.md).

- **Cases.** Model 1: M1-1 … M1-12 (`design/mathematical_models.md` section 9.1–9.2), together with the mass-balance and cut-off unit tests of WP10. Model 2: M2-1 … M2-11 (section 9.3–9.4).
- **Independent expectation.** Expected values are worked out by hand from the equations, never by running the model. After WP04, every case is recomputed by hand with the final values before the model is run. The researcher rechecks at least four cases per model by hand: one boundary case, one cut-off case, one sensor case and one full-loop case. The WP10 condition shows why: the spot checks so far were computed by the agent, not by a person.
- **Pass rule.** Volumes must match exactly; the simulation uses exact fractions (D40). Times must match to the simulation step Δt_s. Any difference is a failed verification. It is investigated as a model or oracle error before any controller run uses that model.
- **Per-run cut-off (D45).** After D45 is approved, M1-12, M2-8 and M2-9 are recomputed with the per-run T_max (section 8).

## 6. Rig run procedure

This is the general procedure. WP04 writes its own measurement steps on top of it. Every rig run needs researcher approval as part of a session plan (section 7.1). No placeholder value is ever used on the rig (D34).

### 6.1 Before a session

1. Both pumps OFF. Firmware version and hash, harness commit, host and serial port are recorded in the session log (section 16).
2. Inspect the rig: no leaks, electronics dry, enough water in the source container, the outlet routed to the destination container.
3. Confirm that the cut-off ceiling compiled into the firmware matches the session plan (section 8).

### 6.2 Reset and start conditions for each run (D46)

The goal is that every run starts with a known settled volume V0 and an **empty intake tube** (f0 = 0, researcher statement 2026-11-25, D40).

1. **Set the level.** The researcher brings the syringe near the planned V0 with setup commands. These are separate, logged pump commands from a setup script. They are not the controller under test, and the cut-off still applies to them. The outtake is never run with the syringe at or below the dead volume (U30).
2. **Empty the intake tube.** Use the reset method chosen after the rig check, applied for R13. The method is TBD: the researcher's plan is to pump or drain for a fixed time. If the method reverses the intake pump, that is a reset-only exception to D20 and must be recorded. If the intake tube end sits below the water line, emptying it may draw water from the syringe; this is why step 3 comes last.
3. **Read V0 last.** Wait R09, then read the settled level and record it as `start` in `manual.csv`, with its uncertainty.
4. **Accept or redo.** The run starts only if the reading is within V0 ± R14 of the plan. The sensor state shown by the firmware must also match the planned case: dry for S1, S2, S4 and S5, wet for S3. Otherwise go back to step 1.

The pumps stay OFF from step 3 until the first controller call. This means the tube is still empty when the run starts.

### 6.3 Run

1. The harness sets the per-run cut-off (section 8), logs it in `run.json`, creates the controller (D36) and calls it every R01 until T_end (R08). Then it commands both pumps OFF (D40 (3)).
2. During the run the researcher only watches. They intervene only under a stop rule (section 6.4); an intervention invalidates the run.
3. After T_end, wait R09 and read the settled level as `end`. If a settled peak was visibly higher (possible only when the outtake ran), record it as `peak` (D41 (8)).
4. Note any anomaly: an unexpected pump sound, a dripping tube, a sensor indicator that differs from the host log.

### 6.4 Stop rules

Stop the session, with both pumps OFF (power off the driver if needed), and run nothing more until the researcher has reviewed it if any of these happens:

- the level rises above the capacity headroom line, C − R12;
- a leak, a spill, or water near the electronics;
- a firmware start-up message, or a lost serial link, during a run (WP06 X8; the run is invalid);
- the cut-off fails to fire when the log shows it should have.

A stop is recorded in the session log. The affected run is marked invalid (`run_invalidated`); it is never scored as a controller verdict.

## 7. Rig sessions

### 7.1 Session plan and approval

Before each session the agent or researcher writes a session plan: the list of runs, each with controller file and hash, scenario run, planned V0, per-run T_max, purpose and order. The researcher approves it in writing before the session; the approval is recorded in the session log. Runs not in the plan are not executed.

### 7.2 Order of rig work

1. Rig checklist, safe mark P04 marked, sensor wired (researcher).
2. WP09a firmware uploaded after approval; cut-off check (section 7.4).
3. WP04 characterization (`calibration` runs, 5 repeats per basic measurement, D27).
4. Final values fixed: section 3 rules, final WP05, WP11 built and verified.
5. Reference controller runs: the ten scenario runs, once each (`reference`).
6. Faulty controller runs: the triggering scenario runs of each selected fault (`fault`, section 15.3).
7. Near-limit repeats as they arise (section 11).

### 7.3 Run budget

| Item | Runs |
|---|---|
| Cut-off check | 1–2 |
| WP04 characterization | Defined in WP04 (5 repeats per basic measurement) |
| Reference controller | 10 |
| Two faulty controllers, at most 4 triggering runs each | ≤ 8 |
| Near-limit repeats | ≤ 4 per affected run |

This keeps the controller experiments to the 15–20 rig runs plus near-limit repeats foreseen by D27. Simulations are deterministic and run once (D27).

### 7.4 Cut-off check

Before any generated controller touches the rig, the firmware cut-off is checked with the labelled never-OFF test double (D27 (1); WP09a acceptance).

1. Start at V0 = P10 with a deliberately short test limit, for example 10 s, set through the same per-run mechanism. Expected: a `cutoff` event at the limit, the pump stops although the command stays ON, and V_end ≈ V0 + Q_in × 10 s.
2. Start a second run with the per-run limit of the session plan, but stop it after 15 s by commanding OFF. Expected: no `cutoff` event, and the logged limit equals the plan.

Neither step raises the level above the safe mark.

## 8. Cut-off sizing (D45)

**Rule.** For every run the harness computes the maximum continuous ON time from the planned start volume:

T_max(run) = ⌊ (C − R12 − (V0_plan + R14) − V_ro) / Q_in,hi ⌋ to 0.1 s

Here C is the measured capacity (P01), V_ro is the WP04 run-on volume (0 if E2 is excluded), and Q_in,hi is the upper end of the WP04 intake calibration (fitted rate plus its spread). The same value is used by the firmware, Model 1 and Model 2 (D27 (2), D38). The firmware also has a compiled-in ceiling equal to the largest T_max of the session plan. A wrong value sent by the host therefore cannot raise the limit further.

**What it protects.** The cut-off protects the physical **capacity**, as D27 states. It does not protect the safe mark. Going above the safe mark is the rig's "overflow" failure (D24). The evaluator detects it through FR08-P1, and it must be possible on the rig. Otherwise the rig could never show an FR08-P1 failure, and D25 would have no rig verdict for that kind of fault.

**Example with placeholders** (C = 60, R12 = 5, R14 = 1, V_ro = 0.5, Q_in,hi = 1.0):

| Start volume | T_max | Correct controller | Controller that never stops |
|---|---|---|---|
| 5 mL (S1, S2, S4, S5) | 48.5 s | Longest fill: FR09 48 mL takes 43 s (Model 1) or 45.2 s (Model 2, empty tube); no cut-off | Stopped at 48.5 s: 53.5 mL (Model 1). That is above the safe mark (FR08-P1 fails) but 6.5 mL below capacity |
| 30 mL (S3) | 23.5 s | Never switches ON | Stopped at 23.5 s: 53.5 mL; also below capacity |

With the single 45 s placeholder (P11), the S3 row would reach 30 + 45 = 75 mL, which is more than a 60 mL syringe holds. With the 45 s limit, a correct FR09 48 mL run also hits the cut-off in Model 2 (M2-8). This is why the limit depends on the start volume.

**Consequences after approval.** The code currently uses one P11 value. WP09a needs a "set limit" command and a compiled-in ceiling. WP10/WP12 need the environment to take T_max per run, `run.json` to record it, and M1-12, M2-8 and M2-9 to be recomputed. Not done here; WP08 changes no code.

## 9. Calibration and held-out data

- **Calibration** (`calibration`): WP04 runs that fit Q_in, any offset b, the sensor switch volume, the delays and the spreads. Only these runs set parameter values.
- **Held-out validation** (`reference`): the reference controller's rig runs on S1–S5. They are never used to fit a parameter.
- **Refitting.** If a parameter is refitted after the validation data have been seen, the refit and its reason are recorded. Any validation run used in the refit becomes calibration data from then on and is reported as such. The held-out comparison is then reported only for the remaining runs.
- **Known parameters for the controller** (R07, D46). The controller receives the WP04 measured rising switch volume as V_sensor, and the WP04 fitted rate as Q_in. Candidate E3 (trigger offset) is then zero by construction (WP05 section 5.4), as for a real installation, where an engineer would supply calibrated values.

## 10. Simulation runs

- **Nominal runs.** Each controller is run on the ten scenario runs at their nominal start volumes, in Model 1 and Model 2. This is done once, because the runs are deterministic (D27).
- **Paired runs** (D46). Each scored rig run gets a paired run in each model, with the start volume set to the measured rig V0 rounded to the graduation. All other inputs are the same: controller, request, override and T_max. The D25 comparison (section 12) uses the paired runs. Nominal and paired verdicts are both reported; if they differ, this is noted. WP12 follow-up: the scenario runner needs a per-run start-volume input recorded in `run.json`, with D41 (5) checking against it.
- The determinism replay (D42 (3)) runs for every scored run in every environment.

## 11. Repetitions and the near-limit rule (D27, D47)

- WP04: each basic measurement 5 times. The rig counts as consistent if the settled readings agree within the reading resolution (D27 (5)).
- Controller experiments: each controller × scenario run once on the rig.
- **Near-limit repeat.** A rig run is repeated if a physical check (FR01-P1, FR03-P1/P2, FR09-P1/P2, FR08-P1, and FR08-P2 when used) has its settled reading within w (R16) of the limit that decides it. Those limits are the safe mark and the ±ε_V bounds. The run is repeated until there are 5 runs in total (R15), each with a full reset. The check's verdict is the common verdict if all 5 agree; otherwise it is **undetermined**. The run's overall verdict follows D41 (2).
- Example (placeholders): S5-48 on the rig ends at 49.3 mL. The margin to the safe mark is 0.7 mL, which is less than w = 1 mL, so the run is repeated 4 more times. If 4 runs pass FR08-P1 and one fails, FR08-P1 is undetermined for this pair.
- D27 names only the safe mark. Extending the rule to the ±ε_V bounds is part of D47.

## 12. Verdicts, model accuracy and the model comparison (D25, D47)

### 12.1 Run verdicts

The evaluator (WP12, D41, D42) gives each run pass, fail, undetermined or invalid. Invalid runs are not scored and are repeated if the plan allows. On the rig, a check whose value cannot be observed is undetermined (D24, D41).

### 12.2 Model accuracy (WP13, reported separately from detection)

These are computed for each `reference` rig run and its paired model run:

| Metric | Definition | Reported as |
|---|---|---|
| e_V | V_end,model − V_end,rig (mL) | Per run; mean absolute and maximum per model |
| e_tw | t_w,model − t_w,rig (s), runs with a wet edge | Per run; maximum per model |

A run is "within observation uncertainty" when |e_V| ≤ 2 × u_read and |e_tw| ≤ R01. This is a descriptive label, not a gate. A less accurate model is still used in section 12.3, because D25 does not assume that "more accurate" means "better for testing".

### 12.3 Verdict comparison (D25)

The unit is a pair: one controller on one scenario run, with a **determined** rig verdict (pass or fail). For each model:

| Model verdict | Rig pass | Rig fail |
|---|---|---|
| Pass | Agreement | **Missed failure** |
| Fail | **False alarm** | Agreement |
| Undetermined | Model inconclusive | Model inconclusive |

- Pairs with an undetermined rig verdict are left out of the counts and listed separately.
- A faulty controller that passes on the rig did not trigger its fault in that run. It is "fault not triggered", not a missed detection by the rig (WP15). If a model fails it, that model counts a false alarm against the rig verdict, and the reason is reported.
- **Check-level table.** For agreeing pairs, the failed check IDs are also compared, to show whether model and rig fail for the same reason (example: the model fails FR03-L2 while the rig fails FR03-P1).
- **Margin.** For every pair record the rig margin to the safe mark (P04 − V_end,rig) and to the deciding ε_V bound. The statement "Model 1 suffices when the margin exceeds X" uses X = the largest margin at which a Model 1 verdict disagreed with the rig. It is descriptive only. With about 18 pairs no statistical test is applied, and no threshold is generalised beyond this rig (WP16).
- **Correctness categories (master context).** "Correct" means the reference controller; "incorrect" means a selected faulty controller whose defect was triggered on the rig. Correct and accepted = agreement on pass; correct and rejected = false alarm; incorrect and rejected = detected; incorrect and accepted = missed; anything undetermined = inconclusive.

## 13. Controller generation (D29, D43)

### 13.1 AI family

**OpenAI ChatGPT** (web app; researcher choice 2026-11-26, D43). D29 requires a family different from the one that builds the models and evaluator, which is Claude (Anthropic). Consequence: Codex, which belongs to the same family as ChatGPT, must not write or modify model, simulation, harness or evaluator code. The exact model name and version shown in the app are recorded for every generation. They are never inferred.

Limitation to report: the scaffold and the requirements draft (D23) were generated with ChatGPT, and Codex made figures and reviews. The separation therefore holds between the controllers and the code that tests them, not across the whole project.

### 13.2 Prompt

- `experiments/prompts/controller_prompt_v1.md`, SHA-256 `8e9ba48c739f67cf724dcf3a5811fd66816874b9bd148aef3687a9cdda449f7c`. Written by Claude Code in the unattended WP08 session of 2026-11-25. Reviewed in this session against D29, D35–D37 and D42, and kept unchanged.
- **Contents.** It contains the device description, the D37 interface, the meaning of the constructor values, the task descriptions and the D42 rule list. It contains no numbers, scenarios, check IDs, tolerances, fault types or model code (D29 (1)). It states the required behaviour that WP06 specifies: single ON interval, latching on the first wet input, the deadline, and do-nothing when already wet. A correct controller cannot be written without this behaviour, so faults stay attributable to the AI rather than to an underspecified task.
- **Expected consequence** (not a result). Because the prompt is explicit, natural faults may be rare. Section 15.4 covers that case.
- **Frozen.** v1 is frozen (D43 approved 2026-11-26). Any change creates v2, with its own hash and reason, and is used only for a new pool.

### 13.3 Session rules

For each generation G01, G02, …:

1. Start a new chat. Memory, personalisation and custom instructions are off. Upload no files and enable no web search or code tools; if the app uses a tool on its own, record it.
2. Paste the prompt verbatim as the only message. Send no follow-up messages and do not regenerate.
3. Save the complete answer verbatim in `experiments/prompts/generations/Gnn.md`. Record the date and time, the app, the model name and version as shown, the account tier, the prompt hash and any tool use.
4. Copy the single Python code block, unchanged and without reformatting, to `src/shared/controllers/Gnn.py`, and record its SHA-256.
5. If the answer has no code block or more than one, the generation counts toward the budget, is recorded as "unusable (format)" and is not run.

The researcher runs these sessions outside the repository and adds the files (WP09b, AGENTS.md). Agents in this repository do not write, edit or "fix" controller files.

### 13.4 Pool and budget (D43)

- **Pool: G01–G10**, all generated from v1 with the same model before any of them is reviewed or run. Generation cannot be steered by results.
- If the model version shown changes during the pool, record it and continue.
- The same pool supplies the reference controller (section 14) and the natural faults (section 15).

## 14. Reference controller (WP09b)

1. **Rule check.** Every usable generation gets the D37/D42 static check. Rejected files are recorded with their violations; they are not eligible as reference or fault.
2. **Code review** (section 15.1) of all generations, before any run.
3. The reference candidate is the first generation, in pool order, that passes the rule check and has no defect in the review.
4. **Confirmation.** It must pass all ten scenario runs in Model 1, including the replay. If it fails, the missed defect is recorded as "found after selection" (section 15.2), and the next candidate is tried.
5. If no generation qualifies, up to five extra generations (G11–G15, same prompt and rules) are made for the reference only. They do not join the fault pool, so its budget stays fixed. If none qualifies, this is reported as a blocker.
6. The reference stays labelled **candidate** until its rig runs in WP13 (D30).

## 15. Defects, eligibility, selection and fallback (D44; settles D10)

### 15.1 Code review

The researcher, who may be assisted by an agent, compares each generation with WP06. A **defect** is code that, for some valid request and input sequence, gives outputs that differ from WP06 by more than the WP03 tolerances accept. Example: stopping one call late is not a defect, because ε_t accepts it. Each defect is recorded in `experiments/controller_error_catalogue.md` with:

- generation, lines and description;
- the WP06 transition or constraint it breaks;
- its D29 fault type (wrong actuator, wrong condition, timing error, missing stop, FR09 calculation error) or "other";
- the scenario runs whose inputs reach it, argued from the code;
- origin: natural.

### 15.2 Eligibility and selection

A defect is **eligible** only if all of the following hold:

1. it is traced to specific lines, and the researcher confirms the root cause;
2. its type is in the D29 fault space;
3. at least one of the ten scenario runs reaches it, argued from the code and not from a run;
4. the file passes the rule check;
5. at least one triggering scenario run reaches this defect and none of the generation's other defects (isolation);
6. it is safe on the rig behind the cut-off. An outtake fault (wrong actuator) is eligible only after U30 is resolved as safe.

**Selection** is mechanical and happens **before any controller of the pool is run in any environment**. The selection record is committed to Git before the first run.

- First fault: the first eligible defect in pool order (G01, G02, …; by line within a generation).
- Second fault: the next eligible defect of a **different** fault type.
- Defects found later, in runs, are recorded as "found after selection". They are reported, but they are used only through the fallback rule below and labelled exploratory.

This keeps the selection blind to which model detects a fault, as master context and WP14 require. Because selection does not use exploratory scenario runs, no separate evaluation scenarios need to be reserved (WP14).

### 15.3 Triggering scenario runs

For each selected fault, the rig runs are its triggering scenario runs from criterion 5, at most four, taken in the order S1 … S5. All ten scenario runs are still run in both models (`fault` for the triggering ones, `pool` for the rest).

### 15.4 Fallback injection

If fewer than two eligible natural defects of different types exist, the missing fault types are made by **isolated injection** into a copy of the reference controller. Each copy has one change. The researcher makes the change by hand, because agents do not write controllers here. The file is saved as `src/shared/controllers/<ref>_inj-<code>.py` with the diff recorded and the origin labelled **injected**. The list and its order are fixed now. They are ordered by rig safety and by how directly each fault maps to one WP06 transition, not by expected detection in any model. The first types in the list that are not already covered are used.

| Code | Fault type | Change (behavioural description) | Triggering runs |
|---|---|---|---|
| I-S | Missing stop | The deadline transition is removed: FR03/FR09 never stop on T_deadline | S4 |
| I-F | FR09 calculation error | Extra time computed as target / Q_in, ignoring V_sensor | S5-30 … S5-48 |
| I-C | Wrong condition | At the first call, FR03/FR09 ignore a wet sensor and start filling | S3-FR03, S3-FR09-40 |
| I-T | Timing error | FR09 extra time counted from the intake ON call instead of from the first wet call | S5-30 … S5-48 |
| I-A | Wrong actuator | FR01 switches the outtake instead of the intake (only if U30 is resolved as safe) | S1-10, S1-20 |

Natural and injected results are always reported separately.

## 16. Data handling

- **Run directories.** `experiments/logs/<run_id>/` with the files of `design/software_architecture.md` section 7 and the key names of `src/testing/README.md` (D41 (6)). `run.json` additionally records `purpose`, the per-run `t_max_s`, the controller generation ID and the planned V0 (for paired runs, the measured rig V0).
- **Run ID.** As the runner already writes it: `<UTC yyyymmddThhmmssZ>_<environment>_<scenario run>_<first 8 hex of controller SHA-256>`, for example `20261210T101500Z_rig_S2_1a2b3c4d`. Repeats differ by timestamp.
- **Manual readings.** For rig runs, the harness creates `manual.csv` with empty `start` and `end` rows. The researcher fills them in during the run, from the syringe, with their uncertainty, before the next run starts. Raw files are never edited afterwards. A wrongly entered reading makes the run invalid; the reason is noted and the run is repeated.
- **Session log.** `experiments/logs/sessions/<date>.md`: approved session plan, approvals, firmware and harness versions, rig inspection, stops, anomalies, and deviations from this protocol.
- **Units.** Time in integer ms in files, s at the controller interface; volume in mL; booleans as 0/1 or true/false.
- **Storage.** Run directories, session logs, generation records and controller files are committed to Git after each session (D11, D17). Calibration data from WP04 goes to `experiments/data/`.
- **Every verdict is provisional** while any parameter is a placeholder (WP12).

## 17. Safety summary

- No placeholder value is used on the rig (D34). Rig runs start only after WP04 has fixed T_max, R12, R14 and the safe mark.
- The firmware cut-off is checked (section 7.4) before any generated controller runs on the rig.
- The cut-off keeps every run below capacity minus headroom, for any controller (section 8). The level may pass the safe mark, which is the rig's overflow verdict, but never capacity.
- Every session runs from an approved plan with stop rules (sections 6.4, 7.1). An outtake fault runs on the rig only after U30 is resolved.

## 18. Open items

| Item | Blocked by | Section |
|---|---|---|
| All final numerical values | WP04, rig check | 3, 8 |
| Reset method and R13 | Rig check (U10, U11), WP04 | 6.2 |
| Model 2 effects included | WP04 (D24), WP11 | 5, 10 |
| Code support for per-run T_max and paired start volume | WP09a, WP10/WP12 follow-up | 8, 10 |
| Firmware "set limit" command and ceiling | WP09a | 8 |
| Generation pool G01–G10 | Researcher sessions in ChatGPT | 13 |
| Outtake (wrong-actuator) runs on the rig | U30 | 15 |
| Final version of this protocol | WP04 | — |
