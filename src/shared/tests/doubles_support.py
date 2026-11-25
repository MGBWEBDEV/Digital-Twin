"""Helpers that write TEST DOUBLE files for the harness tests (WP12).

Nothing here is a controller under test (D29):
- `write_schedule_double` writes an OPEN-LOOP double: the intake is ON for
  t in [on_s, off_s) and the sensor input is never read. The ON/OFF times
  are fixed in advance from the hand-calculated oracles of
  `design/functional_requirements.md` section 9.
- `write_source` writes small rule-breaking files used to test the D37
  static check; they are never loaded or run.
"""

import os

DOUBLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "doubles")
FILL_UNTIL_WET = os.path.join(DOUBLES_DIR, "double_fill_until_wet.py")
NONDETERMINISTIC = os.path.join(DOUBLES_DIR, "double_nondeterministic.py")

_SCHEDULE_TEMPLATE = '''"""TEST DOUBLE - not a controller under test (D29).

Open-loop schedule written by src/shared/tests/doubles_support.py: intake ON
for {on_s!r} <= t_s < {off_s!r} (None: never OFF); the sensor is never read.
"""

ON_S = {on_s!r}
OFF_S = {off_s!r}


class Controller:
    def __init__(self, task, parameter, v_sensor_ml, q_in_ml_per_s, t_deadline_s):
        pass

    def step(self, t_s, sensor_wet):
        on = ON_S is not None and t_s >= ON_S and (OFF_S is None or t_s < OFF_S)
        return (on, False)
'''


def write_schedule_double(directory, name, on_s=0.0, off_s=None):
    """Write an open-loop double; returns its path. on_s None: never ON."""
    path = os.path.join(directory, f"{name}.py")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(_SCHEDULE_TEMPLATE.format(on_s=on_s, off_s=off_s))
    return path


def write_source(directory, name, source):
    path = os.path.join(directory, f"{name}.py")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(source)
    return path
