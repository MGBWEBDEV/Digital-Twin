"""WP11 check M2-11 (design/mathematical_models.md sections 6.3, 9.4): Model 2
with all candidate-effect parameters zero reproduces Model 1 exactly.

The comparison is made on the Model 1 truth columns and on the event log,
for the set-ups of every Model 1 check M1-1 ... M1-12 and for random command
runs. The Model 1 hand-calculated values are also asserted as literals on
the zero-effect Model 2, so the check does not rest on the Model 1 code
alone. The same holds with a primed tube and V_p > 0 (WP05 6.3: "V_p = 0 (or
f0 = V_p)"), checked with the TEST-ONLY PrimedTubePump.
"""

import random
import unittest

from model_1 import MODEL_1_SIMULATION_PARAMETERS, build_model_1
from model_2 import Model2Parameters
from model_2.tests.support import (STEP_MS, T_MAX_V0_5_MS, environment, off, on,
                                   run_schedule, run_steps, tank_system, until)
from shared.simulation_environment import SimulationEnvironment

ZERO = Model2Parameters().with_effects_off()
# Primed tube with V_p = 2 mL, all other effects zero.
PRIMED_ONLY_E1 = Model2Parameters().only("E1")

MODEL_1_COLUMNS = ("volume_ml", "intake_flowing", "outtake_flowing", "overflow", "spill_ml",
                   "shortfall_ml", "outtake_dry", "sensor_wet", "intake_on_ms", "outtake_on_ms")

# (V0, intake, outtake, duration) of M1-1 ... M1-7 (WP05 section 9.1).
TANK_CASES = {
    "M1-1": (5, off, off, 60_000),
    "M1-2": (5, until(10_000), off, 20_000),
    "M1-3": (5, on, off, 20_000),
    "M1-4": (55, until(10_000), off, 12_000),
    "M1-5": (2, off, until(5_000), 6_000),
    "M1-6": (10, until(10_000), until(10_000), 12_000),
    "M1-7": (30, off, off, 1_000),
}

# (V0, intake OFF call, literal V_end) of M1-8 ... M1-12 (WP05 section 9.2).
LOOP_CASES = {
    "M1-8 10 s": (5, 10_000, 15.0),
    "M1-8 20 s": (5, 20_000, 25.0),
    "M1-9": (5, 19_000, 24.0),
    "M1-10": (5, 30_000, 35.0),
    "M1-11": (5, 43_000, 48.0),
    "M1-12": (5, None, 53.5),
}


def model_1_rows(v0, intake, outtake, until_ms):
    ts = build_model_1()
    ts.reset(v0)
    rows = {0: ts.truth()}
    events = []
    t = 0
    while t < until_ms:
        new = ts.step(STEP_MS, intake(t), outtake(t))
        t += STEP_MS
        rows[t] = ts.truth()
        events.extend((t, name) for name in new)
    return rows, events


def project(row):
    return {k: row[k] for k in MODEL_1_COLUMNS}


class TestM2_11_ZeroEffectsEqualModel1(unittest.TestCase):

    def compare_tank_level(self, parameters, primed):
        for case, (v0, intake, outtake, duration) in TANK_CASES.items():
            with self.subTest(case=case, primed=primed):
                rows_1, events_1 = model_1_rows(v0, intake, outtake, duration)
                rows_2, events_2 = run_steps(tank_system(parameters, primed), v0,
                                             intake, outtake, duration)
                self.assertEqual(events_2, events_1)
                self.assertEqual(rows_2.keys(), rows_1.keys())
                for t in rows_1:
                    self.assertEqual(project(rows_2[t]), rows_1[t], f"t = {t} ms")
                    self.assertEqual(rows_2[t]["runon_left_ml"], 0.0)
                    self.assertEqual(rows_2[t]["sensor_true_wet"], rows_2[t]["sensor_wet"])

    def test_tank_level_all_effects_zero(self):
        self.compare_tank_level(ZERO, primed=False)

    def test_tank_level_primed_tube_other_effects_zero(self):
        self.compare_tank_level(PRIMED_ONLY_E1, primed=True)

    def test_model_1_literals_on_zero_model_2(self):
        # A few M1 oracles as literals (WP05 9.1).
        rows, _ = run_steps(tank_system(ZERO), 5, on, off, 19_000)
        self.assertEqual(rows[18_990]["volume_ml"], 23.99)
        self.assertFalse(rows[18_990]["sensor_wet"])
        self.assertEqual(rows[19_000]["volume_ml"], 24.0)
        self.assertTrue(rows[19_000]["sensor_wet"])                  # M1-3
        rows, events = run_steps(tank_system(ZERO), 55, until(10_000), off, 10_000)
        self.assertEqual(events, [(5_010, "overflow")])
        self.assertEqual((rows[10_000]["volume_ml"], rows[10_000]["spill_ml"]), (60.0, 5.0))  # M1-4
        rows, events = run_steps(tank_system(ZERO), 2, off, until(5_000), 5_000)
        self.assertEqual(events, [(2_010, "outtake_dry")])
        self.assertEqual(rows[5_000]["shortfall_ml"], 3.0)           # M1-5

    def compare_loop(self, parameters, primed):
        for case, (v0, off_at, expected) in LOOP_CASES.items():
            with self.subTest(case=case, primed=primed):
                env_1 = SimulationEnvironment(build_model_1(), MODEL_1_SIMULATION_PARAMETERS)
                calls_1 = run_schedule(env_1, v0, off_at, T_MAX_V0_5_MS)
                env_2 = environment(parameters, primed)
                calls_2 = run_schedule(env_2, v0, off_at, T_MAX_V0_5_MS)
                self.assertEqual(calls_2, calls_1)
                self.assertEqual(env_2.events, env_1.events)
                self.assertEqual([project(r) | {"t_ms": r["t_ms"]} for r in env_2.truth_rows],
                                 env_1.truth_rows)
                self.assertEqual(env_2.truth_rows[-1]["volume_ml"], expected)

    def test_full_loop_all_effects_zero(self):
        self.compare_loop(ZERO, primed=False)

    def test_full_loop_primed_tube_other_effects_zero(self):
        self.compare_loop(PRIMED_ONLY_E1, primed=True)

    def test_random_commands_both_pumps(self):
        rng = random.Random(3)
        for v0 in (0, 5, 23.99, 30, 58):
            schedule = []
            u_in = u_out = False
            for _ in range(3_000):                          # 300 s of 100 ms calls
                if rng.random() < 0.1:
                    u_in = not u_in
                if rng.random() < 0.1:
                    u_out = not u_out
                schedule.append((u_in, u_out))
            intake = lambda t, s=schedule: s[t // 100][0]
            outtake = lambda t, s=schedule: s[t // 100][1]
            with self.subTest(v0=v0):
                rows_1, events_1 = model_1_rows(v0, intake, outtake, 300_000)
                rows_2, events_2 = run_steps(tank_system(ZERO), v0, intake, outtake, 300_000)
                self.assertEqual(events_2, events_1)
                self.assertTrue(all(project(rows_2[t]) == rows_1[t] for t in rows_1))


if __name__ == "__main__":
    unittest.main()
