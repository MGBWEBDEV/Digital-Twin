# Reference inputs

## Research draft (included)

- `research_draft.txt`: complete text recovered from the research draft uploaded on 25 November 2026 as `Pasted text.txt`. The original raw attachment could not be exported; this is a text extraction, not a byte-identical source copy. Preserve it as reference material, not a generated report. The draft includes the proof of concept, literature discussion, research scope and provisional experimental outline. The draft uses Arduino terminology; current confirmed hardware is ESP32. Verify references and reconcile any differences with approved project decisions before proceeding.
- SHA-256 of bundled text extraction: `487898f0316247b181564541e46f35c8cb76e5db7fed558ce6ba06e67ead738c`.

## Reconciliation of the draft with current decisions

Where `research_draft.txt` differs from the approved project decisions, the decisions apply. Recorded differences:

| Draft says | Current position | Decision |
|---|---|---|
| Arduino water tank / Arduino controller | ESP32 rig; controller in Python on the host PC, ESP32 as serial I/O server | D02, D21 |
| Reference behavior from "the original Arduino controller" | No original controller program exists; the reference is a clean-room AI-generated controller validated on the rig | D30, D29 |
| Model 1 fixed amounts per step vs Model 2 flow rate × time | Mathematically equivalent for constant rates; the fidelity difference is the set of measurable rig effects | D24 |
| Model 2 keeps "the water level always between X and X" | A controller requirement, not physics: FR08 and the safe-limit mark | D26, D24 |
| "If they behave differently, increase the complexity of the digital twin" | Done once, by plan: effects are included only if measurable in WP04 | D24 |
| "Digital twin" in the title and objectives | Models of a digital twin, not a connected twin (proposed) | D31 |
| Literature references | Not yet verified against originals; verify before citing (WP17) | — |

## LabAutomationKits

The complete StepExample directory and upstream license are included under `references/LabAutomationKits/`. Every file was checked against upstream commit `a22a6b981e1f0cfd5d0311b571e7998846d37a7d`.

Upstream source: https://github.com/rmorenoga/LabAutomationKits/tree/a22a6b981e1f0cfd5d0311b571e7998846d37a7d/Electronics/Firmware/StepExample

`scripts/fetch_labkit.sh` reproduces this snapshot from the pinned commit into an empty location; it refuses to overwrite the bundled copy.

As bundled, StepExample drives only pump A, takes PWM speed and direction per step, and reads no level sensor.

## Rig firmware

The rig runs this StepExample with a single change: a pump function's letter identifier (A → B) so the second pump works; nothing else, including speed and direction, was changed (D32). The modified copy is therefore not stored. Pins, board and speed defaults are read from the bundled code and still need a visual check on the rig (WP01).
