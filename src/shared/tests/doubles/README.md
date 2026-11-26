# Test doubles — NOT controllers under test

The files here are hand-written **test doubles** for the harness tests and for
the end-to-end evaluator check on Model 1 (WP12). They are not reference or
experimental controllers, were not produced by the clean-room procedure
(D29), and must never be used in WP09b, WP13, WP14 or WP15 or stored under
`src/shared/controllers/`. The only rig use allowed is the WP09a cut-off
check (protocol section 7.4); `shared.run_rig` accepts doubles only for that
purpose.

| File | Purpose |
|---|---|
| `double_fill_until_wet.py` | Minimal closed-loop double: intake ON until the sensor input is wet or the deadline passes; nothing if wet at the first call. Ignores the task and parameter, so it is only meaningful for the FR03 cases (S2, S3-FR03, S4) and the FR09 "sensor wet at start" case (S3-FR09-40) |
| `double_never_off.py` | Intake ON at every call, never OFF (WP09a cut-off check, protocol section 7.4 step 1; adapter tests). On the rig only behind the firmware cut-off, from an approved session plan |
| `double_on_15s.py` | Intake ON for 0 <= t < 15 s, then OFF (cut-off check step 2: no cut-off with the plan's limit) |
| `double_on_2s.py` | Intake ON for 0 <= t < 2 s, then OFF (cut-off check step 2 with a short start-up limit, WP04 Session A) |
| `double_nondeterministic.py` | Keeps a counter on the class, so a second instance answers differently; it passes the static check and must be caught by the determinism replay |

Open-loop doubles (fixed intake schedules, never reading the sensor) and the
small rule-breaking files are generated inside the tests from
`src/shared/tests/doubles_support.py`.
