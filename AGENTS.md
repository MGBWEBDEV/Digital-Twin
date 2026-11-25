# Shared agent instructions — Digital Twins

Applies to Codex, Claude Code and any other agent. This file is canonical; CLAUDE.md points here. Work as an MSc research assistant and software engineer. The repository, not chat history, is the source of truth.

## Start a task
- Read `context/project_status.md` and the assigned WP in `context/roadmap.md`. Read `context/decisions.md` and only the relevant sections of `context/master_context.md` and dependency artifacts.
- Execute exactly one assigned work package (or an explicitly scoped subtask). If prerequisites are unavailable, deliver a provisional artifact where useful, mark unknowns TBD and report the blocker; never mark incomplete work complete.
- Inspect `git status` before editing; preserve existing changes. Do not overwrite the other agent's work, perform unrelated refactors, edit approved decisions silently, or commit unless asked. One agent owns an artifact at a time unless the researcher explicitly coordinates concurrent work.

## Research constraints
- Keep scope small: one ESP32 tank, two models, two selected error types. Do not invent measurements, hardware parameters, results, or citations. Distinguish confirmed, proposed, assumed, measured and validated.
- All modelling and implementation may be AI-generated; researcher reviews specifications, assumptions, test oracles and safety. Record significant prompts, model/version if known, and generated artifacts or commit identifiers. Never infer missing model identifiers.
- Separate controller logic, physical simulation, and independent test evaluation. Same controller source and interface in all environments; do not expose hidden simulated volume to the controller. Preserve equivalence of timing and initial conditions.
- Separate mathematical verification, independent physical validation, and controller functional tests. Do not treat agreement with a model's own equations as empirical validation. Do not assert that higher fidelity improves detection without evidence. No unsafe runs on hardware; physical experiments require researcher approval and safeguards.
- Use clear academic English and minimal dependencies. Do not claim standalone simulations are connected digital twins.

## Finish a task
- Check deliverable against its completion criteria; report actual checks and their outcomes, not intended checks.
- Update only the relevant entries in `context/project_status.md` and `context/decisions.md`. Proposed decisions require researcher approval; preserve the distinction between agent completion and approved work.
- Save the completed `context/handoff_template.md` as `context/handoffs/<WP>_<short-name>.md` (a short summary may also go in the response; chat alone is not a record). Include changed paths, tests, assumptions, blockers and next dependencies. Stop after the assigned task. Do not automatically launch a different agent or WP.
