# Software architecture (WP07)

> **Status: Approved by researcher 2026-11-25 (agent-completed by Claude Code).** Minimal architecture for running one controller unchanged against the rig, Model 1 and Model 2, logging every run and judging it independently. Built on WP01–WP03 and WP06. **WP05 has not been done yet** (not even provisionally), so the equation-to-method mapping in section 8 is provisional, taken from the master context and D24, and must be revisited after WP05. Numbers are placeholders (D34). D37 (controller code interface) and D38 (timing, update order and cut-off semantics) approved.

## 1. Principles

- **Same controller, three environments** (D06, D21). The harness and controller code are identical; only the environment object differs.
- **Information parity** (D07). The controller receives only time and the normalized sensor value; it holds no reference to any environment, model or log object.
- **Separation** (AGENTS.md). Controller, physical simulation and evaluation are separate packages. The evaluator reads logs only and imports neither controllers nor models.
- **Determinism in simulation.** Simulated runs are exactly repeatable (D27: run once).
- **Minimal dependencies.** Python standard library for everything except the rig adapter, which needs a serial library (pyserial; PyCmdMessenger only if WP09a keeps the StepExample protocol). Tests use `unittest`. No GUI (D11). Python version TBD (U25).

## 2. Components and responsibilities

| Component | Package | Responsibility | Must not |
|---|---|---|---|
| Controller | generated, stored under `src/shared/controllers/` | Behaviour of WP06 through the D37 interface | Import repository code, read a wall clock, block, do I/O |
| Harness | `src/shared/` | Creates a fresh controller per run (D36); runs the call loop (section 5); applies the scenario's sensor override (D29); writes the call log | Compute physics or verdicts |
| Environment interface | `src/shared/` | Common interface the harness talks to (section 4) | — |
| Rig environment (adapter) | `src/shared/` (hardware adapter, roadmap WP09a) | Serial communication with the firmware; sensor normalization (P18); fixed speed and direction (P19); paces real time; logs commands, acknowledgements and firmware events | Expose anything but the interface to the harness |
| Firmware | `src/esp32/` (WP09a) | Switches each pump independently; reports the sensor; enforces the cut-off (D27); reports start-up and cut-off events | Contain controller logic (D30) |
| Clock | `src/shared/` | Integer-millisecond time (D38). Simulation clock: advances in fixed steps. Rig clock: reads the computer's monotonic time since run start | Be read by the controller (it receives t from the harness) |
| Simulation environment | `src/shared/` | Shared by both models: command and report delays (parameters from the model; zero in Model 1), the cut-off with rig-identical semantics (D27, D38), sensor normalization, truth log | Contain model-specific physics |
| TankSystem, Model 1 | `src/model_1/` | The simulated tank, two pumps and sensor, built from `WaterTank`, `Pump` and `WaterLevelSensor` (section 8); ideal behaviour | Know about the controller |
| TankSystem, Model 2 | `src/model_2/` | Same parts, with the D24 effects WP04 qualifies added to `Pump` and `WaterLevelSensor` | As above |
| Logger | `src/shared/` | Writes the run files (section 7) | Feed anything back to the controller |
| Scenario definitions | `src/testing/scenarios/` | Data for S1–S5: V0, request, override, T_end (WP03 section 8) | — |
| Evaluator | `src/testing/` | Reads the run files and scenario; computes WP03 checks and the WP06 end-state inference; writes the verdict | Import controllers or model packages |

### 2.1 Component diagram

```mermaid
flowchart LR
  subgraph SHARED["src/shared"]
    H["Harness<br/>(clock loop, sensor override)"]
    IF{{"Environment interface"}}
    RIG["Rig environment<br/>(serial adapter)"]
    SIM["Simulation environment<br/>(delays, cut-off, normalization)"]
    LOG["Logger"]
    CLK["Clock"]
  end
  C["Controller under test<br/>(standalone module, D37)"]
  FW["Firmware src/esp32<br/>(pumps, sensor, cut-off)"]
  M1["TankSystem Model 1<br/>src/model_1"]
  M2["TankSystem Model 2<br/>src/model_2"]
  FILES[("Run files<br/>experiments/logs/run_id")]
  MAN[("Manual rig readings")]
  EV["Evaluator<br/>src/testing"]
  SC[("Scenarios<br/>src/testing/scenarios")]

  H -->|"step(t, sensor)"| C
  C -->|"(intake, outtake)"| H
  H --> IF
  IF --- RIG
  IF --- SIM
  RIG -->|"serial"| FW
  SIM -->|"one of"| M1
  SIM -->|"one of"| M2
  SC --> H
  CLK --> H
  H --> LOG
  RIG --> LOG
  SIM --> LOG
  LOG --> FILES
  FILES --> EV
  MAN --> EV
  SC --> EV
```

## 3. Controller code interface (proposed D37)

The clean-room prompt (D29) must state this interface exactly, so it uses only built-in Python types and needs no repository code.

```python
class Controller:
    def __init__(self, task: str, parameter: float,
                 v_sensor_ml: float, q_in_ml_per_s: float, t_deadline_s: float):
        """task is "FR01", "FR03" or "FR09" (wording in the prompt decided in WP08).
        parameter: fill duration in s (FR01), target volume in mL (FR09), ignored (FR03)."""

    def step(self, t_s: float, sensor_wet: bool) -> tuple[bool, bool]:
        """Called every call period. Returns (intake_on, outtake_on)."""
```

Rules: one module, standard library only, no module-level state, no threads, no sleeping, no file or network access. The harness loads the module from a file path and checks the rules statically before a run (imports, names such as `time.time`, `sleep`, `open`, `threading`); a violation is recorded and the controller is not run. Determinism (WP06 K1) is checked by replaying a simulated run and comparing call logs.

The task names given to the controller are neutral labels; the prompt words them (WP08). Check IDs, scenarios and tolerances are not part of the interface.

## 4. Environment interface

```python
class Environment:
    def start(self, scenario) -> None      # set up V0, both pumps OFF, start clock at t = 0
    def now_ms(self) -> int                # current time: simulated, or rig monotonic time since start
    def sensor(self) -> bool               # normalized sensor value (wet = True) as reported now
    def command(self, intake: bool, outtake: bool) -> None
    def advance_to(self, t_ms: int) -> None  # simulation: integrate; rig: wait until then
    def finish(self) -> None               # both pumps OFF; settle period (R09); close
    run_valid: bool                        # False after a rig fault (WP06 X8)
```

Both implementations log their own events (section 7). The interface carries no volume.

## 5. Timing and update order (proposed D38)

**Clock.** Time is kept as integer milliseconds; the controller receives `t_s = t_ms / 1000`. Integer time avoids drift from adding 0.1 s repeatedly.

**Call period** Δt_c = R01 (100 ms placeholder), the same in every environment. **Simulation step** Δt_s = 10 ms (placeholder under D34, fixed with WP05), identical in both models (D24), so delays shorter than Δt_c (e.g. P15 = 20 ms) can be represented. Δt_c is a whole multiple of Δt_s. The water is updated every Δt_s; the controller is called every Δt_c.

**Per call k:**

1. t_k = k × Δt_c (simulation) or the measured time of the call (rig).
2. Environment state is at t_k (the simulated water has been updated up to t_k).
3. s_env = `env.sensor()`.
4. s = override(t_k, s_env) if the scenario defines one (S4 holds it dry), else s_env.
5. (i, o) = `controller.step(t_k / 1000, s)`.
6. `env.command(i, o)`; the command takes effect at t_k plus any command delay of the model (zero in Model 1).
7. Log (t_k, s_env, s, i, o).
8. `env.advance_to(t_{k+1})`.

The loop ends after the call at T_end (R08); the harness then calls `finish()`. In simulation the TankSystem keeps running with pumps OFF for the settle time R09 so that run-on is included in V_end.

**Consequence for the WP06 open point.** With this order, in S2 Model 1 reaches 24.0 mL at t = 19.0 s, the call at 19.0 s sees wet and switches OFF in the same call, so V_end = 24.0 mL (up to floating-point rounding in the volume, which can move the stop to 19.1 s; the WP03 oracles allow one call period).

**Rig pacing.** The rig harness waits until the next nominal tick before each call and logs the actual call time; late calls are logged as events (WP06 X7). The controller receives the actual time.

### 5.1 Sequence of one call

```mermaid
sequenceDiagram
  participant H as Harness
  participant E as Environment (rig or simulation)
  participant C as Controller
  participant L as Logger
  Note over E: state at t_k
  H->>E: sensor()
  E-->>H: s_env
  H->>H: apply override (if scenario has one)
  H->>C: step(t_k, s)
  C-->>H: (intake, outtake)
  H->>E: command(intake, outtake)
  H->>L: call row (t_k, s_env, s, intake, outtake)
  H->>E: advance_to(t_k + Δt_c)
```

## 6. Simulation environment and safety cut-off

```mermaid
flowchart LR
  CMD["command(i, o)<br/>from harness"] --> D1["Command delay<br/>(model parameter; 0 in Model 1)"]
  D1 --> CO["Cut-off<br/>(shared, D27/D38)"]
  CO --> P["TankSystem.step(Δt_s)<br/>Model 1 or Model 2"]
  P --> S["WaterLevelSensor"]
  S --> D2["Report delay<br/>(model parameter; 0 in Model 1)"]
  D2 --> N["Normalized sensor()"]
  P --> T[("Truth log:<br/>volume, flows, overflow")]
```

The order mirrors the rig: serial link → firmware (where the cut-off lives) → pump → water → sensor → firmware → serial link (WP02 section 5.3). Delays and the cut-off are shared code; the TankSystem is the only model-specific part.

**Cut-off semantics (identical in firmware and simulation, D38).** For each pump, the cut-off measures continuous ON time from the moment the ON command reaches it. When it reaches the maximum ON time (P11, placeholder; final value from WP04 with margin, see WP03 finding), the pump is forced OFF and a `cutoff` event is logged. The pump stays OFF while the commanded state is still ON; a new ON edge (OFF then ON) starts a new timer. The controller is not informed (WP06 X6).

## 7. Run files (D11)

One directory per run: `experiments/logs/<run_id>/`. Raw files are never edited after the run.

| File | Written by | Content | Environments |
|---|---|---|---|
| `run.json` | Harness | Run ID, date, git commit, controller file and SHA-256, environment and model version, all parameter values with their P/R IDs, scenario ID, Δt_c, Δt_s, end reason (normal, invalid) | All |
| `calls.csv` | Harness | `t_ms, sensor_env, sensor_given, intake, outtake` (one row per call) | All |
| `events.csv` | Environment | `t_ms, source, event, detail`: command sent/acknowledged, sensor edge reported, cut-off, firmware start-up, late call, run invalidated | All |
| `truth.csv` | Simulation environment | `t_ms, volume_ml, intake_flowing, outtake_flowing, overflow` (per simulation step or decimated); never read by the controller or harness | Models only |
| `manual.csv` | Researcher | `point, time, volume_ml, uncertainty_ml, note` (settled readings before and after; D24, D33) | Rig only |
| `verdict.json` | Evaluator | Each WP03 check: pass/fail/undetermined with evidence; inferred end state (WP06 section 6) | All |

Calibration data from WP04 is stored separately under `experiments/data/` and never mixed with scored runs.

## 8. TankSystem and equation-to-method mapping (provisional until WP05)

`TankSystem` is the simulated counterpart of the physical tank, its two pumps and its sensor. It is the only object the simulation environment talks to, and it is built from one class per physical part, following the master-context mapping (tank → conservation, pump → transferred volume, sensor → threshold).

```mermaid
classDiagram
  class TankSystem {
    +reset(v0_ml)
    +step(dt_ms, intake_cmd, outtake_cmd)
    +sensor_wet() bool
    +truth() dict
  }
  class WaterTank {
    +volume_ml
    +capacity_ml
    +overflow
    +add(ml)
    +remove(ml) float
  }
  class Pump {
    +rate_ml_per_s
    +volume_moved(dt_ms, switched_on) float
  }
  class WaterLevelSensor {
    +level_ml
    +update(dt_ms, volume_ml)
    +is_wet() bool
  }
  TankSystem "1" *-- "1" WaterTank
  TankSystem "1" *-- "2" Pump : intake, outtake
  TankSystem "1" *-- "1" WaterLevelSensor
```

In each `TankSystem.step`: the intake pump reports the volume it moved, the tank adds it; the outtake pump reports its volume, the tank removes what is available; the sensor is updated with the new volume. `switched_on` is the command after the cut-off.

| Concept (master context, D24) | Class and method | Model 1 | Model 2 (only effects WP04 qualifies) |
|---|---|---|---|
| Water balance V(t+Δt) = V(t) + (u_in Q_in − u_out Q_out) Δt | `WaterTank.add` / `remove`, driven by `TankSystem.step` | As written | Same balance; the pump volumes include the effects below |
| Volume moved by a pump | `Pump.volume_moved` | rate × dt while ON, nothing while OFF | Adds the qualifying effects |
| Tube priming | `Pump.volume_moved` (intake) | Absent | No water reaches the tank until the tube is filled (candidate P12) |
| Run-on after OFF | `Pump.volume_moved` | Absent | Extra volume after OFF (candidate P13) |
| Sensor rule S = (V ≥ V_sensor) | `WaterLevelSensor.update` / `is_wet` | Exact at P05 | Measured trigger point and response delay (candidate P14) |
| Communication delay | Simulation environment delays (section 6), not TankSystem | 0 | Measured value (candidate P15) |
| Overflow | `WaterTank.add` sets `overflow` when V > C; volume is not silently clamped (master context) | Same | Same |
| Empty tank | `WaterTank.remove` returns only the water available and logs the shortfall | Same | Same |

**How the two models share code.** `src/model_1/` defines `WaterTank`, `Pump`, `WaterLevelSensor` and `TankSystem`. `src/model_2/` reuses `WaterTank` unchanged (the shared water balance, D24) and defines subclasses of `Pump` and `WaterLevelSensor` that add only the effects WP04 qualifies. The difference between the models is therefore visible in those two subclasses alone.

**Clock.** `Clock` holds integer-millisecond time (D38). The simulation clock is advanced by the simulation environment in steps of Δt_s; the rig clock reads the computer's monotonic time since run start. `Environment.now_ms()` delegates to it; the controller never sees it directly.

## 9. Evaluator boundary

- Input: the run directory, the scenario definition and the parameter set. Output: `verdict.json`.
- Implements the WP03 checks by ID and the WP06 end-state inference; physical checks use `truth.csv` (models) or `manual.csv` (rig) only.
- Runs after the run, never during it, so it cannot influence the controller.
- Built test-first against a stub TankSystem and hand-written logs (D28, WP12), using the WP03 section 9 oracles.

## 10. Directory layout

```
src/
  shared/        harness, environment interface, simulation environment, rig adapter, logger
  shared/controllers/   generated controllers, one file each, unchanged after generation
  esp32/         rig firmware (WP09a), derived from StepExample
  model_1/       TankSystem for Model 1 (WaterTank, Pump, WaterLevelSensor)
  model_2/       TankSystem for Model 2 (reuses WaterTank; extends Pump and WaterLevelSensor)
  testing/       evaluator, scenario definitions, tests (unittest)
experiments/logs/<run_id>/   run files (section 7)
```

## 11. Choices and trade-offs

| Choice | Alternative considered | Reason |
|---|---|---|
| Controller in the same process, loaded from a file | Separate process per controller | Simpler and fast; parity is ensured by passing only built-in values and by the static rule check. A separate process would add isolation but more code |
| Fixed time step | Event-driven simulation | Easy to reason about and to hand-check; matches the scan-cycle controller shape (D29) |
| Integer millisecond clock | Float seconds | Exact times for oracles and replay |
| Post-hoc evaluation from logs | Live checking during runs | Evaluator stays independent and can be re-run on old logs |
| Shared delays and cut-off in the simulation environment | Inside each model | Guarantees the identical cut-off (D27) and keeps the models to the physics |
| Commands sent to the rig only on change | Every call | Less serial traffic; the call log still records every output |

## 12. Requirements on WP09a (rig I/O firmware and adapter)

Independent ON/OFF per pump; sensor reported on change and on request; cut-off with D38 semantics and an event message; start-up message detected by the adapter, which then sets `run_valid = False` (WP06 X8); fixed speed and direction set once (P19), not per command; host timestamps on every send and receive. The protocol (extend StepExample's commands or define new ones) remains open under D16.

## 13. Open points

- WP05: replaces section 8 with the specified equations; may change Δt_s.
- WP08: prompt wording of the task labels; cut-off margin; final R/P values.
- WP09a: protocol (D16); how the adapter normalizes the sensor once U14/U17 are known.
- Run ID scheme and how manual readings are entered (form or hand-edited CSV): decide in WP08.
