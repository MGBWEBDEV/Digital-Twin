"""Test helpers for the WP11 checks (not part of Model 2).

PrimedTubePump is TEST ONLY. Since D40 (2) every run starts with an empty
intake tube and there is no tube-fill input. WP05 section 9 keeps the
primed-tube columns (f0 = V_p) "only for reference and for WP04
identifiability"; this subclass starts the tube full so that those columns
can still be checked against their hand-calculated values. It is never used
by the model, the runner or a scored run.

The full-loop helper drives the shared SimulationEnvironment with a FIXED
intake command schedule written down from the oracle (ON from the call at
0 s, OFF from the call at a given time, or never). The schedule never reads
the sensor, so it is a test input, not a controller (AGENTS.md, D29). Where
an oracle assumes a correct controller that switches OFF at the first call
that sees wet, the test asserts that the environment reports wet for the
first time at that call and dry at the call before.
"""

from model_2 import Model2Parameters, build_model_2, build_model_2_environment
from model_2.priming_run_on_pump import PrimingRunOnPump
from shared.environment import InitialConditions

STEP_MS = 10
CALL_MS = 100              # R01
T_END_MS = 60_000          # R08
# Per-run cut-off (D45, protocol section 8), worked out by hand with
# C = 60, R12 = 5, R14 = 1, V_ro = 0.5, Q_in,hi = 1.0:
# floor((60 - 5 - (5 + 1) - 0.5) / 1.0) = 48.5 s; for V0 = 30: 23.5 s.
T_MAX_V0_5_MS = 48_500
T_MAX_V0_30_MS = 23_500


class PrimedTubePump(PrimingRunOnPump):
    """TEST ONLY: intake tube full at the start of the run (f0 = V_p)."""

    def reset(self) -> None:
        super().reset()
        self.tube_fill_ml = self.tube_volume_ml
        self.tube_fill_start_ml = self.tube_fill_ml


def prime_tube(tank_system):
    """Replace the intake by a PrimedTubePump with the same parameters (test only)."""
    old = tank_system.intake
    tank_system.intake = PrimedTubePump(old.rate_ml_per_s, old.tube_volume_ml, old.runon_ml)
    tank_system.reset(tank_system.v0_ml)
    return tank_system


def tank_system(parameters=None, primed=False):
    ts = build_model_2(parameters or Model2Parameters())
    return prime_tube(ts) if primed else ts


def run_steps(ts, v0, intake, outtake, until_ms):
    """Step a TankSystem from t = 0 to until_ms with effective pump states
    given directly (functions t_ms -> bool for the step starting at t_ms).
    Returns a dict t_ms -> truth row (t = 0 and every step end) and the
    events as (t_ms, name), stamped with the step end time."""
    ts.reset(v0)
    rows = {0: ts.truth()}
    events = []
    t = 0
    while t < until_ms:
        new = ts.step(STEP_MS, intake(t), outtake(t))
        t += STEP_MS
        rows[t] = ts.truth()
        events.extend((t, name) for name in new)
    return rows, events


def off(_t):
    return False


def on(_t):
    return True


def until(t_end_ms):
    return lambda t: t < t_end_ms


def environment(parameters=None, primed=False):
    env = build_model_2_environment(parameters or Model2Parameters())
    if primed:
        prime_tube(env.tank)
    return env


def run_schedule(env, v0, intake_off_at_ms, t_max_ms=T_MAX_V0_5_MS, t_end_ms=T_END_MS):
    """Full loop (D38 call order): at every call read the sensor, send the
    command, advance one call period; after the call at T_end, finish()
    commands OFF and settles for T_set = 10 s (R09). Intake ON from the call
    at 0 s and OFF from the call at intake_off_at_ms (None: never OFF);
    outtake always OFF. Returns the list of calls (t_ms, sensor, intake)."""
    env.start(InitialConditions(v0_ml=v0, t_max_ms=t_max_ms))
    calls = []
    t = 0
    while True:
        assert env.now_ms() == t
        sensor = env.sensor()
        intake = intake_off_at_ms is None or t < intake_off_at_ms
        env.command(intake, False)
        calls.append((t, sensor, intake))
        if t >= t_end_ms:
            break
        env.advance_to(t + CALL_MS)
        t += CALL_MS
    env.finish()
    return calls


def first_wet_call(calls):
    return next((t for t, wet, _ in calls if wet), None)


def sensor_at_call(calls, t_ms):
    return dict((t, wet) for t, wet, _ in calls)[t_ms]


def first_time(rows, column, value=True):
    """First truth-row time at which `column` equals `value`."""
    return next((r["t_ms"] for r in rows if r[column] == value), None)


def row_at(rows, t_ms):
    return next(r for r in rows if r["t_ms"] == t_ms)


def events_named(env, name):
    return [e for e in env.events if e[2] == name]
