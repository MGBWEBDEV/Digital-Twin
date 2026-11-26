"""TEST DOUBLE - not a controller under test (D29). See README.md here.

Hand-written for the WP09a cut-off check (protocol section 7.4, step 2):
intake ON for 0 <= t_s < 15.0, then OFF for good; the sensor is never read.
With the session plan's per-run limit (longer than 15 s) no cut-off fires.
"""

OFF_S = 15.0


class Controller:
    def __init__(self, task, parameter, v_sensor_ml, q_in_ml_per_s, t_deadline_s):
        pass

    def step(self, t_s, sensor_wet):
        return (t_s < OFF_S, False)
