"""End-to-end verification of the evaluator on Model 1 run files (WP12).

Each run goes through the real chain: D37 rule check -> harness (D38 call
loop, sensor override) -> Model 1 in the shared simulation environment
(WP10, cut-off) -> run-file writer -> evaluator reading the files from disk.
The expected results are the hand calculations of
`design/functional_requirements.md` section 9, copied as literal numbers;
they were not derived from any code.

Controllers are TEST DOUBLES only (D29), never controllers under test:
- `double_fill_until_wet.py` (closed loop, labelled) for S2, S3 and S4;
- open-loop schedules whose ON/OFF times are taken from the section 9 table
  (S1, S5 and the faulty examples). The FR09 runs are therefore not closed
  loop on the controller side; t_w still comes from the Model 1 run.

The WP03 section 9 note "results may differ by one call period" is not
needed for Model 1: exact arithmetic (D40) makes the sensor switch exactly
at 24 mL, so the values below are exact.
"""

import os
import tempfile
import unittest

from shared.run_scenario import run_case
from shared.tests.doubles_support import FILL_UNTIL_WET, write_schedule_double
from testing.evaluator import evaluate_run, write_verdict

# case: (double, (on_s, off_s) for schedules, t_w_ms, intervals, V_end, end state)
CORRECT = {
    "S1-10": ("schedule", (0.0, 10.0), None, [[0, 10_000]], 15.0, "DONE_COMPLETE"),
    "S1-20": ("schedule", (0.0, 20.0), 19_000, [[0, 20_000]], 25.0, "DONE_COMPLETE"),
    "S2": ("closed", None, 19_000, [[0, 19_000]], 24.0, "DONE_COMPLETE"),
    "S3-FR03": ("closed", None, 0, [], 30.0, "DONE_SKIPPED"),
    "S3-FR09-40": ("closed", None, 0, [], 30.0, "DONE_SKIPPED"),
    "S4": ("closed", None, None, [[0, 30_000]], 35.0, "DONE_TIMEOUT"),
    "S5-30": ("schedule", (0.0, 25.0), 19_000, [[0, 25_000]], 30.0, "DONE_COMPLETE"),
    "S5-40": ("schedule", (0.0, 35.0), 19_000, [[0, 35_000]], 40.0, "DONE_COMPLETE"),
    "S5-45": ("schedule", (0.0, 40.0), 19_000, [[0, 40_000]], 45.0, "DONE_COMPLETE"),
    "S5-48": ("schedule", (0.0, 43.0), 19_000, [[0, 43_000]], 48.0, "DONE_COMPLETE"),
}


class EndToEnd(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def controller(self, kind, times, name):
        if kind == "closed":
            return FILL_UNTIL_WET
        return write_schedule_double(self.out, name, *times)

    def evaluate(self, controller_path, case_id, run_id):
        run_dir = run_case(controller_path, case_id, self.out, run_id=run_id,
                           purpose="reference")
        verdict = evaluate_run(run_dir)
        write_verdict(run_dir, verdict)
        self.assertTrue(os.path.isfile(os.path.join(run_dir, "verdict.json")))
        return verdict

    def results(self, verdict):
        return {c["id"]: c["result"] for c in verdict["checks"]}


class TestCorrectBehaviour(EndToEnd):

    def test_all_ten_cases_pass(self):
        for case_id, (kind, times, t_w, intervals, v_end, state) in CORRECT.items():
            with self.subTest(case=case_id):
                path = self.controller(kind, times, f"d_{case_id.replace('-', '_')}")
                v = self.evaluate(path, case_id, case_id)
                self.assertEqual(v["invalid_reasons"], [])
                self.assertEqual(v["overall"], "pass", self.results(v))
                obs = v["observations"]
                self.assertEqual(obs["t_w_ms"], t_w)
                self.assertEqual(obs["intake_intervals_ms"], intervals)
                self.assertEqual(obs["v0_ml"], 30.0 if case_id.startswith("S3") else 5.0)
                self.assertEqual(obs["v_end_ml"], v_end)
                self.assertEqual(obs["cutoff_events_ms"], [])
                self.assertFalse(obs["computed_overflow"])
                self.assertEqual(v["inferred_end_state"], state)
                self.assertEqual(self.results(v)["determinism_replay"], "pass")
                self.assertTrue(v["provisional"])

    def test_s4_plant_passes_sensor_while_input_held_dry(self):
        v = self.evaluate(FILL_UNTIL_WET, "S4", "s4")
        self.assertEqual(self.results(v)["FR08-L2"], "pass")
        self.assertEqual(self.results(v)["FR03-L1"], "pass")
        self.assertEqual(v["observations"]["v_peak_ml"], 35.0)

    def test_s5_48_margin(self):
        path = write_schedule_double(self.out, "d48", 0.0, 43.0)
        v = self.evaluate(path, "S5-48", "s5_48")
        self.assertEqual(v["margins"]["v_end_to_safe_mark_ml"], 2.0)
        self.assertEqual(v["margins"]["target_to_safe_mark_ml"], 2.0)


class TestFaultyBehaviour(EndToEnd):

    def test_s2_intake_never_switched_off(self):
        """WP03 section 9 faulty example (M1-12), recomputed for D45: cut-off
        at 48.5 s, V_end = 53.5 mL, above the safe mark."""
        path = write_schedule_double(self.out, "never_off", 0.0, None)
        v = self.evaluate(path, "S2", "never_off")
        r = self.results(v)
        self.assertEqual(v["overall"], "fail")
        self.assertEqual(r["FR03-L2"], "fail")
        self.assertEqual(r["FR08-L4"], "fail")
        self.assertEqual(r["FR08-P1"], "fail")                    # 53.5 > 50 mL
        self.assertEqual(v["observations"]["cutoff_events_ms"], [48_500])
        self.assertEqual(v["observations"]["v_end_ml"], 53.5)
        self.assertEqual(v["inferred_end_state"], "NOT_STOPPED")

    def test_s2_stop_at_19_1_accepted_19_2_rejected(self):
        for off_s, expected in ((19.1, "pass"), (19.2, "fail")):
            with self.subTest(off_s=off_s):
                path = write_schedule_double(self.out, f"off_{int(off_s * 10)}", 0.0, off_s)
                v = self.evaluate(path, "S2", f"s2_{int(off_s * 10)}")
                self.assertEqual(self.results(v)["FR03-L2"], expected)

    def test_s3_single_call_pulse(self):
        path = write_schedule_double(self.out, "pulse", 0.0, 0.1)
        v = self.evaluate(path, "S3-FR03", "pulse")
        self.assertEqual(self.results(v)["FR03-L3"], "fail")
        self.assertEqual(self.results(v)["FR03-P2"], "pass")       # 0.1 mL change only
        self.assertAlmostEqual(v["observations"]["v_end_ml"], 30.1, places=9)

    def test_s5_stops_at_sensor(self):
        """The FR03 double used for an FR09 run stops at t_w: wrong task."""
        v = self.evaluate(FILL_UNTIL_WET, "S5-48", "s5_at_sensor")
        r = self.results(v)
        self.assertEqual(r["FR09-L1"], "fail")
        self.assertEqual(r["FR09-L2"], "fail")
        self.assertEqual(r["FR09-P1"], "fail")
        self.assertEqual(v["observations"]["v_end_ml"], 24.0)

    def test_s1_duration_tolerance(self):
        for off_s, expected in ((10.2, "pass"), (10.3, "fail")):
            with self.subTest(off_s=off_s):
                path = write_schedule_double(self.out, f"s1_{int(off_s * 10)}", 0.0, off_s)
                v = self.evaluate(path, "S1-10", f"s1_{int(off_s * 10)}")
                self.assertEqual(self.results(v)["FR01-L2"], expected)

    def test_nondeterministic_double_fails(self):
        """D42 (3), researcher 2026-11-25: a replay difference fails the run."""
        from shared.tests.doubles_support import NONDETERMINISTIC
        v = self.evaluate(NONDETERMINISTIC, "S1-10", "nondet")
        self.assertEqual(self.results(v)["FR01-L2"], "pass")    # the run itself looks correct
        self.assertEqual(self.results(v)["determinism_replay"], "fail")
        self.assertEqual(v["overall"], "fail")

    def test_controller_error_fails_and_is_logged(self):
        """D42 (1), researcher 2026-11-25: a crash is a fail, with the error logged."""
        from shared.tests.doubles_support import write_source
        path = write_source(self.out, "raises", '''"""TEST DOUBLE: raises at 5 s."""

class Controller:
    def __init__(self, task, parameter, v_sensor_ml, q_in_ml_per_s, t_deadline_s):
        pass

    def step(self, t_s, sensor_wet):
        if t_s >= 5.0:
            raise RuntimeError("boom")
        return (True, False)
''')
        v = self.evaluate(path, "S2", "raises")
        self.assertEqual(v["overall"], "fail")
        self.assertEqual(v["invalid_reasons"], [])
        self.assertEqual([c["id"] for c in v["checks"]], ["controller_error"])
        self.assertIn("5.000 s", v["checks"][0]["evidence"])
        self.assertIn("boom", v["checks"][0]["evidence"])
        self.assertEqual(v["inferred_end_state"], "CONTROLLER_ERROR")
        self.assertEqual(v["observations"]["calls_completed"], 50)
        self.assertEqual(v["observations"]["intake_intervals_ms"], [[0, None]])

    def test_crash_in_constructor_fails(self):
        from shared.tests.doubles_support import write_source
        path = write_source(self.out, "init_raises", '''"""TEST DOUBLE: constructor raises."""

class Controller:
    def __init__(self, task, parameter, v_sensor_ml, q_in_ml_per_s, t_deadline_s):
        raise ValueError("cannot start")

    def step(self, t_s, sensor_wet):
        return (False, False)
''')
        v = self.evaluate(path, "S2", "init_raises")
        self.assertEqual(v["overall"], "fail")
        self.assertIn("cannot start", v["checks"][0]["evidence"])
        self.assertEqual(v["observations"]["calls_completed"], 0)

    def test_wrong_answer_type_fails(self):
        from shared.tests.doubles_support import write_source
        path = write_source(self.out, "ints", '''"""TEST DOUBLE: answers with integers."""

class Controller:
    def __init__(self, task, parameter, v_sensor_ml, q_in_ml_per_s, t_deadline_s):
        pass

    def step(self, t_s, sensor_wet):
        return (1, 0)
''')
        v = self.evaluate(path, "S1-10", "ints")
        self.assertEqual(v["overall"], "fail")
        self.assertIn("expected (bool, bool)", v["checks"][0]["evidence"])


if __name__ == "__main__":
    unittest.main()
