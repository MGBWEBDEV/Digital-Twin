"""Pump: volume moved per simulation step (design/mathematical_models.md
section 4.4; architecture section 8).

Model 1 pump is ideal: it moves Q * dt while effectively ON and nothing while
OFF, starting and stopping instantly (D24). Model 2 extends this class for the
intake (PrimingRunOnPump, WP11).
"""

from fractions import Fraction

from model_1.exact import exact


class Pump:
    """Ideal fixed-rate pump (fixed speed and direction, D20)."""

    def __init__(self, rate_ml_per_s):
        self.rate_ml_per_s = exact(rate_ml_per_s)
        if self.rate_ml_per_s < 0:
            raise ValueError("pump rate must be non-negative")

    def reset(self) -> None:
        """Start-of-run state. Nothing to reset in Model 1. Hook for Model 2,
        whose intake tube starts every run empty (D40)."""

    def volume_moved(self, dt_ms: int, switched_on: bool) -> Fraction:
        """Volume moved during one step of dt_ms with the effective state
        `switched_on` (after command delay and cut-off) held constant."""
        if not switched_on:
            return Fraction(0)
        return self.rate_ml_per_s * dt_ms / 1000
