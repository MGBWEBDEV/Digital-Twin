"""Pure time delay for commands and sensor reports (D38, D39 item 5;
design/mathematical_models.md section 4.3, items 1 and 3).

output(t) = input(t - delay), with the initial value before any input exists.
Delays are whole multiples of the simulation step. In Model 1 both delays are
zero, so the output is the latest input.
"""


class DelayLine:
    """Delay a piecewise-constant signal by a fixed number of milliseconds."""

    def __init__(self, delay_ms: int, initial):
        if not isinstance(delay_ms, int) or isinstance(delay_ms, bool) or delay_ms < 0:
            raise ValueError("delay_ms must be a non-negative integer")
        self.delay_ms = delay_ms
        self.reset(initial)

    def reset(self, initial) -> None:
        self._initial = initial
        self._history = []          # [(t_ms, value)], t_ms strictly increasing

    def put(self, t_ms: int, value) -> None:
        """Record that the input became `value` at t_ms.

        A second put at the same time replaces the first (the later command
        within one instant wins). Times must not decrease.
        """
        if self._history and t_ms < self._history[-1][0]:
            raise ValueError("DelayLine inputs must be in time order")
        if self._history and t_ms == self._history[-1][0]:
            self._history[-1] = (t_ms, value)
        else:
            self._history.append((t_ms, value))

    def get(self, t_ms: int):
        """Return the delayed value at t_ms, i.e. the input at t_ms - delay."""
        cutoff_time = t_ms - self.delay_ms
        value = self._initial
        keep_from = 0
        for index, (t_in, v_in) in enumerate(self._history):
            if t_in <= cutoff_time:
                value = v_in
                keep_from = index
            else:
                break
        # Entries older than the one in effect can never be needed again,
        # because queries do not move backwards in time.
        if keep_from:
            del self._history[:keep_from]
        return value
