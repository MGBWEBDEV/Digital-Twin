"""Independence and consistency of the evaluator side.

- The evaluator modules import only the standard library and `testing`
  (`design/software_architecture.md` sections 1 and 9).
- The parameter values equal the placeholders in the design documents.
- The scenario runs are valid requests (WP03 section 4) and match section 8.
"""

import ast
import os
import re
import sys
import unittest

from testing.parameters import PARAMETERS
from testing.scenarios import SCENARIO_RUNS

HERE = os.path.dirname(os.path.abspath(__file__))
TESTING_DIR = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(TESTING_DIR))
EVALUATOR_MODULES = ("__init__.py", "evaluator.py", "runfiles.py", "parameters.py",
                     os.path.join("scenarios", "__init__.py"))


def imported_top_levels(path):
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), path)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                names.add("testing")
            else:
                names.add(node.module.split(".")[0])
    return names


class TestImports(unittest.TestCase):

    def test_evaluator_imports_only_stdlib_and_testing(self):
        allowed = set(sys.stdlib_module_names) | {"testing"}
        for rel in EVALUATOR_MODULES:
            with self.subTest(module=rel):
                names = imported_top_levels(os.path.join(TESTING_DIR, rel))
                self.assertEqual(names - allowed, set())
                self.assertFalse(names & {"shared", "model_1", "model_2", "controllers"})


def design_table_values(path, id_pattern):
    """{ID: first numeric value in the row's value column} from a markdown table."""
    with open(os.path.join(REPO, path), encoding="utf-8") as fh:
        text = fh.read()
    found = {}
    for line in text.splitlines():
        m = re.match(rf"\|\s*({id_pattern})\s*\|([^|]*)\|([^|]*)\|", line)
        if m:
            num = re.search(r"-?\d+(\.\d+)?", m.group(3))
            if num:
                found.setdefault(m.group(1), float(num.group(0)))
    return found


class TestParametersMatchDesign(unittest.TestCase):

    def test_r_values(self):
        doc = design_table_values("design/functional_requirements.md", r"R\d\d")
        for pid, p in PARAMETERS.items():
            if pid.startswith("R"):
                with self.subTest(pid=pid):
                    self.assertEqual(p.value, doc[pid])

    def test_p_values(self):
        doc = design_table_values("design/physical_system.md", r"P\d\d")
        for pid, p in PARAMETERS.items():
            if pid.startswith("P"):
                with self.subTest(pid=pid):
                    self.assertEqual(p.value, doc[pid])

    def test_all_values_are_placeholders(self):
        # D34: nothing here is a measurement yet.
        self.assertTrue(all(p.placeholder for p in PARAMETERS.values()))


class TestScenarios(unittest.TestCase):

    def test_ten_runs(self):
        # WP03 section 8: ten runs per controller per environment.
        self.assertEqual(len(SCENARIO_RUNS), 10)

    def test_requests_are_valid(self):
        v_sensor = PARAMETERS["P05"].value
        safe = PARAMETERS["P04"].value
        q_in = PARAMETERS["P06"].value
        eps_v = PARAMETERS["R05"].value
        for case in SCENARIO_RUNS.values():
            with self.subTest(case=case.run_case):
                self.assertIn(case.task, ("FR01", "FR03", "FR09"))
                self.assertIn("FR08", case.groups)
                if case.task == "FR01":
                    self.assertLessEqual(case.v0_ml + q_in * case.parameter, safe - eps_v)
                if case.task == "FR09":
                    self.assertGreater(case.parameter, v_sensor)
                    self.assertLessEqual(case.parameter, safe)

    def test_only_s4_overrides_the_sensor(self):
        overridden = [c.run_case for c in SCENARIO_RUNS.values() if c.sensor_override]
        self.assertEqual(overridden, ["S4"])
        self.assertEqual(SCENARIO_RUNS["S4"].sensor_override, "dry")


if __name__ == "__main__":
    unittest.main()
