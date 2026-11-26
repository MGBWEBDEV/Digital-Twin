"""TEST DOUBLE of the rig: fake clock, fake serial link and fake firmware.

Used only by the WP09a adapter and runner tests. It is not a model of the
tank (no water, no volume) and not a controller. It answers the messages of
`src/esp32/src/main.cpp` and applies the cut-off rules of `rig_core` (whose
own C tests are in `src/esp32/test/native`), so that the host adapter can be
tested without hardware. Faults can be switched on to test the adapter's
reactions: no cut-off, no acknowledgement, restart, error replies.
"""

from shared.rig_protocol import ESCAPE, ID_OF, parse_frame


class FakeClock:
    """Monotonic nanoseconds; sleep() advances time instead of waiting."""

    def __init__(self):
        self.ns = 1_000_000_000

    def __call__(self):
        return self.ns

    def sleep(self, seconds):
        self.ns += max(1, int(round(seconds * 1e9)))

    @property
    def ms(self):
        return self.ns // 1_000_000


def _frame(name, *args):
    return (",".join([str(ID_OF[name])] + [str(a) for a in args]) + ";\r\n").encode()


class FakeFirmware:
    def __init__(self, clock, ceiling_ms, sensor_pin=4, sensor_raw=0,
                 cutoff_enabled=True, ack_enabled=True, wet_at_ms=None):
        self.clock = clock
        self.wet_at_ms = wet_at_ms   # optional: sensor goes wet at this clock ms
        self.ceiling_ms = ceiling_ms
        self.sensor_pin = sensor_pin
        self.sensor_raw = sensor_raw if sensor_pin >= 0 else -1
        self.cutoff_enabled = cutoff_enabled
        self.ack_enabled = ack_enabled
        self.limit_ms = 0
        self.commanded = [False, False]
        self.effective = [False, False]
        self.tripped = [False, False]
        self.on_since = [0, 0]
        self.received = []           # (fw_ms, name, args) for assertions
        self.on_intervals = [[], []] # effective ON intervals per channel (start, end)
        self._out = bytearray()
        self._reported_sensor = self.sensor_raw
        self.error_on = set()        # message names answered with kError

    # -- what the fake "hardware" did --------------------------------------

    def _set_effective(self, i, on):
        now = self.clock.ms
        if on and not self.effective[i]:
            self.on_intervals[i].append([now, None])
        if not on and self.effective[i]:
            self.on_intervals[i][-1][1] = now
        self.effective[i] = on

    def restart(self):
        for i in range(2):
            self._set_effective(i, False)
        self.limit_ms = 0
        self.commanded = [False, False]
        self.tripped = [False, False]
        self._out += _frame("kStarted", "dt-rig-io", "0.1.0")

    def set_sensor(self, raw):
        self.sensor_raw = raw

    # -- link side -----------------------------------------------------------

    def _poll(self):
        now = self.clock.ms
        if self.wet_at_ms is not None and now >= self.wet_at_ms and self.sensor_raw == 0:
            self.sensor_raw = 1
        for i in range(2):
            if (self.cutoff_enabled and self.effective[i]
                    and now - self.on_since[i] >= self.limit_ms):
                self._set_effective(i, False)
                self.tripped[i] = True
                self._out += _frame("kCutoff", i + 1, self.limit_ms, now)
        if self.sensor_raw != self._reported_sensor:
            self._reported_sensor = self.sensor_raw
            self._out += _frame("kSensor", self.sensor_raw, now)

    def _pumps(self):
        return _frame("kPumps", int(self.commanded[0]), int(self.effective[0]),
                      int(self.commanded[1]), int(self.effective[1]), self.clock.ms)

    def receive(self, frame):
        msg = parse_frame(frame)
        self.received.append((self.clock.ms, msg.name, msg.args))
        self._poll()
        if msg.name in self.error_on:
            self._out += _frame("kError", "test_error")
            return
        if msg.name == "kGetInfo":
            self._out += _frame("kInfo", "dt-rig-io", "0.1.0", self.ceiling_ms,
                                8, 9, 4095, 1, 16, 21, 4095, 1, self.sensor_pin)
        elif msg.name == "kStop":
            for i in range(2):
                self.commanded[i] = False
                self.tripped[i] = False
                self._set_effective(i, False)
            self._out += self._pumps()
        elif msg.name == "kSetLimit":
            limit = int(msg.args[0])
            if any(self.commanded):
                self._out += _frame("kError", "pumps_on")
            elif limit <= 0:
                self._out += _frame("kError", "limit_not_positive")
            elif limit > self.ceiling_ms:
                self._out += _frame("kError", "limit_above_ceiling")
            else:
                self.limit_ms = limit
                self._out += _frame("kLimitSet", limit)
        elif msg.name == "kSetPumps":
            on = [int(a) for a in msg.args[:2]]
            if any(on) and self.limit_ms == 0:
                self._out += _frame("kError", "no_limit")
                return
            for i in range(2):
                if not on[i]:
                    self.commanded[i] = False
                    self.tripped[i] = False
                    self._set_effective(i, False)
                elif not self.commanded[i]:
                    self.commanded[i] = True
                    self.tripped[i] = False
                    self.on_since[i] = self.clock.ms
                    self._set_effective(i, True)
            if self.ack_enabled:
                self._out += self._pumps()
        elif msg.name == "kGetSensor":
            self._out += _frame("kSensor", self.sensor_raw, self.clock.ms)
        elif msg.name == "kGetState":
            self._out += _frame("kState", int(self.commanded[0]), int(self.effective[0]),
                                int(self.tripped[0]), int(self.commanded[1]),
                                int(self.effective[1]), int(self.tripped[1]),
                                self.limit_ms, self.sensor_raw, self.clock.ms)
        elif msg.name == "kWatchdog":
            self._out += _frame("kWatchdog", "0000000-0000-0000-0000-00000000001")
        else:
            self._out += _frame("kError", "unknown_command")

    def read_out(self):
        self._poll()
        data, self._out = bytes(self._out), bytearray()
        return data


class FakeLink:
    """Serial link to a FakeFirmware; zero transmission delay."""

    def __init__(self, firmware):
        self.firmware = firmware
        self._rx = ""
        self.fail_reads = False

    def write(self, data):
        for ch in data.decode():
            self._rx += ch
            if ch == ";" and not self._rx[:-1].endswith(ESCAPE):
                frame, self._rx = self._rx[:-1], ""
                self.firmware.receive(frame)

    def read(self):
        if self.fail_reads:
            raise OSError("device disconnected")
        return self.firmware.read_out()

    def close(self):
        pass

