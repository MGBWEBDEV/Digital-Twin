# Atomic handoff — WP00 review (part 1)

- Agent / model version if known: Claude Code, model `claude-opus-5-5` (Opus 5.5)
- Status: Ready for review (part 1 applied; part 2 pending)
- Scope completed: Review of the ChatGPT-generated scaffold for logical flaws and workflow stoppers; researcher decisions recorded; mechanical and process fixes applied. Research-design items are listed below, not resolved.
- Created or modified paths:
  - moved `functional_requirements.md` → `design/functional_requirements.md` (status banner, D21 wording, serial latency in timing parameters)
  - `context/decisions.md` (Recorded column, ID/supersede rule, D18–D23, cross-reference notes on D02, D03, D06, D16)
  - `context/master_context.md` (learning outcome, rig status, host controller, FR renumbering)
  - `context/roadmap.md` (WP04 latency characterization, WP09 language/location)
  - `context/project_status.md`, `context/task_template.md`, `context/handoff_template.md`, `AGENTS.md` (handoffs saved as files; "revise" mode defined)
  - `README.md`, `references/README.md`, `.gitignore`, `scripts/fetch_labkit.sh`
  - this file
- Checks performed and actual results:
  - `git check-ignore`: reference `.vscode/` files no longer ignored; other `.vscode/` folders still ignored.
  - `scripts/fetch_labkit.sh` run into a scratch location: fetched pinned commit `a22a6b98…`; `diff -r` against `references/LabAutomationKits` reported no differences; commit file identical; script refuses to overwrite the bundled copy (exit 1).
  - SHA-256 of `references/research_draft.txt` matches the value in `references/README.md`.
- Decisions (proposed vs approved), decision IDs: CONFIRMED D18, D19, D22; APPROVED D21, D23; PROPOSED D20 (approved later, 2026-11-25).
- Assumptions / changes from previous artifacts: Board model (Adafruit Metro ESP32-S2) taken from StepExample only, recorded as unconfirmed. Pump speed values unknown.
- Blockers / outstanding questions: modified rig firmware not in repository; sensor not wired; pump speed/direction values unknown.
- Downstream dependencies: WP01 should use D18–D21 and inspect the rig firmware when supplied.
- Prompt/log reference or commit identifier if available: Claude Code session of 2026-11-25; commit to follow.
- Next suggested atomic task (do not execute): WP00 review part 2 (below).

## Part 2 progress

- **Topic 1, fidelity axis — resolved 2026-11-25.** D24 (Model 2 = Model 1 plus rig effects that are measurable; inclusion rule; visual settled-reading and safe-mark rules) and D25 (models compared by agreement of their pass/fail verdicts with the rig's, against margin to the limit; APPROVED in principle, details depend on topic 3). Updated `context/decisions.md` (D08 superseded, D13 narrowed), `context/master_context.md` (model and outcome sections), `context/roadmap.md` (WP04, WP05, WP11 details). Covers findings 1 and 4 below; finding 2 is addressed by D25's margin reporting and continues in topic 2.
- Researcher discussion points carried forward: communication lag is expected to be negligible but is measured once; tube priming may be the largest effect; a sensor-landmark task ("fill to X % using the sensor as reference, then timed") is a strong candidate for topic 2 because it combines sensor and timing near a limit.
- **Topic 2, scope — resolved 2026-11-25.** D26: selected set FR01 (control), FR03 (sensor), new FR09 (sensor-landmark fill to target, run at several margins), FR08 (safety); FR02, FR04–FR07 deferred (FR07 first reserve); controller only fills. `design/functional_requirements.md` restructured (active table, scenarios, deferred section); D14 narrowed; D24 note on switch-off level; master context and roadmap WP04 aligned. Covers finding 9 and the FR parts of findings 2 and 10 (FR01 weak physical oracle and response limit vs latency remain for WP03; dry-run protection no longer applies while draining is deferred).
- **Topic 3, ground truth — resolved 2026-11-25.** D27: independent firmware maximum-ON-time cut-off sized so overflow is physically impossible, mirrored in both simulation adapters, scored as FR08 failure; faulty controllers run on the rig behind it to give rig verdicts for D25. Repetitions per researcher: 5× in WP04 characterization; if consistent, one rig run per controller × scenario, repeats only near the safe mark; simulations run once. Updated decisions (D25 note), master context, roadmap (WP04, WP08, WP09, WP10, WP15), requirements parameters. Covers finding 3.
- **Topic 4, roadmap — resolved 2026-11-25.** D28: three parallel tracks; WP09 split into WP09a (rig I/O firmware, early) and WP09b (reference controller) to remove the WP04/WP08/WP09 deadlock; provisional WP08 before WP04; WP10 with TBD placeholders; WP12 test-first; WP14 independent of WP13; WP01+WP02 in one session allowed. Updated roadmap (table, tracks section, WP09a/WP09b, WP10, WP12 details), status table, README sequence. Covers finding 8.
- **Topic 5, controller generation and interface — resolved 2026-11-25.** D29: clean-room generation without repository access from a fixed prompt; different AI family from the one building models/evaluator (choice fixed in WP08); step-function controller (time, normalized sensor) → (intake, outtake); adapter normalizes sensor; harness injects sensor faults. Updated decisions, master context, roadmap (WP07, WP08, WP09b, WP14), AGENTS.md. Covers findings 5 and 6.
- **Topic 6, draft vs current plan — resolved 2026-11-25.** D30 (confirmed: no original controller program; reference is the clean-room AI controller), D31 (proposed: keep title, report as models of a digital twin). Reconciliation table added to `references/README.md`. Covers finding 7.
- **Part 2 complete.** Items deliberately left for later work packages: FR01 weak physical oracle, FR09 exact criteria and the response limit relative to serial latency (WP03); power-on/reset state and requests while busy (WP06); D05 wording (WP01); literature verification (WP17). Researcher actions: wire the sensor (D19), then approve WP00. (D20 and D31 approved 2026-11-25.) (Rig firmware need not be supplied: D32.)
- **Next suggested task (do not execute):** WP01 — physical system definition, optionally together with WP02 (D28).

## Open review findings for part 2 (research design)

1. **Fidelity axis (B5).** Model 1 and Model 2 may be mathematically equivalent (D08, D13). Fix a provisional fidelity axis early, e.g. Model 2 adds per-pump calibrated rates, start/stop lag or water delivered after OFF, sensor delay/hysteresis, serial latency (D21) and overflow behaviour.
2. **Open-loop tasks cannot separate the models (B6).** For timed tasks (FR01, FR02, FR05–FR07) the command trace does not depend on the plant; only sensor-driven tasks and physical-outcome checks can differ. Requirement and fault selection must account for this through a predefined rule.
3. **Ground truth for faulty controllers (B7).** Choose between bounded physical replay behind an independent safeguard (which must then exist identically in all environments and be logged) and defect-based ground truth with safe physical evidence.
4. **Measurement resolution (B8).** Add an early feasibility check: is the syringe reading uncertainty smaller than the predicted Model 1/Model 2 difference? Peak volume after OFF may not be readable by hand.
5. **Generation isolation and common-mode errors (B9).** Controller generation for WP14 must run in an isolated context (fixed prompt, no repository access) so that the requirements, tests and fault catalogue cannot leak. The same AI family writes models, evaluator and controller; researcher review of oracles is the explicit gate.
6. **Interface shapes the fault space (B10).** Decide what stays inside the controller (sensor polarity, timing API). The simulation-only "missing transition" scenario needs explicit harness support in WP07.
7. **Draft vs master context (B11).** The draft's reference controller (original Arduino controller), iterative "increase complexity" plan and title ("Digital Twin" while no connected twin is built) need a recorded decision.
8. **Roadmap (C12).** The critical path is fully serial and blocked by hardware from WP08. Candidates: provisional WP08; WP12 evaluator test-first against a stub plant; WP10/WP11 in parallel; WP14 natural generation after WP12; clarify WP09 vs WP14 prompts.
9. **Scope (C13).** Reduce the eight requirements to three or four (e.g. FR01, FR03, FR08, possibly FR06); consider merging WP01+WP02 and WP15+WP16.
10. **Requirements details (D).** FR01/FR02 physical oracles weak ("measurable amount"); no lower bound or dry-run protection for draining; response limit relative to serial latency; power-on/reset state and requests while busy unspecified; D05 wording ambiguous.
