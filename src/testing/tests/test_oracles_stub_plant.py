"""Evaluator against the WP03 section 9 hand calculations, using run files
produced by fixed intake schedules on the stub plant (tests/support.py).

Expected values are copied from `design/functional_requirements.md` section 9
and `design/controller_behavior.md` section 7, not computed by the evaluator.
Placeholder values (D34): Q_in = 1.0 mL/s, sensor at 24 mL, V0 = 5 mL.
"""

import os
import tempfile
import unittest

from testing.evaluator import evaluate_run
from testing.tests.support import simulate


class OracleCase(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def run_schedule(self, scenario_id, intervals):
        run_dir = os.path.join(self._tmp.name, scenario_id)
        simulate(run_dir, scenario_id, intervals)
        return evaluate_run(run_dir)

    def results(self, verdict):
        return {c["id"]: c["result"] for c in verdict["checks"]}

    def assertAllPass(self, verdict, expected_ids):
        self.assertEqual(verdict["overall"], "pass", verdict["checks"])
        res = self.results(verdict)
        # every scored run also gets determinism_replay (D42 (3)); not applicable here
        self.assertEqual(sorted(res), sorted(expected_ids + ["determinism_replay"]))
        for cid, r in res.items():
            self.assertIn(r, ("pass", "not_applicable"), cid)


FR08_IDS = ["FR08-L1", "FR08-L2", "FR08-L3", "FR08-L4", "FR08-P1", "FR08-P2"]


class TestCorrectBehaviourOracles(OracleCase):
    """Rows of WP03 section 9 for a correct controller."""

    def test_s1_10s(self):
        v = self.run_schedule("S1-10", [(0, 10_000)])
        self.assertAllPass(v, ["FR01-L1", "FR01-L2", "FR01-P1"] + FR08_IDS)
        self.assertAlmostEqual(v["observations"]["v_end_ml"], 15.0)
        self.assertEqual(v["inferred_end_state"], "DONE_COMPLETE")

    def test_s1_20s_sensor_wet_at_19s_is_ignored(self):
        v = self.run_schedule("S1-20", [(0, 20_000)])
        self.assertAllPass(v, ["FR01-L1", "FR01-L2", "FR01-P1"] + FR08_IDS)
        self.assertAlmostEqual(v["observations"]["v_end_ml"], 25.0)
        self.assertEqual(v["observations"]["t_w_ms"], 19_000)

    def test_s2_off_at_19_0(self):
        v = self.run_schedule("S2", [(0, 19_000)])
        self.assertAllPass(v, ["FR03-L1", "FR03-L2", "FR03-P1"] + FR08_IDS)
        self.assertEqual(v["observations"]["t_w_ms"], 19_000)
        self.assertAlmostEqual(v["observations"]["v_end_ml"], 24.0)
        self.assertEqual(v["case"], "A")
        self.assertEqual(v["inferred_end_state"], "DONE_COMPLETE")

    def test_s2_off_at_19_1_still_accepted(self):
        v = self.run_schedule("S2", [(0, 19_100)])
        self.assertEqual(v["overall"], "pass")
        self.assertAlmostEqual(v["observations"]["v_end_ml"], 24.1)

    def test_s3_no_on_command(self):
        for sid, ids in (("S3-FR03", ["FR03-L3", "FR03-P2"]),
                         ("S3-FR09-40", ["FR09-L3", "FR09-P2"])):
            with self.subTest(sid):
                v = self.run_schedule(sid, [])
                self.assertAllPass(v, ids + FR08_IDS)
                self.assertEqual(v["case"], "B")
                self.assertAlmostEqual(v["observations"]["v_end_ml"], 30.0)
                self.assertEqual(v["inferred_end_state"], "DONE_SKIPPED")

    def test_s4_sensor_held_dry_stops_at_deadline(self):
        v = self.run_schedule("S4", [(0, 30_000)])
        self.assertAllPass(v, ["FR03-L1"] + FR08_IDS)   # S4: FR08 plus FR03-L1 (D41)
        self.assertEqual(self.results(v)["FR08-L2"], "pass")
        self.assertIsNone(v["observations"]["t_w_ms"])
        self.assertAlmostEqual(v["observations"]["v_end_ml"], 35.0)
        self.assertEqual(v["inferred_end_state"], "DONE_TIMEOUT")

    def test_s5_targets(self):
        # target -> OFF time (t_w = 19 s plus T_extra) and V_end
        for target, off_ms in ((30, 25_000), (40, 35_000), (45, 40_000), (48, 43_000)):
            with self.subTest(target=target):
                v = self.run_schedule(f"S5-{target}", [(0, off_ms)])
                self.assertAllPass(v, ["FR09-L1", "FR09-L2", "FR09-P1"] + FR08_IDS)
                self.assertAlmostEqual(v["observations"]["v_end_ml"], float(target))
                self.assertEqual(v["margins"]["target_to_safe_mark_ml"], 50 - target)
                self.assertEqual(v["inferred_end_state"], "DONE_COMPLETE")


class TestFaultyBehaviourOracles(OracleCase):

    def test_s2_intake_never_switched_off(self):
        """WP03 section 9, last row, recomputed for D45: cut-off at 48.5 s;
        V_end = 53.5 mL, above the safe mark; FR03-L2, FR08-L4 and FR08-P1 fail."""
        v = self.run_schedule("S2", [(0, None)])
        res = self.results(v)
        self.assertEqual(v["overall"], "fail")
        self.assertEqual(res["FR03-L2"], "fail")
        self.assertEqual(res["FR08-L4"], "fail")
        self.assertEqual(res["FR08-P1"], "fail")
        self.assertEqual(v["observations"]["cutoff_events_ms"], [48_500])
        self.assertAlmostEqual(v["observations"]["v_end_ml"], 53.5)
        self.assertEqual(v["inferred_end_state"], "NOT_STOPPED")

    def test_s2_late_stop_fails_response(self):
        v = self.run_schedule("S2", [(0, 19_200)])
        self.assertEqual(self.results(v)["FR03-L2"], "fail")

    def test_s3_single_call_pulse(self):
        """WP03 section 10 example: a pulse violates FR03-L3 even though the
        volume change (0.1 mL) is within the tolerance."""
        v = self.run_schedule("S3-FR03", [(0, 100)])
        res = self.results(v)
        self.assertEqual(res["FR03-L3"], "fail")
        self.assertEqual(res["FR03-P2"], "pass")
        self.assertEqual(v["overall"], "fail")

    def test_s4_deadline_ignored(self):
        v = self.run_schedule("S4", [(0, None)])
        res = self.results(v)
        self.assertEqual(res["FR08-L2"], "fail")
        self.assertEqual(res["FR08-L4"], "fail")
        self.assertEqual(res["FR08-P1"], "fail")       # cut-off 48.5 s: 53.5 mL (D45)
        self.assertAlmostEqual(v["observations"]["v_end_ml"], 53.5)

    def test_s4_pulsing_while_waiting(self):
        # D41: FR03-L1 is also scored in S4, so a restart while waiting is caught.
        v = self.run_schedule("S4", [(0, 10_000), (10_100, 30_000)])
        self.assertEqual(self.results(v)["FR03-L1"], "fail")
        self.assertEqual(v["overall"], "fail")

    def test_s5_stops_at_sensor(self):
        v = self.run_schedule("S5-48", [(0, 19_000)])
        res = self.results(v)
        self.assertEqual(res["FR09-L1"], "fail")
        self.assertEqual(res["FR09-L2"], "fail")
        self.assertEqual(res["FR09-P1"], "fail")
        self.assertEqual(v["inferred_end_state"], "UNEXPECTED_STOP")

    def test_s5_wrong_extra_time_reaches_cutoff(self):
        # Hypothetical calculation error: T_extra = V_target / Q_in = 40 s -> OFF at 59 s.
        v = self.run_schedule("S5-40", [(0, 59_000)])
        res = self.results(v)
        self.assertEqual(res["FR09-L2"], "fail")
        self.assertEqual(res["FR09-P1"], "fail")
        self.assertEqual(res["FR08-L4"], "fail")
        self.assertAlmostEqual(v["observations"]["v_end_ml"], 53.5)   # cut-off 48.5 s


if __name__ == "__main__":
    unittest.main()
