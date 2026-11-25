# Reference inputs

## Research draft (included)

- `research_draft.txt`: complete text recovered from the research draft uploaded on 25 November 2026 as `Pasted text.txt`. The original raw attachment could not be exported; this is a text extraction, not a byte-identical source copy. Preserve it as reference material, not a generated report. The draft includes the proof of concept, literature discussion, research scope and provisional experimental outline. The draft uses Arduino terminology; current confirmed hardware is ESP32. Verify references and reconcile any differences with approved project decisions before proceeding.
- SHA-256 of bundled text extraction: `487898f0316247b181564541e46f35c8cb76e5db7fed558ce6ba06e67ead738c`.

## LabAutomationKits

The complete StepExample directory and upstream license are included under `references/LabAutomationKits/`. Every file was checked against upstream commit `a22a6b981e1f0cfd5d0311b571e7998846d37a7d`.

Upstream source: https://github.com/rmorenoga/LabAutomationKits/tree/a22a6b981e1f0cfd5d0311b571e7998846d37a7d/Electronics/Firmware/StepExample

`scripts/fetch_labkit.sh` reproduces this snapshot from the pinned commit into an empty location; it refuses to overwrite the bundled copy.

StepExample is a base example, not the rig firmware: it drives only pump A, takes PWM speed and direction per step, and reads no level sensor.

## Rig firmware (pending)

The firmware currently running on the rig was modified from StepExample to drive the second pump (D18). Add it here (for example `references/rig_firmware/`) together with any modified host script, and record its origin and date. Until then, pins, driver channels and the board model are unconfirmed.
