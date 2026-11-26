"""WP04 calibration runner (shared.run_calibration) against the labelled fake
firmware (fake_rig.py). No hardware; no water; all numbers are test numbers,
not rig values (D34)."""

import json
import os
import shutil
import tempfile
import unittest

from shared.rig_environment import RigConfig
from shared.run_calibration import check_plan, run_action
from shared.run_scenario import ConfigurationError
from shared.tests.fake_rig import FakeClock, FakeFirmware, FakeLink


def plan(actions, ceiling=None, **kw):
    limits = [a.get("duration_ms") or a.get("pulse_ms") or a.get("max_ms") for a in actions
              if a["kind"] in ("timed_fill", "sensor_steps", "sensor_crossing")]
    p = {"session_id": "TEST", "approved_by": "tester", "approved_on": "2026-11-26",
         "firmware_ceiling_ms": ceiling or (max(limits) if limits else None),
         "graduation_ml": 1.0, "safe_mark_ml": 50.0, "q_hi_ml_per_s": 1.5,
         "q_hi_source": "test number", "actions": actions}
    p.update(kw)
    return p


FILL = {"label": "F1", "kind": "timed_fill", "measure": "M3", "duration_ms": 3000,
        "tube": "empty", "v0_plan_ml": 5.0, "v0_band_ml": 1.0}


class CalibrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.clock = FakeClock()

    def write(self, p):
        path = os.path.join(self.tmp, "plan.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(p, fh)
        return path

    def run_it(self, p, label, answers, sensor_pin=-1, wet_level=None, fw=None):
        fw = fw or FakeFirmware(self.clock, p["firmware_ceiling_ms"] or 1, sensor_pin=sensor_pin)
        ask = answers if callable(answers) else (lambda it: lambda prompt: next(it))(iter(answers))
        out = run_action(self.write(p), label, FakeLink(fw), RigConfig(1, wet_level),
                         os.path.join(self.tmp, "data"), ask=ask, clock_ns=self.clock,
                         sleep=self.clock.sleep)
        with open(os.path.join(out, "calibration.json"), encoding="utf-8") as fh:
            return json.load(fh), fw, out

    def test_timed_fill_firmware_timed(self):
        rec, fw, out = self.run_it(plan([FILL]), "F1", ["5.0", "0.5", "RUN", "8.0", "0.5", ""])
        (start, end), = fw.on_intervals[0]
        self.assertEqual(end - start, 3000)                 # exactly the limit
        self.assertTrue(rec["cutoff_seen"])
        self.assertTrue(rec["valid"])
        self.assertEqual(rec["purpose"], "calibration")
        self.assertEqual(rec["end"]["volume_ml"], 8.0)
        self.assertEqual(rec["cutoffs"][0]["on_ms"], 3000)
        self.assertTrue(os.path.isfile(os.path.join(out, "events.csv")))
        self.assertEqual(os.path.basename(os.path.dirname(out)), "TEST")

    def test_timed_fill_with_settling_series(self):
        action = dict(FILL, measure="M5", settle_readings=True)
        answers = iter(["5.0", "0.5", "RUN", "7.5", "8.0", "8.0", "", "0.5", ""])

        def ask(prompt):
            if "after OFF" in prompt:
                self.clock.sleep(5)                         # the researcher waits 5 s
            return next(answers)

        rec, _, _ = self.run_it(plan([action]), "F1", ask)
        self.assertEqual([r["volume_ml"] for r in rec["end"]["series"]], [7.5, 8.0, 8.0])
        self.assertEqual([r["elapsed_s"] for r in rec["end"]["series"]], [5.0, 10.0, 15.0])
        self.assertEqual(rec["end"]["volume_ml"], 8.0)

    def test_readings_need_no_rig(self):
        p = plan([{"label": "R1", "kind": "readings", "measure": "M1", "count": 3}])
        it = iter(["5.0", "5.5", "5.0", "0.5", ""])
        out = run_action(self.write(p), "R1", None, None, os.path.join(self.tmp, "data"),
                         ask=lambda prompt: next(it), clock_ns=self.clock, sleep=self.clock.sleep)
        with open(os.path.join(out, "calibration.json"), encoding="utf-8") as fh:
            rec = json.load(fh)
        self.assertEqual([r["volume_ml"] for r in rec["readings"]], [5.0, 5.5, 5.0])
        self.assertIsNone(rec["rig"])

    def test_latency(self):
        p = plan([FILL, {"label": "L", "kind": "latency", "measure": "M6", "count": 5}])
        rec, fw, _ = self.run_it(p, "L", [])
        self.assertEqual(len(rec["round_trips_ms"]), 5)
        self.assertEqual(fw.on_intervals, [[], []])

    def test_sensor_steps_stop_at_first_wet(self):
        action = {"label": "S", "kind": "sensor_steps", "measure": "M7", "pulse_ms": 500,
                  "max_pulses": 10, "settle_ms": 10_000, "v0_plan_ml": 21.0, "v0_band_ml": 1.0}
        fw = FakeFirmware(self.clock, 500, sensor_pin=4, sensor_raw=0)
        answers = iter(["21.0", "0.5", "RUN", "21.5", "22.0", "22.5", ""])

        def ask(prompt):
            if prompt.startswith("Pulse 3"):
                fw.set_sensor(1)
            return next(answers)

        rec, fw, _ = self.run_it(plan([action]), "S", ask, sensor_pin=4, wet_level=1, fw=fw)
        self.assertEqual([(s["volume_ml"], s["sensor_wet"]) for s in rec["steps"]],
                         [(21.5, False), (22.0, False), (22.5, True)])
        self.assertTrue(all(s["cutoff_seen"] for s in rec["steps"]))
        self.assertEqual([e - s for s, e in fw.on_intervals[0]], [500, 500, 500])

    def test_sensor_crossing(self):
        action = {"label": "X", "kind": "sensor_crossing", "measure": "M8", "max_ms": 30_000,
                  "v0_plan_ml": 5.0, "v0_band_ml": 1.0}
        fw = FakeFirmware(self.clock, 30_000, sensor_pin=4, sensor_raw=0)
        answers = iter(["5.0", "0.5", "RUN", "24.0", "0.5", ""])

        def ask(prompt):
            if "Type RUN" in prompt:
                fw.wet_at_ms = self.clock.ms + 18_000
            return next(answers)

        rec, fw, _ = self.run_it(plan([action], q_hi_ml_per_s=1.0), "X", ask, sensor_pin=4,
                                 wet_level=1, fw=fw)
        c = rec["crossing"]
        self.assertFalse(c["cutoff_seen"])
        self.assertTrue(18_000 <= c["wet_edge_ms"] <= 18_010, c)
        (start, end), = fw.on_intervals[0]
        self.assertTrue(18_000 <= end - start <= 18_010)

    def test_refusals_before_pumping(self):
        cases = {
            "unapproved": (plan([FILL], approved_by=""), "F1"),
            "no measure": (plan([dict(FILL, measure=None)]), "F1"),
            "ceiling not max": (plan([FILL], ceiling=5000), "F1"),
            "too full": (plan([dict(FILL, duration_ms=30_000)], q_hi_ml_per_s=1.5), "F1"),
            "no rate source": (plan([FILL], q_hi_source=""), "F1"),
        }
        for name, (p, label) in cases.items():
            with self.subTest(name):
                fw = FakeFirmware(self.clock, p["firmware_ceiling_ms"], sensor_pin=-1)
                with self.assertRaises(ConfigurationError):
                    self.run_it(p, label, lambda prompt: self.fail("asked " + prompt), fw=fw)
                self.assertNotIn("kSetPumps", [m[1] for m in fw.received])

    def test_firmware_ceiling_mismatch_and_start_band(self):
        fw = FakeFirmware(self.clock, 4000, sensor_pin=-1)
        with self.assertRaises(ConfigurationError):
            self.run_it(plan([FILL]), "F1", lambda p: self.fail("asked"), fw=fw)
        fw = FakeFirmware(self.clock, 3000, sensor_pin=-1)
        with self.assertRaises(ConfigurationError):
            self.run_it(plan([FILL]), "F1", ["6.5", "0.5"], fw=fw)
        self.assertNotIn("kSetPumps", [m[1] for m in fw.received])

    def test_sensor_action_needs_sensor(self):
        action = {"label": "X", "kind": "sensor_crossing", "measure": "M8", "max_ms": 3000,
                  "v0_plan_ml": 5.0, "v0_band_ml": 1.0}
        with self.assertRaises(ConfigurationError):
            self.run_it(plan([action]), "X", lambda p: self.fail("asked"), sensor_pin=-1)

    def test_worst_end_rule(self):
        # 5 + 1 + 1.5 * 28 = 48 > 50 - 2 = 48? equal is allowed; 28.1 s is not.
        ok = check_plan(plan([dict(FILL, duration_ms=28_000)]), "F1", 28_000)[1]
        self.assertEqual(ok, [])
        bad = check_plan(plan([dict(FILL, duration_ms=28_100)]), "F1", 28_100)[1]
        self.assertTrue(any("worst end" in x for x in bad), bad)


if __name__ == "__main__":
    unittest.main()
