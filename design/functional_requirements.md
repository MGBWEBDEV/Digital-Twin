# Functional requirements for the water-tank controller test suite (WP03)

> **Status: Approved by researcher 2026-11-25 (agent-completed by Claude Code).** Completes the provisional draft adopted by D23 and reduced by D26, aligned with `design/physical_system.md` (WP01) and `design/conceptual_model.md` (WP02). The FR numbering is authoritative. Selected set (D26): FR01, FR03, FR09, FR08; FR02 and FR04–FR07 are deferred (section 11). Numbers are **placeholders** under the D34 rule (P-IDs from WP01, R-IDs below): usable for design, simulation and software tests, never for physical runs or reported results until replaced. D35 (run completion and observation points) approved.

The suite evaluates AI-generated controller code (host-side Python, D21) against one behavioural specification in three environments: the rig, Model 1 and Model 2. The specification is fixed before any controller is generated (D29). A controller may pass every scenario; each failure needs evidence linking the observed behaviour to a numbered check below.

## 1. Selected requirements and their roles (D25, D26)

| ID | Task | Role in the study |
|---|---|---|
| FR01 | Fill for a requested time | Control task; the plant does not influence the commands, so models are expected to agree. Also basis of intake calibration (WP04) |
| FR03 | Fill until the sensor is wet | Sensor-dependent task |
| FR09 | Fill to a target volume above the sensor level, using the sensor as reference | Near-limit task; run at several margins to the safe mark |
| FR08 | Safety and bounded operation | Applies to every run |

## 2. What can be observed (from WP01/WP02)

- **Controller side (boundary B2, D29).** At each call the controller receives the current time and the normalized sensor value (wet = True) and returns intake ON/OFF and outtake ON/OFF. It never receives volume, flow or pump state. Logical checks therefore use only the harness log of these inputs and outputs.
- **Task request.** At the start of a run the controller receives the task (FR01, FR03 or FR09), its parameter (duration or target volume) and the known parameters (section 4). Nothing else is given during the run.
- **Observer side (boundary B4).** On the rig: settled syringe readings before and after the run (D24, D33) and host logs. In the models: the modelled volume over the whole run, including peak and computed overflow (D07). Physical checks use these.
- **No completion output (proposed D35).** The D29 interface has no "done" or status output. A run therefore lasts a fixed observation time T_end set by the harness; "completion" means the pumps are OFF and stay OFF until T_end. A refused or impossible request can only show as "no ON command".

## 3. Common definitions

| Term | Definition |
|---|---|
| Run | One task request, from the first controller call (t = 0) to T_end (R08) |
| Call period Δt_c | Interval between controller calls (R01); the same in all environments |
| ON interval | From the first call that returns ON for a pump to the first later call that returns OFF (harness log) |
| t_w | Time of the first call whose sensor input is wet. Measured at the controller interface, so serial latency is not part of the logical response check; its physical effect shows in the volume checks |
| V0, V_end | Settled volume at the start, settled volume after T_end plus settling time (R09). In the models: modelled volume at the same points |
| V_peak | Highest volume during the run. Models only; on the rig undetermined unless it can be read as a settled level (D24) |
| Cut-off | Independent maximum ON time in firmware and in both simulation adapters (D27; P11) |
| Single interval rule | In every fill task the intake has exactly one ON interval. Reason: each extra start or stop adds priming and run-on on the rig, which would make the physical outcome depend on an arbitrary pause pattern |

All three environments start a run with both pumps OFF, the sensor state recorded and V0 recorded.

## 4. Parameters

Rig parameters come from `design/physical_system.md` section 12 (P01–P19). Requirement parameters below are placeholders under D34, to be fixed in WP08 after WP04.

| ID | Parameter | Placeholder | Basis |
|---|---|---|---|
| R01 | Controller call period Δt_c | 0.1 s | Round value; fixed in WP07 |
| R02 | Start limit t_start (first intake ON at or before) | 0.5 s | A few call periods |
| R03 | Timing tolerance ε_t | 0.2 s | Two call periods (commands are quantized to calls) |
| R04 | Response limit t_resp (from t_w to intake OFF) | 0.1 s | One call period: the controller should switch OFF at the call that first sees wet, or the next one |
| R05 | Volume tolerance ε_V | 2 mL | Two readings of ±0.5 mL (P03) plus run-to-run spread ±0.5 mL (P08), rounded up |
| R06 | Sensor-wait deadline T_deadline (stop if the sensor is not wet by then) | 30 s | Expected time to the sensor from P10 is (24 − 5) / 1 = 19 s; about 1.5 times that. Stays below the cut-off P11 = 45 s so the controller's own safety acts first |
| R07 | Known parameters given to the controller | V_sensor = P05, Q_in = P06, T_deadline = R06 | D29 (prompt contains known parameters only) |
| R08 | Observation time T_end | 60 s | Longer than the longest expected fill (43 s, section 9) and the cut-off |
| R09 | Settling time before a rig reading | 10 s | Round value; WP04 |
| R10 | FR01 requested durations | 10 s, 20 s | From P10 these end at 15 and 25 mL |
| R11 | FR09 targets | 30, 40, 45, 48 mL | Margins 20, 10, 5, 2 mL to the safe mark P04 = 50 mL (D25 margin analysis) |

Valid requests only: FR01 durations keep V0 + Q_in × duration below the safe mark; FR09 targets lie above V_sensor and at or below the safe mark. Invalid-request handling is out of scope (section 7).

## 5. Requirements

Checks are numbered so that the evaluator (WP12) and failure analysis can cite them. L = logical (harness log), P = physical (volume).

### FR01 — Fill for a requested time

- **Request:** duration T_fill (R10).
- **Initial condition:** both pumps OFF; V0 recorded; V0 + Q_in × T_fill ≤ safe mark − ε_V. The sensor state does not matter.
- **Expected behaviour:** run the intake for T_fill, then stop.
- **FR01-L1:** the intake has exactly one ON interval, starting at or before t_start.
- **FR01-L2:** its length is within ε_t of T_fill.
- **FR01-P1:** V_end − V0 is within ε_V of the volume the intake calibration predicts for T_fill. Placeholder calibration: Q_in × T_fill (P06). The calibration comes from separate WP04 runs; runs used to fit it are not scored here (calibration vs held-out, master context).

This replaces the earlier "end volume exceeds start volume by a measurable amount", which accepted any duration error.

### FR03 — Fill until the sensor is wet

- **Request:** none beyond the task.
- **Case A, sensor dry at start (V0 < V_sensor):**
  - **FR03-L1:** the intake has exactly one ON interval, starting at or before t_start.
  - **FR03-L2:** if t_w occurs, the intake is OFF at a call no later than t_w + t_resp. (If the sensor never becomes wet, FR08-L2 applies.)
  - **FR03-P1:** V_sensor − ε_V ≤ V_end ≤ V_sensor + ε_V. The upper bound limits overshoot from response, latency, sensor delay and run-on; V_sensor is the WP04-measured level (P05 for now).
- **Case B, sensor wet at start:**
  - **FR03-L3:** no ON command for either pump at any call during the run, not even a single-call pulse.
  - **FR03-P2:** |V_end − V0| ≤ ε_V.

### FR09 — Fill to a target volume above the sensor level

- **Request:** target V_target (R11), with V_sensor < V_target ≤ safe mark.
- **Known to the controller:** V_sensor, Q_in, T_deadline (R07). The start volume is not known; the sensor edge is the reference.
- **Case A, sensor dry at start:**
  - **FR09-L1:** the intake has exactly one ON interval, starting at or before t_start, and is still ON at t_w (it does not stop at the sensor).
  - **FR09-L2:** the intake switches OFF at time t_off with |(t_off − t_w) − T_extra| ≤ ε_t, where T_extra = (V_target − V_sensor) / Q_in, computed by the evaluator from the same known parameters given to the controller. This checks the controller's calculation; FR09-P1 checks whether that calculation is physically right.
  - **FR09-P1:** |V_end − V_target| ≤ ε_V.
- **Case B, sensor wet at start:** the level above the sensor is unknown, so the target cannot be reached reliably.
  - **FR09-L3:** no ON command for either pump at any call (as FR03-L3).
  - **FR09-P2:** |V_end − V0| ≤ ε_V.

The earlier draft also required the controller to "report that the precondition failed". The D29 interface has no output for that, so it is removed (proposed D35).

### FR08 — Safety and bounded operation (every run)

- **FR08-L1:** the outtake is never ON (the selected tasks only fill, D26).
- **FR08-L2:** if the sensor is not wet by T_deadline in an FR03 or FR09 run, the intake is OFF at a call no later than T_deadline + t_resp.
- **FR08-L3:** after the intake's ON interval ends, both pumps stay OFF until T_end (no restart, even if the sensor input changes).
- **FR08-L4:** the cut-off does not fire. A cut-off is an FR08 failure, never a pass (D27).
- **FR08-P1:** V_end ≤ safe mark (P04).
- **FR08-P2 (models only):** V_peak ≤ safe mark and no computed overflow above capacity C. On the rig this check is undetermined unless the peak can be read as a settled level (D24); overflow is never caused physically.

## 6. Verdicts

Score each check pass, fail or undetermined. Undetermined is used when a required value is still a placeholder for a reported result, or when observation resolution cannot establish the result. A scenario passes only when all applicable checks pass; any failed check makes it fail; undetermined checks are kept in the report.

For each run, retain the prompt and controller version, environment (rig, Model 1, Model 2) and its version, scenario parameters, every controller call (time, sensor input, outputs), firmware or adapter events (including cut-off), volume observations with units, and the end reason. The same controller, scenarios and checks are used in all three environments. Each environment's own t_w is used, so the response checks are evaluated independently per environment.

## 7. Infeasible or excluded requirements

| Requirement idea | Why it is infeasible or excluded |
|---|---|
| Any task that needs the actual volume during the run | The controller never sees volume (B2, D07) |
| Fill to a target below the sensor level | Without the sensor edge the start volume is unknown; only open-loop timing from an unknown start (FR01-like) is possible |
| Fill to a target when the sensor is already wet | Level above the sensor is unknown; required behaviour is "do nothing" (FR03-L3, FR09-L3) |
| Controller reports success or failure | No status output under D29 (proposed D35) |
| Verifying that a pump really runs, from the controller | Not observable by the controller; only the researcher sees it |
| Checking the transient peak on the rig | Only settled levels are read (D24); undetermined |
| Timing the controller's response against the physical sensor edge on the rig | The physical edge is only seen through the firmware report; logical response is measured at the controller interface, the physical lag shows in FR03-P1 and FR09-P1 |
| Handling of invalid requests (target above the safe mark, duration that would overfill) | Not selected; would add a further task. Candidate reserve after FR07 |
| Draining tasks (FR02, FR04–FR07) | Deferred by D26 |
| Power-on/reset behaviour and requests while busy | Left to WP06 |

## 8. Test scenarios (placeholders; final values in WP08)

| ID | Setup | Request | Checks |
|---|---|---|---|
| S1 | V0 = 5 mL (P10) | FR01, T_fill = 10 s and 20 s (two runs) | FR01, FR08 |
| S2 | V0 = 5 mL | FR03 | FR03 case A, FR08 |
| S3 | V0 = 30 mL (sensor wet) | FR03; FR09 with V_target = 40 mL (two runs) | FR03 case B, FR09 case B, FR08 |
| S4 | V0 = 5 mL; the harness holds the sensor input dry for the whole run, in all environments (D29); the plant is unaffected | FR03 | FR08 (L2 in particular) |
| S5 | V0 = 5 mL | FR09, V_target = 30, 40, 45, 48 mL (four runs) | FR09 case A, FR08; record margin to the safe mark |

Ten runs per controller per environment. S4 on the rig is safe with the placeholders (stops at about 35 mL, section 9) but, like every rig run, needs researcher approval.

## 9. Independent hand calculations (Model 1, placeholder values)

These expected results are worked out by hand from the requirements and placeholders, not from any model code. They serve as oracles for testing the evaluator and Model 1 (WP10, WP12) and should be rechecked by the researcher. Model 1: Q_in = 1.0 mL/s, instant start/stop, sensor wet exactly at 24 mL. Results may differ by up to one call period of flow (0.1 mL) depending on event ordering (WP07).

| Scenario | Expected Model 1 result for a correct controller |
|---|---|
| S1, 10 s | Intake ON 0–10 s; V_end = 15 mL; FR01-P1 compares 10 mL with 10 mL |
| S1, 20 s | Intake ON 0–20 s; V_end = 25 mL (sensor becomes wet at 19 s and is ignored) |
| S2 | t_w = 19.0 s; intake OFF at 19.0–19.1 s; V_end ≈ 24.0–24.1 mL; within 24 ± 2 mL |
| S3 | No ON command; V_end = 30 mL in both runs |
| S4 | Water passes the sensor at 19 s but input stays dry; intake OFF at 30.0–30.1 s; V_end ≈ 35 mL ≤ 50 mL; FR08-L2 passes |
| S5, 30 mL | T_extra = 6 s; OFF at 25 s; V_end = 30 mL |
| S5, 40 mL | T_extra = 16 s; OFF at 35 s; V_end = 40 mL |
| S5, 45 mL | T_extra = 21 s; OFF at 40 s; V_end = 45 mL |
| S5, 48 mL | T_extra = 24 s; OFF at 43 s; V_end = 48 mL; 2 s before the cut-off at 45 s |
| Faulty example: intake never switched OFF in S2 | Cut-off at 45 s; V_end = 50 mL = safe mark: FR03-L2, FR08-L4 fail; FR08-P1 passes exactly at the limit |

The last row shows that a cut-off sized to the safe mark (P11) leaves no margin: in Model 2, run-on after the cut-off would exceed the mark. WP08 should size the cut-off with margin below the safe mark, or below capacity as D27 states, and decide which.

## 10. Mapping a failure to controller logic

For each failure, record the check ID, the triggering input, the expected command, the observed command and the measured consequence. Example: an intake ON pulse in S3 violates FR03-L3 even if the syringe shows no measurable change. Inspect the generated code for the start-condition check and confirm the suspected cause by replaying the same input. If the controller met FR03-L2 but FR08-P1 or FR03-P1 failed, investigate delivered volume, stopping delay and headroom before blaming the controller; the cause may be the plant or the tolerance. Keep the cause open until evidence identifies it.

## 11. Deferred requirements (D26)

Not part of the selected set. Kept for reference; FR07 is the first reserve if time allows. IDs are not reused.

| ID | Controller task | Logical acceptance | Physical acceptance | Reason deferred |
|---|---|---|---|---|
| FR02 | Drain for a specified time | Only outtake turns ON. Its ON interval matches the requested duration within the timing tolerance, then it stays OFF. | End volume is measurably below start volume. | Mirror of FR01 |
| FR04 | Drain until the sensor is inactive | If initially inactive, issue no ON command. Otherwise run only outtake and switch it OFF within the response limit after deactivation. | Starting above the level, water falls through the calibrated deactivation range. With the target already met, volume stays within measurement tolerance of its initial value. | Only task where the sensor switch-off level matters; dropping it simplifies Model 2 |
| FR05 | Add and then remove a specified volume | Command intake followed by outtake. Stop each pump before starting the next phase. | Read volume before transfer, between phases and after transfer. For each leg, the absolute difference between the measured transfer and its target must be within volume tolerance. | Covered more cleanly by FR09 |
| FR06 | Fill, wait, then drain | Execute the three phases in order. Both pumps stay OFF throughout the specified wait, whose duration must meet timing tolerance. | Volume rises, remains stable within measurement tolerance during the wait, then falls. | Sequence logic only; models necessarily agree |
| FR07 | Repeat a fill-and-drain cycle | Complete exactly the requested cycle count, in order. After the final cycle both pumps stay OFF until a new request. | Check the specified fill and drain outcomes separately in every cycle. | Sequence logic only; first reserve because it tends to provoke typical AI faults (cycle miscounting) |

If a deferred task returns, its criteria must be rewritten in the style of section 5 (single interval rule, numbered checks, no status output). Deferred scenarios: timed drain, threshold crossing while draining, target already met for draining, missing transition while draining, volume transfer, ordered sequence, cycle count.
