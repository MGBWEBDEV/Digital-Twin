"""TEST DOUBLE - not a controller under test (D29). See README.md here.

Hand-written for the WP09a cut-off check (protocol section 7.4, step 2) in a
start-up session with a short limit (WP04 Session A,
experiments/physical_characterization.md section 3): intake ON for
0 <= t_s < 2.0, then OFF for good; the sensor is never read. With a per-run
limit longer than 2 s no cut-off fires.
"""

OFF_S = 2.0


class Controller:
    def __init__(self, task, parameter, v_sensor_ml, q_in_ml_per_s, t_deadline_s):
        pass

    def step(self, t_s, sensor_wet):
        return (t_s < OFF_S, False)
