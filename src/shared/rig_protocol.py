"""Serial message format of the rig I/O firmware (WP09a, D49).

The firmware (`src/esp32/src/main.cpp`) uses CmdMessenger in text mode, as
StepExample does: a message is ``id,arg,arg;`` with ``/`` escaping a
separator inside an argument. The firmware ends each message with CR LF so
that a serial monitor shows one message per line; the decoder ignores the
line ends. Only pyserial is needed on the host (no PyCmdMessenger).

MESSAGE_IDS must stay in the order of the enum in main.cpp; a unit test
compares the two.
"""

from dataclasses import dataclass

FIELD_SEP = ","
COMMAND_SEP = ";"
ESCAPE = "/"

MESSAGE_IDS = (
    "kWatchdog",   # host -> fw: request identifier; fw -> host: identifier
    "kStarted",    # fw -> host: name, version (firmware has (re)started)
    "kError",      # fw -> host: code
    "kGetInfo",    # host -> fw
    "kInfo",       # fw -> host: see INFO_FIELDS
    "kSetLimit",   # host -> fw: limit_ms
    "kLimitSet",   # fw -> host: limit_ms
    "kSetPumps",   # host -> fw: on_ch1 (0/1), on_ch2 (0/1)
    "kPumps",      # fw -> host: cmd1, eff1, cmd2, eff2, fw_ms
    "kStop",       # host -> fw: both pumps OFF
    "kGetState",   # host -> fw
    "kState",      # fw -> host: cmd1, eff1, trip1, cmd2, eff2, trip2, limit_ms, sensor, fw_ms
    "kGetSensor",  # host -> fw
    "kSensor",     # fw -> host: raw level (0/1; -1 = not wired), fw_ms
    "kCutoff",     # fw -> host: channel (1/2), on_ms, fw_ms
)
ID_OF = {name: i for i, name in enumerate(MESSAGE_IDS)}

INFO_FIELDS = ("name", "version", "ceiling_ms",
               "ch1_pwm_pin", "ch1_dir_pin", "ch1_speed", "ch1_dir_level",
               "ch2_pwm_pin", "ch2_dir_pin", "ch2_speed", "ch2_dir_level",
               "sensor_pin")


class ProtocolError(Exception):
    """A message that cannot be decoded or has the wrong arguments."""


@dataclass(frozen=True)
class Message:
    name: str
    args: tuple

    def ints(self, count):
        """The first `count` arguments as integers."""
        if len(self.args) < count:
            raise ProtocolError(f"{self.name}: expected {count} arguments, got {self.args!r}")
        try:
            return tuple(int(a) for a in self.args[:count])
        except ValueError:
            raise ProtocolError(f"{self.name}: non-integer argument in {self.args!r}") from None


def _escape(text):
    out = []
    for ch in text:
        if ch in (FIELD_SEP, COMMAND_SEP, ESCAPE):
            out.append(ESCAPE)
        out.append(ch)
    return "".join(out)


def encode(name, *args):
    """Bytes for one host -> firmware message. Booleans are sent as 0/1."""
    if name not in ID_OF:
        raise ProtocolError(f"unknown message {name!r}")
    fields = [str(ID_OF[name])]
    for a in args:
        fields.append(_escape(str(int(a)) if isinstance(a, bool) else str(a)))
    return (FIELD_SEP.join(fields) + COMMAND_SEP).encode("ascii")


def _split_fields(frame):
    fields, current, escaped = [], [], False
    for ch in frame:
        if escaped:
            current.append(ch)
            escaped = False
        elif ch == ESCAPE:
            escaped = True
        elif ch == FIELD_SEP:
            fields.append("".join(current))
            current = []
        else:
            current.append(ch)
    fields.append("".join(current))
    return fields


def parse_frame(frame):
    """One frame without its ';' -> Message. Leading/trailing line ends ignored."""
    frame = frame.strip("\r\n")
    fields = _split_fields(frame)
    try:
        index = int(fields[0])
    except ValueError:
        raise ProtocolError(f"bad message id in {frame!r}") from None
    if not 0 <= index < len(MESSAGE_IDS):
        raise ProtocolError(f"unknown message id {index} in {frame!r}")
    return Message(MESSAGE_IDS[index], tuple(fields[1:]))


class Decoder:
    """Splits a byte stream into Messages; keeps an incomplete tail."""

    def __init__(self):
        self._buffer = []
        self._escaped = False

    def feed(self, data: bytes):
        messages = []
        for ch in data.decode("ascii", errors="replace"):
            if self._escaped:
                self._buffer.append(ch)
                self._escaped = False
                continue
            if ch == ESCAPE:
                self._buffer.append(ch)
                self._escaped = True
                continue
            if ch == COMMAND_SEP:
                frame = "".join(self._buffer)
                self._buffer = []
                if frame.strip("\r\n"):
                    messages.append(parse_frame(frame))
                continue
            self._buffer.append(ch)
        return messages
