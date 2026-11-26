"""WP04 analysis rules (experiments/physical_characterization.md section 5).

ALL DATA HERE ARE SYNTHETIC, invented for testing the code, and are not
measurements (D34). Expected values were worked out by hand before running
the code:

  Researcher inputs: P01 60, P02 1, P04 50, P09 0, P10 5, R01 0.1.
  M1: [5.0, 5.0, 5.5, 5.0, 5.0], [40.0, 40.0, 40.0, 40.5, 40.0]
      -> half ranges 0.25, 0.25; u_read = max(0.5, 0.25) = 0.5.
  M3 (empty tube, from 5.0 mL): T 10 s: dV 9.5, 10.0, 9.5, 10.0, 9.5;
      T 20 s: dV 19.5, 20.0, 19.5, 19.5, 20.0.
      n 10, sum T 150, sum dV 147, sum T^2 2500, sum T dV 2455
      Q = (10*2455 - 150*147) / (10*2500 - 150^2) = 2500 / 2500 = 1.0 mL/s
      b = (147 - 150 * 1.0) / 10 = -0.3 mL
      s_run = 0.25 (ranges 0.5); Q_in,hi = max(11/10, 21/20) = 1.1 mL/s.
  M4 (primed, 20 s): dV 20.5, 20.5, 21.0, 20.5, 20.5 -> mean 20.6;
      b_primed = V_ro = 0.6; V_p = 0.6 - (-0.3) = 0.9.
  M5 series -> settling 5, 10, 15 s -> R09 = 15 s.
  M7: brackets (23, 24) and (22.5, 23.5) -> V_sensor 23.25, u 0.5 + 0.5 = 1.0.
  M8: t_pred = (23.25 - 5 + 0.3) / 1 = 18.55 s; edges 18.6, 18.7 -> delays
      0.05, 0.15 (mean 0.1); u_d = (0.5 + 1.0) / 1 = 1.5 -> E4 excluded.
  M6: RTT 4, 5, 6 ms -> median 5 ms, one way 2.5 ms; 0.0025 mL -> E5 excluded.
  E1 0.9 > 0.5 and > 0.5 -> included; E2 0.6 > 0.5 and > 0.5 -> included.
  Final: R05 = ceil(2*0.5 + 0.25 = 1.25) = 2; R12 = max(5, 4) = 5; R14 = 1;
      R16 = 0.5; S3 V0 = ceil(max(29.25, 26.25)) = 30;
      T_max(5) = floor10((60 - 5 - 6 - 0.6) / 1.1) = 48.4 / 1.1 = 44.0 s;
      T_max(30) = 23.4 / 1.1 = 21.27 -> 21.2 s;
      R06 = ceil5(1.5 * 18.25 = 27.375) = 30 (<= 44 - 5); R08 = ceil5(49) = 50;
      longest FR09 fill (48 - 5 + 0.3) / 1 = 43.3 s < 44.0 -> no flag.
"""

import json
import os
import tempfile
import unittest
from fractions import Fraction as Fr

from characterization import analysis as a

INPUTS = {"P01": 60, "P02": 1, "P04": 50, "P09": 0, "P10": 5, "R01": 0.1}


def fill(label, measure, duration_ms, dv, tube="empty", series=None, v0=5.0):
    end = v0 + dv
    return {"label": label, "kind": "timed_fill", "valid": True, "cutoff_seen": True,
            "action": {"measure": measure, "duration_ms": duration_ms, "tube": tube},
            "start": {"volume_ml": v0}, "end": {"volume_ml": end, "series": series or []}}


def synthetic_records():
    recs = [
        {"label": "M1-a", "valid": True, "action": {"measure": "M1"},
         "readings": [{"elapsed_s": 0, "volume_ml": x} for x in (5.0, 5.0, 5.5, 5.0, 5.0)]},
        {"label": "M1-b", "valid": True, "action": {"measure": "M1"},
         "readings": [{"elapsed_s": 0, "volume_ml": x} for x in (40.0, 40.0, 40.0, 40.5, 40.0)]},
        {"label": "M2", "valid": True, "action": {"measure": "M2"},
         "readings": [{"elapsed_s": 0, "volume_ml": 30.0}, {"elapsed_s": 600, "volume_ml": 30.0}]},
    ]
    recs += [fill(f"M3-10-{i}", "M3", 10_000, dv) for i, dv in
             enumerate((9.5, 10.0, 9.5, 10.0, 9.5))]
    series = {
        19.5: [(2, 23.5), (5, 24.0), (10, 24.5), (20, 24.5)],
        20.0: [(2, 23.0), (5, 24.0), (10, 24.5), (15, 25.0), (25, 25.0)],
        "c": [(2, 22.5), (5, 23.0), (10, 23.5), (15, 24.5), (30, 24.5)],
    }
    as_series = lambda s: [{"elapsed_s": t, "volume_ml": v} for t, v in s]  # noqa: E731
    recs += [fill("M5-1", "M5", 20_000, 19.5, series=as_series(series[19.5])),
             fill("M5-2", "M5", 20_000, 20.0, series=as_series(series[20.0])),
             fill("M5-3", "M5", 20_000, 19.5, series=as_series(series["c"])),
             fill("M3-20-4", "M3", 20_000, 19.5), fill("M3-20-5", "M3", 20_000, 20.0)]
    recs += [fill(f"M4-{i}", "M4", 20_000, dv, tube="primed") for i, dv in
             enumerate((20.5, 20.5, 21.0, 20.5, 20.5))]
    recs += [
        {"label": "M6", "valid": True, "action": {"measure": "M6"},
         "round_trips_ms": [4.0, 6.0, 5.0]},
        {"label": "M7-1", "valid": True, "action": {"measure": "M7"},
         "steps": [{"volume_ml": v, "sensor_wet": w} for v, w in
                   ((20.0, False), (21.0, False), (22.0, False), (23.0, False), (24.0, True))]},
        {"label": "M7-2", "valid": True, "action": {"measure": "M7"},
         "steps": [{"volume_ml": v, "sensor_wet": w} for v, w in
                   ((20.5, False), (21.5, False), (22.5, False), (23.5, True))]},
        {"label": "M8-1", "valid": True, "action": {"measure": "M8"},
         "start": {"volume_ml": 5.0}, "crossing": {"wet_edge_ms": 18_600}},
        {"label": "M8-2", "valid": True, "action": {"measure": "M8"},
         "start": {"volume_ml": 5.0}, "crossing": {"wet_edge_ms": 18_700}},
        {"label": "M3-bad", "valid": False, "action": {"measure": "M3", "duration_ms": 10_000},
         "cutoff_seen": True, "start": {"volume_ml": 5.0}, "end": {"volume_ml": 30.0}},
    ]
    return recs


class RuleTest(unittest.TestCase):
    def test_reading_uncertainty(self):
        self.assertEqual(a.reading_uncertainty([[5.0, 5.5, 5.0], [40, 40.5]], 1), Fr(1, 2))
        self.assertEqual(a.reading_uncertainty([[5.0, 6.5]], 1), Fr(3, 4))
        self.assertEqual(a.reading_uncertainty([], 1), Fr(1, 2))

    def test_consistency(self):
        self.assertTrue(a.consistent([[9.5, 10.0, 10.5]], 1))
        self.assertFalse(a.consistent([[9.5, 10.0, 11.0]], 1))

    def test_fit_exact_line(self):
        q, b, res = a.fit_rate_offset([(10, 9.5), (20, 19.5)])
        self.assertEqual((q, b), (Fr(1), Fr(-1, 2)))
        self.assertEqual(res, [0, 0])
        with self.assertRaises(ValueError):
            a.fit_rate_offset([(10, 9.5), (10, 10.0)])

    def test_q_in_hi(self):
        self.assertEqual(a.q_in_hi([(20, 20.0)], 0.5), Fr(21, 20))   # doc example 1.05

    def test_settling_time(self):
        self.assertEqual(a.settling_time([(2, 22.5), (5, 23.0), (10, 23.5), (15, 24.5),
                                          (30, 24.5)], 0.5), 15)
        self.assertEqual(a.r09([5, 10, 15]), 15)
        self.assertEqual(a.r09([3]), 10)
        self.assertEqual(a.r09([11]), 15)

    def test_sensor_switch_volume_needs_dry_then_wet(self):
        with self.assertRaises(ValueError):
            a.sensor_switch_volume([[(24.0, True)]], 0.5)
        with self.assertRaises(ValueError):
            a.sensor_switch_volume([[(20.0, False)]], 0.5)


class SummaryTest(unittest.TestCase):
    def setUp(self):
        self.s = a.summarize(synthetic_records(), INPUTS)

    def test_measured(self):
        s = self.s
        self.assertEqual(s["u_read"], 0.5)
        self.assertEqual(s["Q_in"], 1.0)
        self.assertAlmostEqual(s["b_empty"], -0.3, places=12)
        self.assertEqual(s["s_run"], 0.25)
        self.assertEqual(s["range_repeats"], 0.5)
        self.assertAlmostEqual(s["Q_in_hi"], 1.1, places=12)
        self.assertTrue(s["consistent"])
        self.assertAlmostEqual(s["V_ro"], 0.6, places=12)
        self.assertAlmostEqual(s["V_p"], 0.9, places=12)
        self.assertEqual(s["settling_times"], [5.0, 10.0, 15.0])
        self.assertEqual(s["V_sensor"], 23.25)
        self.assertEqual(s["u_V_sensor"], 1.0)
        self.assertEqual([round(d, 9) for d in s["sensor_delays_s"]], [0.05, 0.15])
        self.assertEqual(s["u_d"], 1.5)
        self.assertEqual(s["rtt_median_s"], 0.005)
        self.assertEqual(s["hold_changes_ml"], [0.0])
        self.assertIn("1 invalid record(s) left out", s["notes"])

    def test_inclusion(self):
        inc = {k: v["included"] for k, v in self.s["inclusion"].items()}
        self.assertEqual(inc, {"E1": True, "E2": True, "E3": False, "E4": False, "E5": False})

    def test_final_values(self):
        v = self.s["final_values"]
        expected = {"R02": 0.5, "R03": 0.2, "R04": 0.1, "R05": 2.0, "R12": 5.0, "R14": 1.0,
                    "R16": 0.5, "R09": 15.0, "S3_V0": 30.0, "T_max_P10": 44.0,
                    "T_max_S3": 21.2, "R06": 30.0, "R08": 50.0, "P13": 0.6,
                    "Q_in,hi": 1.1, "P05": 23.25, "P06": 1.0, "P03": 0.5}
        for key, value in expected.items():
            self.assertAlmostEqual(v[key], value, places=9, msg=key)
        self.assertEqual(v["R11"], [30.0, 40.0, 45.0, 48.0])
        self.assertEqual(self.s["flags"], [])

    def test_load_records_from_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            for rec in synthetic_records():
                os.makedirs(os.path.join(tmp, rec["label"]))
                with open(os.path.join(tmp, rec["label"], "calibration.json"), "w") as fh:
                    json.dump(rec, fh)
            self.assertEqual(a.summarize(a.load_records([tmp]), INPUTS), self.s)


class FlagTest(unittest.TestCase):
    MEASURED = {"u_read": 0.5, "s_run": 0.25, "range_repeats": 0.5, "Q_in": 1.0,
                "Q_in_hi": 1.1, "b_empty": -0.3, "V_sensor": 23.25, "V_ro_cutoff": 0.6,
                "settling_times": [15]}

    def test_target_not_above_sensor(self):
        # P04 40 -> R11 targets 20, 30, 35, 38; 20 <= 23.25 is flagged.
        _, flags = a.final_values(dict(INPUTS, P04=40), self.MEASURED)
        self.assertEqual(len(flags), 1)
        self.assertIn("FR09 target 20.0", flags[0])

    def test_deadline_too_close_to_cutoff(self):
        # V_sensor 33: R06 = ceil5(1.5 * 28 = 42) = 45 > 44 - 5.
        _, flags = a.final_values(INPUTS, dict(self.MEASURED, V_sensor=33))
        self.assertTrue(any("R06 45.0" in f for f in flags), flags)

    def test_fr09_fill_reaches_cutoff(self):
        # Q_in,hi 1.2: T_max(5) = floor10(48.4 / 1.2 = 40.33) = 40.3 s; fill to 48 takes 43.3 s.
        v, flags = a.final_values(INPUTS, dict(self.MEASURED, Q_in_hi=1.2))
        self.assertAlmostEqual(float(v["T_max_P10"]), 40.3, places=9)
        self.assertTrue(any("correct FR09 fill" in f for f in flags), flags)


if __name__ == "__main__":
    unittest.main()
