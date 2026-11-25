"""Safety cut-off (D27, D38; design/software_architecture.md section 6;
design/mathematical_models.md section 4.3, item 2).

Semantics, identical in firmware and simulation: for one pump, a timer counts
continuous ON time from the moment the (delayed) ON command reaches the
cut-off. When it reaches the maximum ON time the pump is forced OFF and a
cut-off event is reported. The pump stays OFF while the command stays ON; only
a new OFF -> ON edge starts a new timer. The controller is not informed.
"""


class CutOff:
    """Maximum-continuous-ON-time cut-off for one pump."""

    def __init__(self, max_on_ms: int):
        if not isinstance(max_on_ms, int) or isinstance(max_on_ms, bool) or max_on_ms <= 0:
            raise ValueError("max_on_ms must be a positive integer")
        self.max_on_ms = max_on_ms
        self.reset()

    def reset(self) -> None:
        self._on_since_ms = None   # time the current ON command reached the cut-off
        self._tripped = False      # latched until the command goes OFF

    def apply(self, t_ms: int, commanded_on: bool) -> tuple[bool, bool]:
        """Return (effective_on, tripped_now) for the step starting at t_ms.

        Called once per simulation step, in increasing time order. A trip is
        detected at the first step start at which the continuous ON time has
        reached max_on_ms; with max_on_ms a whole multiple of the step this is
        exactly max_on_ms after the ON edge.
        """
        if not commanded_on:
            self._on_since_ms = None
            self._tripped = False
            return False, False
        if self._on_since_ms is None:
            self._on_since_ms = t_ms
        if self._tripped:
            return False, False
        if t_ms - self._on_since_ms >= self.max_on_ms:
            self._tripped = True
            return False, True
        return True, False
