"""WP09a: firmware core (native C test), message format, rig adapter and rig
runner, without hardware.

The firmware core is compiled with the host C compiler and its hand-written
C test is run (skipped if no `gcc`/`cc`). The adapter and runner are tested
against a labelled fake firmware (`fake_rig.py`), not against a model of the
tank. Controllers are TEST DOUBLES only (D29). Limits, ceilings and times
here are test numbers, not firmware values (D34).
"""

import csv
import dataclasses
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from shared import harness
from shared.rig_environment import RigConfig, RigEnvironment, RigError
from shared.rig_protocol import MESSAGE_IDS, Decoder, ProtocolError, encode
from shared.run_rig import check_plan, run_rig
from shared.run_scenario import ConfigurationError, planned_t_max_ms
from shared.tests.doubles_support import DOUBLES_DIR, write_schedule_double
from shared.tests.fake_rig import FakeClock, FakeFirmware, FakeLink
from testing import parameters as tp
from testing.scenarios import SCENARIO_RUNS
from testing.runfiles import read_run

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
ESP32 = os.path.join(REPO, "src", "esp32")
NEVER_OFF = os.path.join(DOUBLES_DIR, "double_never_off.py")
ON_15S = os.path.join(DOUBLES_DIR, "double_on_15s.py")
CEILING = 48_500           # test number (the D45 example for V0 = 5 mL with placeholders)
TEST_LIMIT = 10_000


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


# ---------------------------------------------------------------------------
# Firmware core (C)
# ---------------------------------------------------------------------------

class FirmwareCoreNativeTest(unittest.TestCase):
    def test_rig_core_native(self):
        cc = shutil.which("gcc") or shutil.which("cc")
        if cc is None:
            self.skipTest("no C compiler on this host")
        with tempfile.TemporaryDirectory() as tmp:
            exe = os.path.join(tmp, "test_rig_core")
            build = subprocess.run(
                [cc, "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic",
                 "-I", os.path.join(ESP32, "lib", "rig_core"),
                 os.path.join(ESP32, "test", "native", "test_rig_core.c"),
                 os.path.join(ESP32, "lib", "rig_core", "rig_core.c"), "-o", exe],
                capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([exe], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout)
            self.assertIn("0 failures", run.stdout)


class FirmwareSourceTest(unittest.TestCase):
    def test_message_ids_match_firmware_enum(self):
        with open(os.path.join(ESP32, "src", "main.cpp"), encoding="utf-8") as fh:
            source = fh.read()
        body = re.search(r"enum\s*\{(.*?)\};", source, re.S).group(1)
        names = tuple(re.findall(r"^\s*(k\w+)\s*,", body, re.M))
        self.assertEqual(names, MESSAGE_IDS)

    def test_config_refuses_unreviewed_build(self):
        with open(os.path.join(ESP32, "include", "rig_config.h"), encoding="utf-8") as fh:
            source = fh.read()
        self.assertRegex(source, r"#define RIG_CONFIG_REVIEWED 0\b")
        self.assertRegex(source, r"#define CUTOFF_CEILING_MS 0\b")
        self.assertIn('#error "rig_config.h not reviewed', source)
        self.assertIn('#error "CUTOFF_CEILING_MS not set', source)

    def test_cmdmessenger_copy_unchanged(self):
        ref = os.path.join(REPO, "references", "LabAutomationKits", "Electronics", "Firmware",
                           "StepExample", "lib", "CmdMessenger")
        for name in ("CmdMessenger.h", "CmdMessenger.cpp", "LICENSE.md"):
            self.assertEqual(sha256(os.path.join(ref, name)),
                             sha256(os.path.join(ESP32, "lib", "CmdMessenger", name)), name)


# ---------------------------------------------------------------------------
# Message format
# ---------------------------------------------------------------------------

class ProtocolTest(unittest.TestCase):
    def test_encode(self):
        self.assertEqual(encode("kSetLimit", 10000), b"5,10000;")
        self.assertEqual(encode("kSetPumps", True, False), b"7,1,0;")
        self.assertEqual(encode("kStop"), b"9;")
        self.assertEqual(encode("kWatchdog", "a,b;c/d"), b"0,a/,b/;c//d;")

    def test_decode_split_frames_line_ends_and_escapes(self):
        d = Decoder()
        self.assertEqual(d.feed(b"14,1,100"), [])
        msgs = d.feed(b"00,5000;\r\n13,1,77;\r\n0,a/,b/;c;")
        self.assertEqual([(m.name, m.args) for m in msgs],
                         [("kCutoff", ("1", "10000", "5000")), ("kSensor", ("1", "77")),
                          ("kWatchdog", ("a,b;c",))])

    def test_bad_frames(self):
        with self.assertRaises(ProtocolError):
            Decoder().feed(b"99;")
        with self.assertRaises(ProtocolError):
            Decoder().feed(b"x,1;")
        with self.assertRaises(ProtocolError):
            Decoder().feed(b"8,1,1;")[0].ints(5)


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

def rig(intake_channel=1, sensor_wet_level=1, start_sensor_wet=False, allow_unwired=False,
        **firmware):
    clock = FakeClock()
    fw = FakeFirmware(clock, CEILING, **firmware)
    env = RigEnvironment(FakeLink(fw), RigConfig(intake_channel, sensor_wet_level),
                         settle_ms=10_000, start_sensor_wet=start_sensor_wet,
                         allow_unwired_sensor=allow_unwired, clock_ns=clock,
                         sleep=clock.sleep)
    return env, fw, clock


def plan(t_max_ms=TEST_LIMIT, t_end_ms=20_000):
    request = harness.Request("FR03", 0.0, 24.0, 1.0, 30.0)
    return harness.RunPlan("S2", 5.0, request, None, 100, t_end_ms, t_max_ms)


def events(env, name):
    return [e for e in env.events if e[2] == name]


def load(path):
    from shared.controller_check import load_controller_class
    return load_controller_class(path)


class AdapterStartTest(unittest.TestCase):
    def test_connect_reads_info(self):
        env, _, _ = rig()
        info = env.connect()
        self.assertEqual(info["ceiling_ms"], CEILING)
        self.assertEqual(info["sensor_pin"], 4)
        self.assertEqual(info["name"], "dt-rig-io")

    def test_start_sets_limit_pumps_off_t0(self):
        env, fw, _ = rig()
        env.start(plan())
        self.assertEqual(fw.limit_ms, TEST_LIMIT)
        self.assertEqual([m[1] for m in fw.received],
                         ["kGetInfo", "kStop", "kSetLimit", "kGetSensor"])
        self.assertEqual(env.now_ms(), 0)
        self.assertTrue(env.run_valid)
        self.assertIn("t_max_ms=10000", events(env, "start")[0][3])

    def test_limit_above_ceiling_refused_before_sending(self):
        env, fw, _ = rig()
        with self.assertRaises(RigError):
            env.start(plan(t_max_ms=CEILING + 100))
        self.assertNotIn("kSetLimit", [m[1] for m in fw.received])

    def test_firmware_refusal_raises(self):
        env, fw, _ = rig()
        fw.error_on.add("kSetLimit")
        with self.assertRaises(RigError):
            env.start(plan())

    def test_unwired_sensor_refused_unless_allowed(self):
        env, _, _ = rig(sensor_pin=-1)
        with self.assertRaises(RigError):
            env.start(plan())
        env, _, _ = rig(sensor_pin=-1, start_sensor_wet=None, allow_unwired=True)
        env.start(plan())
        self.assertFalse(env.sensor())

    def test_start_sensor_state_checked(self):
        env, _, _ = rig(sensor_raw=1, start_sensor_wet=False)
        with self.assertRaises(RigError):
            env.start(plan())
        env, _, _ = rig(sensor_raw=1, start_sensor_wet=True)
        env.start(plan())
        self.assertTrue(env.sensor())

    def test_sensor_polarity_normalized(self):
        env, _, _ = rig(sensor_wet_level=0, sensor_raw=0, start_sensor_wet=True)
        env.start(plan())
        self.assertTrue(env.sensor())


class AdapterRunTest(unittest.TestCase):
    def test_never_off_double_is_cut_off_at_limit(self):
        env, fw, _ = rig(start_sensor_wet=None, allow_unwired=True)
        record = harness.run_controller(load(NEVER_OFF), env, plan())
        self.assertEqual(record.end_reason, harness.END_NORMAL)
        self.assertTrue(env.run_valid)
        cut = events(env, "cutoff")
        self.assertEqual(len(cut), 1)
        self.assertIn("pump=intake", cut[0][3])
        self.assertTrue(TEST_LIMIT <= cut[0][0] < TEST_LIMIT + 5, cut[0][0])
        # the fake hardware was ON for exactly the limit on channel 1 only
        (start, end), = fw.on_intervals[0]
        self.assertEqual(end - start, TEST_LIMIT)
        self.assertEqual(fw.on_intervals[1], [])
        # one ON command, then the OFF of finish(); calls continue to T_end
        self.assertEqual(len(events(env, "command")), 1)
        self.assertEqual(record.calls[-1][0] >= 20_000, True)
        self.assertEqual(len(record.calls), 201)
        self.assertEqual(events(env, "finish")[0][0] >= record.calls[-1][0] + 10_000, True)

    def test_off_before_limit_no_cutoff(self):
        env, fw, _ = rig(start_sensor_wet=None, allow_unwired=True)
        record = harness.run_controller(load(ON_15S), env, plan(t_max_ms=CEILING))
        self.assertEqual(record.end_reason, harness.END_NORMAL)
        self.assertEqual(events(env, "cutoff"), [])
        (start, end), = fw.on_intervals[0]
        self.assertEqual(end - start, 15_000)
        self.assertIn("intake=0", events(env, "command")[-1][3])

    def test_channel_mapping(self):
        env, fw, _ = rig(intake_channel=2, start_sensor_wet=None, allow_unwired=True)
        harness.run_controller(load(NEVER_OFF), env, plan())
        self.assertEqual(fw.on_intervals[0], [])
        self.assertEqual(len(fw.on_intervals[1]), 1)
        self.assertIn("pump=intake channel=2", events(env, "cutoff")[0][3])

    def test_sensor_edges_logged_and_given_to_controller(self):
        env, fw, clock = rig()
        env.start(plan())
        env.advance_to(1_000)
        fw.set_sensor(1)
        env.advance_to(1_010)
        self.assertTrue(env.sensor())
        edge, = events(env, "sensor_edge")
        self.assertIn("wet=True", edge[3])

    def test_missing_cutoff_detected_and_stopped(self):
        env, fw, _ = rig(start_sensor_wet=None, allow_unwired=True, cutoff_enabled=False)
        record = harness.run_controller(load(NEVER_OFF), env, plan())
        self.assertEqual(record.end_reason, harness.END_INVALID)
        miss, = events(env, "cutoff_missing")
        self.assertTrue(TEST_LIMIT + 500 < miss[0] <= TEST_LIMIT + 510, miss[0])
        self.assertIn("kStop", [m[1] for m in fw.received if m[0] > 0][-3:])
        (start, end), = fw.on_intervals[0]
        self.assertLessEqual(end - start, TEST_LIMIT + 510)

    def test_firmware_restart_invalidates(self):
        env, fw, clock = rig(start_sensor_wet=None, allow_unwired=True)
        env.start(plan())
        env.command(True, False)
        env.advance_to(2_000)
        fw.restart()
        env.advance_to(2_100)
        self.assertFalse(env.run_valid)
        self.assertEqual(len(events(env, "firmware_start")), 1)
        self.assertEqual(len(events(env, "run_fault")), 1)

    def test_firmware_error_invalidates(self):
        env, fw, _ = rig(start_sensor_wet=None, allow_unwired=True)
        env.start(plan())
        fw.error_on.add("kSetPumps")
        env.command(True, False)
        env.advance_to(100)
        self.assertFalse(env.run_valid)
        self.assertEqual(len(events(env, "firmware_error")), 1)

    def test_missing_ack_invalidates(self):
        env, fw, _ = rig(start_sensor_wet=None, allow_unwired=True, ack_enabled=False)
        env.start(plan())
        env.command(True, False)
        env.advance_to(1_500)
        self.assertFalse(env.run_valid)
        self.assertEqual(len(events(env, "ack_missing")), 1)
        self.assertFalse(fw.effective[0])           # stopped

    def test_lost_link_invalidates(self):
        env, fw, _ = rig(start_sensor_wet=None, allow_unwired=True)
        env.start(plan())
        env.link.fail_reads = True
        env.advance_to(100)
        self.assertFalse(env.run_valid)
        self.assertEqual(len(events(env, "link_lost")), 1)

    def test_researcher_stop(self):
        env, fw, _ = rig(start_sensor_wet=None, allow_unwired=True)
        env.start(plan())
        env.command(True, False)
        env.advance_to(1_000)
        env.request_stop("test")
        env.advance_to(1_010)
        self.assertFalse(env.run_valid)
        self.assertFalse(fw.effective[0])
        env.command(False, False)
        env.command(True, False)                    # ignored after invalidation
        self.assertFalse(fw.effective[0])

    def test_commands_sent_only_on_change(self):
        env, fw, _ = rig(start_sensor_wet=None, allow_unwired=True)
        env.start(plan())
        for t in (0, 100, 200):
            env.advance_to(t)
            env.command(True, False)
        self.assertEqual([m[1] for m in fw.received].count("kSetPumps"), 1)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def final_parameters():
    """Test copy of the parameter set with placeholder=False (values unchanged)."""
    return {pid: dataclasses.replace(p, placeholder=False) for pid, p in tp.PARAMETERS.items()}


class GenerationIdTest(unittest.TestCase):
    def test_generation_id(self):
        from shared.run_scenario import CONTROLLERS_DIR, generation_id
        self.assertEqual(generation_id(os.path.join(CONTROLLERS_DIR, "G03.py")), "G03")
        self.assertEqual(generation_id(os.path.join(CONTROLLERS_DIR, "G01_inj-I-S.py")),
                         "G01_inj-I-S")
        self.assertIsNone(generation_id(NEVER_OFF))


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.clock = FakeClock()

    def write_plan(self, runs, ceiling=None, approved=True):
        plan = {"session_id": "TEST", "approved_by": "tester" if approved else "",
                "approved_on": "2026-11-26" if approved else "",
                "firmware_ceiling_ms": ceiling or max(r["t_max_ms"] for r in runs),
                "runs": runs}
        path = os.path.join(self.tmp, "plan.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(plan, fh)
        return path

    def entry(self, controller, label="C1", purpose="cutoff_check", t_max_ms=TEST_LIMIT,
              **kw):
        e = {"label": label, "purpose": purpose, "controller": controller,
             "controller_sha256": sha256(controller), "scenario_id": "S2",
             "v0_plan_ml": 5.0, "v0_band_ml": 1.0, "start_sensor": None,
             "t_max_ms": t_max_ms, "dt_call_ms": 100, "t_end_ms": 15_000,
             "settle_ms": 10_000}
        e.update(kw)
        return e

    def run_planned(self, plan_path, label, answers, ceiling=CEILING, sensor_pin=-1, parameters=None,
            **fw_kw):
        fw = FakeFirmware(self.clock, ceiling, sensor_pin=sensor_pin, **fw_kw)
        answers = iter(answers)
        out = run_rig(plan_path, label, FakeLink(fw), RigConfig(1, 1), self.tmp,
                      ask=lambda prompt: next(answers), clock_ns=self.clock,
                      sleep=self.clock.sleep, install_signal_handler=False,
                      run_id=f"run_{label}", parameters=parameters)
        return out, fw

    def test_cutoff_check_run_writes_run_files(self):
        path = self.write_plan([self.entry(NEVER_OFF),
                                self.entry(ON_15S, label="C2", t_max_ms=CEILING,
                                           t_end_ms=20_000)])
        run_dir, fw = self.run_planned(path, "C1", ["5.0", "0.5", "RUN", "15.0", "0.5", "", ""])
        files = read_run(run_dir)
        self.assertEqual(files.run["environment"], "rig")
        self.assertEqual(files.run["purpose"], "cutoff_check")
        self.assertEqual(files.run["t_max_s"], 10.0)
        self.assertEqual(files.run["end_reason"], "normal")
        self.assertTrue(files.run["determinism_replay"]["identical"])
        self.assertEqual(files.run["rig"]["firmware"]["ceiling_ms"], CEILING)
        self.assertIsNone(files.run["controller"]["generation_id"])      # a test double
        self.assertEqual(files.manual, {"start": 5.0, "end": 15.0})
        cut = [e for e in files.events if e.event == "cutoff"]
        self.assertEqual(len(cut), 1)
        self.assertTrue(TEST_LIMIT <= cut[0].t_ms < TEST_LIMIT + 5)
        self.assertEqual(files.calls[0].t_ms, 0)
        self.assertGreaterEqual(files.calls[-1].t_ms, 15_000)

    def test_refusals_switch_nothing_on(self):
        good = self.entry(NEVER_OFF)
        cases = {
            "unapproved": (self.write_plan([good], approved=False), "C1", {}),
            "not in plan": (self.write_plan([good]), "C9", {}),
            "ceiling mismatch": (self.write_plan([good]), "C1", {"ceiling": CEILING}),
            "plan ceiling not max": (self.write_plan([good], ceiling=TEST_LIMIT + 1), "C1", {}),
            "sha": (self.write_plan([dict(good, controller_sha256="0" * 64)]), "C1", {}),
        }
        for name, (path, label, kw) in cases.items():
            with self.subTest(name):
                fw = FakeFirmware(self.clock, kw.get("ceiling", TEST_LIMIT), sensor_pin=-1)
                with self.assertRaises(ConfigurationError):
                    run_rig(path, label, FakeLink(fw), RigConfig(1, 1), self.tmp,
                            ask=lambda p: self.fail("asked " + p), clock_ns=self.clock,
                            sleep=self.clock.sleep, install_signal_handler=False)
                self.assertNotIn("kSetPumps", [m[1] for m in fw.received])

    def test_v0_outside_band_and_no_confirmation(self):
        path = self.write_plan([self.entry(NEVER_OFF)])
        for answers in (["6.5", "0.5"], ["5.5", "0.5", "run"]):
            with self.subTest(answers=answers):
                fw = FakeFirmware(self.clock, TEST_LIMIT, sensor_pin=-1)
                it = iter(answers)
                with self.assertRaises(ConfigurationError):
                    run_rig(path, "C1", FakeLink(fw), RigConfig(1, 1), self.tmp,
                            ask=lambda p: next(it), clock_ns=self.clock,
                            sleep=self.clock.sleep, install_signal_handler=False)
                self.assertNotIn("kSetPumps", [m[1] for m in fw.received])

    def test_cutoff_check_only_with_doubles(self):
        other = write_schedule_double(self.tmp, "schedule", 0.0, None)
        path = self.write_plan([self.entry(other)])
        fw = FakeFirmware(self.clock, TEST_LIMIT, sensor_pin=-1)
        with self.assertRaises(ConfigurationError):
            run_rig(path, "C1", FakeLink(fw), RigConfig(1, 1), self.tmp,
                    ask=lambda p: self.fail("asked"), clock_ns=self.clock,
                    sleep=self.clock.sleep, install_signal_handler=False)

    def test_reference_run_refused_with_placeholders(self):
        controller = write_schedule_double(self.tmp, "schedule", 0.0, 19.0)
        case = SCENARIO_RUNS["S2"]
        t_max = planned_t_max_ms(case, tp.values())
        entry = self.entry(controller, purpose="reference", t_max_ms=t_max,
                           start_sensor="dry", t_end_ms=60_000)
        problems = check_plan({"approved_by": "x", "approved_on": "y",
                               "firmware_ceiling_ms": t_max, "runs": [entry]},
                              "C1", t_max, SCENARIO_RUNS, tp.values(), tp.placeholder_ids())[1]
        self.assertTrue(any("placeholder" in p for p in problems), problems)

    def test_reference_run_with_final_values(self):
        """With a parameter set marked final (a test copy), a reference run
        whose plan entry matches the scenario runs and is evaluable."""
        controller = write_schedule_double(self.tmp, "schedule", 0.0, 19.0)
        params = tp.values()
        case = SCENARIO_RUNS["S2"]
        t_max = planned_t_max_ms(case, params)          # 48 500 ms with these values
        entry = self.entry(controller, purpose="reference", t_max_ms=t_max,
                           start_sensor="dry", t_end_ms=60_000)
        path = self.write_plan([entry])
        run_dir, fw = self.run_planned(path, "C1", ["5.0", "0.5", "RUN", "24.0", "0.5", "", ""],
                               ceiling=t_max, sensor_pin=4, parameters=final_parameters())
        files = read_run(run_dir)
        self.assertEqual(files.run["purpose"], "reference")
        self.assertFalse(files.run["placeholder_parameters"])
        self.assertEqual(files.run["v0_ml"], 5.0)
        (start, end), = fw.on_intervals[0]
        self.assertEqual(end - start, 19_000)
        self.assertEqual([e for e in files.events if e.event == "cutoff"], [])
        with open(os.path.join(run_dir, "manual.csv"), newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual([r["point"] for r in rows], ["start", "end"])

    def test_reference_entry_must_match_scenario(self):
        controller = write_schedule_double(self.tmp, "schedule", 0.0, 19.0)
        params = tp.values()
        t_max = planned_t_max_ms(SCENARIO_RUNS["S2"], params)
        entry = self.entry(controller, purpose="reference", t_max_ms=t_max + 100,
                           start_sensor="wet", t_end_ms=60_000)
        problems = check_plan({"approved_by": "x", "approved_on": "y",
                               "firmware_ceiling_ms": t_max + 100, "runs": [entry]},
                              "C1", t_max + 100, SCENARIO_RUNS, params, [])[1]
        joined = " ".join(problems)
        self.assertIn("t_max_ms", joined)
        self.assertIn("start_sensor", joined)


if __name__ == "__main__":
    unittest.main()
