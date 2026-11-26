"""WP11 mathematical verification, TankSystem level, one effect at a time.

Oracles M2-1 ... M2-3b are the hand-calculated values of
design/mathematical_models.md section 9.3, copied as literal numbers (not
recomputed from the model's own equations). Effective pump states are given
directly. Placeholders (D34): Q_in = Q_out = 1.0 mL/s, C = 60, V_sensor = 24,
V_dead = 0, dt_s = 10 ms; V_p = 2 mL (P12 = 2 s), V_ro = 0.5 mL (P13),
d_s = 0.1 s (P14); delta_trig = +0.5 mL in M2-3b is illustrative only.

Tests marked "hand calculation (WP11)" are additional cases worked out by
hand by Claude Code from WP05 section 5 for this WP, not taken from WP05;
they are not an independent human check.
"""

import random
import unittest
from fractions import Fraction

from model_1.pump import Pump
from model_1.water_tank import WaterTank
from model_2 import DelayedSensor, Model2Parameters, PrimingRunOnPump, build_model_2
from model_2.tests.support import (STEP_MS, off, on, run_steps, tank_system, until)

P = Model2Parameters()


class TestOneEffectAtATime(unittest.TestCase):
    """WP05 section 9.3."""

    def test_M2_1_E1_priming_empty_tube(self):
        ts = tank_system(P.only("E1"))
        rows, events = run_steps(ts, 5, until(10_000), off, 12_000)
        self.assertEqual(rows[1_990]["tube_fill_ml"], 1.99)
        self.assertEqual(rows[2_000]["tube_fill_ml"], 2.0)          # tube full at 2.0 s
        self.assertEqual(rows[2_000]["volume_ml"], 5.0)              # nothing reached the tank yet
        self.assertEqual(rows[10_000]["volume_ml"], 13.0)
        self.assertEqual(rows[12_000]["volume_ml"], 13.0)            # no run-on (E2 off)
        self.assertEqual(rows[12_000]["tube_fill_ml"], 2.0)          # retained while OFF
        self.assertEqual(events, [])

    def test_M2_1_E1_primed_tube_as_model_1(self):
        ts = tank_system(P.only("E1"), primed=True)
        rows, _ = run_steps(ts, 5, until(10_000), off, 12_000)
        self.assertEqual(rows[10_000]["volume_ml"], 15.0)
        self.assertEqual(rows[12_000]["volume_ml"], 15.0)

    def test_M2_2_E2_run_on(self):
        ts = tank_system(P.only("E2"))
        rows, _ = run_steps(ts, 5, until(10_000), off, 20_000)
        self.assertEqual(rows[10_000]["volume_ml"], 15.0)
        self.assertLess(rows[10_490]["volume_ml"], 15.5)
        self.assertEqual(rows[10_500]["volume_ml"], 15.5)            # rises to 15.5 at 10.5 s
        self.assertTrue(all(rows[t]["volume_ml"] == 15.5 for t in range(10_500, 20_001, 10)))

    def test_M2_3_E4_sensor_delay(self):
        ts = tank_system(P.only("E4"))
        rows, _ = run_steps(ts, 5, on, off, 20_000)
        true_wet = min(t for t, r in rows.items() if r["sensor_true_wet"])
        out_wet = min(t for t, r in rows.items() if r["sensor_wet"])
        self.assertEqual(true_wet, 19_000)
        self.assertEqual(out_wet, 19_100)
        self.assertEqual(rows[19_100]["volume_ml"], 24.1)

    def test_M2_3b_E3_illustrative_trigger_offset(self):
        # delta_trig = +0.5 mL is illustrative (WP05 5.4), not a placeholder.
        ts = tank_system(Model2Parameters(trigger_offset_ml=0.5).only("E3"))
        rows, _ = run_steps(ts, 5, on, off, 20_000)
        out_wet = min(t for t, r in rows.items() if r["sensor_wet"])
        self.assertEqual(out_wet, 19_500)
        self.assertEqual(rows[19_500]["volume_ml"], 24.5)
        self.assertEqual(ts.sensor.level_ml, 24)                     # value told to the controller unchanged


class TestIntakeRules(unittest.TestCase):
    """WP05 section 5.2. Hand calculation (WP11) unless stated."""

    def test_restart_supersedes_pending_run_on(self):
        # E2 only. ON 0-1 s, OFF 1.0-1.2 s, ON 1.2-3.0 s, then OFF.
        # Pumped: 1.0 + 0.2 (run-on, 0.3 still pending, then dropped by the
        # restart) + 1.8 + 0.5 (run-on after 3.0 s) = 3.5; V_end = 8.5.
        ts = tank_system(P.only("E2"))
        rows, _ = run_steps(ts, 5, lambda t: t < 1_000 or 1_200 <= t < 3_000, off, 5_000)
        self.assertEqual(rows[1_200]["volume_ml"], 6.2)
        self.assertEqual(rows[1_200]["runon_left_ml"], 0.3)
        self.assertEqual(rows[1_210]["runon_left_ml"], 0.0)
        self.assertEqual(rows[5_000]["volume_ml"], 8.5)
        self.assertEqual(rows[5_000]["intake_pumped_ml"], 3.5)

    def test_run_on_into_unprimed_tube_fills_tube_first(self):
        # E1 + E2. ON 0-1 s: 1.0 mL + run-on 0.5 mL, all into the 2 mL tube.
        ts = tank_system(P.only("E1", "E2"))
        rows, _ = run_steps(ts, 5, until(1_000), off, 3_000)
        self.assertEqual(rows[3_000]["volume_ml"], 5.0)
        self.assertEqual(rows[3_000]["tube_fill_ml"], 1.5)
        self.assertFalse(any(r["intake_flowing"] for r in rows.values()))

    def test_tube_retained_while_off_and_empty_at_every_reset(self):
        ts = tank_system(P.only("E1"))
        rows, _ = run_steps(ts, 5, until(1_000), off, 30_000)
        self.assertEqual(rows[30_000]["tube_fill_ml"], 1.0)
        ts.reset(5)                                                  # new run: D40 (2)
        self.assertEqual(ts.intake.tube_fill_ml, 0)
        self.assertEqual(ts.intake.runon_left_ml, 0)
        self.assertEqual(ts.intake.pumped_ml, 0)

    def test_intake_flowing_means_water_reaching_the_tank(self):
        ts = tank_system(P.only("E1", "E2"))
        rows, _ = run_steps(ts, 5, until(5_000), off, 7_000)
        self.assertFalse(rows[2_000]["intake_flowing"])              # tube still filling
        self.assertTrue(rows[2_010]["intake_flowing"])
        self.assertTrue(rows[5_500]["intake_flowing"])               # last run-on step
        self.assertFalse(rows[5_510]["intake_flowing"])
        self.assertEqual(rows[7_000]["volume_ml"], 8.5)              # 5 + 5 + 0.5 - 2

    def test_outtake_and_tank_are_the_model_1_classes(self):
        ts = build_model_2()
        self.assertIs(type(ts.outtake), Pump)
        self.assertIs(type(ts.tank), WaterTank)
        self.assertIsInstance(ts.intake, PrimingRunOnPump)
        self.assertIsInstance(ts.sensor, DelayedSensor)


class TestSensorRules(unittest.TestCase):
    """WP05 sections 5.3, 5.7. Hand calculation (WP11)."""

    def test_wet_at_start_is_output_immediately(self):
        ts = tank_system(P.only("E4"))
        rows, _ = run_steps(ts, 30, off, off, 500)
        self.assertTrue(all(r["sensor_wet"] for r in rows.values()))

    def test_falling_edge_is_delayed_too(self):
        # V0 = 24 (wet), outtake ON: V = 23.99 at 0.01 s, S_true dry at
        # 0.01 s, S_out dry at 0.11 s.
        ts = tank_system(P.only("E4"))
        rows, _ = run_steps(ts, 24, off, on, 500)
        self.assertFalse(rows[10]["sensor_true_wet"])
        self.assertTrue(rows[100]["sensor_wet"])
        self.assertFalse(rows[110]["sensor_wet"])

    def test_zero_delay_sensor_is_memoryless(self):
        s = DelayedSensor(24, 0, 0)
        s.reset(5)
        s.update(10, 24)
        self.assertTrue(s.is_wet())
        s.update(10, Fraction(2399, 100))
        self.assertFalse(s.is_wet())

    def test_invalid_delay_rejected(self):
        for bad in (-10, 10.0, True):
            with self.subTest(delay=bad), self.assertRaises(ValueError):
                DelayedSensor(24, 0, bad)


class TestMassBalance(unittest.TestCase):
    """WP05 section 5.7: V + f + spill - shortfall = V0 + f0 + P_in - Q_out * T_out,
    exact, after every step; random commands reaching overflow and empty tank."""

    def check(self, primed):
        rng = random.Random(11 if primed else 7)
        for v0 in (0, 2, 5, 23.99, 30, 58):
            ts = tank_system(P, primed=primed)
            ts.reset(v0)
            v0_exact = ts.v0_ml
            f0 = ts.intake.tube_fill_start_ml
            u_in = u_out = False
            for n in range(20_000):                       # 200 s
                if n % 10 == 0:                           # change only at call times
                    if rng.random() < 0.1:
                        u_in = not u_in
                    if rng.random() < 0.1:
                        u_out = not u_out
                ts.step(STEP_MS, u_in, u_out)
                tank, intake = ts.tank, ts.intake
                left = tank.volume_ml + intake.tube_fill_ml + tank.spill_ml - tank.shortfall_ml
                right = (v0_exact + f0 + intake.pumped_ml
                         - ts.outtake.rate_ml_per_s * ts.outtake_on_ms / 1000)
                self.assertEqual(left, right, f"V0={v0} step {n}")
                self.assertTrue(0 <= intake.tube_fill_ml <= intake.tube_volume_ml)
                self.assertTrue(0 <= intake.runon_left_ml <= intake.runon_ml)
            self.assertTrue(isinstance(ts.tank.volume_ml, Fraction))

    def test_empty_tube(self):
        self.check(primed=False)

    def test_primed_tube(self):
        self.check(primed=True)

    def test_random_runs_reach_both_boundaries(self):
        seen_overflow = seen_dry = False
        rng = random.Random(7)
        for v0 in (0, 2, 5, 23.99, 30, 58):
            ts = tank_system(P)
            ts.reset(v0)
            u_in = u_out = False
            for n in range(20_000):
                if n % 10 == 0:
                    if rng.random() < 0.1:
                        u_in = not u_in
                    if rng.random() < 0.1:
                        u_out = not u_out
                ts.step(STEP_MS, u_in, u_out)
            seen_overflow |= ts.tank.overflow
            seen_dry |= ts.tank.dry
        self.assertTrue(seen_overflow and seen_dry)


class TestParameters(unittest.TestCase):

    def test_placeholder_values_as_in_wp05_section_3(self):
        self.assertEqual(P.priming_time_s, 2.0)        # P12
        self.assertEqual(P.tube_volume_ml, 2)          # V_p = Q_in * t_p, exact
        self.assertEqual(P.runon_ml, 0.5)              # P13
        self.assertEqual(P.trigger_offset_ml, 0.0)     # delta_trig TBD -> 0
        self.assertEqual(P.sensor_delay_ms, 100)       # P14
        self.assertEqual((P.command_delay_ms, P.report_delay_ms), (20, 20))   # P15
        s = P.shared
        self.assertEqual((s.capacity_ml, s.sensor_level_ml, s.q_in_ml_per_s,
                          s.q_out_ml_per_s, s.dead_volume_ml), (60.0, 24.0, 1.0, 1.0, 0.0))

    def test_environment_parameters(self):
        sp = P.simulation_parameters()
        self.assertEqual((sp.step_ms, sp.settle_ms, sp.command_delay_ms, sp.report_delay_ms),
                         (10, 10_000, 20, 20))

    def test_delays_must_be_on_the_step_grid(self):
        with self.assertRaises(ValueError):
            Model2Parameters(sensor_delay_ms=105).simulation_parameters()
        with self.assertRaises(ValueError):
            Model2Parameters(command_delay_ms=25).simulation_parameters()

    def test_invalid_values_rejected(self):
        for kwargs in ({"priming_time_s": -1}, {"runon_ml": -0.1}, {"sensor_delay_ms": 0.1},
                       {"command_delay_ms": -20}, {"trigger_offset_ml": None}):
            with self.subTest(**kwargs), self.assertRaises((ValueError, TypeError)):
                Model2Parameters(**kwargs)

    def test_only_and_effects_off(self):
        zero = P.with_effects_off()
        self.assertEqual((zero.tube_volume_ml, zero.runon_ml, zero.trigger_offset_ml,
                          zero.sensor_delay_ms, zero.command_delay_ms, zero.report_delay_ms),
                         (0, 0, 0, 0, 0, 0))
        e5 = P.only("E5")
        self.assertEqual((e5.tube_volume_ml, e5.runon_ml, e5.sensor_delay_ms,
                          e5.command_delay_ms, e5.report_delay_ms), (0, 0, 0, 20, 20))
        with self.assertRaises(ValueError):
            P.only("E6")


if __name__ == "__main__":
    unittest.main()
