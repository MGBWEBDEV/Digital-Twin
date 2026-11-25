"""Harness: runs one controller for one run (WP12 remainder).

Implements `design/software_architecture.md` sections 3-5 and D35-D38:

- a freshly created controller per run, given exactly one request at the
  start (D35, D36);
- the call loop in the D38 order: environment state at t_k, read sensor,
  apply the scenario's sensor override (D29), controller decides, command
  sent, call logged, time advances; after the call at T_end the environment's
  `finish()` switches both pumps OFF and settles;
- the controller receives only t_s and the Boolean sensor value (D07); it
  never sees the environment, the model or any log;
- a determinism replay (D37, WP06 K1): a second instance of the same loaded
  class gets the recorded inputs and must give the recorded outputs.

The harness computes no physics and no verdicts. It never reads simulated
volume; the run-file writer collects the environment's truth log after the
run (run_files.py).
"""

from dataclasses import dataclass, field
from typing import Callable, Optional

SOURCE = "harness"

END_NORMAL = "normal"
END_INVALID = "invalid"                    # environment fault (WP06 X8)
END_CONTROLLER_ERROR = "controller_error"  # controller raised or answered wrongly
END_RULE_VIOLATION = "rule_violation"      # D37 static check failed; not run


@dataclass(frozen=True)
class Request:
    """What the controller is given at the start of a run (D35, D37, R07)."""

    task: str
    parameter: float
    v_sensor_ml: float
    q_in_ml_per_s: float
    t_deadline_s: float

    def args(self):
        return (self.task, self.parameter, self.v_sensor_ml,
                self.q_in_ml_per_s, self.t_deadline_s)

    def as_dict(self):
        return {"task": self.task, "parameter": self.parameter,
                "v_sensor_ml": self.v_sensor_ml,
                "q_in_ml_per_s": self.q_in_ml_per_s,
                "t_deadline_s": self.t_deadline_s}


@dataclass(frozen=True)
class RunPlan:
    """Everything the harness needs for one run.

    v0_ml            start volume given to the environment (never to the controller)
    sensor_override  None, or "dry": the controller's sensor input is held dry
                     for the whole run while the plant is unaffected (S4, D29)
    dt_call_ms       call period (R01)
    t_end_ms         observation time T_end (R08); the last call is at T_end
    late_call_ms     a call later than its nominal time by at least this much
                     is logged as `late_call` (rig only; placeholder, WP09a)
    """

    scenario_id: str
    v0_ml: float
    request: Request
    sensor_override: Optional[str]
    dt_call_ms: int
    t_end_ms: int
    late_call_ms: int = 50

    def __post_init__(self):
        if self.sensor_override not in (None, "dry"):
            raise ValueError(f"unknown sensor override {self.sensor_override!r}")
        if self.dt_call_ms <= 0 or self.t_end_ms % self.dt_call_ms:
            raise ValueError("T_end must be a whole number of call periods")


@dataclass
class RunRecord:
    """What the harness observed. calls: (t_ms, sensor_env, sensor_given,
    intake, outtake); events: (t_ms, source, event, detail)."""

    calls: list = field(default_factory=list)
    events: list = field(default_factory=list)
    end_reason: str = END_NORMAL
    error: Optional[str] = None


def sensor_override(plan: RunPlan) -> Callable[[int, bool], bool]:
    if plan.sensor_override == "dry":
        return lambda t_ms, s_env: False
    return lambda t_ms, s_env: s_env


class ControllerAnswerError(Exception):
    """step() returned something other than two booleans."""


def _checked_answer(answer):
    if (not isinstance(answer, (tuple, list)) or len(answer) != 2
            or not all(isinstance(x, bool) for x in answer)):
        raise ControllerAnswerError(f"step() returned {answer!r}, expected (bool, bool)")
    return answer[0], answer[1]


def run_controller(controller_class, env, plan: RunPlan) -> RunRecord:
    """Run one fresh controller instance against `env` for one run."""
    record = RunRecord()
    log = record.events.append
    override = sensor_override(plan)

    env.start(plan)                                  # V0, both pumps OFF, t = 0 (D36)
    try:
        controller = controller_class(*plan.request.args())
    except Exception as exc:                         # noqa: BLE001 - any controller fault
        record.end_reason, record.error = END_CONTROLLER_ERROR, f"__init__: {exc!r}"
        log((env.now_ms(), SOURCE, "controller_error", record.error))
        env.finish()
        return record

    k = 0
    while True:
        nominal = k * plan.dt_call_ms
        t_ms = env.now_ms()                          # simulation: equals nominal
        if t_ms - nominal >= plan.late_call_ms:
            log((t_ms, SOURCE, "late_call", f"nominal_ms={nominal} late_ms={t_ms - nominal}"))
        s_env = bool(env.sensor())
        s_given = override(t_ms, s_env)
        try:
            intake, outtake = _checked_answer(controller.step(t_ms / 1000, s_given))
        except Exception as exc:                     # noqa: BLE001 - any controller fault
            record.end_reason, record.error = END_CONTROLLER_ERROR, f"step at {t_ms} ms: {exc!r}"
            log((t_ms, SOURCE, "controller_error", record.error))
            break
        env.command(intake, outtake)
        record.calls.append((t_ms, s_env, s_given, intake, outtake))
        if not env.run_valid:
            record.end_reason = END_INVALID
            log((env.now_ms(), SOURCE, "run_invalidated", "environment reported a fault"))
            break
        if nominal >= plan.t_end_ms:
            break
        k += 1
        env.advance_to(k * plan.dt_call_ms)
    env.finish()                                     # both pumps OFF, settle (R09)
    if not env.run_valid and record.end_reason == END_NORMAL:
        record.end_reason = END_INVALID
        log((env.now_ms(), SOURCE, "run_invalidated", "environment reported a fault at finish"))
    return record


def replay(controller_class, request: Request, calls):
    """Feed the recorded inputs to a new instance; compare its answers (D37).

    Returns None if every answer is identical, else a dict describing the
    first difference. Uses the same loaded class as the run, so state kept
    on the class or module between instances shows up as a difference.
    """
    try:
        controller = controller_class(*request.args())
        for t_ms, _s_env, s_given, intake, outtake in calls:
            got = _checked_answer(controller.step(t_ms / 1000, s_given))
            if got != (intake, outtake):
                return {"t_ms": t_ms, "recorded": [intake, outtake], "replayed": list(got)}
    except Exception as exc:                         # noqa: BLE001
        return {"t_ms": None, "error": repr(exc)}
    return None
