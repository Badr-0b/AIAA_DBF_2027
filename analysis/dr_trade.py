# Copyright © 2026 Badr Obtel. All rights reserved.
"""Deployment-and-recovery (D&R) architecture trade: proposal Table 06 (PROVISIONAL).

    python analysis/dr_trade.py          (after s6_studies.py)

Inputs: inputs/dr_trade.toml (drives, parts, failure modes, judgments; each value
VERIFIED, RESELLER or ESTIMATE) and Script 6's robust reference. Physics:
s5_tow.py. Method:
  1. screen concepts against the rules and physics;
  2. size each surviving candidate at its best drive and drum radius;
  3. turn each criterion into expected total-mission points where a model exists
     (recovery, signal, stow time, mass), so the weights are the points at stake
     (swing weights); manufacturability enters by pairwise judgment;
  4. compare every option against every other on every criterion (pairwise),
     then decide four ways: expected points, Table 06 weighted score, AHP
     priorities and a Condorcet round robin;
  5. Monte Carlo over every estimate (failure rates, masses, score values,
     judgments, weights): P(each option wins) and P(i beats j).
Writes out/dr_trade_report.txt, out/dr_trade.pdf, out/dr_trade_table.csv.
Nothing here is a team decision (user, 13 Oct).
"""
import copy
import csv
import math
import sys
from functools import lru_cache
from itertools import combinations

import numpy as np

import common
from common import G0, OUT, RULES
import s3_performance as s3
import s4_sizing as s4
import s5_tow as s5
import s6_studies as s6
from config_trades import ref_point

T = common.load("dr_trade")
CRIT = ["recovery", "signal", "time", "weight", "make"]
LABEL = {"recovery": "Recovery reliability", "signal": "Signal path integrity", "time": "Deploy/stow time",
         "weight": "Weight and volume", "make": "Manufacturability"}
RI = {3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24}     # Saaty's random consistency index (Saaty 1980)
CANDS = [c["id"] for c in T["candidate"]]
CAND = {c["id"]: c for c in T["candidate"]}
DRIVE = {d["id"]: d for d in T["drive"]}
RPM = 2.0 * math.pi / 60.0


# ------------------------------------------------------------------ pure helpers (tested)
def ahp_priorities(a):
    """Principal-eigenvector priorities of a reciprocal pairwise matrix, with
    lambda_max and the consistency ratio CR = (lambda_max - n) / ((n - 1) RI)."""
    a = np.asarray(a, dtype=float)
    n = len(a)
    vals, vecs = np.linalg.eig(a)
    i = int(np.argmax(vals.real))
    w = np.abs(vecs[:, i].real)
    lam = float(vals[i].real)
    cr = (lam - n) / ((n - 1) * RI[n]) if n >= 3 else 0.0
    return w / w.sum(), lam, cr


def saaty_from_difference(d, d_max):
    """Map a difference in a better-is-larger quantity onto Saaty's 1-9 scale:
    1 + 8 |d| / d_max, inverted when d < 0 (the second option is better)."""
    if d_max <= 0.0:
        return 1.0
    a = 1.0 + 8.0 * min(abs(d) / d_max, 1.0)
    return a if d >= 0.0 else 1.0 / a


def pairwise_from_values(values, min_span=0.0):
    """Reciprocal pairwise matrix from better-is-larger values (e.g. minus points lost).
    Differences are scaled by the larger of the actual range and min_span, so a
    difference too small to matter is not stretched to 9:1."""
    v = np.asarray(values, dtype=float)
    d_max = max(float(v.max() - v.min()), min_span)
    return np.array([[saaty_from_difference(x - y, d_max) for y in v] for x in v])


def head_to_head(mats, weights):
    """H[i, j]: weighted share of preference for i over j, sum_k w_k a_ijk / (1 + a_ijk).
    i beats j head-to-head when H[i, j] > 0.5."""
    m = len(mats[0])
    h = np.zeros((m, m))
    for a, w in zip(mats, weights):
        a = np.asarray(a, dtype=float)
        h += w * a / (1.0 + a)
    return h


def condorcet(h, tol=1e-9):
    """(Copeland wins per option, index of the Condorcet winner or None)."""
    m = len(h)
    beats = np.array([[i != j and h[i, j] > 0.5 + tol for j in range(m)] for i in range(m)])
    wins = beats.sum(axis=1)
    winner = [i for i in range(m) if wins[i] == m - 1]
    return wins, (winner[0] if winner else None)


def expected_points(parts, p, attempts, gm_tries, fb, fc):
    """Expected M1 + M2 + M3 + GM points with D&R failures in the M3 attempts.

    M1 is waived (credited by M2, as Script 6). M2 then M3 share `attempts`; a flight
    attempt succeeds with probability p apart from the D&R. In an M3 attempt that flies,
    the D&R fails benignly with fb (attempt lost, retry allowed) or catastrophically with
    fc (sensor lost or destroyed: no further M3, and the GM, flown after M3, is lost).
    """
    @lru_cache(maxsize=None)
    def go(stage, left):
        if left == 0:
            return 0.0, 0.0, 1.0                    # (E[M1+M2], E[M3], P(sensor intact))
        if stage == 2:
            a, b = go(3, left - 1), go(2, left - 1)
            return (p * (parts["M1"] + parts["M2"] + a[0]) + (1 - p) * b[0],
                    p * a[1] + (1 - p) * b[1], p * a[2] + (1 - p) * b[2])
        r = go(3, left - 1)
        ok, lost, again = p * (1 - fb - fc), p * fc, 1 - p + p * fb
        return again * r[0], ok * parts["M3"] + again * r[1], ok + again * r[2]
    e12, e3, intact = go(2, attempts)
    p_gm = 1.0 - (1.0 - p) ** gm_tries
    return e12 + e3 + parts["GM"] * p_gm * intact


def class_probs(fails, p_damage):
    """Combine independent failure modes [(probability, consequence)] into the benign and
    catastrophic probabilities of one attempt; a severe failure destroys the sensor with
    probability p_damage and is otherwise benign."""
    q = {"benign": 1.0, "severe": 1.0, "catastrophic": 1.0}
    for f, kind in fails:
        q[kind] *= 1.0 - f
    pb, ps, pc = 1 - q["benign"], 1 - q["severe"], 1 - q["catastrophic"]
    return pb + (1 - p_damage) * ps, pc + p_damage * ps


def interval_scores(values, min_span=0.0):
    """Better-is-larger values onto 1-5: best 5, and 1 at the worst, or at min_span
    below the best when the actual range is smaller (all 5 if equal)."""
    v = np.asarray(values, dtype=float)
    span = max(v.max() - v.min(), min_span)
    return np.full(len(v), 5.0) if span <= 0 else 5.0 - 4.0 * (v.max() - v) / span


# ------------------------------------------------------------------ reference condition
def m3_point(s, m_sensor, P):
    """Fastest feasible M3 lap at wing area s towing m_sensor: (V, bank, n, lap time)."""
    _, v, bank = s4.grids(True)
    ar, e, clf, clc = s4.family("straight", s, P)
    k = s3.induced_factor(ar, e * P.e_factor)
    cd0 = P.cd_w + (P.f_body + P.f_tow) / s
    m = P.empty(s) + P.battery() + m_sensor
    V, B = np.meshgrid(v, bank, indexing="ij")
    t_lap, p_mean, n, cl = s3.lap(P.rho, V, B, s, cd0, k, m, G0)
    e_wh = p_mean / P.eta * RULES["missions"]["window_s"] / 3600.0
    p_peak = s3.power_required(P.rho, V, s, cd0, k, m, n, G0) / P.eta
    ok = ((s3.stall_speed(P.rho, s, m, clf, G0) <= P.vs_max) & (cl <= P.cl_margin * clc) & (n <= P.n_struct)
          & (p_peak <= P.p_max) & (e_wh <= P.e_usable))
    t = np.where(ok, t_lap, np.inf)
    i = np.unravel_index(np.argmin(t), t.shape)
    return float(V[i]), float(B[i]), float(n[i]), float(t[i] * P.time_cal)


def reference():
    s, unit = ref_point()
    P = s6.base_params()
    r0 = s6.evaluate("straight", s, unit, P, fine=True)
    m = r0["m3_mass"]
    v, bank, n, t_lap = m3_point(s, m, P)
    rho = P.rho
    q = 0.5 * rho * v * v
    g = T["geometry"]
    span = RULES["aircraft"]["span_max_m"]
    deploy = s5.deploy_length(span, RULES["sensor"]["tow_factor"]) + g["deploy_margin_m"]
    wound = deploy + g["stowed_offset_m"]
    r_turn = v * v / (G0 * math.tan(math.radians(bank)))
    x_lof = T["flight"]["x_liftoff_m"]
    marker = RULES["course"]["marker_offset_m"]                    # 152.4 m start line to each marker
    # take-off to the first downwind 180-deg turn: upwind leg, upwind 180, back leg with the 360
    window = (marker - x_lof + math.pi * r_turn + 2 * marker + 2 * math.pi * r_turn) / v \
        - T["flight"]["t_after_liftoff_s"]
    return {"s": s, "unit": unit, "m": m, "sensor_max": r0["sensor_max"], "laps": r0["laps"], "parts": r0["expected"],
            "v": v, "bank": bank, "n_race": n, "t_lap": t_lap, "rho": rho, "q": q, "span": span,
            "deploy": deploy, "wound": wound, "r_turn": r_turn, "window": window}


def tension(ref, n, cda, length=None):
    ln = T["line"]
    return s5.tow_tension(ref["m"], n, ref["q"], cda, ln["d_m"], ln["cd"],
                          ref["deploy"] if length is None else length, G0)


# ------------------------------------------------------------------ score value of mass and time
def score_value(ref):
    """Mean total (both fields) over Script 6's draws vs added D&R mass and stow time:
    least-squares slopes, points per kg and points per s."""
    mc = s6.ST["monte_carlo"]
    Ps = s6.draws(mc["draws"], mc["seed"])
    s, unit = ref["s"], ref["unit"]

    def mean_totals(dm=0.0, t_stow=None):
        saved = s6.ST["design"]["t_stow_extra_s"]
        if t_stow is not None:
            s6.ST["design"]["t_stow_extra_s"] = t_stow
        out = {"expected": [], "aggressive": []}
        try:
            for P in Ps:
                Q = copy.copy(P)
                Q.af_factor = (Q.airframe(s) + dm) / (Q.k_af * s ** Q.p_af)
                r = s6.evaluate("straight", s, unit, Q)
                for sc in out:
                    out[sc].append(r[sc]["total"])
        finally:
            s6.ST["design"]["t_stow_extra_s"] = saved
        return {sc: float(np.mean(v)) for sc, v in out.items()}

    dms, tss = T["value"]["dm_grid_kg"], T["value"]["stow_grid_s"]
    by_m = [mean_totals(dm=x) for x in dms]
    by_t = [mean_totals(t_stow=x) for x in tss]
    val = {}
    for sc in ("expected", "aggressive"):
        val[sc] = {"per_kg": float(np.polyfit(dms, [b[sc] for b in by_m], 1)[0]),
                   "per_s": float(np.polyfit(tss, [b[sc] for b in by_t], 1)[0]),
                   "by_m": [b[sc] for b in by_m], "by_t": [b[sc] for b in by_t]}
    return val


# ------------------------------------------------------------------ sizing
def size(cid, did, ref, cda):
    """Best drum (or capstan) radius for one candidate with one drive.
    Returns the best feasible design dict, or the reason it is infeasible."""
    c, d, fl, g, ln = CAND[cid], DRIVE[did], T["flight"], T["geometry"], T["line"]
    ts, wf = d["tau_stall_nm"], d["rpm_free"] * RPM
    t1, tn, t2 = (tension(ref, n, cda) for n in (1.0, fl["n_stow"], fl["n_reverse_check"]))
    best, why = None, "no radius passes"
    for r in np.arange(g["r_core_min_m"], g["r_core_max_m"] + 1e-9, g["r_core_step_m"]):
        r_eff, turns, width = s5.drum_layout(ref["wound"], r, ln["d_m"], g["pitch_factor"], g["dead_wraps"])
        if c["storage"] == "bin":
            r_eff, turns, width = r + ln["d_m"] / 2.0, float("nan"), float("nan")
        tau1, taun, tau2 = t1 * r_eff, tn * r_eff, t2 * r_eff
        checks = [(tau1 <= fl["duty_max"] * ts, "stow torque above 50 % of stall"),
                  (taun < ts, "stalls at the n = 1.5 stow load"),
                  (tau2 < ts, "back-driven at n = 2")]
        if not math.isnan(d["limit_cont_nm"]):
            checks += [(tau1 <= d["limit_cont_nm"], "gearbox continuous limit at n = 1"),
                       (max(taun, tau2) <= d["limit_inst_nm"], "gearbox instantaneous limit")]
        bad = [m for ok, m in checks if not ok]
        if bad:
            why = bad[0]
            continue
        v_in = s5.drive_speed(tau1, ts, wf) * r_eff
        v_out = fl["v_governor_mps"] if c["control"] == "free" else wf * r_eff   # free speed, conservative
        t_dep = s5.run_time(ref["wound"], v_out, fl["t_door_s"] + fl["t_latch_s"])
        closed = c["control"] == "closed"
        t_stow = s5.stow_time(ref["wound"], t1, r_eff, ts, wf, fl["dock_zone_m"] if closed else 0.0,
                              fl["dock_speed_mps"] if closed else math.inf, fl["t_door_s"] + fl["t_latch_s"])
        if t_dep > ref["window"]:
            why = f"deploy {t_dep:.0f} s exceeds the {ref['window']:.0f} s window"
            continue
        des = {"drive": did, "r": float(r), "r_eff": r_eff, "turns": turns, "width": width,
               "tau1_frac": tau1 / ts, "tau2_frac": tau2 / ts, "v_in": v_in, "v_out": v_out,
               "t_deploy": t_dep, "t_stow": t_stow, "rpm": v_in / r_eff / RPM,
               "fairlead_min": (0.5 * width / math.tan(math.radians(g["fleet_angle_max_deg"])))
               if c["storage"] == "drum" else float("nan")}
        if best is None or des["t_stow"] < best["t_stow"]:
            best = des
    return best if best else why


def part_mass(cid, did, q=0.5):
    """D&R mass, kg, with every ranged mass at quantile q (or a dict part -> q)."""
    qq = (lambda name: q.get(name, 0.5)) if isinstance(q, dict) else (lambda name: q)
    lohi = lambda rng, name: rng[0] + qq(name) * (rng[1] - rng[0])
    d, c, P = DRIVE[did], CAND[cid], T["parts"]
    m = lohi(d["mass_kg"], "drive:" + did)
    names = list(c["parts"])
    if d["needs_driver"]:
        names.append("motor_driver")
    if c["control"] == "closed" and not d["encoder"]:
        names.append("encoder_addon")
    return m + sum(lohi(P[n], n) for n in names), names


# ------------------------------------------------------------------ points per criterion
def failure_points(cid, ref, q_fail, p_damage, scale=1.0):
    """Expected points lost to D&R failures, split by criterion (each with only its own modes).
    q_fail maps a failure key, or (candidate, key), to its quantile in the range; `scale`
    multiplies the candidate-specific modes (not the shared hardware) for break-even searches."""
    shared = set(T["monte_carlo"]["shared_keys"])
    rel = s6.ST["reliability"]
    p, att, gmt = rel["p_attempt"], rel["attempts"], rel["gm_attempts"]
    parts = {k: ref["parts"][k] for k in ("M1", "M2", "M3", "GM")}
    e0 = expected_points(parts, p, att, gmt, 0.0, 0.0)
    out, probs = {}, {}
    for crit in ("recovery", "signal"):
        fails = []
        for fm in T["failure"]:
            if fm["criterion"] == crit and cid in fm["range"]:
                lo, hi = fm["range"][cid]
                q = q_fail.get((cid, fm["key"]), q_fail.get(fm["key"]))
                f = math.exp(math.log(lo) + q * (math.log(hi) - math.log(lo)))
                fails.append((f if fm["key"] in shared else f * scale, fm["consequence"]))
        fb, fc = class_probs(fails, p_damage)
        out[crit] = e0 - expected_points(parts, p, att, gmt, fb, fc)
        probs[crit] = (fb, fc)
    return out, probs


def make_matrix(q_shift=None):
    """Manufacturability pairwise matrix from the judgments; q_shift moves judgments by
    whole Saaty steps (Monte Carlo)."""
    scale = [1 / 9, 1 / 8, 1 / 7, 1 / 6, 1 / 5, 1 / 4, 1 / 3, 1 / 2, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    idx = {c: i for i, c in enumerate(CANDS)}
    a = np.ones((len(CANDS), len(CANDS)))
    for k, j in enumerate(T["make"]):
        x = j["saaty"]
        if q_shift is not None:
            pos = int(np.argmin([abs(math.log(x / s)) for s in scale])) + int(q_shift[k])
            x = scale[min(max(pos, 0), len(scale) - 1)]
        i1, i2 = idx[j["pair"][0]], idx[j["pair"][1]]
        a[i1, i2], a[i2, i1] = x, 1.0 / x
    return a


def evaluate(designs, ref, val, q_fail, p_damage, q_mass, a_rm, q_shift=None, scale=None):
    """All four decision lenses for one set of uncertain inputs."""
    loss = {c: {} for c in CANDS}
    probs = {}
    dmin = T["criteria"]["min_span_points"]
    for c in CANDS:
        fp, probs[c] = failure_points(c, ref, q_fail, p_damage, (scale or {}).get(c, 1.0))
        loss[c]["recovery"], loss[c]["signal"] = fp["recovery"], fp["signal"]
        loss[c]["time"] = -val["per_s"] * designs[c]["t_stow"]
        loss[c]["weight"] = -val["per_kg"] * part_mass(c, designs[c]["drive"], q_mass)[0]
    pts = {k: np.array([-loss[c][k] for c in CANDS]) for k in CRIT[:4]}
    swing = {k: float(pts[k].max() - pts[k].min()) for k in CRIT[:4]}
    w = {k: max(v, dmin) for k, v in swing.items()}
    w["make"] = w["recovery"] / a_rm
    tot = sum(w.values())
    w = {k: v / tot for k, v in w.items()}
    am = make_matrix(q_shift)
    p_make, _, cr_make = ahp_priorities(am)
    mats = {k: pairwise_from_values(pts[k], dmin) for k in CRIT[:4]}
    mats["make"] = am
    pri = {k: ahp_priorities(mats[k])[0] for k in CRIT}
    scores = {k: interval_scores(pts[k], dmin) for k in CRIT[:4]}
    scores["make"] = interval_scores(p_make)
    table = sum(w[k] * scores[k] for k in CRIT)
    ahp = sum(w[k] * pri[k] for k in CRIT)
    h = head_to_head([mats[k] for k in CRIT], [w[k] for k in CRIT])
    points = sum(pts[k] for k in CRIT[:4])
    return {"loss": loss, "probs": probs, "pts": pts, "w": w, "swing": swing, "mats": mats, "pri": pri,
            "scores": scores, "table": table, "ahp": ahp, "h": h, "points": points, "cr_make": cr_make}


# ------------------------------------------------------------------ screening numbers
def screening(ref, cda):
    fl, ln = T["flight"], T["line"]
    out = []
    tn = tension(ref, fl["n_stow"], cda)
    t1 = tension(ref, 1.0, cda)
    # F: pulley block. Line travel = 2 n_sheave x stroke; actuator force = 2 n T / eff.
    a = next(x for x in T["screen_drive"] if x["id"] == "p16_256")
    for pairs in (2, 3, 4):
        eff = 0.95 ** (2 * pairs)                        # ESTIMATE: 95 % per sheave pass
        force = 2 * pairs * t1 / eff
        t_dep = ref["wound"] / (2 * pairs * a["speed_max_mps"])
        out.append(f"F  pulley block, {pairs} sheave pairs: stroke {ref['wound'] / (2 * pairs):.2f} m, actuator "
                   f"force {force:.0f} N at n = 1 (P16 peak-power point {a['force_peak_n']:.0f} N), payout at the "
                   f"P16's no-load speed {t_dep:.0f} s against a {ref['window']:.0f} s deploy window -> out")
    # X3: spring retract. It must pull at least the n = 1.5 stow tension at full deployment,
    # so in level flight the sensor's weight and drag cannot pull the line out against it.
    out.append(f"X3 spring reel: retracting needs >= {tn:.0f} N (n = {fl['n_stow']}) at full deployment, but "
               f"weight plus drag at n = 1 gives only {t1:.0f} N to pull the line out against it; stored energy "
               f">= {tn * ref['wound']:.0f} J over {ref['wound']:.2f} m -> out")
    # X5: clock spring. Turns needed on a 20 mm drum.
    r_eff, turns, _ = s5.drum_layout(ref["wound"], 0.020, ln["d_m"], 1.0, 0.0)
    out.append(f"X5 limited-turn lead: {turns:.0f} drum turns at a 20 mm drum radius, against a few turns for "
               f"flat-cable clock springs -> out")
    # X6: position-mode sail winch.
    sw = next(x for x in T["screen_drive"] if x["id"] == "hs785hb")
    r_need = ref["wound"] / (2 * math.pi * sw["turns_max"])
    out.append(f"X6 sail-winch servo (position mode): {sw['turns_max']} turns -> drum radius {1000 * r_need:.0f} mm; "
               f"torque {t1 * r_need:.2f} N m at n = 1 against {sw['tau_stall_nm']:.2f} N m stall -> out")
    # C needs a governor: free-fall energy against the line's strain energy at break.
    v_drop = s5.drop_speed(ref["deploy"], G0)
    ke = 0.5 * ref["m"] * v_drop ** 2
    cap = s5.line_energy_capacity(ln["break_n"], ln["strain_break"], ref["wound"])
    out.append(f"C  unbraked free-spool: the sensor falls {ref['deploy']:.2f} m to {v_drop:.1f} m/s, {ke:.0f} J at "
               f"the stop, against {cap:.0f} J the line stores at break -> C is kept only with a governor (S5)")
    # E: capstan friction.
    lo, hi = ln["mu"]
    out.append(f"E  capstan: UHMWPE mu {lo}-{hi}; 3 wraps hold {s5.capstan_ratio(lo, 3):.1f}-"
               f"{s5.capstan_ratio(hi, 3):.0f} x the tail tension, so a {tn:.0f} N stow needs "
               f"{tn / s5.capstan_ratio(hi, 3):.1f}-{tn / s5.capstan_ratio(lo, 3):.1f} N from a self-tailer -> kept, with S6, S7")
    return out


# ------------------------------------------------------------------ report
def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ref = reference()
    cda_hi = T["flight"]["sensor_cda_m2"][1]
    fl, ln = T["flight"], T["line"]
    lines = []
    say = lines.append
    say("D&R ARCHITECTURE TRADE, proposal Table 06 (PROVISIONAL; nothing here is a team decision)")
    say(f"Reference (Script 6 robust optimum): S {ref['s']:.2f} m2, unit {ref['unit']:.1f} kg, declared sensor "
        f"{ref['sensor_max']:.1f} kg, M3 flown at {ref['m']:.1f} kg for {ref['laps']} laps.")
    say(f"M3 race point: V {ref['v']:.1f} m/s, bank {ref['bank']:.0f} deg (n {ref['n_race']:.2f}), turn radius "
        f"{ref['r_turn']:.0f} m, lap {ref['t_lap']:.1f} s (flown time base); q {ref['q']:.0f} Pa at rho {ref['rho']:.3f}.")
    say(f"Deploy distance at the span limit {ref['span']:.4f} m: 1.5 b = {1.5 * ref['span']:.3f} m, + margin -> "
        f"{ref['deploy']:.2f} m; line on the reel {ref['wound']:.2f} m.")
    say(f"Deploy window, take-off to the first downwind 180 (Sec. 3.3.3.3): {ref['window']:.0f} s "
        f"(upwind leg from lift-off at {fl['x_liftoff_m']:.0f} m, upwind 180, back leg with the 360, less "
        f"{fl['t_after_liftoff_s']:.0f} s climb-out).")
    say("Tow tension at the airplane end (sensor CdA high end, whole line in cross-flow):")
    for n in (1.0, fl["n_stow"], fl["n_reverse_check"], ref["n_race"], s4.Params().n_struct):
        t = tension(ref, n, cda_hi)
        say(f"  n {n:4.2f}: {t:6.1f} N   80 lb line ({ln['break_n']:.0f} N) margin x{ln['break_n'] / t:.1f}")
    say("  -> at n_struct the 80 lb line keeps < x3 margin for knots and wear; specify >= 80 lb, spliced ends.")

    val = score_value(ref)
    say("\nScore value (Script 6 draws at the reference; mean total mission score; least-squares slope):")
    for sc in ("expected", "aggressive"):
        v = val[sc]
        say(f"  {sc:10} field: {0.1 * v['per_kg']:+.4f} points per 100 g of D&R mass ({v['per_kg']:+.3f}/kg);  "
            f"{v['per_s']:+.4f} points per second of stow")
    ve = val["expected"]
    say(f"  exchange rate (expected field): 1 s of stow = {1000 * ve['per_s'] / ve['per_kg']:.1f} g of D&R mass")
    say("  stow counts inside the window here (aircraft.toml, conservative until Q&A); if it does not, time is free.")

    say("\nSCREENING (before the trade):")
    for s in T["screened"]:
        if not s["reason"].startswith("computed"):
            say(f"  {s['id']:3} {s['name']}: {' '.join(s['reason'].split())}")
    for line in screening(ref, cda_hi):
        say("  " + line)

    say("\nDRIVE SIZING (each candidate at its best drum radius; deploy must beat the window; stow at n = 1,"
        f" checks at n = {fl['n_stow']} and {fl['n_reverse_check']}; sensor CdA {cda_hi}):")
    designs = {}
    for c in CANDS:
        best = None
        for did in CAND[c]["drives"]:
            des = size(c, did, ref, cda_hi)
            m, _ = part_mass(c, did)
            if isinstance(des, str):
                say(f"  {c} {did:13} infeasible: {des}")
                continue
            cost = -ve["per_kg"] * m - ve["per_s"] * des["t_stow"]
            say(f"  {c} {did:13} r {1000 * des['r']:4.0f} mm  deploy {des['t_deploy']:5.1f} s  stow {des['t_stow']:5.1f} s"
                f"  tau/stall {des['tau1_frac']:.2f} (n=2 {des['tau2_frac']:.2f})  drum {des['rpm']:5.0f} rpm  "
                f"mass {1000 * m:4.0f} g  cost {cost:.4f} pts")
            if best is None or cost < best[0]:
                best = (cost, des)
        designs[c] = best[1]
    say("  chosen (least points lost to mass + stow time):")
    for c in CANDS:
        d = designs[c]
        m, names = part_mass(c, d["drive"])
        extra = (f", {d['turns']:.0f} turns on a {1000 * d['width']:.0f} mm face, fairlead >= {d['fairlead_min']:.2f} m "
                 f"for {T['geometry']['fleet_angle_max_deg']:.0f} deg") if CAND[c]["storage"] == "drum" else ""
        say(f"  {c} {CAND[c]['name']:30} {DRIVE[d['drive']]['name']}; r {1000 * d['r']:.0f} mm{extra}; "
            f"deploy {d['t_deploy']:.1f} s, stow {d['t_stow']:.1f} s, mass {1000 * m:.0f} g "
            f"({', '.join(names)})")
    slow = [c for c in CANDS if designs[c]["rpm"] > 300]
    if slow:
        say(f"  drum speed above the slip ring's 300 rpm rating while moving: {', '.join(slow)} (noise only; "
            "lights are OFF in deploy and stow, mode changes happen with the drum stopped)")

    # base case: log-uniform medians, mid masses, a_rm 5, expected field
    keys = sorted({fm["key"] for fm in T["failure"]})
    q_mid = {k: 0.5 for k in keys}
    pd_mid = float(np.mean(T["consequence"]["p_damage_severe"]))
    base = evaluate(designs, ref, ve, q_mid, pd_mid, 0.5, 5.0)
    say("\nFAILURE MODES (base case: log-uniform medians; p_damage severe "
        f"{pd_mid:.2f}); per M3 attempt that flies:")
    for c in CANDS:
        (rb, rc), (sb, sc_) = base["probs"][c]["recovery"], base["probs"][c]["signal"]
        say(f"  {c}: recovery benign {100 * rb:4.1f} %, catastrophic {100 * rc:4.1f} %;  signal benign {100 * sb:4.1f} %")

    say("\nPOINTS AT STAKE (expected total-mission points lost, base case; lower is better):")
    say("  option                          " + "".join(f"{LABEL[k][:20]:>22}" for k in CRIT[:4]) + "        sum")
    for i, c in enumerate(CANDS):
        say(f"  {c} {CAND[c]['name']:30}" + "".join(f"{base['loss'][c][k]:22.4f}" for k in CRIT[:4])
            + f"  {-base['points'][i]:9.4f}")
    say("  swing (points between best and worst option): " + ", ".join(f"{LABEL[k]} {base['swing'][k]:.4f}"
                                                                        for k in CRIT[:4]))
    say("  weights: " + ", ".join(f"{LABEL[k]} {100 * base['w'][k]:.1f} %" for k in CRIT)
        + "  (manufacturability = recovery swing / 5)")
    say(f"  manufacturability AHP priorities: " + ", ".join(f"{c} {p:.3f}" for c, p in zip(CANDS, base["pri"]["make"]))
        + f"   CR {base['cr_make']:.3f} (< 0.10 acceptable)")

    say("\nPAIRWISE, EACH OPTION AGAINST EACH OTHER (base case). Per criterion: Saaty value (>1 favours the first)"
        " and the points difference; then the weighted head-to-head share:")
    idx = {c: i for i, c in enumerate(CANDS)}
    make_reason = {tuple(j["pair"]): " ".join(j["reason"].split()) for j in T["make"]}
    for a, b in combinations(CANDS, 2):
        i, j = idx[a], idx[b]
        say(f"  {a} vs {b}  ({CAND[a]['name']} vs {CAND[b]['name']})")
        for k in CRIT:
            sa = base["mats"][k][i, j]
            if k == "make":
                say(f"     {LABEL[k]:24} {sa:5.2f}   {make_reason[(a, b)]}")
            else:
                d = base["pts"][k][i] - base["pts"][k][j]
                fav = a if d > 1e-12 else (b if d < -1e-12 else "neither")
                say(f"     {LABEL[k]:24} {sa:5.2f}   {fav} better by {abs(d):.4f} points")
        hij = base["h"][i, j]
        say(f"     head-to-head share for {a}: {hij:.3f} -> {a if hij > 0.5 else b} wins")

    wins, cw = condorcet(base["h"])
    say("\nDECISION, BASE CASE:")
    say("  option                          exp. points  Table-06 total  AHP priority  Copeland wins")
    for i, c in enumerate(CANDS):
        say(f"  {c} {CAND[c]['name']:30} {base['points'][i]:11.4f}  {base['table'][i]:14.2f}  {base['ahp'][i]:12.3f}"
            f"  {wins[i]:13d}")
    say(f"  Condorcet winner: {CANDS[cw] if cw is not None else 'none (a cycle)'}")

    say(f"\nROBUSTNESS ({T['monte_carlo']['draws']} draws each: failure rates log-uniform in their ranges, part "
        "masses, p_damage, score value of either field, manufacturability judgments +/-1 step, its weight 1/3-1/7 "
        "of recovery, Dirichlet on the weights). Two ways to draw the failure rates:")
    runs = {}
    for indep, title in ((False, "SHARED: one quantile per failure key for every option (common level uncertain, "
                                  "the ranking inside each key follows the ranges)"),
                         (True, "INDEPENDENT: each option draws its own quantile, except the shared hardware "
                                "(overlapping ranges can reverse a ranking)")):
        mc = robustness(designs, ref, val, keys, independent=indep)
        runs[indep] = mc
        say(f"  {title}")
        say("    option                          P(win): points   Table-06   AHP   Condorcet")
        for i, c in enumerate(CANDS):
            say(f"    {c} {CAND[c]['name']:30}          {100 * mc['win']['points'][i]:5.1f} %  "
                f"{100 * mc['win']['table'][i]:7.1f} %  {100 * mc['win']['ahp'][i]:5.1f} %  "
                f"{100 * mc['win']['condorcet'][i]:7.1f} %")
        say(f"    no Condorcet winner in {100 * mc['no_condorcet']:.1f} % of draws; P(row beats column head-to-head):")
        say("         " + "".join(f"{c:>8}" for c in CANDS))
        for i, c in enumerate(CANDS):
            say(f"    {c:4} " + "".join(f"{'-':>8}" if i == j else f"{100 * mc['beats'][i, j]:7.1f}%"
                                      for j in range(len(CANDS))))
    mc = runs[True]

    lead = CANDS[int(np.argmax(base["points"]))]
    say(f"\nBREAK-EVEN against the expected-points leader {lead} (base case): factor on each rival's own failure "
        "rates (shared hardware unchanged) that ties it with the leader:")
    for c in CANDS:
        if c == lead:
            continue
        k = breakeven(designs, ref, ve, q_mid, pd_mid, c, lead)
        say(f"  {c} {CAND[c]['name']:30} " + (f"x{k:.2f}  (its own failure rates must fall to {100 * k:.0f} % of "
                                               "the estimate)" if k is not None else "cannot tie even at zero"))
    ver = verified_designs(ref, cda_hi, ve)
    vb = evaluate(ver, ref, ve, q_mid, pd_mid, 0.5, 5.0)
    say("\nCHECK with VERIFIED drives only (no reseller data): " + ", ".join(
        f"{c} {ver[c]['drive']} ({ver[c]['t_stow']:.0f} s, {1000 * part_mass(c, ver[c]['drive'])[0]:.0f} g)"
        for c in CANDS))
    say("  expected points: " + ", ".join(f"{c} {v:.4f}" for c, v in zip(CANDS, vb["points"]))
        + f";  Table-06 totals: " + ", ".join(f"{c} {v:.2f}" for c, v in zip(CANDS, vb["table"]))
        + f";  Condorcet winner {CANDS[condorcet(vb['h'])[1]] if condorcet(vb['h'])[1] is not None else 'none'}")

    top = list(np.argsort(-base["table"])[:3])
    say("\nPROPOSED TABLE 06 (top three by the Table-06 total; scores 1-5 interval-scaled across all four "
        f"candidates, never stretched below a {T['criteria']['min_span_points']} point range, with weights on the "
        "same scale, so the weighted total ranks exactly as expected points plus manufacturability):")
    say("  criterion                 wt.   " + "".join(f"{CANDS[i] + ' ' + CAND[CANDS[i]]['short']:>30}" for i in top))
    for k in CRIT:
        say(f"  {LABEL[k]:24} {base['w'][k]:.2f}  " + "".join(f"{base['scores'][k][i]:30.1f}" for i in top))
    say(f"  {'Weighted total':24} 1.00  " + "".join(f"{base['table'][i]:30.2f}" for i in top))
    with (OUT / "dr_trade_table.csv").open("w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["criterion", "weight"] + [f"{CANDS[i]} {CAND[CANDS[i]]['name']}" for i in top])
        for k in CRIT:
            wr.writerow([LABEL[k], f"{base['w'][k]:.2f}"] + [f"{base['scores'][k][i]:.1f}" for i in top])
        wr.writerow(["Weighted total", "1.00"] + [f"{base['table'][i]:.2f}" for i in top])
    text = "\n".join(lines)
    print(text)
    (OUT / "dr_trade_report.txt").write_text(text + "\n", encoding="utf-8")
    chart(base, mc)
    print("\nwrote out/dr_trade_report.txt, out/dr_trade.pdf, out/dr_trade_table.csv")


def breakeven(designs, ref, val, q, pd, rival, lead):
    """Factor on the rival's candidate-specific failure rates at which its expected points
    equal the leader's (bisection on [0, 1]); None if it cannot tie even at zero."""
    def gap(k):
        r = evaluate(designs, ref, val, q, pd, 0.5, 5.0, scale={rival: k})
        return r["points"][CANDS.index(rival)] - r["points"][CANDS.index(lead)]
    if gap(0.0) < 0:
        return None
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if gap(mid) > 0 else (lo, mid)
    return 0.5 * (lo + hi)


def verified_designs(ref, cda, val):
    """Each candidate sized with VERIFIED drives only."""
    out = {}
    for c in CANDS:
        best = None
        for did in CAND[c]["drives"]:
            if not DRIVE[did]["status"].startswith("VERIFIED"):
                continue
            des = size(c, did, ref, cda)
            if isinstance(des, str):
                continue
            cost = -val["per_kg"] * part_mass(c, did)[0] - val["per_s"] * des["t_stow"]
            if best is None or cost < best[0]:
                best = (cost, des)
        out[c] = best[1]
    return out


def robustness(designs, ref, val, keys, independent=False):
    """Monte Carlo. independent=False: one quantile per failure key, shared by every
    option (tests the valuation and the common level; the options' ranking inside each
    key is then fixed by the ranges). independent=True: options draw their own quantile
    for every mode except shared hardware, so overlapping ranges can reverse a ranking."""
    cfg = T["monte_carlo"]
    shared = set(cfg["shared_keys"])
    rng = np.random.default_rng(cfg["seed"])
    n, m = cfg["draws"], len(CANDS)
    win = {k: np.zeros(m) for k in ("points", "table", "ahp", "condorcet")}
    beats = np.zeros((m, m))
    no_cw = 0
    mass_names = list(T["parts"]) + ["drive:" + d for d in DRIVE]
    pdr = T["consequence"]["p_damage_severe"]
    for _ in range(n):
        q_fail = {k: rng.random() for k in keys}
        if independent:
            q_fail.update({(c, k): rng.random() for c in CANDS for k in keys if k not in shared})
        q_mass = {k: rng.random() for k in mass_names}
        pdmg = rng.uniform(*pdr)
        sc = val["expected"] if rng.random() < 0.5 else val["aggressive"]
        a_rm = float(rng.choice(T["criteria"]["make_vs_recovery"]))
        shift = rng.choice([-1, 0, 1], p=[cfg["judgment_step_p"], 1 - 2 * cfg["judgment_step_p"],
                                          cfg["judgment_step_p"]], size=len(T["make"]))
        r = evaluate(designs, ref, sc, q_fail, pdmg, q_mass, a_rm, shift)
        wv = np.array([r["w"][k] for k in CRIT])
        wd = rng.dirichlet(cfg["dirichlet_alpha"] * wv + 1e-9)
        table = sum(wd[i] * r["scores"][k] for i, k in enumerate(CRIT))
        ahp = sum(wd[i] * r["pri"][k] for i, k in enumerate(CRIT))
        h = head_to_head([r["mats"][k] for k in CRIT], wd)
        for name, v in (("points", r["points"]), ("table", table), ("ahp", ahp)):
            best = np.flatnonzero(v >= v.max() - 1e-12)
            win[name][best] += 1.0 / len(best)
        wins, cw = condorcet(h)
        if cw is None:
            no_cw += 1
        else:
            win["condorcet"][cw] += 1
        beats += h > 0.5
    return {"win": {k: v / n for k, v in win.items()}, "beats": beats / n, "no_condorcet": no_cw / n}


def chart(base, mc):
    sys.path.insert(0, str(common.REPO / "design-system" / "matplotlib"))
    import dbfplot as dp
    dp.use()
    fig, (a1, a2) = dp.figure("page", 2.4, ncols=2)
    y = np.arange(len(CANDS))[::-1]
    left = np.zeros(len(CANDS))
    shades = [dp.INK, dp.GRAPHITE, dp.STEEL, dp.FOG]
    for k, col in zip(CRIT[:4], shades):
        v = np.array([base["loss"][c][k] for c in CANDS])
        a1.barh(y, v, left=left, height=0.55, color=col, label=LABEL[k].upper())
        left += v
    a1.set_yticks(y, [f"{c}  {CAND[c]['short'].upper()}" for c in CANDS], fontsize=5.2, family=dp.MONO)
    a1.set_xlabel("Expected total-mission points lost (base case)")
    a1.legend(fontsize=4.4, loc="upper right", frameon=False)
    a1.grid(axis="y", visible=False)
    a1.set_title("POINTS AT STAKE, BASE CASE", fontsize=5.2, family=dp.MONO, color=dp.GRAPHITE, loc="left")
    width = 0.2
    for j, (name, col) in enumerate((("points", dp.INK), ("table", dp.GRAPHITE), ("ahp", dp.STEEL),
                                     ("condorcet", dp.FOG))):
        a2.barh(y + (1.5 - j) * width, 100 * mc["win"][name], height=width, color=col, label=name.upper())
    a2.set_yticks(y, [c for c in CANDS], fontsize=5.2, family=dp.MONO)
    a2.set_xlim(0, 100)
    a2.set_xlabel("P(option wins), Monte Carlo (%)")
    a2.legend(fontsize=4.4, loc="lower right", frameon=False)
    a2.grid(axis="y", visible=False)
    a2.set_title("P(WIN), INDEPENDENT FAILURE DRAWS", fontsize=5.2, family=dp.MONO, color=dp.GRAPHITE, loc="left")
    dp.save(fig, OUT / "dr_trade.pdf")


if __name__ == "__main__":
    main()
