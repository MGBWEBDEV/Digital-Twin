# WP10 physical test readiness review, 2026-11-25

- Agent: Codex. Review complete. Physical comparison blocked.
- Request: verify whether Model 1 can be tested against physical equipment on 26 November.
- Checked implementation inventory, WP04/08/09/10/12/13 status, WP01 checklist and decisions D19, D27 and D34. Ran python3 -m unittest discover -s src: 104 tests passed. No equipment inspected or actuated.
- Changed path: this review record only. No decisions or work-package status changes.
- Open items: verify rig and safe mark, establish approved pump-only characterization conditions, calibrate model parameters, complete rig I/O, independent cut-off and logging. Sensor tasks also require verified wet/dry readout. Closed-loop comparison needs the common harness, controller and protocol.
- Next suggested task: researcher rig checklist in design/physical_system.md section 10. Keep calibration records separate from later validation runs.
