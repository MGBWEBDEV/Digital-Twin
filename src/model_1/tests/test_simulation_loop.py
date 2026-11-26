"""WP10 mathematical verification, full loop with the shared simulation
environment and the cut-off.

Oracles M1-8 ... M1-12 are the hand-calculated values of
design/mathematical_models.md section 9.2, copied as literal numbers.

No controller is used (AGENTS.md, D29). Each run is driven by a FIXED intake
command schedule written down in advance from the oracle ("intake ON from the
call at 0 s until the call at X s"). The schedule never reads the sensor, so
it is a test input, not a controller. Where an oracle assumes that a
correct controller switches OFF at the first call that sees wet, the test
instead asserts that the environment reports wet for the first time at that
call; closed-loop runs with a real controller wait for the harness (WP12) and
the clean-room reference controller (WP09b).

Call loop follows D38 (architecture section 5): at each call t_k read the
sensor, send the command, advance by the call period; after the call at
T_end = 60 s (R08) the environment's finish() commands OFF and settles for
T_set = 10 s (R09). V_end is the volume after settling.

Cut-off limit per run (D45, protocol section 8), worked out by hand with the
placeholders C = 60, R12 = 5, R14 = 1, V_ro = 0.5, Q_in,hi = 1.0:
T_max = floor((60 - 5 - (V0_plan + 1) - 0.5) / 1.0) = 48.5 s for V0_plan = 5 mL
and 23.5 s for V0_plan = 30 mL. Literal values below, not computed by code.
"""

import unittest

from model_1 import MODEL_1_SIMULATION_PARAMETERS, build_model_1
from shared.environment import Environment, InitialConditions
from shared.simulation_environment import SimulationEnvironment

CALL_MS = 100          # R01
T_END_MS = 60_000      # R08
T_MAX_V0_5_MS = 48_500     # D45, planned V0 = 5 mL (hand calculation above)
T_MAX_V0_30_MS = 23_500    # D45, planned V0 = 30 mL


def start(env, v0, t_max_ms=T_MAX_V0_5_MS):
    env.start(InitialConditions(v0_ml=v0, t_max_ms=t_max_ms))


def run_schedule(v0, intake_off_at_ms, t_end_ms=T_END_MS):
    """Run with intake commanded ON from t = 0 and OFF from the call at
    intake_off_at_ms (None: never OFF). Outtake always OFF.

    Returns (env, calls) where calls is a list of (t_ms, sensor, intake).
    """
    env = SimulationEnvironment(build_model_1(), MODEL_1_SIMULATION_PARAMETERS)
    start(env, v0)
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
    return env, calls


def first_wet_call(calls):
    return next((t for t, wet, _ in calls if wet), None)


def v_end(env):
    return env.truth_rows[-1]["volume_ml"]


def v_peak(env):
    return max(row["volume_ml"] for row in env.truth_rows)


def events_named(env, name):
    return [e for e in env.events if e[2] == name]


class TestFullLoopChecks(unittest.TestCase):

    def test_M1_8_S1_FR01_10_s(self):
        env, calls = run_schedule(5, 10_000)
        self.assertEqual(v_end(env), 15.0)
        self.assertIsNone(first_wet_call(calls))
        self.assertEqual(events_named(env, "cutoff"), [])

    def test_M1_8_S1_FR01_20_s(self):
        env, calls = run_schedule(5, 20_000)
        self.assertEqual(v_end(env), 25.0)
        self.assertEqual(first_wet_call(calls), 19_000)   # wet from 19.0 s

    def test_M1_9_S2_FR03(self):
        env, calls = run_schedule(5, 19_000)
        self.assertEqual(first_wet_call(calls), 19_000)   # call at 19.0 s sees wet
        self.assertFalse(dict((t, w) for t, w, _ in calls)[18_900])
        self.assertEqual(v_end(env), 24.0)

    def test_M1_10_S4_plant_unaffected_by_held_dry_sensor(self):
        # The S4 override (sensor input held dry) is applied by the harness,
        # not the environment: the environment still reports wet from 19.0 s.
        env, calls = run_schedule(5, 30_000)
        self.assertEqual(first_wet_call(calls), 19_000)
        self.assertEqual(v_end(env), 35.0)

    def test_M1_11_S5_FR09_48_mL(self):
        env, calls = run_schedule(5, 43_000)               # t_w = 19.0, + 24 s
        self.assertEqual(first_wet_call(calls), 19_000)
        self.assertEqual(v_end(env), 48.0)
        self.assertEqual(events_named(env, "cutoff"), [])

    def test_M1_12_fault_intake_never_off(self):
        # Recomputed for D45: T_max = 48.5 s from V0 = 5 mL. V_end = 5 + 48.5
        # = 53.5 mL: above the safe mark P04 = 50 (FR08-P1 fails), 6.5 mL
        # below capacity, no overflow.
        env, _ = run_schedule(5, None)
        self.assertEqual(events_named(env, "cutoff"),
                         [(48_500, "sim_env", "cutoff", "pump=intake")])
        self.assertEqual(v_end(env), 53.5)
        self.assertEqual(v_peak(env), 53.5)
        self.assertEqual(events_named(env, "overflow"), [])


class TestCutOffInEnvironment(unittest.TestCase):

    def make_env(self, v0=5, t_max_ms=T_MAX_V0_5_MS):
        env = SimulationEnvironment(build_model_1(), MODEL_1_SIMULATION_PARAMETERS)
        start(env, v0, t_max_ms)
        return env

    def test_pump_stays_off_while_command_stays_on(self):
        env = self.make_env()
        env.command(True, False)
        env.advance_to(52_000)
        self.assertEqual(env.truth_rows[-1]["volume_ml"], 53.5)   # 5 + 48.5
        self.assertFalse(env.truth_rows[-1]["intake_flowing"])

    def test_new_on_edge_restarts_timer(self):
        env = self.make_env(v0=0)
        env.command(True, False)
        env.advance_to(49_000)              # cut-off at 48.5 s: V = 48.5
        env.command(False, False)
        env.advance_to(49_100)
        env.command(True, False)            # new ON edge at 49.1 s
        env.advance_to(59_100)
        self.assertEqual(env.truth_rows[-1]["volume_ml"], 58.5)
        self.assertEqual(len(events_named(env, "cutoff")), 1)

    def test_outtake_has_its_own_cutoff(self):
        env = self.make_env(v0=60)
        env.command(False, True)
        env.advance_to(50_000)
        self.assertEqual(events_named(env, "cutoff"),
                         [(48_500, "sim_env", "cutoff", "pump=outtake")])
        self.assertEqual(env.truth_rows[-1]["volume_ml"], 11.5)   # 60 - 48.5

    def test_controller_not_informed_of_cutoff(self):
        # The interface offers only time and the sensor; the cut-off changes
        # neither (sensor stays as the water dictates).
        env = self.make_env(v0=5)
        env.command(True, False)
        env.advance_to(48_400)
        before = env.sensor()
        env.advance_to(48_600)
        self.assertEqual(before, env.sensor())
        self.assertIs(type(env.sensor()), bool)

    def test_limit_is_set_per_run(self):
        # D45: the same environment object takes each run's own limit at start().
        env = self.make_env(v0=30, t_max_ms=T_MAX_V0_30_MS)
        env.command(True, False)
        env.advance_to(25_000)
        self.assertEqual(events_named(env, "cutoff"),
                         [(23_500, "sim_env", "cutoff", "pump=intake")])
        self.assertEqual(env.truth_rows[-1]["volume_ml"], 53.5)   # 30 + 23.5
        start(env, 5, T_MAX_V0_5_MS)
        env.command(True, False)
        env.advance_to(25_000)
        self.assertEqual(events_named(env, "cutoff"), [])
        self.assertEqual(env.t_max_ms, 48_500)

    def test_limit_must_be_given_and_on_step_grid(self):
        env = SimulationEnvironment(build_model_1(), MODEL_1_SIMULATION_PARAMETERS)
        for bad in (0, -100, 48_505, 48.5, None):
            with self.subTest(t_max_ms=bad), self.assertRaises(ValueError):
                start(env, 5, bad)
        with self.assertRaises(TypeError):
            env.start(InitialConditions(v0_ml=5))            # no default limit (P11 removed)


class TestEnvironmentConventions(unittest.TestCase):

    def test_is_an_environment(self):
        env = SimulationEnvironment(build_model_1(), MODEL_1_SIMULATION_PARAMETERS)
        self.assertIsInstance(env, Environment)

    def test_model_1_delay_slots_are_zero(self):
        p = MODEL_1_SIMULATION_PARAMETERS
        self.assertEqual((p.command_delay_ms, p.report_delay_ms), (0, 0))
        self.assertEqual((p.step_ms, p.settle_ms), (10, 10_000))
        self.assertFalse(hasattr(p, "max_on_ms"))           # per run since D45

    def test_command_takes_effect_in_the_same_step(self):
        env = SimulationEnvironment(build_model_1(), MODEL_1_SIMULATION_PARAMETERS)
        start(env, 5)
        env.command(True, False)
        env.advance_to(10)
        self.assertAlmostEqual(env.truth_rows[-1]["volume_ml"], 5.01, places=12)

    def test_sensor_report_is_immediate(self):
        env = SimulationEnvironment(build_model_1(), MODEL_1_SIMULATION_PARAMETERS)
        start(env, 23.99)
        env.command(True, False)
        self.assertFalse(env.sensor())
        env.advance_to(10)
        self.assertTrue(env.sensor())
        self.assertEqual(events_named(env, "sensor_edge"),
                         [(10, "sim_env", "sensor_edge", "wet=True")])

    def test_wet_at_start_reported_at_first_call(self):
        env = SimulationEnvironment(build_model_1(), MODEL_1_SIMULATION_PARAMETERS)
        start(env, 30)
        self.assertTrue(env.sensor())

    def test_truth_logged_at_start_and_every_step(self):
        env, _ = run_schedule(5, 10_000)
        times = [row["t_ms"] for row in env.truth_rows]
        self.assertEqual(times, list(range(0, 70_001, 10)))

    def test_finish_switches_pumps_off_and_settles(self):
        env = SimulationEnvironment(build_model_1(), MODEL_1_SIMULATION_PARAMETERS)
        start(env, 5)
        env.command(True, False)            # still ON when the run ends
        env.advance_to(10_000)
        env.finish()
        self.assertEqual(env.now_ms(), 20_000)              # T_set = 10 s (R09)
        self.assertEqual(env.truth_rows[-1]["volume_ml"], 15.0)
        self.assertEqual(env.events[-1][2], "finish")

    def test_deterministic(self):
        a, calls_a = run_schedule(5, 43_000)
        b, calls_b = run_schedule(5, 43_000)
        self.assertEqual(calls_a, calls_b)
        self.assertEqual(a.truth_rows, b.truth_rows)
        self.assertEqual(a.events, b.events)

    def test_invalid_start_volume_rejected(self):
        env = SimulationEnvironment(build_model_1(), MODEL_1_SIMULATION_PARAMETERS)
        with self.assertRaises(ValueError):
            start(env, 61)

    def test_advance_must_be_on_step_grid_and_forward(self):
        env = SimulationEnvironment(build_model_1(), MODEL_1_SIMULATION_PARAMETERS)
        start(env, 5)
        with self.assertRaises(ValueError):
            env.advance_to(15)
        env.advance_to(100)
        with self.assertRaises(ValueError):
            env.advance_to(50)


if __name__ == "__main__":
    unittest.main()
