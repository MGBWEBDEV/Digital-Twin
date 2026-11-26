"""Model 2 TankSystem: the Model 1 TankSystem built from the Model 2 parts
(design/software_architecture.md section 8; design/mathematical_models.md
section 5).

WaterTank and the outtake Pump are the Model 1 classes, unchanged (D24, D39
(6)). The intake is a PrimingRunOnPump and the sensor a DelayedSensor. The
step order, event handling and controller-facing behaviour are those of
model_1.tank_system.TankSystem; this subclass only adds simulation-only truth
columns (D40 (5) allows extra columns). The E5 delays are not part of the
TankSystem: they are the environment's delay slots (build_model_2_environment).
"""

from model_1.pump import Pump
from model_1.tank_system import TankSystem
from model_1.water_tank import WaterTank
from model_2.delayed_sensor import DelayedSensor
from model_2.parameters import Model2Parameters
from model_2.priming_run_on_pump import PrimingRunOnPump
from shared.simulation_environment import SimulationEnvironment


class Model2TankSystem(TankSystem):
    """TankSystem with a PrimingRunOnPump intake and a DelayedSensor."""

    def truth(self) -> dict:
        """Model 1 truth columns, then the Model 2 states (never given to the
        controller). `intake_flowing` means water reaching the tank (q_in > 0),
        as in Model 1; it is False while the tube fills and True during run-on.
        `sensor_wet` is the sensor output S_out (after d_s, before d_r);
        `sensor_true_wet` is S_true."""
        row = super().truth()
        row.update({
            "tube_fill_ml": float(self.intake.tube_fill_ml),
            "runon_left_ml": float(self.intake.runon_left_ml),
            "intake_pumped_ml": float(self.intake.pumped_ml),
            "sensor_true_wet": self.sensor.is_true_wet(),
        })
        return row


def build_model_2(parameters: Model2Parameters | None = None) -> Model2TankSystem:
    """Build the Model 2 TankSystem from (placeholder) parameters."""
    p = parameters or Model2Parameters()
    s = p.shared
    return Model2TankSystem(
        tank=WaterTank(s.capacity_ml, s.dead_volume_ml),
        intake=PrimingRunOnPump(s.q_in_ml_per_s, p.tube_volume_ml, p.runon_ml),
        outtake=Pump(s.q_out_ml_per_s),
        sensor=DelayedSensor(s.sensor_level_ml, p.trigger_offset_ml, p.sensor_delay_ms),
    )


def build_model_2_environment(parameters: Model2Parameters | None = None,
                              step_ms: int = 10,
                              settle_ms: int = 10_000) -> SimulationEnvironment:
    """The shared SimulationEnvironment (unchanged) driving a Model 2
    TankSystem, with the E5 delays in its delay slots."""
    p = parameters or Model2Parameters()
    return SimulationEnvironment(build_model_2(p), p.simulation_parameters(step_ms, settle_ms))
