"""Parameter set used by the evaluator.

Every value is a PLACEHOLDER under D34 (`design/physical_system.md` section 12
for P-IDs, `design/functional_requirements.md` section 4 for R-IDs). Verdicts
computed with these values are provisional. Replace values here, by ID, when
WP04/WP08 fix them; do not add values that are not in the design documents.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Parameter:
    pid: str
    name: str
    value: float
    unit: str
    placeholder: bool = True


PARAMETERS = {
    p.pid: p
    for p in (
        Parameter("R01", "Controller call period", 0.1, "s"),
        Parameter("R02", "Start limit t_start", 0.5, "s"),
        Parameter("R03", "Timing tolerance eps_t", 0.2, "s"),
        Parameter("R04", "Response limit t_resp", 0.1, "s"),
        Parameter("R05", "Volume tolerance eps_V", 2.0, "mL"),
        Parameter("R06", "Sensor-wait deadline T_deadline", 30.0, "s"),
        Parameter("R08", "Observation time T_end", 60.0, "s"),
        Parameter("R09", "Settling time before reading", 10.0, "s"),
        Parameter("P04", "Safe-limit mark", 50.0, "mL"),
        Parameter("P05", "Sensor level V_sensor", 24.0, "mL"),
        Parameter("P06", "Intake flow Q_in", 1.0, "mL/s"),
    )
}


def values(params=None):
    """Return {ID: value} for the given parameter mapping (default: PARAMETERS)."""
    params = PARAMETERS if params is None else params
    return {pid: p.value for pid, p in params.items()}


def placeholder_ids(params=None):
    params = PARAMETERS if params is None else params
    return sorted(pid for pid, p in params.items() if p.placeholder)
