"""WP11 mathematical verification, full loop with the shared simulation
environment, the per-run cut-off and the E5 delays.

Oracles M2-4 ... M2-10 and the S2 step-by-step trace are the hand-calculated
values of design/mathematical_models.md sections 9.3 and 9.4, copied as
literal numbers. Columns: f0 = 0 (empty tube, every real run, D40 (2));
f0 = V_p (primed tube, TEST-ONLY PrimedTubePump, kept for reference); and the
Model 1 column of the same table, run on Model 1 with the same schedule so
that the difference between the models is visible in one place.

No controller is used (AGENTS.md, D29): fixed command schedules only (see
tests/support.py). "t_w" in the table is the first call that sees wet; the
schedule switches OFF at that call (FR03) or at t_w + 24 s (FR09 48 mL), and
the test asserts that the environment indeed reports wet first at t_w.
Closed-loop runs with a real controller are WP12/WP09b.
"""

import unittest

from model_1 import MODEL_1_SIMULATION_PARAMETERS, build_model_1
from model_2 import Model2Parameters
from model_2.tests.support import (T_MAX_V0_5_MS, T_MAX_V0_30_MS, environment,
                                   events_named, first_time, first_wet_call, row_at,
                                   run_schedule, sensor_at_call)
from shared.simulation_environment import SimulationEnvironment

P = Model2Parameters()          # provisional configuration, all candidates at placeholders


def v_end(env):
    return env.truth_rows[-1]["volume_ml"]


def run_model_2(v0, off_at, primed=False, t_max_ms=T_MAX_V0_5_MS, parameters=P):
    env = environment(parameters, primed=primed)
    calls = run_schedule(env, v0, off_at, t_max_ms)
    return env, calls


def run_model_1(v0, off_at, t_max_ms=T_MAX_V0_5_MS):
    env = SimulationEnvironment(build_model_1(), MODEL_1_SIMULATION_PARAMETERS)
    calls = run_schedule(env, v0, off_at, t_max_ms)
    return env, calls


class MassBalanceMixin:

    def assert_mass_balance(self, env):
        """WP05 section 5.7, exact, at the end of the run."""
        ts = env.tank
        tank, intake = ts.tank, ts.intake
        left = tank.volume_ml + intake.tube_fill_ml + tank.spill_ml - tank.shortfall_ml
        right = (ts.v0_ml + intake.tube_fill_start_ml + intake.pumped_ml
                 - ts.outtake.rate_ml_per_s * ts.outtake_on_ms / 1000)
        self.assertEqual(left, right)


class TestM2_4_CommunicationDelayOnly(unittest.TestCase):
    """E5 only: d_c = d_r = 0.02 s."""

    E5 = P.only("E5")

    def test_FR01_10_s(self):
        env, _ = run_model_2(5, 10_000, parameters=self.E5)
        rows = env.truth_rows
        self.assertEqual(row_at(rows, 20)["volume_ml"], 5.0)          # flow from 0.02 s
        self.assertEqual(row_at(rows, 30)["volume_ml"], 5.01)
        self.assertEqual(row_at(rows, 10_010)["volume_ml"], 14.99)
        self.assertEqual(row_at(rows, 10_020)["volume_ml"], 15.0)     # ... to 10.02 s
        self.assertEqual(row_at(rows, 10_030)["volume_ml"], 15.0)
        self.assertEqual(v_end(env), 15.0)                             # as Model 1

    def test_FR03(self):
        env, calls = run_model_2(5, 19_100, parameters=self.E5)
        rows = env.truth_rows
        self.assertEqual(first_time(rows, "sensor_true_wet"), 19_020)  # crossing at 19.02 s
        self.assertEqual(row_at(rows, 19_020)["volume_ml"], 24.0)
        self.assertEqual(events_named(env, "sensor_edge"),
                         [(19_040, "sim_env", "sensor_edge", "wet=True")])   # reported 19.04 s
        self.assertFalse(sensor_at_call(calls, 19_000))                # call 19.0 sees dry
        self.assertEqual(first_wet_call(calls), 19_100)                # call 19.1 sees wet
        self.assertEqual(row_at(rows, 19_110)["volume_ml"], 24.09)
        self.assertEqual(row_at(rows, 19_120)["volume_ml"], 24.1)      # flow stops 19.12 s
        self.assertEqual(v_end(env), 24.1)


class TestS2TraceProvisionalConfiguration(unittest.TestCase, MassBalanceMixin):
    """WP05 section 9.4, step-by-step S2 trace with f0 = 0."""

    def test_trace(self):
        env, calls = run_model_2(5, 21_200)
        rows = env.truth_rows
        self.assertEqual(row_at(rows, 20)["intake_pumped_ml"], 0.0)    # flow from 0.02 s
        self.assertEqual(row_at(rows, 30)["intake_pumped_ml"], 0.01)
        self.assertEqual(first_time(rows, "tube_fill_ml", 2.0), 2_020)  # tube full at 2.02 s
        self.assertEqual(row_at(rows, 21_010)["volume_ml"], 23.99)
        self.assertEqual(row_at(rows, 21_020)["volume_ml"], 24.0)      # V = 24 at 21.02 s
        self.assertEqual(first_time(rows, "sensor_true_wet"), 21_020)
        self.assertEqual(first_time(rows, "sensor_wet"), 21_120)      # S_out wet at 21.12 s
        self.assertEqual(events_named(env, "sensor_edge"),
                         [(21_140, "sim_env", "sensor_edge", "wet=True")])   # reported 21.14 s
        self.assertFalse(sensor_at_call(calls, 21_100))                # call 21.1 sees dry
        self.assertEqual(row_at(rows, 20_980)["volume_ml"], 23.96)     # true state seen at 21.1
        self.assertEqual(first_wet_call(calls), 21_200)                # call 21.2 sees wet
        self.assertEqual(env.tank.intake_on_ms, 21_200)                # effective ON 0.02-21.22 s
        # Row t_{n+1} describes step [t_n, t_{n+1}): the step ending 21.22 s is
        # still ON; the first run-on step is [21.22, 21.23).
        self.assertEqual(row_at(rows, 21_220)["runon_left_ml"], 0.0)
        self.assertEqual(row_at(rows, 21_220)["volume_ml"], 24.2)
        self.assertEqual(row_at(rows, 21_230)["runon_left_ml"], 0.49)  # run-on from 21.22 s
        self.assertEqual(row_at(rows, 21_720)["runon_left_ml"], 0.0)   # ... until 21.72 s
        self.assertTrue(row_at(rows, 21_720)["intake_flowing"])
        self.assertFalse(row_at(rows, 21_730)["intake_flowing"])
        self.assertEqual(v_end(env), 24.7)
        self.assertEqual(rows[-1]["intake_pumped_ml"], 21.7)
        self.assertEqual(rows[-1]["tube_fill_ml"], 2.0)
        self.assert_mass_balance(env)                                   # 24.70 + 2.00 = 5 + 0 + 21.70


class TestProvisionalConfigurationTable(unittest.TestCase, MassBalanceMixin):
    """WP05 section 9.4 table, columns f0 = 0, f0 = V_p, Model 1."""

    def check(self, v0, off_at, expected_empty, expected_primed, expected_model_1,
              t_max_ms=T_MAX_V0_5_MS):
        env, _ = run_model_2(v0, off_at, False, t_max_ms)
        self.assertEqual(v_end(env), expected_empty, "f0 = 0")
        self.assert_mass_balance(env)
        env, _ = run_model_2(v0, off_at, True, t_max_ms)
        self.assertEqual(v_end(env), expected_primed, "f0 = V_p")
        self.assert_mass_balance(env)
        env, _ = run_model_1(v0, off_at, t_max_ms)
        self.assertEqual(v_end(env), expected_model_1, "Model 1")

    def test_M2_5_S1_FR01_10_s(self):
        self.check(5, 10_000, 13.5, 15.5, 15.0)

    def test_M2_5_S1_FR01_20_s(self):
        self.check(5, 20_000, 23.5, 25.5, 25.0)
        env, calls = run_model_2(5, 20_000)
        self.assertIsNone(first_wet_call(calls))           # sensor never wet in the 20 s run
        self.assertFalse(any(r["sensor_true_wet"] for r in env.truth_rows))

    def test_M2_6_S2_FR03(self):
        env, calls = run_model_2(5, 21_200)
        self.assertEqual(first_wet_call(calls), 21_200)     # t_w = 21.2 s
        self.assertEqual(v_end(env), 24.7)
        env, calls = run_model_2(5, 19_200, primed=True)
        self.assertFalse(sensor_at_call(calls, 19_100))
        self.assertEqual(first_wet_call(calls), 19_200)     # t_w = 19.2 s
        self.assertEqual(v_end(env), 24.7)
        self.assert_mass_balance(env)
        env, calls = run_model_1(5, 19_000)
        self.assertEqual(first_wet_call(calls), 19_000)
        self.assertEqual(v_end(env), 24.0)

    def test_M2_7_S4_stop_at_deadline(self):
        self.check(5, 30_000, 33.5, 35.5, 35.0)

    def test_M2_8_S5_FR09_48_mL_empty_tube(self):
        env, calls = run_model_2(5, 21_200 + 24_000)        # OFF at 45.2 s
        self.assertEqual(first_wet_call(calls), 21_200)
        self.assertEqual(events_named(env, "cutoff"), [])   # would fire at 48.52 s
        self.assertEqual(env.tank.intake_on_ms, 45_200)     # flow stops 45.22 s
        self.assertEqual(env.truth_rows[-1]["intake_pumped_ml"], 45.7)
        self.assertEqual(env.truth_rows[-1]["tube_fill_ml"], 2.0)
        self.assertEqual(v_end(env), 48.7)
        self.assert_mass_balance(env)

    def test_M2_8_S5_FR09_48_mL_primed_tube(self):
        env, calls = run_model_2(5, 19_200 + 24_000, primed=True)   # OFF at 43.2 s
        self.assertEqual(first_wet_call(calls), 19_200)
        self.assertEqual(events_named(env, "cutoff"), [])
        self.assertEqual(env.tank.intake_on_ms, 43_200)     # flow stops 43.22 s
        self.assertEqual(v_end(env), 48.7)

    def test_M2_8_model_1_column(self):
        env, _ = run_model_1(5, 43_000)
        self.assertEqual(events_named(env, "cutoff"), [])
        self.assertEqual(v_end(env), 48.0)

    def test_M2_9_fault_intake_never_off(self):
        self.check(5, None, 52.0, 54.0, 53.5)
        for primed in (False, True):
            env, _ = run_model_2(5, None, primed)
            self.assertEqual(events_named(env, "cutoff"),
                             [(48_520, "sim_env", "cutoff", "pump=intake")])
            self.assertEqual(env.truth_rows[-1]["intake_pumped_ml"], 49.0)   # 48.5 + run-on 0.5
            self.assertEqual(events_named(env, "overflow"), [])
        env, _ = run_model_1(5, None)
        self.assertEqual(events_named(env, "cutoff"),
                         [(48_500, "sim_env", "cutoff", "pump=intake")])

    def test_M2_10_one_call_pulse_S3(self):
        self.check(30, 100, 30.0, 30.6, 30.1, t_max_ms=T_MAX_V0_30_MS)
        env, _ = run_model_2(30, 100, t_max_ms=T_MAX_V0_30_MS)
        self.assertEqual(env.truth_rows[-1]["tube_fill_ml"], 0.6)    # 0.1 + 0.5 into the tube


class TestInterfaceUnchanged(unittest.TestCase):
    """The controller-facing API and execution semantics are those of the
    shared environment (roadmap WP11)."""

    def test_same_environment_class_and_interface(self):
        env = environment()
        self.assertIs(type(env), SimulationEnvironment)
        env2, calls = run_model_2(5, 21_200)
        self.assertTrue(all(type(s) is bool for _, s, _ in calls))
        self.assertEqual(env2.parameters.step_ms, MODEL_1_SIMULATION_PARAMETERS.step_ms)
        self.assertEqual(env2.parameters.settle_ms, MODEL_1_SIMULATION_PARAMETERS.settle_ms)

    def test_truth_logged_at_start_and_every_step(self):
        env, _ = run_model_2(5, 10_000)
        self.assertEqual([r["t_ms"] for r in env.truth_rows], list(range(0, 70_001, 10)))

    def test_deterministic(self):
        a, calls_a = run_model_2(5, 45_200)
        b, calls_b = run_model_2(5, 45_200)
        self.assertEqual(calls_a, calls_b)
        self.assertEqual(a.truth_rows, b.truth_rows)
        self.assertEqual(a.events, b.events)

    def test_reused_environment_starts_with_empty_tube(self):
        env = environment()
        run_schedule(env, 5, 10_000)
        self.assertEqual(env.truth_rows[-1]["tube_fill_ml"], 2.0)
        run_schedule(env, 5, 10_000)                       # second run, same object
        self.assertEqual(env.truth_rows[0]["tube_fill_ml"], 0.0)
        self.assertEqual(v_end(env), 13.5)


if __name__ == "__main__":
    unittest.main()
