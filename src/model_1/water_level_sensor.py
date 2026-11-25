"""WaterLevelSensor (design/mathematical_models.md section 4.5;
architecture section 8).

Model 1: S = (V >= V_sensor), wet at equality, no delay, no hysteresis.
The output is already normalized (wet = True, D29). Model 2 extends this class
(DelayedSensor, WP11).
"""

from model_1.exact import exact


class WaterLevelSensor:
    """Ideal threshold sensor."""

    def __init__(self, level_ml):
        self.level_ml = exact(level_ml)
        self._wet = False

    def reset(self, volume_ml) -> None:
        """Sensor state at t = 0 from V0 (WP05 section 4.7)."""
        self._wet = exact(volume_ml) >= self.level_ml

    def update(self, dt_ms: int, volume_ml) -> None:
        """Evaluate at the end of a step on the new volume. dt_ms is unused in
        Model 1 and kept for the Model 2 delayed sensor."""
        self._wet = exact(volume_ml) >= self.level_ml

    def is_wet(self) -> bool:
        return self._wet
