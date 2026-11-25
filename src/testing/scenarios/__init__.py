"""Scenario definitions S1-S5 (`design/functional_requirements.md` section 8).

Placeholder values (D34); final values in WP08. One entry per run, so S1, S3
and S5 have several entries. `groups` lists the requirement groups whose
checks are scored in that run, as the "Checks" column of the WP03 table;
`extra_checks` adds single checks from other groups (S4: FR08 plus FR03-L1,
D41). `sensor_override` is None or "dry" (S4: the harness
holds the sensor input dry for the whole run, D29; the plant is unaffected).

This module is data only. It is never given to a controller (D29).
"""

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class ScenarioRun:
    run_case: str            # e.g. "S1-10"
    scenario: str            # e.g. "S1"
    task: str                # "FR01", "FR03" or "FR09"
    parameter: float         # T_fill in s (FR01), V_target in mL (FR09), 0.0 (FR03)
    v0_ml: float
    groups: Tuple[str, ...]
    sensor_override: Optional[str] = None
    extra_checks: Tuple[str, ...] = ()


_RUNS = (
    ScenarioRun("S1-10", "S1", "FR01", 10.0, 5.0, ("FR01", "FR08")),
    ScenarioRun("S1-20", "S1", "FR01", 20.0, 5.0, ("FR01", "FR08")),
    ScenarioRun("S2", "S2", "FR03", 0.0, 5.0, ("FR03", "FR08")),
    ScenarioRun("S3-FR03", "S3", "FR03", 0.0, 30.0, ("FR03", "FR08")),
    ScenarioRun("S3-FR09-40", "S3", "FR09", 40.0, 30.0, ("FR09", "FR08")),
    ScenarioRun("S4", "S4", "FR03", 0.0, 5.0, ("FR08",), sensor_override="dry",
                extra_checks=("FR03-L1",)),
    ScenarioRun("S5-30", "S5", "FR09", 30.0, 5.0, ("FR09", "FR08")),
    ScenarioRun("S5-40", "S5", "FR09", 40.0, 5.0, ("FR09", "FR08")),
    ScenarioRun("S5-45", "S5", "FR09", 45.0, 5.0, ("FR09", "FR08")),
    ScenarioRun("S5-48", "S5", "FR09", 48.0, 5.0, ("FR09", "FR08")),
)

SCENARIO_RUNS = {r.run_case: r for r in _RUNS}
