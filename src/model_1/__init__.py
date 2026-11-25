"""Model 1 ("ideal rig"), provisional implementation (WP10).

Implements design/mathematical_models.md section 4 with placeholder parameters
(D34). Run the tests from the repository root with:

    python3 -m unittest discover -s src -t src
"""

from model_1.parameters import MODEL_1_SIMULATION_PARAMETERS, Model1Parameters
from model_1.pump import Pump
from model_1.tank_system import TankSystem, build_model_1
from model_1.water_level_sensor import WaterLevelSensor
from model_1.water_tank import WaterTank

__all__ = [
    "MODEL_1_SIMULATION_PARAMETERS",
    "Model1Parameters",
    "Pump",
    "TankSystem",
    "WaterLevelSensor",
    "WaterTank",
    "build_model_1",
]
