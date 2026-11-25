"""TEST DOUBLE - not a controller under test (D29). See README.md here.

Hand-written for the WP12 harness tests. Minimal closed-loop behaviour:
intake ON from the first call until the first call whose sensor input is wet
or whose time is at or after the deadline; then both pumps OFF for good. If
the sensor input is wet at the first call, it never switches anything ON.
It ignores `task` and `parameter`.
"""


class Controller:
    def __init__(self, task, parameter, v_sensor_ml, q_in_ml_per_s, t_deadline_s):
        self._deadline_s = t_deadline_s
        self._state = "start"

    def step(self, t_s, sensor_wet):
        if self._state == "start":
            self._state = "done" if sensor_wet else "filling"
        if self._state == "filling" and (sensor_wet or t_s >= self._deadline_s):
            self._state = "done"
        return (self._state == "filling", False)
