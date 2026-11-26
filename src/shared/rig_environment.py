"""Rig environment: serial hardware adapter for the WP09a firmware
(design/software_architecture.md sections 4, 5 and 12; D21, D27, D38, D45;
D49).

It implements the same Environment interface as the simulation, so the
harness and the controller are unchanged (D06, D21). It
- maps intake/outtake to driver channels (P17, from the rig check);
- normalizes the raw sensor level to wet/dry (P18) and hides it otherwise;
- paces real time with the host's monotonic clock (integer ms since start);
- sends commands only when they change (architecture section 11);
- sets the per-run cut-off limit at start() and refuses a limit above the
  firmware's compiled-in ceiling (D45);
- logs every command, acknowledgement, sensor edge, cut-off and firmware
  message with a host timestamp, plus the firmware's own millis();
- marks the run invalid (run_valid = False) and stops the pumps on a
  firmware restart, a firmware error, a protocol error, a lost link, a
  missing acknowledgement, a researcher interrupt, or a cut-off that does
  not arrive in time (WP06 X8; protocol section 6.4).

The host check of a missing cut-off is a backstop that only detects a
firmware fault; it never replaces the firmware cut-off (D27 (1)).

No volume passes through this class (D07): the rig has no volume signal.
"""

import time
from dataclasses import dataclass
from typing import Optional

from shared.environment import Environment
from shared.rig_protocol import INFO_FIELDS, Decoder, ProtocolError, encode

SOURCE = "rig_env"
FIRMWARE = "firmware"
PUMPS = ("intake", "outtake")


class RigError(Exception):
    """The rig cannot be used for this run; nothing was switched ON."""


@dataclass(frozen=True)
class RigConfig:
    """Adapter settings. The first two come from the rig check, not from
    placeholders (D34): they are given in the rig configuration file.

    intake_channel     driver channel (1 or 2) of the intake pump (P17, U20);
                       the outtake is on the other channel
    sensor_wet_level   raw level (0 or 1) that means wet (P18, U14, U17);
                       None if the sensor is not wired (D19)
    reply_timeout_ms   maximum wait for a firmware reply or acknowledgement
    cutoff_grace_ms    host backstop: a pump still commanded ON this long after
                       its limit without a kCutoff report invalidates the run
    poll_ms            sleep between reads while waiting
    """

    intake_channel: int
    sensor_wet_level: Optional[int]
    reply_timeout_ms: int = 1000
    cutoff_grace_ms: int = 500
    poll_ms: int = 2

    def __post_init__(self):
        if self.intake_channel not in (1, 2):
            raise ValueError("intake_channel must be 1 or 2")
        if self.sensor_wet_level not in (None, 0, 1):
            raise ValueError("sensor_wet_level must be 0, 1 or None")
        for name in ("reply_timeout_ms", "cutoff_grace_ms", "poll_ms"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")

    def as_dict(self):
        return {"intake_channel": self.intake_channel,
                "sensor_wet_level": self.sensor_wet_level,
                "reply_timeout_ms": self.reply_timeout_ms,
                "cutoff_grace_ms": self.cutoff_grace_ms, "poll_ms": self.poll_ms}


class SerialLink:
    """pyserial transport (imported only here, so tests need no pyserial)."""

    def __init__(self, port, baud=115200):
        import serial  # pyserial
        self.port = port
        self._serial = serial.Serial(port, baud, timeout=0, write_timeout=1)

    def write(self, data: bytes) -> None:
        self._serial.write(data)
        self._serial.flush()

    def read(self) -> bytes:
        n = self._serial.in_waiting
        return self._serial.read(n) if n else b""

    def close(self) -> None:
        self._serial.close()


class RigEnvironment(Environment):
    """Environment that drives the physical rig through the firmware."""

    def __init__(self, link, config: RigConfig, settle_ms: int,
                 start_sensor_wet: Optional[bool], allow_unwired_sensor=False,
                 clock_ns=time.monotonic_ns, sleep=time.sleep):
        """settle_ms: wait after T_end before the end reading (R09).
        start_sensor_wet: required normalized sensor state at start (protocol
        6.2 (4)); None only together with allow_unwired_sensor (cut-off check
        with an unwired sensor)."""
        if start_sensor_wet is None and not allow_unwired_sensor:
            raise ValueError("start_sensor_wet is required unless the sensor may be unwired")
        self.link = link
        self.config = config
        self.settle_ms = settle_ms
        self.start_sensor_wet = start_sensor_wet
        self.allow_unwired_sensor = allow_unwired_sensor
        self._clock_ns = clock_ns
        self._sleep = sleep
        self._decoder = Decoder()
        self._link_lost = False
        self._t0_ns = None
        self.firmware_info = None
        self.t_max_ms = None
        self.run_valid = True
        self.events = []
        self._reset_run_state()

    # -- Setup ----------------------------------------------------------

    def connect(self) -> dict:
        """Ask the firmware for its identity and configuration (kInfo)."""
        msg = self._request("kGetInfo", expect="kInfo")
        if len(msg.args) < len(INFO_FIELDS):
            raise RigError(f"kInfo has too few fields: {msg.args!r}")
        info = dict(zip(INFO_FIELDS, msg.args))
        for key in INFO_FIELDS[2:]:
            try:
                info[key] = int(info[key])
            except ValueError:
                raise RigError(f"kInfo field {key} is not an integer: {info[key]!r}") from None
        self.firmware_info = info
        self._log("firmware_info", " ".join(f"{k}={info[k]}" for k in INFO_FIELDS),
                  source=FIRMWARE)
        return info

    def _reset_run_state(self):
        self._sensor_raw = None
        self._last_command = (False, False)
        self._on_since = {p: None for p in PUMPS}
        self._cutoff_seen = {p: False for p in PUMPS}
        self._pending_acks = []          # deadlines (host ns) of unanswered commands
        self._stop_reason = None

    # -- Environment interface ------------------------------------------

    def start(self, scenario) -> None:
        """Both pumps OFF, set the per-run limit, check the sensor, t = 0.

        Raises RigError (nothing switched ON) if the limit is above the
        firmware ceiling, the firmware refuses it, the sensor is not wired,
        or the start sensor state differs from the plan.
        """
        self.events = []
        self.run_valid = True
        self._t0_ns = None
        self._reset_run_state()
        if self.firmware_info is None:
            self.connect()
        t_max_ms = scenario.t_max_ms
        ceiling = self.firmware_info["ceiling_ms"]
        if (not isinstance(t_max_ms, int) or isinstance(t_max_ms, bool) or t_max_ms <= 0):
            raise RigError("t_max_ms must be a positive integer (D45)")
        if t_max_ms > ceiling:
            raise RigError(f"limit {t_max_ms} ms is above the firmware ceiling {ceiling} ms")

        pumps = self._request("kStop", expect="kPumps")
        if any(pumps.ints(4)):
            raise RigError(f"pumps not OFF after kStop: {pumps.args!r}")
        reply = self._request("kSetLimit", t_max_ms, expect="kLimitSet")
        if reply.ints(1)[0] != t_max_ms:
            raise RigError(f"firmware set limit {reply.args!r}, expected {t_max_ms}")
        self.t_max_ms = t_max_ms
        sensor = self._request("kGetSensor", expect="kSensor")
        self._sensor_raw = sensor.ints(1)[0]
        if self._sensor_raw == -1 or self.config.sensor_wet_level is None:
            if not self.allow_unwired_sensor:
                raise RigError("sensor not wired (firmware SENSOR_PIN -1 or no "
                               "sensor_wet_level); this run needs it")
        elif self.start_sensor_wet is not None and self._wet() != self.start_sensor_wet:
            raise RigError(f"sensor reads {'wet' if self._wet() else 'dry'} at start; "
                           f"plan says {'wet' if self.start_sensor_wet else 'dry'} "
                           "(protocol 6.2 (4))")
        self._t0_ns = self._clock_ns()
        self._log("start", f"t_max_ms={t_max_ms} ceiling_ms={ceiling} "
                           f"sensor_raw={self._sensor_raw} sensor_wet={self._wet()}")

    def now_ms(self) -> int:
        if self._t0_ns is None:
            return 0
        return (self._clock_ns() - self._t0_ns) // 1_000_000

    def sensor(self) -> bool:
        self._pump()
        return self._wet()

    def command(self, intake: bool, outtake: bool) -> None:
        self._pump()
        cmd = (bool(intake), bool(outtake))
        if cmd == self._last_command or not self.run_valid:
            return
        now = self.now_ms()
        for pump, before, after in zip(PUMPS, self._last_command, cmd):
            if after and not before:
                self._on_since[pump] = now
                self._cutoff_seen[pump] = False
            elif before and not after:
                self._on_since[pump] = None
        self._last_command = cmd
        channels = [False, False]
        channels[self.config.intake_channel - 1] = cmd[0]
        channels[2 - self.config.intake_channel] = cmd[1]
        self._log("command", f"intake={int(cmd[0])} outtake={int(cmd[1])}")
        self._send("kSetPumps", *channels)
        self._pending_acks.append(self._clock_ns() + self.config.reply_timeout_ms * 1_000_000)

    def advance_to(self, t_ms: int) -> None:
        while True:
            self._pump()
            remaining = t_ms - self.now_ms()
            if remaining <= 0:
                return
            self._sleep(min(self.config.poll_ms, remaining) / 1000)

    def finish(self) -> None:
        """Both pumps OFF (kStop), then wait the settle time R09 while logging."""
        self.stop_pumps("finish")
        self._last_command = (False, False)
        self._on_since = {p: None for p in PUMPS}
        end = self.now_ms() + self.settle_ms
        while self.now_ms() < end:
            self._pump()
            self._sleep(min(self.config.poll_ms * 50, max(1, end - self.now_ms())) / 1000)
        self._pump()
        self._log("finish", "")

    def round_trip_ms(self) -> float:
        """One kGetState request and its reply; host round-trip time in ms
        (WP04 M6). Setup use only, never during a controller run."""
        t0 = self._clock_ns()
        self._request("kGetState", expect="kState")
        return (self._clock_ns() - t0) / 1e6

    def cutoff_seen(self, pump: str) -> bool:
        """True once a kCutoff for this pump arrived since its last ON command."""
        return self._cutoff_seen[pump]

    # -- Safety ---------------------------------------------------------

    def stop_pumps(self, reason: str) -> None:
        """Best-effort kStop; never raises."""
        try:
            self._send("kStop")
            self._log("stop_sent", reason)
        except Exception as exc:                     # noqa: BLE001 - link may be gone
            self._log("stop_failed", f"{reason}: {exc!r}")

    def request_stop(self, reason: str) -> None:
        """Called from a signal handler (researcher interrupt): the next read
        stops the pumps and invalidates the run."""
        self._stop_reason = reason

    def _invalidate(self, event: str, detail: str) -> None:
        self._log(event, detail)
        if self.run_valid:
            self.run_valid = False
            self.stop_pumps(event)

    # -- Messages ---------------------------------------------------------

    def _send(self, name, *args):
        self.link.write(encode(name, *args))

    def _read(self):
        if self._link_lost:
            return []
        try:
            data = self.link.read()
        except Exception as exc:                     # noqa: BLE001 - serial errors vary
            self._link_lost = True                   # logged once; not read again
            self._invalidate("link_lost", repr(exc))
            return []
        try:
            return self._decoder.feed(data) if data else []
        except ProtocolError as exc:
            self._invalidate("protocol_error", str(exc))
            return []

    def _request(self, name, *args, expect):
        """Send a setup request and wait for the expected reply (start/connect only)."""
        self._send(name, *args)
        deadline = self._clock_ns() + self.config.reply_timeout_ms * 1_000_000
        while self._clock_ns() <= deadline:
            for msg in self._read():
                if msg.name == expect:
                    return msg
                if msg.name == "kError":
                    raise RigError(f"firmware refused {name}: {','.join(msg.args)}")
                if msg.name == "kStarted":
                    self._log("firmware_start", ",".join(msg.args), source=FIRMWARE)
                    continue
                self._handle(msg)
            self._sleep(self.config.poll_ms / 1000)
        raise RigError(f"no {expect} reply to {name} within {self.config.reply_timeout_ms} ms")

    def _pump(self) -> None:
        """Read and handle everything that arrived; run the host checks."""
        if self._stop_reason is not None:
            reason, self._stop_reason = self._stop_reason, None
            self._invalidate("researcher_stop", reason)
        for msg in self._read():
            self._handle(msg)
        now_ns = self._clock_ns()
        if self._pending_acks and now_ns > self._pending_acks[0]:
            self._pending_acks = []
            self._invalidate("ack_missing",
                             f"no kPumps within {self.config.reply_timeout_ms} ms")
        if self.t_max_ms is not None and self.run_valid:
            limit = self.t_max_ms + self.config.cutoff_grace_ms
            for pump in PUMPS:
                since = self._on_since[pump]
                if since is not None and not self._cutoff_seen[pump] \
                        and self.now_ms() - since > limit:
                    self._invalidate("cutoff_missing",
                                     f"pump={pump} on_since_ms={since} t_max_ms={self.t_max_ms}")

    def _handle(self, msg) -> None:
        try:
            if msg.name == "kPumps":
                cmd1, eff1, cmd2, eff2, fw_ms = msg.ints(5)
                if self._pending_acks:
                    self._pending_acks.pop(0)
                self._log("command_ack", f"ch1={cmd1}/{eff1} ch2={cmd2}/{eff2} fw_ms={fw_ms}",
                          source=FIRMWARE)
            elif msg.name == "kCutoff":
                channel, on_ms, fw_ms = msg.ints(3)
                pump = PUMPS[0] if channel == self.config.intake_channel else PUMPS[1]
                self._cutoff_seen[pump] = True
                self._log("cutoff", f"pump={pump} channel={channel} on_ms={on_ms} fw_ms={fw_ms}",
                          source=FIRMWARE)
            elif msg.name == "kSensor":
                raw, fw_ms = msg.ints(2)
                before = self._wet() if self._sensor_raw is not None else None
                self._sensor_raw = raw
                if self._t0_ns is not None and self._wet() != before:
                    self._log("sensor_edge", f"wet={self._wet()} raw={raw} fw_ms={fw_ms}",
                              source=FIRMWARE)
            elif msg.name == "kStarted":
                self._log("firmware_start", ",".join(msg.args), source=FIRMWARE)
                if self._t0_ns is not None:
                    self._invalidate("run_fault", "firmware restarted during the run (WP06 X8)")
            elif msg.name == "kError":
                self._log("firmware_error", ",".join(msg.args), source=FIRMWARE)
                self._invalidate("run_fault", "firmware reported an error")
            else:
                self._log("firmware_reply", f"{msg.name} {','.join(msg.args)}", source=FIRMWARE)
        except ProtocolError as exc:
            self._invalidate("protocol_error", str(exc))

    # -- Helpers --------------------------------------------------------

    def _wet(self) -> bool:
        level = self.config.sensor_wet_level
        if level is None or self._sensor_raw in (None, -1):
            return False
        return self._sensor_raw == level

    def _log(self, event, detail, source=SOURCE):
        self.events.append((self.now_ms(), source, event, detail))
