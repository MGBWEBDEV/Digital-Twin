"""Model 1 parameters (design/mathematical_models.md section 3).

Every value is a placeholder under D34: not a measurement or hardware fact,
never to be used for a physical run, a firmware limit or a reported result.
Each field names its placeholder ID so that it can be found and replaced after
the rig check / WP04 (design/physical_system.md section 12).

Environment parameters (step, cut-off, settling time, delays) live in
shared.simulation_environment.SimulationParameters; Model 1 uses zero delays.
"""

from dataclasses import dataclass

from shared.simulation_environment import SimulationParameters


@dataclass(frozen=True)
class Model1Parameters:
    capacity_ml: float = 60.0          # C, P01 -> rig check
    dead_volume_ml: float = 0.0        # V_dead, P09 -> rig check
    sensor_level_ml: float = 24.0      # V_sensor, P05 -> rig check, WP04
    q_in_ml_per_s: float = 1.0         # Q_in, P06 -> WP04
    q_out_ml_per_s: float = 1.0        # Q_out, P07 -> WP04


# Model 1 environment: ideal communication, so both delay slots are zero (D24).
# step_ms = 10 (D38), max_on_ms = 45 000 (P11), settle_ms = 10 000 (R09).
MODEL_1_SIMULATION_PARAMETERS = SimulationParameters(
    command_delay_ms=0,
    report_delay_ms=0,
)

PLACEHOLDER_IDS = {
    "capacity_ml": "P01",
    "dead_volume_ml": "P09",
    "sensor_level_ml": "P05",
    "q_in_ml_per_s": "P06",
    "q_out_ml_per_s": "P07",
    "max_on_ms": "P11",
    "settle_ms": "R09",
    "step_ms": "D38",
}
