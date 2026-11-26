"""Model 2 parameters (design/mathematical_models.md sections 3 and 5).

Provisional build under D51: every candidate effect E1-E5 is present with its
placeholder value (D34). No effect is "included" in the D24 sense yet; after
WP04, an effect that fails the D24/D50 inclusion test is switched off by
setting its parameter to zero (WP05 section 6.3). Nothing computed with these
values may be reported as a result (D51).

The parameters Model 2 shares with Model 1 (capacity, dead volume, sensor
level, flow rates) are not repeated here: they are taken from the same
Model1Parameters object, so the two models cannot drift apart in a shared
value (roadmap WP11: no duplicate independent changes).
"""

from dataclasses import dataclass, field, replace

from model_1.exact import exact
from model_1.parameters import Model1Parameters
from shared.simulation_environment import SimulationParameters


@dataclass(frozen=True)
class Model2Parameters:
    # Shared with Model 1 (D24): C, V_dead, V_sensor, Q_in, Q_out.
    shared: Model1Parameters = field(default_factory=Model1Parameters)

    # E1 intake tube priming: priming time t_p at Q_in, so V_p = Q_in * t_p.
    priming_time_s: float = 2.0        # t_p, P12 -> WP04
    # E2 intake run-on volume after every effective OFF edge (incl. cut-off).
    runon_ml: float = 0.5              # V_ro, P13 -> WP04
    # E3 real rising switch point minus V_sensor. No placeholder exists; it is
    # zero by construction when the controller is given the measured switch
    # volume (D46 (2)) and never included (D50 (5)). Kept as a parameter so
    # that the rule of section 5.4 can be checked (illustrative value in M2-3b).
    trigger_offset_ml: float = 0.0     # delta_trig, TBD -> treated as 0
    # E4 sensor response delay (pure delay of the Boolean signal).
    sensor_delay_ms: int = 100         # d_s, P14 -> WP04
    # E5 command and report delays, applied by the shared environment.
    command_delay_ms: int = 20         # d_c, P15 -> WP04
    report_delay_ms: int = 20          # d_r, P15 -> WP04

    def __post_init__(self):
        for name in ("priming_time_s", "runon_ml"):
            if exact(getattr(self, name)) < 0:
                raise ValueError(f"{name} must be non-negative")
        exact(self.trigger_offset_ml)          # must be a number; sign is free
        for name in ("sensor_delay_ms", "command_delay_ms", "report_delay_ms"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer (ms)")

    @property
    def tube_volume_ml(self):
        """V_p = Q_in * t_p (exact), derived from P06 and P12."""
        return exact(self.shared.q_in_ml_per_s) * exact(self.priming_time_s)

    def simulation_parameters(self, step_ms: int = 10,
                              settle_ms: int = 10_000) -> SimulationParameters:
        """Environment parameters for Model 2: the shared environment with the
        E5 delays in its delay slots (D38, D39 (5)). step_ms = 10 (D38) and
        settle_ms = 10 000 (R09) as in Model 1. The sensor delay must also be
        a whole multiple of the step (WP05 section 2)."""
        if self.sensor_delay_ms % step_ms:
            raise ValueError("sensor_delay_ms must be a whole multiple of step_ms (D39 (5))")
        return SimulationParameters(step_ms=step_ms, settle_ms=settle_ms,
                                    command_delay_ms=self.command_delay_ms,
                                    report_delay_ms=self.report_delay_ms)

    def with_effects_off(self) -> "Model2Parameters":
        """All candidate effects zero: Model 2 reduces to Model 1 (WP05 6.3, M2-11)."""
        return replace(self, priming_time_s=0.0, runon_ml=0.0, trigger_offset_ml=0.0,
                       sensor_delay_ms=0, command_delay_ms=0, report_delay_ms=0)

    def only(self, *effects: str) -> "Model2Parameters":
        """Keep only the named effects ("E1" ... "E5") at their values, others zero
        (WP05 section 9.3, one effect at a time)."""
        unknown = set(effects) - {"E1", "E2", "E3", "E4", "E5"}
        if unknown:
            raise ValueError(f"unknown effects {sorted(unknown)}")
        off = self.with_effects_off()
        keep = {}
        if "E1" in effects:
            keep["priming_time_s"] = self.priming_time_s
        if "E2" in effects:
            keep["runon_ml"] = self.runon_ml
        if "E3" in effects:
            keep["trigger_offset_ml"] = self.trigger_offset_ml
        if "E4" in effects:
            keep["sensor_delay_ms"] = self.sensor_delay_ms
        if "E5" in effects:
            keep["command_delay_ms"] = self.command_delay_ms
            keep["report_delay_ms"] = self.report_delay_ms
        return replace(off, **keep)


PLACEHOLDER_IDS = {
    "shared": "see model_1.parameters.PLACEHOLDER_IDS",
    "priming_time_s": "P12",
    "runon_ml": "P13",
    "trigger_offset_ml": "delta_trig (TBD, 0; D46 (2), D50 (5))",
    "sensor_delay_ms": "P14",
    "command_delay_ms": "P15",
    "report_delay_ms": "P15",
}
