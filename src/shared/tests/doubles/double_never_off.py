"""TEST DOUBLE - not a controller under test (D29). See README.md here.

Hand-written for the WP09a cut-off check (protocol section 7.4, step 1) and
the adapter tests: intake ON at every call, never OFF; the sensor is never
read. On the rig it may only run behind the firmware cut-off, from an
approved session plan with a short test limit.
"""


class Controller:
    def __init__(self, task, parameter, v_sensor_ml, q_in_ml_per_s, t_deadline_s):
        pass

    def step(self, t_s, sensor_wet):
        return (True, False)
