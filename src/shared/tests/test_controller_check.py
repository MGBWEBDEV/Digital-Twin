"""D37 static rule check (WP12 remainder).

Every rule in D37 is exercised with a small rule-breaking file, plus the
labelled test doubles, which must pass. The check must never execute a file.
"""

import os
import sys
import tempfile
import unittest

from shared.controller_check import check_file, check_source, load_controller_class
from shared.tests.doubles_support import (FILL_UNTIL_WET, NONDETERMINISTIC,
                                          write_schedule_double, write_source)

GOOD_CLASS = '''
class Controller:
    def __init__(self, task, parameter, v_sensor_ml, q_in_ml_per_s, t_deadline_s):
        self.on = True

    def step(self, t_s, sensor_wet):
        {body}
        return (False, False)
'''


def with_body(body, header=""):
    return header + GOOD_CLASS.format(body=body)


class TestDoublesPass(unittest.TestCase):

    def test_labelled_doubles_pass(self):
        with tempfile.TemporaryDirectory() as d:
            schedule = write_schedule_double(d, "sched", 0.0, 10.0)
            for path in (FILL_UNTIL_WET, NONDETERMINISTIC, schedule):
                with self.subTest(path=os.path.basename(path)):
                    result = check_file(path)
                    self.assertTrue(result.ok, result.as_dict())
                    self.assertEqual(result.warnings, [])
                    self.assertEqual(len(result.sha256), 64)

    def test_allowed_standard_library(self):
        src = with_body("pass", "from __future__ import annotations\nimport math\n"
                                "from dataclasses import dataclass\n")
        self.assertTrue(check_source(src).ok)


class TestViolations(unittest.TestCase):

    CASES = {
        "clock time": (with_body("x = time.time()", "import time\n"), "clock or pause"),
        "monotonic": (with_body("x = monotonic()", "from time import monotonic\n"), "clock or pause"),
        "datetime": (with_body("x = datetime.now()", "from datetime import datetime\n"), "clock"),
        "sleep": (with_body("sleep(1)", "from time import sleep\n"), "clock or pause"),
        "input": (with_body("input()"), "pause"),
        "thread": (with_body("pass", "import threading\n"), "threads"),
        "asyncio": (with_body("pass", "import asyncio\n"), "threads"),
        "subprocess": (with_body("pass", "import subprocess\n"), "threads"),
        "open file": (with_body("open('log.txt', 'w')"), "files"),
        "os": (with_body("pass", "import os\n"), "files"),
        "pathlib": (with_body("pass", "from pathlib import Path\n"), "files"),
        "socket": (with_body("pass", "import socket\n"), "network"),
        "urllib": (with_body("pass", "import urllib.request\n"), "network"),
        "global stmt": (with_body("global COUNT\n        COUNT = 1"), "global state"),
        "module list": (with_body("pass", "HISTORY = []\n"), "global state"),
        "module dict call": (with_body("pass", "CACHE = dict()\n"), "global state"),
        "class list": ('''
class Controller:
    seen = []
    def __init__(self, task, parameter, v_sensor_ml, q_in_ml_per_s, t_deadline_s):
        pass
    def step(self, t_s, sensor_wet):
        return (False, False)
''', "global state"),
        "repository import": (with_body("pass", "import shared\n"), "not standard library"),
        "model import": (with_body("pass", "from model_1 import build_model_1\n"),
                         "not standard library"),
        "third party": (with_body("pass", "import numpy\n"), "not standard library"),
        "relative import": (with_body("pass", "from . import helper\n"), "not standard library"),
        "eval": (with_body("eval('1')"), "dynamic code"),
        "dunder import": (with_body("__import__('time')"), "dynamic import"),
        "importlib": (with_body("pass", "import importlib\n"), "dynamic import"),
        "random": (with_body("pass", "import random\n"), "non-deterministic"),
        "syntax": ("class Controller(:\n", "syntax"),
        "no class": ("def step(t_s, sensor_wet):\n    return (False, False)\n", "interface"),
        "no step": ('''
class Controller:
    def __init__(self, task, parameter, v_sensor_ml, q_in_ml_per_s, t_deadline_s):
        pass
''', "interface"),
        "step arity": ('''
class Controller:
    def __init__(self, task, parameter, v_sensor_ml, q_in_ml_per_s, t_deadline_s):
        pass
    def step(self, t_s):
        return (False, False)
''', "interface"),
        "init arity": ('''
class Controller:
    def __init__(self, task):
        pass
    def step(self, t_s, sensor_wet):
        return (False, False)
''', "interface"),
    }

    def test_each_rule(self):
        for name, (source, rule) in self.CASES.items():
            with self.subTest(case=name):
                result = check_source(source)
                self.assertFalse(result.ok)
                self.assertIn(rule, [f.rule for f in result.violations], result.as_dict())

    def test_constants_at_module_level_allowed(self):
        src = with_body("pass", "PERIOD_S = 0.1\nSTATES = ('a', 'b')\n")
        self.assertTrue(check_source(src).ok)


class TestWarnings(unittest.TestCase):

    def test_extra_class_and_renamed_arguments_warn_only(self):
        src = '''
class State:
    IDLE = 0

class Controller:
    def __init__(self, a, b, c, d, e):
        pass
    def step(self, t, wet):
        return (False, False)
'''
        result = check_source(src)
        self.assertTrue(result.ok, result.as_dict())
        self.assertEqual(sorted(f.rule for f in result.warnings),
                         ["interface", "interface", "one class"])


class TestNeverExecutes(unittest.TestCase):

    def test_check_does_not_run_the_file(self):
        with tempfile.TemporaryDirectory() as d:
            marker = os.path.join(d, "ran")
            path = write_source(d, "bad", f"open({marker!r}, 'w').close()\n" + GOOD_CLASS.format(body="pass"))
            result = check_file(path)
            self.assertFalse(result.ok)
            self.assertFalse(os.path.exists(marker))

    def test_each_load_is_a_fresh_module(self):
        first = load_controller_class(NONDETERMINISTIC)
        second = load_controller_class(NONDETERMINISTIC)
        self.assertIsNot(first, second)
        self.assertFalse([m for m in sys.modules if m.startswith("_controller_under_test_")])
        first(*("FR03", 0.0, 24.0, 1.0, 30.0))
        self.assertEqual(first.instances, 1)
        self.assertEqual(second.instances, 0)


if __name__ == "__main__":
    unittest.main()
