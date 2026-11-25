"""TankSystem: the simulated tank, two pumps and sensor
(design/software_architecture.md section 8; design/mathematical_models.md
section 4).

The TankSystem receives the effective pump states (after command delay and
cut-off, applied by the simulation environment) and knows nothing about the
controller. Order inside a step: intake, then outtake, then sensor (WP05
section 4.4 convention).
"""

from fractions import Fraction

from model_1.parameters import Model1Parameters
from model_1.pump import Pump
from model_1.water_level_sensor import WaterLevelSensor
from model_1.water_tank import WaterTank


class TankSystem:
    """Composition of WaterTank, intake Pump, outtake Pump and WaterLevelSensor."""

    def __init__(self, tank: WaterTank, intake: Pump, outtake: Pump,
                 sensor: WaterLevelSensor):
        self.tank = tank
        self.intake = intake
        self.outtake = outtake
        self.sensor = sensor
        self.reset(tank.dead_volume_ml)

    def reset(self, v0_ml) -> None:
        """Start of run (WP05 section 4.7): V = V0, spill and shortfall 0,
        pumps OFF, sensor computed from V0. The intake tube is always empty at
        the start of a run (D40); Model 1 has no tube."""
        self.tank.reset(v0_ml)
        self.v0_ml = self.tank.volume_ml
        self.intake.reset()
        self.outtake.reset()
        self.sensor.reset(self.tank.volume_ml)
        self.intake_on_ms = 0            # cumulative effective ON time T_in
        self.outtake_on_ms = 0           # cumulative effective ON time T_out
        self._q_in_last = Fraction(0)
        self._q_out_last = Fraction(0)

    def step(self, dt_ms: int, intake_on: bool, outtake_on: bool) -> list[str]:
        """Advance one simulation step (WP05 section 4.4).

        Returns the boundary events that occurred for the first time in this
        step ("overflow", "outtake_dry"); the environment stamps them with the
        step end time t_{n+1}.
        """
        overflow_before = self.tank.overflow
        dry_before = self.tank.dry

        q_in = self.intake.volume_moved(dt_ms, intake_on)
        self.tank.add(q_in)
        q_out_requested = self.outtake.volume_moved(dt_ms, outtake_on)
        q_out = self.tank.remove(q_out_requested)
        self.sensor.update(dt_ms, self.tank.volume_ml)

        if intake_on:
            self.intake_on_ms += dt_ms
        if outtake_on:
            self.outtake_on_ms += dt_ms
        self._q_in_last = q_in
        self._q_out_last = q_out

        events = []
        if self.tank.overflow and not overflow_before:
            events.append("overflow")
        if self.tank.dry and not dry_before:
            events.append("outtake_dry")
        return events

    def sensor_wet(self) -> bool:
        return self.sensor.is_wet()

    def truth(self) -> dict:
        """Simulation-only ground truth for the truth log (architecture section 7).
        Never given to the controller."""
        return {
            "volume_ml": float(self.tank.volume_ml),
            "intake_flowing": self._q_in_last > 0,
            "outtake_flowing": self._q_out_last > 0,
            "overflow": self.tank.overflow,
            "spill_ml": float(self.tank.spill_ml),
            "shortfall_ml": float(self.tank.shortfall_ml),
            "outtake_dry": self.tank.dry,
            "sensor_wet": self.sensor.is_wet(),
            "intake_on_ms": self.intake_on_ms,
            "outtake_on_ms": self.outtake_on_ms,
        }


def build_model_1(parameters: Model1Parameters | None = None) -> TankSystem:
    """Build the Model 1 TankSystem from (placeholder) parameters."""
    p = parameters or Model1Parameters()
    return TankSystem(
        tank=WaterTank(p.capacity_ml, p.dead_volume_ml),
        intake=Pump(p.q_in_ml_per_s),
        outtake=Pump(p.q_out_ml_per_s),
        sensor=WaterLevelSensor(p.sensor_level_ml),
    )
