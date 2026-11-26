"""WP04 analysis rules (experiments/physical_characterization.md section 5;
D50). Standard library only.

Turns calibration records (written by shared.run_calibration) and the
researcher's rig-check inputs into the measured parameters, the D24
inclusion table and the final values of experiments/experimental_protocol.md
section 3. It decides nothing that a rule cannot decide: rules that cannot
be met are returned as flags for the researcher.

Arithmetic on readings uses exact fractions of the values as written (as in
D40 (1)); results are returned as floats.

Usage (after approved sessions):
    PYTHONPATH=src python3 -m characterization.analysis --inputs INPUTS.json \
        experiments/data/<session> [experiments/data/<session> ...]
INPUTS.json holds the researcher's values: P01, P02, P04, P09, P10, R01
(rig check and protocol choices), never placeholders.
"""

import argparse
import json
import math
import os
import sys
from fractions import Fraction

from shared.cutoff import t_max_ms

P16_S = Fraction(1, 1000)    # host log timestamp resolution: 1 ms (WP09a adapter)


def F(x):
    return Fraction(str(x))


def _f(x):
    return None if x is None else float(x)


def ceil_to(x, step):
    """Smallest multiple of step that is >= x (exact)."""
    return math.ceil(F(x) / F(step)) * F(step)


# ---------------------------------------------------------------------------
# Single rules (section 5)
# ---------------------------------------------------------------------------

def reading_uncertainty(groups, graduation):
    """Rule 1: u_read = max(graduation / 2, half the range of any repeat group)."""
    half_ranges = [(max(map(F, g)) - min(map(F, g))) / 2 for g in groups if g]
    return max([F(graduation) / 2] + half_ranges)


def consistent(groups, graduation):
    """Rule 2 (D27 (5)): every repeat group has range <= one graduation."""
    return all(max(map(F, g)) - min(map(F, g)) <= F(graduation) for g in groups if g)


def fit_rate_offset(points):
    """Rule 3: least squares dV = Q * T + b over (T_s, dV) points.
    Needs at least two different durations. Returns (Q, b, residuals)."""
    pts = [(F(t), F(v)) for t, v in points]
    n = len(pts)
    if len({t for t, _ in pts}) < 2:
        raise ValueError("the fit needs at least two different durations (R10)")
    st = sum(t for t, _ in pts)
    sv = sum(v for _, v in pts)
    stt = sum(t * t for t, _ in pts)
    stv = sum(t * v for t, v in pts)
    q = (n * stv - st * sv) / (n * stt - st * st)
    b = (sv - q * st) / n
    return q, b, [v - (q * t + b) for t, v in pts]


def half_range_spread(groups):
    """s_run: half the largest range among repeat groups (P08, protocol R05)."""
    return max((max(map(F, g)) - min(map(F, g))) / 2 for g in groups if g)


def largest_range(groups):
    return max(max(map(F, g)) - min(map(F, g)) for g in groups if g)


def q_in_hi(points, u_read):
    """Rule 4: max over fills of (dV + 2 u_read) / T."""
    return max((F(v) + 2 * F(u_read)) / F(t) for t, v in points)


def run_on_and_priming(q, b_empty, primed_dv, t2_s):
    """Rule 5: b_primed = mean(dV primed) - Q T2; V_ro = b_primed; V_p = b_primed - b_empty."""
    b_primed = sum(map(F, primed_dv)) / len(primed_dv) - F(q) * F(t2_s)
    return {"b_primed": b_primed, "v_ro": b_primed, "v_p": b_primed - F(b_empty)}


def sensor_switch_volume(series_list, u_read):
    """Rule 6: each series is [(volume, wet), ...] in pulse order; the switch
    volume lies between the last dry and the first wet reading."""
    mids, widths = [], []
    for series in series_list:
        first_wet = next((i for i, (_, wet) in enumerate(series) if wet), None)
        if first_wet is None or first_wet == 0:
            raise ValueError("each series needs a dry reading followed by a wet one")
        lo, hi = F(series[first_wet - 1][0]), F(series[first_wet][0])
        mids.append((lo + hi) / 2)
        widths.append((hi - lo) / 2)
    return sum(mids) / len(mids), max(widths) + F(u_read)


def sensor_delays(crossings, v_sensor, u_v_sensor, q, b_empty, u_read):
    """Rule 7: crossings are (v0, t_edge_s) with the ON command at t = 0.
    Returns (delays, u_d)."""
    delays = [F(t) - (F(v_sensor) - F(v0) - F(b_empty)) / F(q) for v0, t in crossings]
    return delays, (F(u_read) + F(u_v_sensor)) / F(q)


def settling_time(series, u_read):
    """Rule 8: earliest elapsed time from which every later reading is within
    u_read of the last one. series: [(elapsed_s, volume), ...] in time order."""
    last = F(series[-1][1])
    t = F(series[-1][0])
    for elapsed, v in reversed(series):
        if abs(F(v) - last) > F(u_read):
            break
        t = F(elapsed)
    return t


def r09(settling_times):
    """R09: largest settling time rounded up to 5 s, at least 10 s."""
    return max(F(10), ceil_to(max(settling_times), 5))


def inclusion(u_read, s_run, q, v_p=None, v_ro=None, delays=None, u_d=None, rtt_s=None):
    """Rule 9: D24 inclusion test with the uncertainty condition (D50 (5))."""
    u, s, q = F(u_read), F(s_run), F(q)
    table = {}

    def volume_effect(name, value):
        if value is None:
            table[name] = {"included": None, "reason": "not measured"}
            return
        ok = value > u and value > 2 * s
        table[name] = {"included": ok, "value_ml": float(value),
                       "reason": f"{float(value):.3f} mL vs u_read {float(u):.3f} and "
                                 f"2 s_run {float(2 * s):.3f}"}

    volume_effect("E1", v_p)
    volume_effect("E2", v_ro)
    table["E3"] = {"included": False,
                   "reason": "measured switch volume is given to the controller (D46 (2))"}
    if delays:
        d = sum(delays) / len(delays)
        ok = d > P16_S and d > 2 * F(u_d) and q * d > u
        table["E4"] = {"included": ok, "value_s": float(d),
                       "reason": f"mean delay {float(d):.3f} s, 2 u_d {float(2 * F(u_d)):.3f} s, "
                                 f"overshoot {float(q * d):.3f} mL vs u_read {float(u):.3f}"}
    else:
        table["E4"] = {"included": None, "reason": "not measured"}
    if rtt_s is not None:
        one_way = F(rtt_s) / 2
        ok = one_way > P16_S and q * one_way > u
        table["E5"] = {"included": ok, "value_s": float(one_way),
                       "reason": f"one way {float(one_way) * 1000:.2f} ms, volume effect "
                                 f"{float(q * one_way):.4f} mL vs u_read {float(u):.3f}"}
    else:
        table["E5"] = {"included": None, "reason": "not measured"}
    return table


# ---------------------------------------------------------------------------
# Final values (rule 10; protocol section 3)
# ---------------------------------------------------------------------------

def final_values(inputs, measured):
    """inputs: researcher values P01, P02, P04, P09, P10, R01.
    measured: u_read, s_run, range_repeats, Q_in, Q_in_hi, b_empty, V_sensor,
    V_ro_cutoff (V_ro if E2 is included, else 0), settling_times.
    Returns (values by ID, flags)."""
    p = {k: F(v) for k, v in inputs.items()}
    m = {k: (v if k == "settling_times" else F(v)) for k, v in measured.items()}
    grad, u, q = p["P02"], m["u_read"], m["Q_in"]
    v = {"P01": p["P01"], "P02": grad, "P03": u, "P04": p["P04"], "P05": m["V_sensor"],
         "P06": q, "P08": m["s_run"], "P09": p["P09"], "P10": p["P10"],
         "P13": m["V_ro_cutoff"], "Q_in,hi": m["Q_in_hi"], "R01": p["R01"]}
    flags = []
    v["R02"], v["R03"], v["R04"] = 5 * p["R01"], 2 * p["R01"], p["R01"]
    v["R05"] = ceil_to(2 * u + m["s_run"], grad)
    v["R12"] = max(5 * grad, 2 * v["R05"])
    v["R14"] = 2 * u
    v["R16"] = max(m["range_repeats"], u)
    v["R09"] = r09(m["settling_times"])
    v["S3_V0"] = ceil_to(max(m["V_sensor"] + 6, m["V_sensor"] + 3 * grad), grad)

    def tmax(v0):
        try:
            return F(t_max_ms(v["P01"], v["R12"], v0, v["R14"], v["P13"], v["Q_in,hi"])) / 1000
        except ValueError:
            flags.append(f"no positive T_max for start volume {float(v0)} mL")
            return None

    v["T_max_P10"] = tmax(p["P10"])
    v["T_max_S3"] = tmax(v["S3_V0"])
    v["R06"] = ceil_to(F("1.5") * (m["V_sensor"] - p["P10"]) / q, 5)
    if v["T_max_P10"] is not None and v["R06"] > v["T_max_P10"] - 5:
        flags.append(f"R06 {float(v['R06'])} s is not at least 5 s below T_max(P10) "
                     f"{float(v['T_max_P10'])} s (protocol R06)")
    tmaxes = [t for t in (v["T_max_P10"], v["T_max_S3"]) if t is not None]
    v["R08"] = ceil_to(max(tmaxes) + 5, 5) if tmaxes else None
    v["R10"] = [F(10), F(20)]
    for duration in v["R10"]:
        if p["P10"] + q * duration > p["P04"] - v["R05"]:
            flags.append(f"FR01 duration {float(duration)} s from P10 would pass the safe mark "
                         f"minus eps_V (protocol R10)")
    v["R11"] = [p["P04"] - d for d in (20, 10, 5, 2)]
    for target in v["R11"]:
        if target <= m["V_sensor"]:
            flags.append(f"FR09 target {float(target)} mL is not above V_sensor (protocol R11)")
    if v["T_max_P10"] is not None:
        longest = (max(v["R11"]) - p["P10"] - min(m["b_empty"], 0)) / q
        if longest >= v["T_max_P10"]:
            flags.append(f"correct FR09 fill to {float(max(v['R11']))} mL takes about "
                         f"{float(longest):.1f} s, not below T_max(P10) "
                         f"{float(v['T_max_P10'])} s (protocol section 8)")
    if p["P10"] < p["P09"] + 2 * grad:
        flags.append("P10 is less than 2 graduations above the dead volume (protocol P10)")
    if p["P10"] >= m["V_sensor"]:
        flags.append("P10 is not below V_sensor (protocol P10)")
    return v, flags


# ---------------------------------------------------------------------------
# Records -> summary
# ---------------------------------------------------------------------------

def load_records(session_dirs):
    records = []
    for d in session_dirs:
        for name in sorted(os.listdir(d)):
            path = os.path.join(d, name, "calibration.json")
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as fh:
                    records.append(json.load(fh))
    return records


def _dv(rec):
    return F(rec["end"]["volume_ml"]) - F(rec["start"]["volume_ml"])


def summarize(records, inputs):
    """Apply rules 1-10 to valid calibration records. Missing measurements
    leave the dependent results None and add a note."""
    notes = []
    valid = [r for r in records if r.get("valid", True)]
    if len(valid) != len(records):
        notes.append(f"{len(records) - len(valid)} invalid record(s) left out")
    by = {}
    for r in valid:
        by.setdefault(r["action"]["measure"], []).append(r)

    out = {"notes": notes}
    m1 = [[x["volume_ml"] for x in r["readings"]] for r in by.get("M1", [])]
    if not m1:
        notes.append("no M1 readings: u_read from the graduation only")
    u = reading_uncertainty(m1, inputs["P02"])
    out["u_read"] = u
    for r in by.get("M2", []):
        vals = [F(x["volume_ml"]) for x in r["readings"]]
        change = vals[-1] - vals[0]
        out.setdefault("hold_changes_ml", []).append(float(change))
        if abs(change) > u:
            notes.append(f"M2 {r['label']}: level changed {float(change)} mL with pumps OFF "
                         "(U27, X4, X7)")

    fills = [r for r in by.get("M3", []) + by.get("M5", [])
             if r.get("cutoff_seen") and r["end"]["volume_ml"] is not None]
    groups = {}
    for r in fills:
        groups.setdefault(r["action"]["duration_ms"], []).append(_dv(r))
    points = [(F(d) / 1000, dv) for d, dvs in groups.items() for dv in dvs]
    primed = [r for r in by.get("M4", []) if r.get("cutoff_seen")
              and r["end"]["volume_ml"] is not None]
    repeat_groups = list(groups.values())
    if primed:
        repeat_groups.append([_dv(r) for r in primed])
    if len(groups) < 2:
        notes.append("M3 needs two durations: no fit")
        return _floats(out)
    q, b, residuals = fit_rate_offset(points)
    s_run = half_range_spread(repeat_groups)
    out.update(Q_in=q, b_empty=b, max_abs_residual=max(abs(x) for x in residuals),
               s_run=s_run, range_repeats=largest_range(repeat_groups),
               Q_in_hi=q_in_hi(points, u),
               consistent=consistent(repeat_groups, inputs["P02"]))
    v_p = v_ro = None
    if primed:
        t2 = {r["action"]["duration_ms"] for r in primed}
        if len(t2) == 1:
            rp = run_on_and_priming(q, b, [_dv(r) for r in primed], F(t2.pop()) / 1000)
            v_p, v_ro = rp["v_p"], rp["v_ro"]
            out.update(b_primed=rp["b_primed"], V_ro=v_ro, V_p=v_p)
        else:
            notes.append("M4 runs must share one duration")
    else:
        notes.append("no M4 runs: V_ro and V_p not separated (WP05 section 8)")

    series = [[(x["elapsed_s"], x["volume_ml"]) for x in r["end"]["series"]]
              for r in fills if r["end"].get("series")]
    settle = [settling_time(s_, u) for s_ in series]
    if not settle:
        notes.append("no M5 series: R09 from the 10 s minimum")
        settle = [F(0)]
    out["settling_times"] = settle

    v_sensor = u_vs = None
    steps = [[(x["volume_ml"], x["sensor_wet"]) for x in r["steps"]] for r in by.get("M7", [])]
    if steps:
        v_sensor, u_vs = sensor_switch_volume(steps, u)
        out.update(V_sensor=v_sensor, u_V_sensor=u_vs)
    else:
        notes.append("no M7 series: V_sensor not measured")
    delays = u_d = None
    crossings = [(r["start"]["volume_ml"], F(r["crossing"]["wet_edge_ms"]) / 1000)
                 for r in by.get("M8", []) if r["crossing"].get("wet_edge_ms") is not None]
    if crossings and v_sensor is not None:
        delays, u_d = sensor_delays(crossings, v_sensor, u_vs, q, b, u)
        out.update(sensor_delays_s=delays, u_d=u_d)
    rtts = sorted(F(x) / 1000 for r in by.get("M6", []) for x in r["round_trips_ms"])
    rtt = rtts[len(rtts) // 2] if rtts else None
    if rtt is not None:
        out.update(rtt_median_s=rtt, rtt_max_s=rtts[-1])

    table = inclusion(u, s_run, q, v_p, v_ro, delays, u_d, rtt)
    out["inclusion"] = table
    if v_sensor is not None:
        e2 = table["E2"]["included"]
        values, flags = final_values(inputs, {
            "u_read": u, "s_run": s_run, "range_repeats": out["range_repeats"], "Q_in": q,
            "Q_in_hi": out["Q_in_hi"], "b_empty": b, "V_sensor": v_sensor,
            "V_ro_cutoff": v_ro if e2 else 0, "settling_times": settle})
        out.update(final_values=values, flags=flags)
    else:
        notes.append("final values need V_sensor (M7)")
    return _floats(out)


def _floats(x):
    if isinstance(x, Fraction):
        return float(x)
    if isinstance(x, dict):
        return {k: _floats(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_floats(v) for v in x]
    return x


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--inputs", required=True, help="researcher inputs (JSON)")
    parser.add_argument("sessions", nargs="+", help="experiments/data/<session> directories")
    args = parser.parse_args(argv)
    with open(args.inputs, encoding="utf-8") as fh:
        inputs = json.load(fh)
    json.dump(summarize(load_records(args.sessions), inputs), sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
