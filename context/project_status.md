# Project status

Scaffold plus WP00 review fixes. No hardware measurements, source code, test runs, completed research artifacts or empirical findings are included. The research draft text and the StepExample firmware are bundled; the rig runs StepExample with only a pump identifier changed (D32), so no separate rig firmware is needed.

Statuses: Pending / In progress / Provisional / Blocked / Ready for review / Approved. A deliverable is not approved merely because an agent generated it. WP00 = initialized scaffold; review upon extraction.

| WP | Status | Owner | Notes |
|---|---|---|---|
| WP00 | Approved | Claude Code (review fixes) | Scaffold reviewed and fixed 2026-11-25 (see `context/handoffs/WP00_review.md`); decisions D18–D32 recorded. Approved by researcher 2026-11-25 |
| WP01 | Approved | Claude Code | `design/physical_system.md` (2026-11-25). Components, boundary, states, I/O, constraints, unknowns U01–U31 and a rig checklist; details from StepExample marked "derived from code". D33 (D05 wording) approved. Placeholder values P01–P19 added in section 12 (D34). Handoff: `context/handoffs/WP01_WP02_physical-conceptual.md`. Approved by researcher 2026-11-25; "derived from code" items and placeholders still to be replaced after the rig check/WP04 |
| WP02 | Approved | Claude Code | `design/conceptual_model.md` with three Mermaid diagrams (2026-11-25); boundaries B1–B4, control/feedback paths, delay points, abstractions. Same handoff as WP01. Approved by researcher 2026-11-25 |
| WP03 | Approved | Claude Code | `design/functional_requirements.md` completed 2026-11-25: FR01, FR03, FR09, FR08 with numbered logical/physical checks, placeholder parameters R01–R11 (D34 rule), scenarios S1–S5, infeasibility list, hand-calculated Model 1 oracles. D35 approved. Handoff: `context/handoffs/WP03_functional-requirements.md`. Approved by researcher 2026-11-25; numbers remain placeholders (D34) |
| WP04 | Pending | — | Needs WP09a and sensor wiring (D19); protocol and pump-only measurements may start earlier with approval |
| WP05 | Pending | — | WP02; provisional before WP04, final after |
| WP06 | Approved | Claude Code | `design/controller_behavior.md` (2026-11-25): constraints K1–K7, states, Mermaid state machine and per-call order, transition table mapped to WP03 checks, exceptions X1–X11, evaluator inference, scenario paths, fault-space mapping. D36 approved. Handoff: `context/handoffs/WP06_controller-behavior.md`. Approved by researcher 2026-11-25 |
| WP07 | Pending | — | WP02–03, WP06; WP05 provisional suffices |
| WP08 | Pending | — | WP03, WP05–07; provisional before WP04, final after |
| WP09a | Pending | — | WP01, WP07; starts from bundled StepExample (D32); researcher approval before upload |
| WP09b | Pending | — | WP03, WP06–08, WP09a; researcher safety review |
| WP10 | Pending | — | WP05 (provisional), WP07, WP09a interface; TBD placeholders until WP04 |
| WP11 | Pending | — | WP05 final (needs WP04), WP10 |
| WP12 | Pending | — | WP03, WP08 (provisional); test-first with stub plant; final verification with WP10–11 |
| WP13 | Pending | — | WP04, WP08, WP09b, WP10–12; physical access |
| WP14 | Pending | — | WP03, WP06, WP08, WP09b, WP12 |
| WP15 | Pending | — | WP08, WP12–14 |
| WP16 | Pending | — | WP13, WP15 |
| WP17 | Pending | — | Relevant outputs WP01–16 |

## Current blockers / missing inputs

- Complete extracted research draft/PoC text bundled at `references/research_draft.txt`; original raw attachment was not exportable. Review against current project context before approving the baseline.
- Pins, board, speed defaults and all other "derived from code" details in `design/physical_system.md` need the researcher's visual rig check (checklist in section 10 of that file). Many physical details are TBD (unknowns U01–U31).
- Level sensor installed but not wired (D19): sensor-dependent rig tests blocked; design and simulation can proceed.
- Fixed pump speed/direction approved (D20); values used so far are probably the StepExample host-script defaults (full speed, direction True; D32).
- Hardware verification, physical measurements, tolerances and fidelity distinction pending.
- Claude Code verified working in the repository (2026-11-25); Codex not verified.

## Next task

WP07 — software architecture (unblocks WP09a and WP10); provisional WP05 may run in parallel. Researcher: rig checklist (`design/physical_system.md` section 10). Alongside: researcher wires the sensor (D19) and marks the safe limit (U26).

## Change log

- WP00: scaffold initialized; no research tasks executed.
- Reference update: research draft text recovered and bundled. LabAutomationKits code remains missing.

- Reference update: researcher supplied the exact `Electronics/Firmware/StepExample` URL; remote access failed in packaging. Local fetch script added, source still pending. No research package completed.

- Workspace recovery, 25 November 2026. The complete StepExample directory and upstream license are included under `references/LabAutomationKits/`. Every file was checked against upstream commit `a22a6b981e1f0cfd5d0311b571e7998846d37a7d`.

- WP00 review part 1, 2026-11-25 (Claude Code). Researcher decisions recorded (D18–D23); requirements draft moved to `design/`; master context, README, roadmap (WP04, WP09 notes), templates and agent instructions aligned; `.gitignore` keeps reference `.vscode/` files; fetch script pinned to the reference commit and verified to reproduce the bundled snapshot byte-for-byte. Status line on firmware corrected.

- WP00 review part 2, topic 1, 2026-11-25 (Claude Code with researcher). Fidelity axis approved (D24, supersedes D08) and model comparison criterion approved in principle (D25); master context and roadmap WP04/WP05/WP11 updated.

- WP00 review part 2, topic 2, 2026-11-25 (Claude Code with researcher). Requirement set reduced to FR01, FR03, FR09 (new), FR08 (D26); deferred requirements kept in `design/functional_requirements.md`.

- WP00 review part 2, topic 3, 2026-11-25 (Claude Code with researcher). Ground truth via independent firmware cut-off mirrored in simulation, and reduced repetition rule (D27); roadmap WP04, WP08, WP09, WP10, WP15 updated.

- WP00 review part 2, topic 4, 2026-11-25 (Claude Code with researcher). Roadmap re-sequenced into paper, rig and software tracks (D28); WP09 split into WP09a (rig I/O firmware, early) and WP09b (reference controller) to remove the WP04 → WP08 → WP09 → WP04 deadlock.

- WP00 review part 2, topic 5, 2026-11-25 (Claude Code with researcher). Clean-room controller generation by a different AI family and step-function controller interface (D29); AGENTS.md rule added.

- WP00 review part 2, topic 6, 2026-11-25 (Claude Code with researcher). No original controller program exists (D30); title kept with "models of a digital twin" framing proposed (D31); draft reconciliation table added to `references/README.md`. WP00 review complete.

- 2026-11-25: researcher confirmed the rig firmware is StepExample with only a pump identifier changed (D32); "add rig firmware" removed from blockers and roadmap gates.

- 2026-11-25: researcher approved D20 (fixed pump speed and direction) and D31 (keep title; models of a digital twin).

- 2026-11-25: scaffold decisions settled by researcher: D07, D09, D11, D17 approved; D08 marked superseded by D24; D10 left proposed until WP08.

- 2026-11-25: WP00 approved by researcher.

- 2026-11-25: WP01 and WP02 executed together (D28) by Claude Code; `design/physical_system.md` and `design/conceptual_model.md` ready for review; D33 proposed (D05 wording). No hardware inspected, no measurements.
- 2026-11-25: placeholder values P01–P19 added to `design/physical_system.md` section 12 at the researcher's request (D34); not for physical runs or results.
- 2026-11-25: researcher approved WP01, WP02 and D33.
- 2026-11-25: researcher approved placeholder values P01–P19 as they are (D34); they remain placeholders, not facts.
- 2026-11-25: WP03 completed by Claude Code (ready for review); D35 proposed.
- 2026-11-25: researcher approved WP03 and D35.
- 2026-11-25: WP06 completed by Claude Code (ready for review); D36 proposed.
- 2026-11-25: researcher approved WP06 and D36.
