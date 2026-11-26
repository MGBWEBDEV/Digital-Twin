"""DelayedSensor: Model 2 sensor with trigger offset (E3) and response delay
(E4) (design/mathematical_models.md sections 5.3, 5.4; architecture section 8).

    S_true(t_{n+1}) = (V(t_{n+1}) >= V_sensor + delta_trig)
    S_out(t)        = S_true(t - d_s),  and S_true(0) for t < d_s

V_sensor (level_ml) stays the value the controller is told (R07); only the
real switch point moves by delta_trig. The report delay d_r is applied after
this by the shared environment. With delta_trig = 0 and d_s = 0 this is
exactly the Model 1 WaterLevelSensor (WP05 section 6.3).

The pure delay reuses shared.delay_line.DelayLine (unchanged), fed with
S_true at the end of every step on the sensor's own step-time count.
"""

from model_1.exact import exact
from model_1.water_level_sensor import WaterLevelSensor
from shared.delay_line import DelayLine


class DelayedSensor(WaterLevelSensor):
    """Threshold sensor with a shifted real switch point and a pure delay."""

    def __init__(self, level_ml, trigger_offset_ml=0, delay_ms: int = 0):
        super().__init__(level_ml)
        self.trigger_offset_ml = exact(trigger_offset_ml)    # delta_trig
        if not isinstance(delay_ms, int) or isinstance(delay_ms, bool) or delay_ms < 0:
            raise ValueError("delay_ms must be a non-negative integer")
        self.delay_ms = delay_ms                              # d_s
        self._history = DelayLine(delay_ms, False)
        self._t_ms = 0
        self._true_wet = False                                # until reset() from V0

    def switch_level_ml(self):
        """Volume at which the real sensor switches when filling."""
        return self.level_ml + self.trigger_offset_ml

    def reset(self, volume_ml) -> None:
        """t = 0: S_true(0) from V0; history filled with S_true(0) (WP05 5.7)."""
        self._t_ms = 0
        self._true_wet = exact(volume_ml) >= self.switch_level_ml()
        self._history.reset(self._true_wet)
        self._history.put(0, self._true_wet)
        self._wet = self._true_wet

    def update(self, dt_ms: int, volume_ml) -> None:
        """End of a step of dt_ms on the new volume."""
        if not isinstance(dt_ms, int) or isinstance(dt_ms, bool) or dt_ms <= 0:
            raise ValueError("dt_ms must be a positive integer")
        self._t_ms += dt_ms
        self._true_wet = exact(volume_ml) >= self.switch_level_ml()
        self._history.put(self._t_ms, self._true_wet)
        self._wet = bool(self._history.get(self._t_ms))

    def is_true_wet(self) -> bool:
        """Undelayed S_true (simulation-only truth; never given to the controller)."""
        return self._true_wet
