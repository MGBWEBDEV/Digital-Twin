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
- Decisions (proposed vs approved), decision IDs: CONFIRMED D18, D19, D22; APPROVED D21, D23; PROPOSED D20.
- Assumptions / changes from previous artifacts: Board model (Adafruit Metro ESP32-S2) taken from StepExample only, recorded as unconfirmed. Pump speed values unknown.
- Blockers / outstanding questions: modified rig firmware not in repository; sensor not wired; pump speed/direction values unknown.
- Downstream dependencies: WP01 should use D18–D21 and inspect the rig firmware when supplied.
- Prompt/log reference or commit identifier if available: Claude Code session of 2026-11-25; commit to follow.
- Next suggested atomic task (do not execute): WP00 review part 2 (below).

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
