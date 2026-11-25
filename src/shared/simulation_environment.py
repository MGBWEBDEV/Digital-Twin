"""Simulation environment shared by Model 1 and Model 2
(design/software_architecture.md sections 4-6; design/mathematical_models.md
section 4.3; D27, D38, D39).

Signal chain inside one simulation step, mirroring the rig:
command delay -> cut-off -> TankSystem (pumps, water, sensor) -> report delay.
The delays are parameters supplied with the model (zero in Model 1). The
cut-off is the same code for both models. The TankSystem is the only
model-specific part.

Truth rows and events are kept in memory for the logger (run files, section 7
of the architecture). They are never passed to the controller or harness
through the Environment interface.
"""

from dataclasses import dataclass

from shared.clock import SimulationClock
from shared.cutoff import CutOff
from shared.delay_line import DelayLine
from shared.environment import Environment

SOURCE = "sim_env"


@dataclass(frozen=True)
class SimulationParameters:
    """Environment parameters. Values are placeholders (D34) unless noted.

    step_ms          simulation step dt_s = 10 ms (D38, kept in WP05 section 2)
    max_on_ms        cut-off maximum continuous ON time T_max = 45 s (P11)
    settle_ms        settling time after T_end, T_set = 10 s (R09)
    command_delay_ms d_c host -> pump; 0 in Model 1 (Model 2 candidate: P15)
    report_delay_ms  d_r sensor -> host; 0 in Model 1 (Model 2 candidate: P15)
    """

    step_ms: int = 10
    max_on_ms: int = 45_000
    settle_ms: int = 10_000
    command_delay_ms: int = 0
    report_delay_ms: int = 0

    def __post_init__(self):
        for name in ("step_ms", "max_on_ms", "settle_ms",
                     "command_delay_ms", "report_delay_ms"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer (ms)")
        if self.step_ms <= 0 or self.max_on_ms <= 0:
            raise ValueError("step_ms and max_on_ms must be positive")
        for name in ("command_delay_ms", "report_delay_ms", "settle_ms"):
            if getattr(self, name) % self.step_ms:
                raise ValueError(f"{name} must be a whole multiple of step_ms (D39)")


class SimulationEnvironment(Environment):
    """Environment that drives a simulated TankSystem.

    tank_system must provide reset(v0_ml) (intake tube always empty, D40),
    step(dt_ms, intake_on, outtake_on) -> list of new boundary event names,
    sensor_wet() -> bool (already normalized: wet = True) and truth() -> dict.
    """

    def __init__(self, tank_system, parameters: SimulationParameters | None = None):
        self.tank = tank_system
        self.parameters = parameters or SimulationParameters()
        p = self.parameters
        self._clock = SimulationClock(p.step_ms)
        self._cutoff_in = CutOff(p.max_on_ms)
        self._cutoff_out = CutOff(p.max_on_ms)
        self._commands = DelayLine(p.command_delay_ms, (False, False))
        self._reports = DelayLine(p.report_delay_ms, False)
        self._started = False
        self.run_valid = True
        self.truth_rows: list[dict] = []
        self.events: list[tuple[int, str, str, str]] = []

    # -- Environment interface -------------------------------------------

    def start(self, scenario) -> None:
        v0_ml = scenario.v0_ml
        self.tank.reset(v0_ml)                      # rejects V0 outside [V_dead, C]
        self._clock.reset()
        self._cutoff_in.reset()
        self._cutoff_out.reset()
        self._commands.reset((False, False))        # both pumps OFF before the first call (D36)
        initial_sensor = self.tank.sensor_wet()
        self._reports.reset(initial_sensor)         # buffer filled with S(0) (WP05 4.7)
        self._reports.put(0, initial_sensor)
        self._last_command = (False, False)
        self._last_reported = initial_sensor
        self.run_valid = True
        self.truth_rows = []
        self.events = []
        self._started = True
        self._log(0, "start", f"v0_ml={float(v0_ml)} sensor_wet={initial_sensor}")
        self._record_truth(0)

    def now_ms(self) -> int:
        return self._clock.now_ms()

    def sensor(self) -> bool:
        self._require_started()
        return bool(self._reports.get(self.now_ms()))

    def command(self, intake: bool, outtake: bool) -> None:
        self._require_started()
        cmd = (bool(intake), bool(outtake))
        self._commands.put(self.now_ms(), cmd)
        if cmd != self._last_command:
            self._log(self.now_ms(), "command", f"intake={int(cmd[0])} outtake={int(cmd[1])}")
            self._last_command = cmd

    def advance_to(self, t_ms: int) -> None:
        self._require_started()
        if t_ms < self.now_ms():
            raise ValueError("cannot advance backwards in time")
        if t_ms % self._clock.step_ms:
            raise ValueError("t_ms must be a whole multiple of the simulation step")
        while self.now_ms() < t_ms:
            self._step()

    def finish(self) -> None:
        """Command both pumps OFF at T_end, then keep simulating for T_set (R09)."""
        self._require_started()
        self.command(False, False)
        self.advance_to(self.now_ms() + self.parameters.settle_ms)
        self._log(self.now_ms(), "finish", "")

    # -- Internals -------------------------------------------------------

    def _step(self) -> None:
        t_n = self.now_ms()
        cmd_in, cmd_out = self._commands.get(t_n)               # command delay
        eff_in, trip_in = self._cutoff_in.apply(t_n, cmd_in)     # cut-off
        eff_out, trip_out = self._cutoff_out.apply(t_n, cmd_out)
        if trip_in:
            self._log(t_n, "cutoff", "pump=intake")
        if trip_out:
            self._log(t_n, "cutoff", "pump=outtake")
        new_events = self.tank.step(self._clock.step_ms, eff_in, eff_out)
        t_next = self._clock.tick()
        for name in new_events:                                  # stamped at t_{n+1}
            self._log(t_next, name, "", source="tank_system")
        self._reports.put(t_next, self.tank.sensor_wet())
        reported = bool(self._reports.get(t_next))               # report delay
        if reported != self._last_reported:
            self._log(t_next, "sensor_edge", f"wet={reported}")
            self._last_reported = reported
        self._record_truth(t_next)

    def _record_truth(self, t_ms: int) -> None:
        row = {"t_ms": t_ms}
        row.update(self.tank.truth())
        self.truth_rows.append(row)

    def _log(self, t_ms: int, event: str, detail: str, source: str = SOURCE) -> None:
        self.events.append((t_ms, source, event, detail))

    def _require_started(self) -> None:
        if not self._started:
            raise RuntimeError("start() must be called first")
