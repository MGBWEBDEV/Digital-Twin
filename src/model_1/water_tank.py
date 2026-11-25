"""WaterTank: the water balance shared by both models (D24;
design/mathematical_models.md sections 4.4 and 4.8; architecture section 8).

Model 2 reuses this class unchanged.
"""

from fractions import Fraction

from model_1.exact import exact


class WaterTank:
    """Syringe volume with overflow (spill) and empty-tank (shortfall) accounting."""

    def __init__(self, capacity_ml, dead_volume_ml=0):
        self.capacity_ml = exact(capacity_ml)
        self.dead_volume_ml = exact(dead_volume_ml)
        if self.capacity_ml <= 0:
            raise ValueError("capacity must be positive")
        if not 0 <= self.dead_volume_ml <= self.capacity_ml:
            raise ValueError("dead volume must lie in [0, capacity]")
        self.reset(self.dead_volume_ml)

    def reset(self, v0_ml) -> None:
        """Initialise at V0 (WP05 section 4.7). V0 outside [V_dead, C] is rejected."""
        v0 = exact(v0_ml)
        if not self.dead_volume_ml <= v0 <= self.capacity_ml:
            raise ValueError(
                f"V0 = {float(v0)} mL outside [{float(self.dead_volume_ml)}, "
                f"{float(self.capacity_ml)}] mL; scenario rejected")
        self.volume_ml: Fraction = v0
        self.spill_ml = Fraction(0)
        self.shortfall_ml = Fraction(0)
        self.overflow = False      # latched: overflow has occurred
        self.dry = False           # latched: outtake has run on an empty tank

    def add(self, ml) -> None:
        """Add water. Above capacity, V is held at C and the excess is spill."""
        v = self.volume_ml + exact(ml)
        if v > self.capacity_ml:
            self.spill_ml += v - self.capacity_ml
            v = self.capacity_ml
            self.overflow = True
        self.volume_ml = v

    def remove(self, ml) -> Fraction:
        """Remove up to `ml`; only water above the dead volume is available.

        Returns the volume actually removed. The missing part is shortfall.
        """
        requested = exact(ml)
        available = max(Fraction(0), self.volume_ml - self.dead_volume_ml)
        removed = min(requested, available)
        if removed < requested:
            self.shortfall_ml += requested - removed
            self.dry = True
        self.volume_ml -= removed
        return removed
