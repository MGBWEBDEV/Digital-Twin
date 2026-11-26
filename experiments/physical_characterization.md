# Physical characterization (WP04): protocol, tools and analysis rules

> **Status: provisional protocol, approved by researcher 2026-11-26 (D50). No measurement has been made.** Written by Claude Code on 2026-11-26 without access to the rig, as the roadmap allows ("can deliver protocol only as partial if no hardware access"). Every number here is a rule, a researcher input or a labelled example. None is a measurement (D34). The data sections (section 9) stay empty until the researcher runs approved sessions. Proposed decision: D50.
>
> Inputs: roadmap WP04; D19, D20, D24, D27 (5), D34, D40, D45, D46, D49; `design/physical_system.md` (unknowns U01–U31, placeholders P01–P19); `design/mathematical_models.md` sections 7–8 (candidate effects E1–E5, identifiability); `experiments/experimental_protocol.md` sections 3, 6–9, 16 (final-value rules R01–R16, rig procedure, cut-off sizing).

## 1. In plain terms

WP04 measures the few numbers the models and the tests need: how fast the intake fills the syringe, how repeatable that is, how precisely a level can be read, where the sensor switches, and whether the small real-world effects of Model 2 are big enough to see. Example (invented numbers, for illustration only): five 20 s fills from 5 mL end at 24.5, 25.0, 24.5, 25.0 and 25.0 mL. Five 10 s fills end at 14.5 or 15.0 mL. A straight line through these gives a rate of about 1.0 mL/s and an offset of about −0.4 mL, and the repeats agree within one graduation.

Each fill is timed by the firmware itself: the per-run limit is set to the wanted duration and the cut-off ends the fill. The pump is therefore ON for exactly the chosen time, and the host cannot make it longer.

## 2. Prerequisites and gates

| Gate | Needed before | Who |
|---|---|---|
| Rig check (`design/physical_system.md` section 10): C (P01), graduation (P02), safe mark (P04), dead volume (P09), channel of each pump (P17), tubing (U10, U11), leak and electronics position (U27, U29) | Session A | Researcher |
| Researcher estimate of the highest plausible intake rate, q_bound, with its source (pump datasheet U07, or earlier observation of the rig) | Choosing the Session A ceiling | Researcher |
| WP09a firmware reviewed (D49), `rig_config.h` filled in, build uploaded with approval | Session A | Researcher (upload), agent (build) |
| Sensor wired, pin and polarity known (D19, U15, U17) | Sensor measurements M7, M8 only | Researcher |
| Written session plan approved (protocol section 7.1) | Every session | Agent drafts, researcher approves |

Pump-only measurements (M1–M6) do not need the sensor.

## 3. Staged sessions (D50 (1))

The cut-off ceiling is compiled into the firmware and must be safe before the intake rate is known. The sessions are therefore staged, so that each ceiling is sized from the previous session's evidence:

| Session | Firmware ceiling | Contents | Gives |
|---|---|---|---|
| A (start-up) | L_A, chosen by the researcher from q_bound: V0 + R14_A + q_bound × L_A ≤ C − 5 graduations | Reading uncertainty M1 (no pumping), hold check M2, latency M6, cut-off check (protocol 7.4) with limit L_A and the OFF-early double, one more timed fill M3a of L_A | u_read; leak/siphon finding; host round trip; proof the cut-off works; first rate bound q_hi,A |
| B (calibration) | L_B = the longest fill of the plan, with V0 + R14_A + q_hi,A × L_B ≤ P04 − 2 graduations | Timed fills M3 (two durations × 5, empty tube), primed-tube fills M4, settling readings M5, sensor steps M7 and crossing M8 if the sensor is wired | Q_in, b, spreads, V_ro, V_p, R09, V_sensor, sensor delay |
| C (controller runs, later) | Largest T_max of the session plan (D45), from the final values | Reference and fault runs (WP13, WP15) | — |

Example (invented numbers, for illustration only): the researcher states that the pump cannot exceed q_bound = 5 mL/s. With C = 60 mL, a 1 mL graduation, V0 = 5 mL and a 1 mL band, L_A ≤ (60 − 5 − 5 − 1) / 5 = 9.8 s, so the researcher might choose L_A = 3 s. If the Session A fills end 3.0 mL higher and u_read = 0.5 mL, then q_hi,A = (3.0 + 1.0) / 3 = 1.33 mL/s. With a 50 mL safe mark, L_B ≤ (50 − 2 − 5 − 1) / 1.33 = 31.5 s, which allows fills of 10 s and 20 s.

R14_A is the start band used before u_read is known. It is one graduation.

Each session needs its own firmware build (different ceiling) and its own upload approval. The session log records the build hash (protocol section 16).

## 4. Measurements

All rig actions go through the WP09a tools. `shared.run_rig` runs the cut-off check. `shared.run_calibration` runs the other measurements (section 7). Every pumping action starts with an empty intake tube (D40), using the reset method chosen after the rig check (protocol 6.2), unless the measurement says "primed". Settled readings are taken at eye level at the bottom of the meniscus. Each reading is entered with its uncertainty.

| ID | Measures | Procedure | Repeats | Feeds |
|---|---|---|---|---|
| M1 | Reading uncertainty u_read (P03, U03) | Pumps OFF. The researcher reads the same settled level 5 times, looking away and repositioning between readings. Repeat at two levels (near P10 and near the safe mark) | 5 × 2 | P03, R05, R14, R16 floor |
| M2 | Leaks, siphoning, drain-back (U27, X4, X7) | Pumps OFF. Read the level, wait 10 min, read again | 1 | Conservation assumption |
| M3 | Intake rate Q_in and offset b, empty tube (U08, U09; E1/E2 combined) | Timed fill from P10 with an empty tube, limit = duration T, firmware-timed. Durations T1 and T2 = 2 × T1 (R10 needs two durations to separate rate and offset). Read the settled level after settling | 5 per duration | P06, P08, Q_in,hi, b_empty |
| M4 | Primed-tube offset (E1 and E2 separately, WP05 section 8) | As M3 with duration T2, but the tube is left full from the previous fill (no reset of the tube; the level is brought back with setup commands only if needed) | 5 | b_primed → V_ro, V_p |
| M5 | Settling time (R09) | During M3 at T2: after the cut-off, readings at about 2, 5, 10, 20 and 30 s with the elapsed time (the tool prints it) | in 3 of the M3 runs | R09 |
| M6 | Host–firmware round trip (U31, E5) | Pumps OFF; 200 state requests; host times of send and reply | 1 | P15, E5 |
| M7 | Sensor switch volume (U16, E3) | Fill in short firmware-timed pulses (e.g. 0.5 s) from about 3 mL below the expected level. After each pulse wait the settling time, read the level and note the sensor state. Stop at the first wet state | 5 | V_sensor (P05), its uncertainty |
| M8 | Sensor timing (U18, E4 + E5) | Continuous fill from P10; the tool switches OFF on the first wet report; host time of the wet edge; settled end reading | 5 | E4 delay estimate; overshoot |

Not measured in WP04: outtake rate Q_out (P07) and outtake run-on. No selected task runs the outtake (X5), and running it near the dead volume is unsafe until U30 is resolved. If the reset method uses the outtake, its rate is measured in a separate, separately approved step.

## 5. Analysis rules (D50 (2)–(6))

`src/characterization/analysis.py` implements these rules. The tests use hand-calculated synthetic data that are labelled as such.

1. **Reading uncertainty.** u_read = max(P02 / 2, (max − min) / 2 of the M1 repeats at either level).
2. **Consistency (D27 (5)).** The rig counts as consistent if, for every M3/M4 group of 5 repeats, max − min ≤ P02, the reading resolution.
3. **Rate and offset.** Fit ΔV = Q_in × T + b by least squares to all M3 runs (ΔV = settled end − settled start). Q_in is P06 and b_empty is the offset. s_run is half the largest range among the repeat groups (P08, protocol R05).
4. **Upper rate for the cut-off (Q_in,hi, D45, D48 (2)).** Q_in,hi = max over all M3 runs of (ΔV + 2 × u_read) / T. This is the highest rate that any single fill allows once reading uncertainty is added. Example: a 20 s fill of 20.0 mL with u_read = 0.5 mL gives 21.0 / 20 = 1.05 mL/s.
5. **Run-on and priming (E2, E1).** b_primed = mean(ΔV_M4) − Q_in × T2. V_ro = b_primed (P13). V_p = b_primed − b_empty (P12 as t_p = V_p / Q_in).
6. **Sensor switch volume (E3).** In each M7 series, the switch volume lies between the last dry reading and the first wet reading. The estimate is the mean of the midpoints over the series. Its uncertainty is half the widest bracket plus u_read. This value is given to the controller (D46 (2)), so E3 is zero by construction.
7. **Sensor delay (E4 + E5).** For each M8 run, predicted crossing t_pred = (V_sensor − V0 − b_empty) / Q_in. The delay is d = t_edge − t_pred. Its uncertainty is u_d = (u_read + u_Vsensor) / Q_in.
8. **Settling time.** In each M5 series, the settling time is the earliest reading time from which every later reading is within u_read of the last one. R09 = the largest of these, rounded up to 5 s, and at least 10 s (protocol R09).
9. **D24 inclusion test.** An effect is included only if it is larger than the resolution named by D24 **and** larger than its own estimation uncertainty. The second condition is added so that noise is not modelled (D50 (5)).

| Effect | Included if |
|---|---|
| E1 priming | V_p > u_read and V_p > 2 × s_run |
| E2 run-on | V_ro > u_read and V_ro > 2 × s_run |
| E3 trigger offset | Never: the measured value is given to the controller (D46 (2)) |
| E4 sensor delay | d > P16 (1 ms) and d > 2 × u_d, and the overshoot Q_in × d > u_read |
| E5 communication | RTT / 2 > P16 and Q_in × RTT / 2 > u_read (a visible effect, WP05 section 7) |

If no effect qualifies, the result "Model 1 is sufficient at this rig's resolution" is recorded (D24) and the researcher decides the fallback.

10. **Final values.** The final values follow the rules of protocol section 3. Researcher inputs: P01, P02, P04, P09, P10, R01; measured: everything else. The tool computes R02–R06, R08, R09, R11, R12, R14, R16, the S3 start volume, Q_in,hi and the D45 T_max of every scenario start volume. It flags each rule that cannot be met, for example R06 not 5 s below T_max(S2), or an FR01 duration that would pass the safe mark. It decides nothing; a flagged rule goes to the researcher.

## 6. Safety

- Every session runs from an approved plan with the stop rules of protocol section 6.4. The researcher watches every pumping action.
- Every fill is firmware-timed by the cut-off. The limit can only be as long as the compiled-in ceiling (D45, D49).
- The tools refuse a start reading outside the planned band. They refuse a fill whose planned end, V0 + band + q_hi × T, would pass the safe mark minus two graduations. q_hi comes from the plan, with its source recorded.
- No outtake pumping in WP04 (section 4). No placeholder value is used on the rig (D34). All plan numbers come from the researcher or from earlier measured sessions.

## 7. Tools

| Tool | Does | Writes |
|---|---|---|
| `shared.run_rig` (WP09a) | Cut-off check runs (protocol 7.4) with the test doubles `double_never_off.py` and `double_on_2s.py` (stops at 2 s, for a short Session A limit) or `double_on_15s.py` | `experiments/logs/<run_id>/` (purpose `cutoff_check`) |
| `shared.run_calibration` | Actions `readings` (M1, M2), `timed_fill` (M3, M4, M5), `latency` (M6), `sensor_steps` (M7), `sensor_crossing` (M8) from an approved calibration plan | `experiments/data/<session_id>/<label>/calibration.json`, `events.csv` |
| `characterization.analysis` | Rules of section 5 on the calibration records | A summary (JSON) for section 9 and for the final WP05/WP08 |

Calibration data never go to `experiments/logs/` and are never scored (protocol sections 4 and 9).

Calibration plan format (one file per session, approved in writing; every number below is an example, not a value):

```json
{
  "session_id": "<id>", "approved_by": "<researcher>", "approved_on": "<date>",
  "firmware_ceiling_ms": 3000,
  "graduation_ml": 1, "safe_mark_ml": 50,
  "q_hi_ml_per_s": 5, "q_hi_source": "<researcher statement or earlier session>",
  "actions": [
    {"label": "M1-low", "kind": "readings", "measure": "M1", "count": 5},
    {"label": "M6", "kind": "latency", "measure": "M6", "count": 200},
    {"label": "M3a-1", "kind": "timed_fill", "measure": "M3", "duration_ms": 3000,
     "tube": "empty", "v0_plan_ml": 5, "v0_band_ml": 1},
    {"label": "M5-1", "kind": "timed_fill", "measure": "M5", "duration_ms": 3000,
     "tube": "empty", "v0_plan_ml": 5, "v0_band_ml": 1, "settle_readings": true}
  ]
}
```

This example is a Session A plan. A Session B plan has the same structure with longer fills. A `sensor_steps` action adds `pulse_ms`, `max_pulses`, `settle_ms`, `v0_plan_ml` and `v0_band_ml`. A `sensor_crossing` action adds `max_ms`, `v0_plan_ml` and `v0_band_ml`. The worst-end check counts `pulse_ms × max_pulses` or `max_ms` as the longest ON time.

The plan ceiling must equal the largest limit in the plan and the firmware's ceiling. An M5 action is an M3 fill with a settling series, and the analysis counts it as an M3 fill. The analysis groups records by `measure`.

## 8. What this produces for other work packages

- Final values of P01–P10, P12–P16 and R01–R16 → `experiments/experimental_protocol.md` (final version), `src/testing/parameters.py`, `src/model_1/parameters.py`.
- Inclusion table → final WP05 section 7 → WP11 (Model 2).
- Q_in,hi, V_ro and the final values → T_max per scenario start volume → session plans and firmware ceiling for Session C.
- A record of the early feasibility check: whether any Model 2 effect is measurable (roadmap WP04).

## 9. Data and results

Empty. Filled in from `experiments/data/` after the approved sessions.
