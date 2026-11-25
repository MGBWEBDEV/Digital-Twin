# Project status

Scaffold plus WP00 review fixes. No hardware measurements, source code, test runs, completed research artifacts or empirical findings are included. The research draft text and the StepExample firmware are bundled; the rig runs StepExample with only a pump identifier changed (D32), so no separate rig firmware is needed.

Statuses: Pending / In progress / Provisional / Blocked / Ready for review / Approved. A deliverable is not approved merely because an agent generated it. WP00 = initialized scaffold; review upon extraction.

| WP | Status | Owner | Notes |
|---|---|---|---|
| WP00 | Ready for review | Claude Code (review fixes) | Scaffold reviewed 2026-11-25; part 1 fixes applied (see `context/handoffs/WP00_review.md`). Part 2 in progress: topic 1 (fidelity axis) resolved as D24/D25; topic 2 (scope) resolved as D26; topic 3 (ground truth, repetitions) resolved as D27; topic 4 (roadmap tracks) resolved as D28; topic 5 (controller generation) resolved as D29; topic 6 (draft reconciliation) resolved as D30/D31. Review complete; D20 and D31 approved 2026-11-25; awaiting researcher approval of WP00 |
| WP01 | Pending | — | Can start now from confirmed facts (D18, D19, D21) and references; may be done together with WP02; pins, board and speed defaults from bundled StepExample (D32) to be checked on the rig |
| WP02 | Pending | — | WP01 (same session allowed) |
| WP03 | Provisional | — | Draft at `design/functional_requirements.md` (D23); reduced to FR01, FR03, FR09, FR08 (D26); FR09 criteria and alignment with WP01–02 still to complete |
| WP04 | Pending | — | Needs WP09a and sensor wiring (D19); protocol and pump-only measurements may start earlier with approval |
| WP05 | Pending | — | WP02; provisional before WP04, final after |
| WP06 | Pending | — | WP03 |
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
- Pins, board and speed defaults are taken from the bundled StepExample code (D32) and still need a visual check on the rig (WP01).
- Level sensor installed but not wired (D19): sensor-dependent rig tests blocked; design and simulation can proceed.
- Fixed pump speed/direction approved (D20); values used so far are probably the StepExample host-script defaults (full speed, direction True; D32).
- Hardware verification, physical measurements, tolerances and fidelity distinction pending.
- Claude Code verified working in the repository (2026-11-25); Codex not verified.

## Next task

WP01 — physical system definition, optionally together with WP02 (D28). Before or alongside: researcher approves WP00 and wires the sensor (see `context/handoffs/WP00_review.md`).

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
