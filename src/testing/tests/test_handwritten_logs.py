"""Evaluator on hand-written run files: tolerance boundaries, each fault type
of `design/controller_behavior.md` section 6, rig readings, invalid runs and
malformed files. Volumes are written by hand, not computed by a plant.
"""

import contextlib
import io
import json
import os
import tempfile
import unittest

from testing.evaluator import evaluate_run, main
from testing.runfiles import RunFileError
from testing.tests.support import hand_calls, hand_truth, run_json, write_run


class HandCase(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._n = 0

    def evaluate(self, case_id, calls, truth=None, events=(), manual=None,
                 environment="stub", **run_overrides):
        self._n += 1
        run_dir = os.path.join(self._tmp.name, f"run{self._n}")
        run = run_json(case_id, environment=environment, **run_overrides)
        write_run(run_dir, run, calls, events, truth, manual)
        return evaluate_run(run_dir)

    @staticmethod
    def res(verdict):
        return {c["id"]: c["result"] for c in verdict["checks"]}


class TestTimingBoundaries(HandCase):

    def test_fr01_length_tolerance(self):
        # eps_t = 0.2 s (R03): 10.2 s passes, 10.3 s fails; 9.8 passes, 9.7 fails.
        for off, expected in ((10_200, "pass"), (10_300, "fail"),
                              (9_800, "pass"), (9_700, "fail")):
            with self.subTest(off=off):
                v = self.evaluate("S1-10", hand_calls([(0, off)], wet_from_ms=None),
                                  hand_truth(5.0, 5.0 + off / 1000))
                self.assertEqual(self.res(v)["FR01-L2"], expected)

    def test_fr01_start_limit(self):
        # t_start = 0.5 s (R02).
        for on, expected in ((500, "pass"), (600, "fail")):
            with self.subTest(on=on):
                v = self.evaluate("S1-10", hand_calls([(on, on + 10_000)]),
                                  hand_truth(5.0, 15.0))
                self.assertEqual(self.res(v)["FR01-L1"], expected)

    def test_fr01_volume_tolerance(self):
        # eps_V = 2 mL (R05): delivered 12.0 passes, 12.1 fails.
        for v_end, expected in ((17.0, "pass"), (17.1, "fail"), (13.0, "pass"), (12.9, "fail")):
            with self.subTest(v_end=v_end):
                v = self.evaluate("S1-10", hand_calls([(0, 10_000)]), hand_truth(5.0, v_end))
                self.assertEqual(self.res(v)["FR01-P1"], expected)

    def test_fr03_response_limit(self):
        # t_resp = 0.1 s (R04) after t_w = 19.0 s.
        for off, expected in ((19_000, "pass"), (19_100, "pass"), (19_200, "fail")):
            with self.subTest(off=off):
                v = self.evaluate("S2", hand_calls([(0, off)], wet_from_ms=19_000),
                                  hand_truth(5.0, 24.0))
                self.assertEqual(self.res(v)["FR03-L2"], expected)

    def test_fr09_extra_time_tolerance(self):
        # S5-40: T_extra = 16 s after t_w = 19 s -> nominal OFF 35.0 s, eps_t = 0.2 s.
        for off, expected in ((35_200, "pass"), (35_300, "fail"),
                              (34_800, "pass"), (34_700, "fail")):
            with self.subTest(off=off):
                v = self.evaluate("S5-40", hand_calls([(0, off)], wet_from_ms=19_000),
                                  hand_truth(5.0, 40.0))
                self.assertEqual(self.res(v)["FR09-L2"], expected)

    def test_fr08_deadline_with_sensor_held_dry(self):
        # S4: T_deadline 30 s + t_resp 0.1 s.
        for off, expected in ((30_000, "pass"), (30_100, "pass"), (30_200, "fail")):
            with self.subTest(off=off):
                v = self.evaluate("S4", hand_calls([(0, off)], wet_from_ms=19_000,
                                                   override_dry=True),
                                  hand_truth(5.0, 5.0 + off / 1000))
                self.assertEqual(self.res(v)["FR08-L2"], expected)

    def test_wet_exactly_at_deadline_counts_as_wet(self):
        # WP06 section 4: a wet input at the deadline call counts as wet by T_deadline.
        v = self.evaluate("S2", hand_calls([(0, 30_000)], wet_from_ms=30_000),
                          hand_truth(5.0, 24.0))
        self.assertEqual(self.res(v)["FR08-L2"], "not_applicable")
        self.assertEqual(self.res(v)["FR03-L2"], "pass")


class TestFaultEvents(HandCase):

    def test_outtake_on_once(self):
        v = self.evaluate("S1-10", hand_calls([(0, 10_000)], outtake_at={5_000}),
                          hand_truth(5.0, 15.0))
        self.assertEqual(self.res(v)["FR08-L1"], "fail")
        self.assertEqual(v["overall"], "fail")

    def test_restart_after_off(self):
        v = self.evaluate("S1-10", hand_calls([(0, 10_000), (20_000, 20_100)]),
                          hand_truth(5.0, 15.1))
        r = self.res(v)
        self.assertEqual(r["FR01-L1"], "fail")
        self.assertEqual(r["FR08-L3"], "fail")
        self.assertEqual(v["observations"]["extra_on_edges"], 1)

    def test_no_start(self):
        v = self.evaluate("S1-10", hand_calls([]), hand_truth(5.0, 5.0))
        r = self.res(v)
        self.assertEqual(r["FR01-L1"], "fail")
        self.assertEqual(r["FR01-P1"], "fail")
        self.assertEqual(v["inferred_end_state"], "NO_START")

    def test_cutoff_event_fails_fr08_l4(self):
        events = [(45_000, "simulation", "cutoff", "intake")]
        v = self.evaluate("S2", hand_calls([(0, 19_000)], wet_from_ms=19_000),
                          hand_truth(5.0, 24.0), events=events)
        self.assertEqual(self.res(v)["FR08-L4"], "fail")

    def test_computed_overflow_fails_fr08_p2(self):
        v = self.evaluate("S1-10", hand_calls([(0, 10_000)]),
                          hand_truth(5.0, 15.0, peak=60.0, overflow=True, spill=3.0))
        self.assertEqual(self.res(v)["FR08-P2"], "fail")

    def test_overflow_flag_alone_fails_fr08_p2(self):
        # Artificial log (peak below the mark but spill recorded) that isolates
        # the "no computed overflow" clause of FR08-P2.
        v = self.evaluate("S1-10", hand_calls([(0, 10_000)]),
                          hand_truth(5.0, 15.0, peak=40.0, overflow=True, spill=1.0))
        self.assertEqual(self.res(v)["FR08-P2"], "fail")

    def test_peak_above_mark_but_end_below(self):
        v = self.evaluate("S1-10", hand_calls([(0, 10_000)]),
                          hand_truth(5.0, 15.0, peak=50.5))
        r = self.res(v)
        self.assertEqual(r["FR08-P1"], "pass")
        self.assertEqual(r["FR08-P2"], "fail")

    def test_end_above_safe_mark(self):
        v = self.evaluate("S5-48", hand_calls([(0, 43_000)], wet_from_ms=19_000),
                          hand_truth(5.0, 50.1))
        self.assertEqual(self.res(v)["FR08-P1"], "fail")


class TestUndetermined(HandCase):

    def test_truth_log_ends_before_settling(self):
        v = self.evaluate("S2", hand_calls([(0, 19_000)], wet_from_ms=19_000),
                          hand_truth(5.0, 24.0, settled=False))
        r = self.res(v)
        self.assertEqual(r["FR03-P1"], "undetermined")
        self.assertEqual(r["FR08-P1"], "undetermined")
        self.assertEqual(v["overall"], "undetermined")

    def test_rig_end_reading_used_as_peak(self):
        # D41: outtake never ON, so the settled end reading stands for the peak.
        v = self.evaluate("S2", hand_calls([(0, 19_000)], wet_from_ms=19_000),
                          environment="rig", manual={"start": 5.0, "end": 24.5})
        r = self.res(v)
        self.assertEqual(r["FR03-P1"], "pass")
        self.assertEqual(r["FR08-P1"], "pass")
        self.assertEqual(r["FR08-P2"], "pass")
        self.assertEqual(v["overall"], "pass")
        self.assertEqual(v["observations"]["volume_source"], "manual.csv")

    def test_rig_end_reading_above_mark_fails_peak(self):
        v = self.evaluate("S5-48", hand_calls([(0, 43_000)], wet_from_ms=19_000),
                          environment="rig", manual={"start": 5.0, "end": 50.5})
        self.assertEqual(self.res(v)["FR08-P2"], "fail")

    def test_rig_peak_undetermined_when_outtake_ran(self):
        v = self.evaluate("S1-10", hand_calls([(0, 10_000)], outtake_at={5_000}),
                          environment="rig", manual={"start": 5.0, "end": 14.9})
        r = self.res(v)
        self.assertEqual(r["FR08-P2"], "undetermined")
        self.assertEqual(r["FR08-L1"], "fail")

    def test_rig_with_peak_reading(self):
        v = self.evaluate("S2", hand_calls([(0, 19_000)], wet_from_ms=19_000),
                          environment="rig", manual={"start": 5.0, "end": 24.5, "peak": 24.5})
        self.assertEqual(v["overall"], "pass")

    def test_rig_missing_end_reading(self):
        v = self.evaluate("S1-10", hand_calls([(0, 10_000)]),
                          environment="rig", manual={"start": 5.0})
        r = self.res(v)
        self.assertEqual(r["FR01-P1"], "undetermined")
        self.assertEqual(r["FR08-P1"], "undetermined")
        self.assertEqual(r["FR08-P2"], "undetermined")
        self.assertEqual(r["FR01-L2"], "pass")

    def test_rig_calls_may_be_irregular(self):
        calls = hand_calls([(0, 10_000)])
        calls = [(t + (7 if t == 5_000 else 0), *rest) for t, *rest in calls]
        v = self.evaluate("S1-10", calls, environment="rig",
                          manual={"start": 5.0, "end": 15.0, "peak": 15.0})
        self.assertEqual(v["overall"], "pass")


class TestInvalidRuns(HandCase):

    def assertInvalid(self, verdict, fragment):
        self.assertEqual(verdict["overall"], "invalid")
        self.assertEqual(verdict["checks"], [])
        self.assertTrue(any(fragment in r for r in verdict["invalid_reasons"]),
                        verdict["invalid_reasons"])

    def good(self):
        return hand_calls([(0, 10_000)]), hand_truth(5.0, 15.0)

    def test_end_reason_invalid(self):
        v = self.evaluate("S1-10", *self.good(), end_reason="invalid")
        self.assertInvalid(v, "end_reason")

    def test_run_invalidated_event(self):
        calls, truth = self.good()
        v = self.evaluate("S1-10", calls, truth,
                          events=[(3_000, "rig", "run_invalidated", "board reset")])
        self.assertInvalid(v, "run_invalidated")

    def test_parameter_mismatch(self):
        run = run_json("S1-10")
        params = dict(run["parameters"], R05=3.0)
        v = self.evaluate("S1-10", *self.good(), parameters=params)
        self.assertInvalid(v, "parameter R05")

    def test_request_mismatch(self):
        run = run_json("S5-40")
        req = dict(run["request"], v_sensor_ml=25.0)
        v = self.evaluate("S5-40", hand_calls([(0, 35_000)], wet_from_ms=19_000),
                          hand_truth(5.0, 40.0), request=req)
        self.assertInvalid(v, "request v_sensor_ml")

    def test_controller_error_with_setup_problem_still_invalid(self):
        """D42 (1): a crash fails the run only when the setup was valid."""
        run = run_json("S1-10")
        params = dict(run["parameters"], R05=3.0)
        v = self.evaluate("S1-10", hand_calls([(0, None)], t_end_ms=4_900),
                          hand_truth(5.0, 15.0, settled=False),
                          events=[(5_000, "harness", "controller_error", "boom")],
                          end_reason="controller_error", parameters=params)
        self.assertInvalid(v, "parameter R05")

    def test_controller_error_without_event_invalid(self):
        v = self.evaluate("S1-10", hand_calls([(0, None)], t_end_ms=4_900),
                          hand_truth(5.0, 15.0, settled=False),
                          end_reason="controller_error")
        self.assertInvalid(v, "no controller_error event")

    def test_replay_difference_fails(self):
        """D42 (3), researcher 2026-11-25."""
        v = self.evaluate("S1-10", hand_calls([(0, 10_000)]), hand_truth(5.0, 15.0),
                          events=[(0, "harness", "replay_differs", "t_ms 0")])
        self.assertEqual(v["overall"], "fail")
        self.assertEqual(self.res(v)["determinism_replay"], "fail")

    def test_replay_recorded_identical_passes(self):
        v = self.evaluate("S1-10", hand_calls([(0, 10_000)]), hand_truth(5.0, 15.0),
                          determinism_replay={"checked": True, "identical": True,
                                              "first_difference": None})
        self.assertEqual(v["overall"], "pass")
        self.assertEqual(self.res(v)["determinism_replay"], "pass")

    def test_replay_missing_not_applicable(self):
        v = self.evaluate("S1-10", hand_calls([(0, 10_000)]), hand_truth(5.0, 15.0))
        self.assertEqual(self.res(v)["determinism_replay"], "not_applicable")

    def test_controller_error_fails(self):
        v = self.evaluate("S1-10", hand_calls([(0, None)], t_end_ms=4_900),
                          hand_truth(5.0, 15.0, settled=False),
                          events=[(5_000, "harness", "controller_error", "boom")],
                          end_reason="controller_error")
        self.assertEqual(v["overall"], "fail")
        self.assertEqual(self.res(v), {"controller_error": "fail"})

    def test_call_log_ends_before_t_end(self):
        v = self.evaluate("S1-10", hand_calls([(0, 10_000)], t_end_ms=50_000),
                          hand_truth(5.0, 15.0))
        self.assertInvalid(v, "before T_end")

    def test_simulated_call_times_must_be_regular(self):
        calls = [(t + (1 if t == 5_000 else 0), *rest)
                 for t, *rest in hand_calls([(0, 10_000)])]
        v = self.evaluate("S1-10", calls, hand_truth(5.0, 15.0))
        self.assertInvalid(v, "k * dt_call")

    def test_sensor_override_inconsistent(self):
        # S2 has no override, so sensor_given must equal sensor_env.
        calls = hand_calls([(0, 30_000)], wet_from_ms=19_000, override_dry=True)
        v = self.evaluate("S2", calls, hand_truth(5.0, 35.0))
        self.assertInvalid(v, "override")

    def test_truth_v0_differs_from_scenario(self):
        v = self.evaluate("S1-10", hand_calls([(0, 10_000)]), hand_truth(6.0, 16.0))
        self.assertInvalid(v, "V0")

    def test_paired_run_v0_within_band_scored(self):
        # D46 (3): a paired run starts from the measured rig V0 (here 5.5 mL,
        # planned 5 +/- R14 = 1 mL); T_max stays that of the planned V0.
        v = self.evaluate("S1-10", hand_calls([(0, 10_000)]), hand_truth(5.5, 15.5),
                          purpose="paired", v0_ml=5.5)
        self.assertEqual(v["invalid_reasons"], [])
        self.assertEqual(v["overall"], "pass")
        self.assertEqual(v["purpose"], "paired")

    def test_paired_run_v0_outside_band(self):
        v = self.evaluate("S1-10", hand_calls([(0, 10_000)]), hand_truth(6.5, 16.5),
                          purpose="paired", v0_ml=6.5)
        self.assertInvalid(v, "paired V0")

    def test_changed_v0_only_for_paired_runs(self):
        v = self.evaluate("S1-10", hand_calls([(0, 10_000)]), hand_truth(5.5, 15.5),
                          v0_ml=5.5)
        self.assertInvalid(v, "run V0")

    def test_truth_v0_differs_from_run_v0(self):
        v = self.evaluate("S1-10", hand_calls([(0, 10_000)]), hand_truth(5.0, 15.0),
                          purpose="paired", v0_ml=5.5)
        self.assertInvalid(v, "truth V0")

    def test_t_max_must_follow_planned_v0(self):
        # D45: 48.5 s for V0 = 5 mL, 23.5 s for V0 = 30 mL (hand calculation).
        # A run made with the old single limit (45 s) is a setup error.
        calls, truth = self.good()
        v = self.evaluate("S1-10", calls, truth, t_max_s=45.0)
        self.assertInvalid(v, "t_max_s")
        v = self.evaluate("S3-FR03", hand_calls([], wet_from_ms=0), hand_truth(30.0, 30.0),
                          t_max_s=48.5)
        self.assertInvalid(v, "t_max_s")
        v = self.evaluate("S3-FR03", hand_calls([], wet_from_ms=0), hand_truth(30.0, 30.0))
        self.assertEqual(v["invalid_reasons"], [])
        # Paired runs keep the planned-V0 limit even when the measured V0 differs.
        v = self.evaluate("S1-10", hand_calls([(0, 10_000)]), hand_truth(5.5, 15.5),
                          purpose="paired", v0_ml=5.5, t_max_s=48.0)
        self.assertInvalid(v, "t_max_s")

    def test_unscored_purpose(self):
        for purpose in ("calibration", "cutoff_check", "verification", "unknown"):
            with self.subTest(purpose=purpose):
                v = self.evaluate("S1-10", *self.good(), purpose=purpose)
                self.assertInvalid(v, "not scored")

    def test_pool_runs_marked_exploratory(self):
        v = self.evaluate("S1-10", *self.good(), purpose="pool")
        self.assertEqual(v["overall"], "pass")
        self.assertTrue(v["exploratory"])
        v = self.evaluate("S1-10", *self.good(), purpose="fault")
        self.assertFalse(v["exploratory"])

    def test_unknown_scenario(self):
        calls, truth = self.good()
        v = self.evaluate("S1-10", calls, truth, scenario_id="S9")
        self.assertInvalid(v, "unknown scenario")

    def test_rig_start_reading_outside_band(self):
        # D46 (1): planned V0 5 mL, R14 = 1 mL; 6.0 is inside, 6.5 outside.
        calls = hand_calls([(0, 19_000)], wet_from_ms=19_000)
        v = self.evaluate("S2", calls, environment="rig", manual={"start": 6.0, "end": 25.0})
        self.assertNotEqual(v["overall"], "invalid")
        v = self.evaluate("S2", calls, environment="rig", manual={"start": 6.5, "end": 25.5})
        self.assertInvalid(v, "outside planned V0")
        v = self.evaluate("S2", calls, environment="rig", manual={"start": 3.9, "end": 22.9})
        self.assertInvalid(v, "outside planned V0")

    def test_fr01_precondition_on_rig(self):
        # V0 + Q_in * T_fill must be <= 50 - 2 mL: 39 + 10 = 49 > 48.
        v = self.evaluate("S1-10", hand_calls([(0, 10_000)]), environment="rig",
                          manual={"start": 39.0, "end": 49.0})
        self.assertInvalid(v, "precondition")


class TestMalformedFiles(HandCase):

    def test_missing_calls_file(self):
        run_dir = os.path.join(self._tmp.name, "broken")
        write_run(run_dir, run_json("S1-10"), hand_calls([]), truth=hand_truth(5.0, 5.0))
        os.remove(os.path.join(run_dir, "calls.csv"))
        with self.assertRaises(RunFileError):
            evaluate_run(run_dir)

    def test_bad_boolean(self):
        run_dir = os.path.join(self._tmp.name, "broken")
        write_run(run_dir, run_json("S1-10"), hand_calls([]), truth=hand_truth(5.0, 5.0))
        with open(os.path.join(run_dir, "calls.csv"), "a", encoding="utf-8") as fh:
            fh.write("60100,maybe,0,0,0\n")
        with self.assertRaises(RunFileError):
            evaluate_run(run_dir)

    def test_missing_new_run_keys(self):
        # purpose, v0_ml and t_max_s are required run.json keys (D45, D46).
        for key in ("purpose", "v0_ml", "t_max_s"):
            with self.subTest(key=key):
                run_dir = os.path.join(self._tmp.name, f"no_{key}")
                run = run_json("S1-10")
                del run[key]
                write_run(run_dir, run, hand_calls([(0, 10_000)]), truth=hand_truth(5.0, 15.0))
                with self.assertRaises(RunFileError):
                    evaluate_run(run_dir)

    def test_missing_truth_for_model_run(self):
        run_dir = os.path.join(self._tmp.name, "broken")
        write_run(run_dir, run_json("S1-10", environment="model_1"), hand_calls([]))
        with self.assertRaises(RunFileError):
            evaluate_run(run_dir)


class TestCommandLine(HandCase):

    def test_main_writes_verdict_json(self):
        run_dir = os.path.join(self._tmp.name, "cli")
        write_run(run_dir, run_json("S1-10"), hand_calls([(0, 10_000)]),
                  truth=hand_truth(5.0, 15.0))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main([run_dir]), 0)
        with open(os.path.join(run_dir, "verdict.json"), encoding="utf-8") as fh:
            verdict = json.load(fh)
        self.assertEqual(verdict["overall"], "pass")
        self.assertTrue(verdict["provisional"])
        self.assertIn("P05", verdict["placeholder_ids"])

    def test_main_reports_malformed_run(self):
        run_dir = os.path.join(self._tmp.name, "empty")
        os.makedirs(run_dir)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(main([run_dir]), 1)
        self.assertIn("missing file", err.getvalue())


if __name__ == "__main__":
    unittest.main()
