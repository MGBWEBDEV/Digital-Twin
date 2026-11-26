"""Unit tests for the shared simulation pieces: clock, cut-off, delay line,
parameters. They use no model."""

import unittest

from shared.clock import SimulationClock
from shared.cutoff import CutOff, t_max_ms
from shared.delay_line import DelayLine
from shared.simulation_environment import SimulationParameters


class TestClock(unittest.TestCase):

    def test_integer_ms_steps(self):
        clock = SimulationClock(10)
        for _ in range(10_000):
            clock.tick()
        self.assertEqual(clock.now_ms(), 100_000)
        clock.reset()
        self.assertEqual(clock.now_ms(), 0)

    def test_rejects_bad_step(self):
        for bad in (0, -10, 1.5, True):
            with self.assertRaises(ValueError):
                SimulationClock(bad)


class TestCutOff(unittest.TestCase):

    def test_trips_exactly_at_max_and_latches(self):
        c = CutOff(45_000)
        results = {t: c.apply(t, True) for t in range(0, 50_000, 10)}
        self.assertEqual(results[44_990], (True, False))
        self.assertEqual(results[45_000], (False, True))
        self.assertEqual(results[45_010], (False, False))
        self.assertEqual(sum(1 for _, trip in results.values() if trip), 1)

    def test_off_resets_and_new_edge_restarts(self):
        c = CutOff(1_000)
        for t in range(0, 1_010, 10):
            c.apply(t, True)
        self.assertEqual(c.apply(1_010, False), (False, False))
        self.assertEqual(c.apply(1_020, True), (True, False))
        self.assertEqual(c.apply(2_010, True), (True, False))
        self.assertEqual(c.apply(2_020, True), (False, True))

    def test_short_on_intervals_do_not_accumulate(self):
        c = CutOff(1_000)
        t = 0
        for _ in range(5):                  # five 0.9 s ON intervals
            for _ in range(90):
                self.assertEqual(c.apply(t, True), (True, False))
                t += 10
            c.apply(t, False)
            t += 10


class TestDelayLine(unittest.TestCase):

    def test_zero_delay_returns_latest(self):
        d = DelayLine(0, False)
        self.assertFalse(d.get(0))
        d.put(0, True)
        self.assertTrue(d.get(0))

    def test_later_put_at_same_time_wins(self):
        d = DelayLine(0, (False, False))
        d.put(100, (True, False))
        d.put(100, (False, False))
        self.assertEqual(d.get(100), (False, False))

    def test_nonzero_delay_slot(self):
        # The slot works for a non-zero delay (used by Model 2, WP11).
        d = DelayLine(20, False)
        d.put(100, True)
        self.assertFalse(d.get(110))
        self.assertTrue(d.get(120))

    def test_rejects_out_of_order_input(self):
        d = DelayLine(0, 0)
        d.put(100, 1)
        with self.assertRaises(ValueError):
            d.put(90, 2)


class TestPerRunCutOffLimit(unittest.TestCase):
    """D45 rule, protocol section 8. Expected values worked out by hand with
    the placeholders C = 60, R12 = 5, R14 = 1, V_ro = 0.5, Q_in,hi = 1.0."""

    PLACEHOLDERS = dict(capacity_ml=60.0, headroom_ml=5.0, v0_band_ml=1.0,
                        run_on_ml=0.5, q_in_hi_ml_per_s=1.0)

    def test_protocol_section_8_examples(self):
        # (60 - 5 - 6 - 0.5) / 1 = 48.5 s; (60 - 5 - 31 - 0.5) / 1 = 23.5 s
        self.assertEqual(t_max_ms(v0_plan_ml=5.0, **self.PLACEHOLDERS), 48_500)
        self.assertEqual(t_max_ms(v0_plan_ml=30.0, **self.PLACEHOLDERS), 23_500)

    def test_floored_to_tenth_of_a_second(self):
        # 48.5 / 1.3 = 37.307... s -> 37.3 s; 48.5 / 0.97 = 50.0 s exactly
        p = dict(self.PLACEHOLDERS, q_in_hi_ml_per_s=1.3)
        self.assertEqual(t_max_ms(v0_plan_ml=5.0, **p), 37_300)
        p = dict(self.PLACEHOLDERS, q_in_hi_ml_per_s=0.97)
        self.assertEqual(t_max_ms(v0_plan_ml=5.0, **p), 50_000)
        # Exact decimals: 0.1 + 0.2 style rounding must not lose a tenth.
        p = dict(self.PLACEHOLDERS, run_on_ml=0.3, headroom_ml=5.2)
        self.assertEqual(t_max_ms(v0_plan_ml=5.0, **p), 48_500)   # 60-5.2-6-0.3 = 48.5

    def test_no_positive_limit_refused(self):
        with self.assertRaises(ValueError):
            t_max_ms(v0_plan_ml=53.5, **self.PLACEHOLDERS)       # room exactly 0
        with self.assertRaises(ValueError):
            t_max_ms(v0_plan_ml=5.0, **dict(self.PLACEHOLDERS, q_in_hi_ml_per_s=0))


class TestSimulationParameters(unittest.TestCase):

    def test_defaults_are_the_placeholders(self):
        p = SimulationParameters()
        self.assertEqual((p.step_ms, p.settle_ms), (10, 10_000))
        self.assertEqual((p.command_delay_ms, p.report_delay_ms), (0, 0))

    def test_delays_must_be_whole_steps(self):
        with self.assertRaises(ValueError):
            SimulationParameters(command_delay_ms=15)
        with self.assertRaises(ValueError):
            SimulationParameters(report_delay_ms=-10)


if __name__ == "__main__":
    unittest.main()
