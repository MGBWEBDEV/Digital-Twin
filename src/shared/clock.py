"""Simulation clock (D38, design/software_architecture.md sections 5 and 8).

Time is an integer number of milliseconds since the start of the run. The
simulation environment advances the clock in fixed steps of dt_s. The
controller never reads the clock: the harness passes it t_ms / 1000.

The rig clock (host monotonic time since run start) belongs to the rig
adapter (WP09a) and is not implemented here.
"""


class SimulationClock:
    """Integer-millisecond clock advanced in fixed simulation steps."""

    def __init__(self, step_ms: int):
        if not isinstance(step_ms, int) or isinstance(step_ms, bool) or step_ms <= 0:
            raise ValueError("step_ms must be a positive integer")
        self.step_ms = step_ms
        self._now_ms = 0

    def reset(self) -> None:
        self._now_ms = 0

    def now_ms(self) -> int:
        return self._now_ms

    def tick(self) -> int:
        """Advance by one simulation step and return the new time."""
        self._now_ms += self.step_ms
        return self._now_ms
