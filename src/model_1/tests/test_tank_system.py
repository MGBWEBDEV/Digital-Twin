"""WP10 mathematical verification, TankSystem level.

Oracles M1-1 ... M1-7 are the hand-calculated values of
design/mathematical_models.md section 9.1, copied as literal numbers (not
recomputed from the model's own equations). Effective pump states are given
directly, as in that section. Placeholder parameters (D34): Q_in = Q_out =
1.0 mL/s, C = 60 mL, V_sensor = 24 mL, V_dead = 0, dt_s = 10 ms.
"""

import random
import unittest
from fractions import Fraction

from model_1 import Model1Parameters, build_model_1
from model_1.exact import exact
from model_1.water_tank import WaterTank

STEP_MS = 10


def run(v0, intake, outtake, until_ms):
    """Step a Model 1 TankSystem from t = 0 to until_ms.

    intake, outtake: functions t_ms -> bool giving the effective state for the
    step starting at t_ms. Returns (system, volumes, sensor, events) where
    volumes and sensor map t_ms -> value (t = 0 and every step end) and events
    is a list of (t_ms, name) stamped with the step end time t_{n+1}.
    """
    ts = build_model_1()
    ts.reset(v0)
    volumes = {0: ts.tank.volume_ml}
    sensor = {0: ts.sensor_wet()}
    events = []
    t = 0
    while t < until_ms:
        new = ts.step(STEP_MS, intake(t), outtake(t))
        t += STEP_MS
        volumes[t] = ts.tank.volume_ml
        sensor[t] = ts.sensor_wet()
        events.extend((t, name) for name in new)
    return ts, volumes, sensor, events


def off(_t):
    return False


def on(_t):
    return True


def until(t_end_ms):
    return lambda t: t < t_end_ms


class TestHandCalculatedChecks(unittest.TestCase):

    def test_M1_1_both_off(self):
        _, vol, sensor, events = run(5, off, off, 60_000)
        self.assertTrue(all(v == 5 for v in vol.values()))
        self.assertEqual(events, [])
        self.assertFalse(any(sensor.values()))

    def test_M1_2_intake_on_0_to_10_s(self):
        _, vol, _, events = run(5, until(10_000), off, 30_000)
        self.assertEqual(vol[10_000], 15)
        self.assertTrue(all(vol[t] == 15 for t in vol if t >= 10_000))
        self.assertEqual(events, [])

    def test_M1_3_sensor_wet_at_equality(self):
        _, vol, sensor, _ = run(5, on, off, 19_000)
        self.assertEqual(vol[18_990], Fraction("23.99"))
        self.assertFalse(sensor[18_990])
        self.assertEqual(vol[19_000], 24)
        self.assertTrue(sensor[19_000])

    def test_M1_4_overflow_held_at_capacity_with_spill(self):
        ts, vol, _, events = run(55, until(10_000), off, 10_000)
        self.assertLess(vol[4_990], 60)
        self.assertTrue(all(vol[t] == 60 for t in vol if t >= 5_000))
        self.assertEqual(events, [(5_010, "overflow")])
        self.assertEqual(vol[10_000], 60)
        self.assertEqual(ts.tank.spill_ml, 5)
        self.assertTrue(ts.tank.overflow)
        # balance 60 + 5 = 55 + 10
        self.assertEqual(ts.tank.volume_ml + ts.tank.spill_ml, 55 + 10)

    def test_M1_5_outtake_dry_with_shortfall(self):
        ts, vol, _, events = run(2, off, until(5_000), 5_000)
        self.assertGreater(vol[1_990], 0)
        self.assertTrue(all(vol[t] == 0 for t in vol if t >= 2_000))
        self.assertEqual(events, [(2_010, "outtake_dry")])
        self.assertEqual(ts.tank.shortfall_ml, 3)
        self.assertTrue(ts.tank.dry)
        # balance 0 - 3 = 2 - 5
        self.assertEqual(ts.tank.volume_ml - ts.tank.shortfall_ml, 2 - 5)

    def test_M1_6_both_on(self):
        _, vol, _, events = run(10, until(10_000), until(10_000), 10_000)
        self.assertTrue(all(v == 10 for v in vol.values()))
        self.assertEqual(events, [])

    def test_M1_7_wet_at_start(self):
        _, _, sensor, _ = run(30, off, off, 0)
        self.assertTrue(sensor[0])


class TestMassBalance(unittest.TestCase):
    """WP05 section 4.8: V + V_spill - V_short = V0 + Q_in*T_in - Q_out*T_out
    at every step, exactly."""

    def check_balance(self, ts, v0):
        p = Model1Parameters()
        lhs = ts.tank.volume_ml + ts.tank.spill_ml - ts.tank.shortfall_ml
        rhs = (exact(v0)
               + exact(p.q_in_ml_per_s) * Fraction(ts.intake_on_ms, 1000)
               - exact(p.q_out_ml_per_s) * Fraction(ts.outtake_on_ms, 1000))
        self.assertEqual(lhs, rhs)

    def test_balance_random_commands_across_both_boundaries(self):
        rng = random.Random(20261125)      # fixed seed: deterministic test
        reached_overflow = reached_dry = False
        for v0 in (0, 2, 5, 30, 55, 60):
            ts = build_model_1()
            ts.reset(v0)
            intake = outtake = False
            for n in range(20_000):        # 200 s
                if n % 10 == 0:            # commands change at call times only
                    intake = rng.random() < 0.6
                    outtake = rng.random() < 0.4
                ts.step(STEP_MS, intake, outtake)
                self.check_balance(ts, v0)
                self.assertTrue(0 <= ts.tank.volume_ml <= 60)
            reached_overflow |= ts.tank.overflow
            reached_dry |= ts.tank.dry
        # The random runs must actually reach both boundaries to test them.
        self.assertTrue(reached_overflow and reached_dry)

    def test_balance_in_M1_4_and_M1_5(self):
        ts, *_ = run(55, until(10_000), off, 10_000)
        self.check_balance(ts, 55)
        ts, *_ = run(2, off, until(5_000), 5_000)
        self.check_balance(ts, 2)


class TestBoundariesAndInputs(unittest.TestCase):

    def test_v0_outside_range_rejected(self):
        ts = build_model_1()
        with self.assertRaises(ValueError):
            ts.reset(-0.1)
        with self.assertRaises(ValueError):
            ts.reset(60.01)
        ts.reset(0)
        ts.reset(60)

    def test_dead_volume_is_not_removable(self):
        tank = WaterTank(capacity_ml=60, dead_volume_ml=1)
        tank.reset(3)
        removed = tank.remove(5)
        self.assertEqual(removed, 2)
        self.assertEqual(tank.volume_ml, 1)
        self.assertEqual(tank.shortfall_ml, 3)
        self.assertTrue(tank.dry)

    def test_events_reported_first_time_only(self):
        _, _, _, events = run(59, on, off, 5_000)
        self.assertEqual([name for _, name in events], ["overflow"])

    def test_no_tube_fill_input(self):
        # Researcher 2026-11-25 (D40): the intake tube is always empty at the
        # start of a run, so reset takes the start volume only.
        ts = build_model_1()
        with self.assertRaises(TypeError):
            ts.reset(5, 2)

    def test_float_rate_converted_exactly(self):
        p = Model1Parameters(q_in_ml_per_s=0.83)
        ts = build_model_1(p)
        ts.reset(5)
        for _ in range(1000):              # 10 s
            ts.step(STEP_MS, True, False)
        self.assertEqual(ts.tank.volume_ml, Fraction("13.3"))

    def test_truth_row_has_truth_log_columns(self):
        ts = build_model_1()
        ts.reset(5)
        row = ts.truth()
        for key in ("volume_ml", "intake_flowing", "outtake_flowing",
                    "overflow", "spill_ml", "shortfall_ml"):
            self.assertIn(key, row)
        self.assertIsInstance(row["volume_ml"], float)


if __name__ == "__main__":
    unittest.main()
