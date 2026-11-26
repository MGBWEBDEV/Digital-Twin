"""Environment interface the harness talks to
(design/software_architecture.md section 4).

The interface carries time, the normalized sensor value (wet = True) and pump
commands only. It never carries volume (information parity, D07).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class InitialConditions:
    """Run initial conditions needed by the environment.

    Provisional stand-in for a scenario object until WP12 defines scenarios;
    `start` only reads `v0_ml`.

    v0_ml: settled start volume V0 (P10 by default in scenarios; WP03 section 8).
    t_max_ms: per-run cut-off maximum continuous ON time (D45), computed from
        the PLANNED start volume (shared.cutoff.t_max_ms).

    The intake tube is always empty at the start of a run (researcher,
    2026-11-25; D40): there is no tube-fill input.
    """

    v0_ml: float
    t_max_ms: int


class Environment(ABC):
    """Common interface of the rig environment and the simulation environment."""

    run_valid: bool = True   # False after a rig fault (WP06 X8)

    @abstractmethod
    def start(self, scenario) -> None:
        """Set up V0 and the per-run cut-off (D45), both pumps OFF, clock at t = 0."""

    @abstractmethod
    def now_ms(self) -> int:
        """Current time in integer milliseconds since the start of the run."""

    @abstractmethod
    def sensor(self) -> bool:
        """Normalized sensor value (wet = True) as reported now."""

    @abstractmethod
    def command(self, intake: bool, outtake: bool) -> None:
        """Send the pump command issued at the current time."""

    @abstractmethod
    def advance_to(self, t_ms: int) -> None:
        """Simulation: integrate up to t_ms. Rig: wait until then."""

    @abstractmethod
    def finish(self) -> None:
        """Both pumps OFF; settle period (R09); close."""
