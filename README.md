# Digital Twins — research starter repository

MSc Software Design research project, IT University of Copenhagen. Investigates how simulation fidelity affects detection of behavioral defects in AI-generated controller code for an ESP32-based water-tank rig. The controller runs in Python on a host PC; the ESP32 acts as a serial I/O server for the pumps and sensor (see `context/decisions.md`, D21).

This is a documentation scaffold, not an implemented simulation. WP00 is initialized; all other work is pending researcher review. Hardware measurements, model parameters and selected defects are deliberately unspecified.

## Start

Open this folder in your editor or terminal. Begin with [the master context](context/master_context.md) and [project status](context/project_status.md). Keep unpublished research private.

## Collaborate with Claude Code and Codex

Run the installed CLI from the repository root (for example `claude` or `codex`, depending on your installation and authentication). Both agents use the same files: `CLAUDE.md` imports the canonical `AGENTS.md`; Codex uses `AGENTS.md`. If an agent does not automatically load instructions, explicitly ask it to read that file. No automatic agent-to-agent communication, shared chat history or direct access to your local machine is configured by this scaffold.

1. Choose one unblocked WP in `context/roadmap.md` and `context/project_status.md`.
2. Start a fresh CLI session and paste `context/task_template.md` with the WP ID, scope and relevant inputs. Let the agent read repository artifacts rather than pasting the full history.
3. Review its changes and handoff. Use `git status`, `git diff`, and inspect untracked files. Approve decisions only after reviewing them.
4. If useful, start the other CLI in a fresh session for independent review of that same deliverable. Ask it to report findings without editing unless authorized. Never run two writers over the same artifacts simultaneously. An AI review by the other agent is a quality check, not independent validation: both agents read the same instructions and context, so the researcher still reviews specifications, oracles and safety.
5. Review and stage specific changed files, inspect `git diff --cached`, and commit when satisfied. Close the session. Repeat for the next task.

Example first assignment:

> Execute WP01 only. Read AGENTS.md, the WP01 roadmap entry, the relevant hardware section of master_context.md, current decisions/status and available references. Create design/physical_system.md. Mark unverified parameters TBD; do not implement downstream packages. Update status and save a compact handoff under context/handoffs/.

Example reviewer assignment:

> Review WP01 deliverable against its completion criteria and available hardware evidence. Report contradictions, unsupported assumptions and blockers with file references; do not edit or implement WP02.

## Layout

- `context/` — master context, roadmap, approved/proposed decisions, progress, task and handoff templates.
- `design/` — design artifacts produced by individual WPs.
- `references/` — source research draft, hardware documents and source register.
- `src/` — future shared interfaces, ESP32 adapter, models and testing software.
- `experiments/` — protocols, measured datasets, logs and significant AI prompts.
- `report/` — research report integration.

## Recommended first sequence

Paper track: WP01 → WP02 → WP03 → WP06 → WP07. Rig track: wire the sensor, then WP09a → WP04. Software track: provisional WP05 → WP10, and WP12 test-first. See the track overview (D28) in the roadmap, which holds the authoritative dependencies and completion criteria. Physical tests must be researcher-approved and safely bounded.

## Reference material

The complete StepExample directory and upstream license are included under `references/LabAutomationKits/`. Every file was checked against upstream commit `a22a6b981e1f0cfd5d0311b571e7998846d37a7d`. The rig runs this StepExample with only a pump identifier changed so the second pump works (D32).

The recovered draft and its checksum are listed in [the reference register](references/README.md).
