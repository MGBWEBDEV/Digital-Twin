"""Safety cut-off (D27, D38; design/software_architecture.md section 6;
design/mathematical_models.md section 4.3, item 2).

Semantics, identical in firmware and simulation: for one pump, a timer counts
continuous ON time from the moment the (delayed) ON command reaches the
cut-off. When it reaches the maximum ON time the pump is forced OFF and a
cut-off event is reported. The pump stays OFF while the command stays ON; only
a new OFF -> ON edge starts a new timer. The controller is not informed.

The maximum ON time is set per run from the planned start volume (D45;
experiments/experimental_protocol.md section 8); `t_max_ms` computes it. It
replaces the former single value P11.
"""

import math
from fractions import Fraction


def _exact(value) -> Fraction:
    """Decimal parameter values taken exactly as written (D40 (1))."""
    return Fraction(str(value))


def t_max_ms(capacity_ml, headroom_ml, v0_plan_ml, v0_band_ml, run_on_ml,
             q_in_hi_ml_per_s) -> int:
    """Per-run cut-off T_max in integer ms (D45):

        T_max = floor((C - R12 - (V0_plan + R14) - V_ro) / Q_in,hi) to 0.1 s

    C capacity (P01), R12 capacity headroom, V0_plan the PLANNED start volume
    of the scenario (also for paired runs, D46 (3)), R14 start-volume band,
    V_ro run-on volume (P13; 0 if E2 is excluded), Q_in,hi upper intake rate.
    The same value is used by the firmware and both models. Raises ValueError
    if the planned start volume leaves no positive ON time.
    """
    q = _exact(q_in_hi_ml_per_s)
    if q <= 0:
        raise ValueError("Q_in,hi must be positive")
    room = (_exact(capacity_ml) - _exact(headroom_ml)
            - (_exact(v0_plan_ml) + _exact(v0_band_ml)) - _exact(run_on_ml))
    tenths = math.floor(room / q * 10)
    if tenths <= 0:
        raise ValueError(f"no positive cut-off time for planned V0 = {v0_plan_ml} mL")
    return tenths * 100


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
