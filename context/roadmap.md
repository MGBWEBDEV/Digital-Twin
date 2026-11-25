# Atomic work-package roadmap

Execute one assigned WP (or smaller explicitly scoped subtask) per session. Dependencies are gates for final approval; provisional work may proceed when stated, with unresolved dependencies marked. WP00 creates the scaffold, not research results. Every package follows AGENTS.md and records artifact paths, checks, assumptions and handoff. Researcher reviews before marking approved. Use WP IDs in commits and experiment records.

| WP | Dependencies | Artifact(s) | Completion criteria |
|---|---|---|---|
| WP00 Initialization | None | README, agent instructions, context files, directories | Scaffold created and verified; no research work claimed |
| WP01 Physical system definition | Existing hardware evidence (rig firmware when supplied) | design/physical_system.md | Components, boundary, states, I/O, constraints and unknowns documented; unverified details marked |
| WP02 Conceptual model | WP01 (may be done in the same session) | design/conceptual_model.md + diagram | Hardware entities, physical flows, control/feedback and boundaries clear; implementation-independent |
| WP03 Functional requirements | WP01–02 | design/functional_requirements.md | Small, feasible, identifiable tasks with initial conditions, completion and measurable criteria; provisional tolerances flagged |
| WP04 Physical characterization | WP01, WP03, WP09a; hardware access (rig firmware supplied, sensor wired) | experiments/physical_characterization.md, experiments/data/ | Safe approved procedure, repeatable data, uncertainty, calibration vs held-out validation; enough evidence to parameterize intended differences. Protocol and pump-only measurements may start before WP09a with the existing self-expiring timed-step firmware, with researcher approval |
| WP05 Mathematical models | WP02; WP04 for final version | design/mathematical_models.md | Two specified physical models, units, equations, assumptions, boundaries and justified meaningful difference; provisional version allowed before WP04 |
| WP06 Controller behavior | WP03 | design/controller_behavior.md + diagram(s) | Expected states/actions/transitions/timing and exceptions specified independently of code |
| WP07 Software architecture | WP02–03, WP06; WP05 (provisional suffices) | design/software_architecture.md + diagrams | Common interface, physical and simulated adapters, clock, class responsibilities, equation mapping, logger/evaluator boundaries, safety cut-off placement clear |
| WP08 Experiment protocol | WP03, WP05–07; WP04 for final numbers | experiments/experimental_protocol.md | Independent checks, scenarios, conditions, tolerances, data handling, outcome rules, generation budget and fault-selection procedure defined before experiments; provisional version allowed before WP04 |
| WP09a Rig I/O firmware and serial adapter | WP01, WP07 (provisional suffices); rig firmware supplied | src/esp32/, src/shared/ (hardware adapter) | Both pumps switch ON/OFF over serial; sensor state reported; host-side logging; independent maximum-ON-time cut-off logged when it fires, starting with a conservative limit and updated after WP04; reviewed for safe execution (researcher approval before upload) |
| WP09b Reference controller | WP03, WP06–08, WP09a | src/shared/ (controller) | Same controller source runs against the rig adapter and a simulation adapter; reviewed for safe physical execution (researcher approval required); labelled candidate until WP13 |
| WP10 Model 1 | WP05 (provisional suffices, parameters as TBD placeholders), WP07, WP09a interface; WP04 values for final version | src/model_1/ | Implements basic physics, sensor/time, interface, cut-off and logging; mathematical checks pass |
| WP11 Model 2 | WP05 final (needs WP04), WP10 | src/model_2/ | Implements only effects included under D24; comparable interface/logs; mathematical checks pass |
| WP12 Testing framework | WP03, WP08 (provisional suffices); WP10–11 for final verification | src/testing/ | Built test-first against a stub plant; identical scenarios and functional acceptance criteria in both models; independent evaluator checks verified |
| WP13 Physical/simulation validation | WP04, WP08, WP09b, WP10–12 | experiments/model_validation.md, experiments/logs/ | Safe paired tests, mathematical consistency, held-out physical evidence, accuracy and limitations characterized |
| WP14 AI controller generation/error identification | WP03, WP06, WP08, WP09b, WP12 | experiments/controller_error_catalogue.md, experiments/prompts/, versioned code | Two suitable documented fault types, origin and root cause established; follow preset selection/fallback rules |
| WP15 Comparative controller error experiments | WP08, WP12–14 | experiments/controller_error_results.md, experiments/logs/ | Same controllers/scenarios/oracles; paired detection outcomes with independent ground truth or inconclusive label |
| WP16 Analysis/discussion | WP13, WP15 | report/experimental_discussion.md | Evidence-supported comparison, limitations and thesis transferability; no unsupported generalization |
| WP17 Report integration | Relevant WP01–16 outputs | report/experiments_and_results.md | Concise report with traceable methods/results/limitations, consistent with PoC and project scope |

## Tracks (D28)

Three tracks can progress in parallel; arrows show the main gates. Provisional work is allowed where the table says so; final approval still follows all dependencies.

```
PAPER (no hardware)     WP01 → WP02 → WP03 → WP06 → WP07 → WP08 (provisional → final after WP04)
RIG   (hardware)        rig firmware supplied + sensor wired → WP09a → WP04 → WP13
SOFTWARE (no hardware)  WP05 (provisional) → WP10 → WP11 (after WP04/WP05 final);  WP12 test-first
JOIN                    WP09b → WP14 → WP15 → WP16 → WP17
```

The researcher-side gates of the rig track are supplying the modified rig firmware (D18) and wiring the sensor (D19).

## Task details

### WP01 — Physical system definition
Inspect confirmed facts and hardware reference documentation. Document real entities, boundary, variables, controller-accessible signals vs researcher observations, actuator/sensor constraints, unknowns and evidence sources. Do not invent hardware specifications. No equations beyond shared physical principle, no downstream design.

### WP02 — Conceptual model
Define component relationships, water transfer and information exchange, external boundaries and initial abstraction exclusions. Supply a diagram (Mermaid or text where appropriate). Label assumptions and actual vs conceptual descriptions.

### WP03 — Functional requirements
Choose a small set from master context candidates. Define IDs, tasks, preconditions, logical and physical expected outcomes, completion/safety and acceptance criteria; identify infeasible requirements given Boolean sensor and no direct volume measurement. Mark provisional numerical criteria TBD; plan mathematical checks independently.

### WP04 — Physical characterization
First design and obtain researcher approval for safe experiments; then researcher supplies measured data. Read initial/final syringe volume, commanded pump duration and sensor transitions; characterize host–ESP32 command and sensor-report latency (D21); investigate repeatability. Measure the D24 candidate effects (tube priming, run-on after OFF, sensor trigger point, reporting/communication delay; switch-off level only if draining tasks return, D26) using settled visual readings and host timestamps, and compare each with the syringe reading resolution and timestamp resolution; report early whether any effect is measurable (feasibility check before Model 2 is built). Repeat each basic measurement 5 times and report the spread (D27). Derive the firmware maximum ON time from the intake calibration and syringe capacity (D27). Separate parameter-fitting observations from held-out validation. No fabricated readings; can deliver protocol only as partial if no hardware access. Do not deploy code or activate physical equipment without approval.

### WP05 — Mathematical modelling
Specify Model 1 and Model 2 with units, states, inputs, time updates, transfer and sensor rules, initialization, physical/operational boundaries, assumptions and parameter source. Confirm differences are not mathematically equivalent under identical assumptions. Apply the D24 inclusion rule to WP04 evidence and list included and excluded effects with reasons. No invented rates, capacity or thresholds. Document how boundary events remain observable.

### WP06 — Controller behavioral modelling
Derive normal and exceptional paths from requirements. States/actions/conditions/timers/transitions, guard conditions and termination, possible state machine diagram. Keep normative behavior separate from AI implementation strategy; map requirement IDs to expected states and observable events.

### WP07 — Software architecture
Define minimal classes/interfaces and responsibilities, physical vs simulation adapters, consistent timing/clock semantics and update order, equation-to-method mapping, logger/evaluator separation. Controller cannot access simulator-only ground truth. Document choices and tradeoffs; no unnecessary frameworks.

### WP08 — Experimental protocol
Specify mathematical verification cases with independent expectations, held-out physical validation, controller scenarios and common evaluation rules. Define data schema, repeatability, initial conditions, units, metrics, acceptance tolerances, classification, independent evidence and safety. Predefine generation budget, prompt constraints, fault eligibility/selection and fallback injection; avoid outcome-driven selection. Define the rig run plan and the near-limit repeat rule (D27) and the verdict comparison rules (D25). Mark unresolved prerequisites explicitly.

### WP09a — Rig I/O firmware and serial adapter
Start from the researcher-supplied rig firmware (D18). Extend it as a serial I/O server for both pumps and the sensor (D21), with an independent maximum-ON-time cut-off that is logged when it fires (D27); start with a conservative limit and update it from WP04 calibration. Generate the host-side serial hardware adapter and logger. Document code generation prompts and changes; verify interface compatibility. Review and bound physical execution; no unapproved upload or actuation.

### WP09b — Reference controller
Generate the shared Python reference controller against the WP07 interface. Verify that the same source runs against the rig adapter (WP09a) and a simulation adapter. Document prompts and changes. Reference controller is only considered physically validated after evidence from WP13; until then label it candidate.

### WP10 — Model 1 implementation
May start with TBD placeholder parameters before WP04; replace them with WP04 values for the final version. Generate the minimal basic model with volume, intake/outtake transfer, Boolean sensor, clock and log support. The simulation adapter reproduces the firmware maximum-ON-time cut-off exactly, shared with Model 2 (D27). Use shared interface; verify independent mathematical cases, unit conventions and boundary handling.

### WP11 — Model 2 implementation
Generate only the Model 2 effects included under D24 (per WP05), without changing controller-facing API or unrelated execution semantics. Verify the extended mathematical behavior and document differences with Model 1. Avoid duplicate independent changes that confound comparison.

### WP12 — Testing framework
Build test-first from WP03/WP08 against a stub plant, then verify with both models. Generate reusable runner, scenario initialization, structured logs, logical and physical outcome checks and independent mathematical verification. Check evaluator using independently hand-derived passing/failing cases. Keep model-specific verification separate from common controller requirements; report inconclusive when evidence is insufficient.

### WP13 — Physical and simulation validation
Run approved reference operations physically and equivalent operations in both simulations. Compare held-out measured volumes and sensor transitions at corresponding points; document discrepancies, repeatability and tolerance outcomes. Evaluate scope of reference controller validity. Do not claim empirical validation from simulations alone. Record iterations and avoid reusing held-out data as if independent after tuning.

### WP14 — AI generation and error identification
Use predeclared correct-code prompts and generation budget. Record outputs and behavior; map violations to source logic. Select two error types with predefined eligibility criteria, using isolated controlled injection only if appropriate under protocol. Keep naturally occurring and injected origins distinct; independently substantiate that defects can trigger failures. No cherry-picking Model 2 success. If selecting using exploratory scenarios, reserve separate evaluation scenarios when feasible and disclose limitations.

### WP15 — Comparative experiments
Run each selected faulty controller and validated reference where applicable on both models, matching initial conditions and test rules. Capture logs, evaluate same physical/logic requirements, confirm true failure independently where feasible, classify each paired outcome. Unsafe physical execution prohibited without explicit safeguards and approval; faulty controllers run on the rig only behind the D27 cut-off, following the D27 repetition rule. Untriggered faults and unknown ground truth are not false negatives.

### WP16 — Analysis/discussion
Compare model accuracy, paired detections, false alarms, missed/inconclusive outcomes and limitations. Discuss complexity/fidelity relationship without presupposing Model 2 superiority. Two error types do not establish universal reliability thresholds. Describe reusable approach for later thesis.

### WP17 — Report integration
Write concise Experiments and Results chapter per master context; trace claims to actual artifacts and data, distinguish proposed and validated, and verify academic references against originals. Do not turn research project into industrial thesis.
