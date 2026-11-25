"""Harness and run-file writer (WP12 remainder), on Model 1.

Controllers here are TEST DOUBLES only (D29): the labelled files in
`doubles/`, open-loop schedules from `doubles_support.py`, and small spy
classes defined in this file that record what the harness passes in. No
controller under test is written or generated.
"""

import ast
import csv
import json
import os
import sys
import tempfile
import unittest

from model_1 import MODEL_1_SIMULATION_PARAMETERS, build_model_1
from shared import harness
from shared.environment import Environment
from shared.run_files import write_run_files
from shared.run_scenario import ConfigurationError, plan_for_case, run_case
from shared.simulation_environment import SimulationEnvironment
from shared.tests.doubles_support import (FILL_UNTIL_WET, NONDETERMINISTIC,
                                          write_schedule_double, write_source)
from testing.parameters import values
from testing.scenarios import SCENARIO_RUNS

SHARED_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def model_1_env():
    return SimulationEnvironment(build_model_1(), MODEL_1_SIMULATION_PARAMETERS)


def plan(case_id):
    return plan_for_case(SCENARIO_RUNS[case_id], values())


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class Spy:
    """TEST DOUBLE: records its constructor arguments and every step input;
    intake ON until 10 s, never reads the sensor."""

    instances = []

    def __init__(self, *args, **kwargs):
        self.args, self.kwargs, self.inputs = args, kwargs, []
        Spy.instances.append(self)

    def step(self, *args, **kwargs):
        self.inputs.append((args, kwargs))
        return (args[0] < 10.0, False)


class TestCallLoop(unittest.TestCase):

    def setUp(self):
        Spy.instances = []

    def test_call_times_order_and_inputs(self):
        env = model_1_env()
        record = harness.run_controller(Spy, env, plan("S2"))
        self.assertEqual(record.end_reason, harness.END_NORMAL)
        self.assertEqual(len(Spy.instances), 1)                     # fresh, once (D36)
        spy = Spy.instances[0]
        self.assertEqual(spy.args, ("FR03", 0.0, 24.0, 1.0, 30.0))  # request only (D35, R07)
        self.assertEqual(spy.kwargs, {})
        self.assertEqual([c[0] for c in record.calls], list(range(0, 60_001, 100)))
        for (args, kwargs), call in zip(spy.inputs, record.calls):
            self.assertEqual(kwargs, {})
            self.assertEqual(len(args), 2)                          # time and sensor only (D07)
            self.assertIs(type(args[0]), float)
            self.assertIs(type(args[1]), bool)
            self.assertEqual(args[0], call[0] / 1000)
            self.assertEqual(args[1], call[2])
        # finish(): pumps OFF at T_end and 10 s settling (D40 (3), R09).
        self.assertEqual(env.truth_rows[-1]["t_ms"], 70_000)
        self.assertEqual(env.truth_rows[-1]["volume_ml"], 15.0)

    def test_sensor_read_before_decision_at_each_call(self):
        """D38: the call at 19.0 s already sees the water reach 24 mL."""
        from shared.controller_check import load_controller_class
        with tempfile.TemporaryDirectory() as d:
            cls = load_controller_class(write_schedule_double(d, "sched", 0.0, 20.0))
        record = harness.run_controller(cls, model_1_env(), plan("S1-20"))
        wet = [c[0] for c in record.calls if c[1]]
        self.assertEqual(wet[0], 19_000)
        self.assertTrue(record.calls[190][3])        # S1-20: wet input ignored, still ON

    def test_override_dry_holds_input_but_not_plant(self):
        env = model_1_env()
        from shared.controller_check import load_controller_class
        record = harness.run_controller(load_controller_class(FILL_UNTIL_WET), env, plan("S4"))
        self.assertTrue(all(c[2] is False for c in record.calls))   # sensor_given
        self.assertEqual(next(c[0] for c in record.calls if c[1]), 19_000)  # plant wet
        self.assertEqual(env.truth_rows[-1]["volume_ml"], 35.0)

    def test_harness_has_no_physics_or_truth_access(self):
        with open(os.path.join(SHARED_DIR, "harness.py"), encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported.add(node.module.split(".")[0])
            elif isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.Attribute):
                self.assertNotIn(node.attr, ("truth_rows", "truth", "tank", "volume_ml"))
        self.assertEqual(imported - set(sys.stdlib_module_names), set())


class FakeRigEnvironment(Environment):
    """TEST DOUBLE environment for rig-like paths: calls arrive late by a
    fixed amount, and the environment can report a fault (WP06 X7, X8)."""

    def __init__(self, lateness_ms=0, fault_at_ms=None):
        self.lateness_ms, self.fault_at_ms = lateness_ms, fault_at_ms

    def start(self, scenario):
        self.t, self.run_valid, self.commands = 0, True, []

    def now_ms(self):
        return self.t

    def sensor(self):
        return False

    def command(self, intake, outtake):
        self.commands.append((self.t, intake, outtake))
        if self.fault_at_ms is not None and self.t >= self.fault_at_ms:
            self.run_valid = False

    def advance_to(self, t_ms):
        self.t = t_ms + self.lateness_ms

    def finish(self):
        self.commands.append((self.t, False, False))


class TestEnvironmentFaultsAndLateCalls(unittest.TestCase):

    def test_late_calls_logged_and_actual_time_given(self):
        env = FakeRigEnvironment(lateness_ms=60)
        record = harness.run_controller(Spy, env, plan("S2"))
        self.assertEqual(record.calls[1][0], 160)
        late = [e for e in record.events if e[2] == "late_call"]
        self.assertEqual(len(late), len(record.calls) - 1)

    def test_small_lateness_not_logged(self):
        record = harness.run_controller(Spy, FakeRigEnvironment(lateness_ms=49), plan("S2"))
        self.assertEqual([e for e in record.events if e[2] == "late_call"], [])

    def test_lateness_at_threshold_logged(self):
        record = harness.run_controller(Spy, FakeRigEnvironment(lateness_ms=50), plan("S2"))
        self.assertEqual(len([e for e in record.events if e[2] == "late_call"]),
                         len(record.calls) - 1)

    def test_fault_invalidates_run(self):
        env = FakeRigEnvironment(fault_at_ms=2_000)
        record = harness.run_controller(Spy, env, plan("S2"))
        self.assertEqual(record.end_reason, harness.END_INVALID)
        self.assertEqual(record.calls[-1][0], 2_000)
        self.assertIn("run_invalidated", [e[2] for e in record.events])
        self.assertEqual(env.commands[-1][1:], (False, False))      # finish() still called


class Raises:
    """TEST DOUBLE: raises at 5 s."""

    def __init__(self, *args):
        pass

    def step(self, t_s, sensor_wet):
        if t_s >= 5.0:
            raise RuntimeError("boom")
        return (True, False)


class WrongType:
    """TEST DOUBLE: answers with integers instead of booleans."""

    def __init__(self, *args):
        pass

    def step(self, t_s, sensor_wet):
        return (1, 0)


class InitFails:
    def __init__(self, *args):
        raise ValueError("bad request")


class TestControllerErrors(unittest.TestCase):

    def test_exception_in_step(self):
        env = model_1_env()
        record = harness.run_controller(Raises, env, plan("S2"))
        self.assertEqual(record.end_reason, harness.END_CONTROLLER_ERROR)
        self.assertEqual(record.calls[-1][0], 4_900)
        self.assertIn("boom", record.error)
        self.assertEqual(env.truth_rows[-1]["volume_ml"], 10.0)     # OFF at 5 s, settled

    def test_wrong_answer_type(self):
        record = harness.run_controller(WrongType, model_1_env(), plan("S2"))
        self.assertEqual(record.end_reason, harness.END_CONTROLLER_ERROR)
        self.assertEqual(record.calls, [])

    def test_exception_in_init(self):
        env = model_1_env()
        record = harness.run_controller(InitFails, env, plan("S2"))
        self.assertEqual(record.end_reason, harness.END_CONTROLLER_ERROR)
        self.assertEqual(record.calls, [])
        self.assertEqual(env.truth_rows[-1]["volume_ml"], 5.0)


class TestRunFiles(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_files_and_keys(self):
        run_dir = run_case(FILL_UNTIL_WET, "S2", self.out, run_id="r1")
        self.assertEqual(sorted(os.listdir(run_dir)),
                         ["calls.csv", "events.csv", "run.json", "truth.csv"])
        with open(os.path.join(run_dir, "run.json"), encoding="utf-8") as fh:
            run = json.load(fh)
        for key in ("run_id", "environment", "scenario_id", "request", "parameters",
                    "dt_call_ms", "end_reason"):                       # D41 (6)
            self.assertIn(key, run)
        self.assertEqual(run["end_reason"], "normal")
        self.assertEqual(run["environment"], "model_1")
        self.assertEqual(run["dt_sim_ms"], 10)
        self.assertEqual(run["controller"]["file"],
                         os.path.relpath(FILL_UNTIL_WET, os.path.dirname(os.path.dirname(SHARED_DIR))))
        self.assertTrue(run["controller"]["rule_check"]["ok"])
        self.assertEqual(run["determinism_replay"],
                         {"checked": True, "identical": True, "first_difference": None})
        for pid, value in values().items():
            self.assertEqual(run["parameters"][pid], value)
        self.assertEqual(run["parameters"]["P11"], 45.0)
        self.assertEqual(run["parameters"]["P01"], 60.0)

        calls = read_csv(os.path.join(run_dir, "calls.csv"))
        self.assertEqual(len(calls), 601)
        self.assertEqual(calls[190], {"t_ms": "19000", "sensor_env": "1", "sensor_given": "1",
                                      "intake": "0", "outtake": "0"})
        self.assertEqual(calls[189]["intake"], "1")

        truth = read_csv(os.path.join(run_dir, "truth.csv"))
        self.assertEqual(list(truth[0])[:7], ["t_ms", "volume_ml", "intake_flowing",
                                              "outtake_flowing", "overflow", "spill_ml",
                                              "shortfall_ml"])
        self.assertEqual(len(truth), 7_001)                          # t = 0 and every 10 ms
        self.assertEqual(float(truth[-1]["volume_ml"]), 24.0)

        events = read_csv(os.path.join(run_dir, "events.csv"))
        names = [e["event"] for e in events]
        self.assertEqual(names[0], "start")
        self.assertIn("sensor_edge", names)
        self.assertEqual(names[-1], "finish")
        times = [int(e["t_ms"]) for e in events]
        self.assertEqual(times, sorted(times))

    def test_never_overwrites(self):
        run_case(FILL_UNTIL_WET, "S2", self.out, run_id="same")
        with self.assertRaises(ConfigurationError):
            run_case(FILL_UNTIL_WET, "S2", self.out, run_id="same")
        with self.assertRaises(FileExistsError):
            write_run_files(os.path.join(self.out, "same"), {}, [], [])

    def test_parameter_mismatch_refused(self):
        plan_values = dict(values(), P05=25.0)
        with self.assertRaises(ConfigurationError):
            run_case(FILL_UNTIL_WET, "S2", self.out, run_id="x", plan_values=plan_values)
        self.assertFalse(os.path.exists(os.path.join(self.out, "x")))

    def test_rule_violation_not_run(self):
        marker = os.path.join(self.out, "ran")
        path = write_source(self.out, "bad", f'''
import time
open({marker!r}, "w").close()

class Controller:
    def __init__(self, task, parameter, v_sensor_ml, q_in_ml_per_s, t_deadline_s):
        pass
    def step(self, t_s, sensor_wet):
        return (time.time() > 0, False)
''')
        run_dir = run_case(path, "S2", self.out, run_id="bad")
        self.assertFalse(os.path.exists(marker))
        with open(os.path.join(run_dir, "run.json"), encoding="utf-8") as fh:
            run = json.load(fh)
        self.assertEqual(run["end_reason"], "rule_violation")
        rules = {v["rule"] for v in run["controller"]["rule_check"]["violations"]}
        self.assertEqual(rules, {"clock or pause", "files"})
        self.assertEqual(read_csv(os.path.join(run_dir, "calls.csv")), [])
        self.assertFalse(os.path.exists(os.path.join(run_dir, "truth.csv")))

    def test_determinism_replay_detects_difference(self):
        run_dir = run_case(NONDETERMINISTIC, "S1-10", self.out, run_id="nd")
        with open(os.path.join(run_dir, "run.json"), encoding="utf-8") as fh:
            run = json.load(fh)
        self.assertFalse(run["determinism_replay"]["identical"])
        self.assertEqual(run["determinism_replay"]["first_difference"],
                         {"t_ms": 0, "recorded": [True, False], "replayed": [False, False]})
        events = read_csv(os.path.join(run_dir, "events.csv"))
        self.assertIn("replay_differs", [e["event"] for e in events])
        times = [int(e["t_ms"]) for e in events]       # harness events merged in time order
        self.assertEqual(times, sorted(times))

    def test_fresh_controller_module_per_run(self):
        """D36: no memory of earlier runs, even for class-level state."""
        for run_id in ("a", "b"):
            run_dir = run_case(NONDETERMINISTIC, "S1-10", self.out, run_id=run_id)
            calls = read_csv(os.path.join(run_dir, "calls.csv"))
            self.assertEqual(calls[0]["intake"], "1", run_id)

    def test_schedule_double_runs(self):
        path = write_schedule_double(self.out, "sched", 0.0, 10.0)
        run_dir = run_case(path, "S1-10", self.out, run_id="s")
        truth = read_csv(os.path.join(run_dir, "truth.csv"))
        self.assertEqual(float(truth[-1]["volume_ml"]), 15.0)


if __name__ == "__main__":
    unittest.main()
