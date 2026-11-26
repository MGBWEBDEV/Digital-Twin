"""Model 2 ("Model 1 plus candidate rig effects"), provisional implementation
(WP11, D51).

Implements design/mathematical_models.md section 5 with all candidate effects
E1-E5 at their placeholder values (D34); none is included under D24 yet, and
no result may be reported from this version (D51). Reuses src/shared/ and the
Model 1 WaterTank, Pump and TankSystem unchanged. Run the tests from the
repository root with:

    python3 -m unittest discover -s src -t src
"""

from model_2.delayed_sensor import DelayedSensor
from model_2.parameters import Model2Parameters
from model_2.priming_run_on_pump import PrimingRunOnPump
from model_2.tank_system import Model2TankSystem, build_model_2, build_model_2_environment

__all__ = [
    "DelayedSensor",
    "Model2Parameters",
    "Model2TankSystem",
    "PrimingRunOnPump",
    "build_model_2",
    "build_model_2_environment",
]
