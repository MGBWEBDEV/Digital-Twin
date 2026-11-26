"""PrimingRunOnPump: Model 2 intake with tube priming (E1) and run-on (E2)
(design/mathematical_models.md section 5.2; architecture section 8).

Per step n, with u_in the effective intake state (after command delay and
cut-off, applied by the shared environment):

    if u_in = 1 and u_in,prev = 0:  r = 0        (restart supersedes pending run-on)
    if u_in = 0 and u_in,prev = 1:  r = V_ro     (effective OFF edge, incl. cut-off)
    if u_in = 1:      pumped = Q_in * dt
    elif r > 0:       pumped = min(Q_in * dt, r);  r = r - pumped
    else:             pumped = 0
    to_tube = min(pumped, V_p - f);  f = f + to_tube
    q_in = pumped - to_tube                      (what reaches the tank)

The tube keeps its water while the pump is OFF (retention assumption, WP05
5.2). The tube is empty at the start of every run (D40 (2)), so reset() sets
f = 0. With V_p = 0 and V_ro = 0 this is exactly the Model 1 Pump (WP05 6.3).
"""

from fractions import Fraction

from model_1.exact import exact
from model_1.pump import Pump


class PrimingRunOnPump(Pump):
    """Intake pump with an intake tube that fills first and a run-on volume."""

    def __init__(self, rate_ml_per_s, tube_volume_ml=0, runon_ml=0):
        super().__init__(rate_ml_per_s)
        self.tube_volume_ml = exact(tube_volume_ml)     # V_p
        self.runon_ml = exact(runon_ml)                 # V_ro
        if self.tube_volume_ml < 0 or self.runon_ml < 0:
            raise ValueError("tube volume and run-on must be non-negative")
        self.reset()

    def reset(self) -> None:
        """Start of run: empty tube (D40 (2)), no pending run-on, pump OFF."""
        self.tube_fill_ml = Fraction(0)                 # f
        self.tube_fill_start_ml = self.tube_fill_ml     # f0, for the mass balance
        self.runon_left_ml = Fraction(0)                # r
        self.pumped_ml = Fraction(0)                    # P_in, cumulative incl. run-on
        self._was_on = False                            # u_in,prev

    def volume_moved(self, dt_ms: int, switched_on: bool) -> Fraction:
        """Volume that reaches the tank in one step (q_in)."""
        if switched_on and not self._was_on:
            self.runon_left_ml = Fraction(0)
        elif not switched_on and self._was_on:
            self.runon_left_ml = self.runon_ml

        if switched_on:
            pumped = super().volume_moved(dt_ms, True)
        elif self.runon_left_ml > 0:
            pumped = min(super().volume_moved(dt_ms, True), self.runon_left_ml)
            self.runon_left_ml -= pumped
        else:
            pumped = Fraction(0)

        to_tube = min(pumped, self.tube_volume_ml - self.tube_fill_ml)
        self.tube_fill_ml += to_tube
        self.pumped_ml += pumped
        self._was_on = switched_on
        return pumped - to_tube
