"""TEST DOUBLE - not a controller under test (D29). See README.md here.

Deliberately breaks determinism without breaking a static rule: an integer
on the class counts the instances created, and every instance after the
first never switches the intake ON. The run and its replay therefore differ.
"""


class Controller:
    instances = 0

    def __init__(self, task, parameter, v_sensor_ml, q_in_ml_per_s, t_deadline_s):
        type(self).instances += 1
        self._first = type(self).instances == 1

    def step(self, t_s, sensor_wet):
        return (self._first and t_s < 10.0, False)
