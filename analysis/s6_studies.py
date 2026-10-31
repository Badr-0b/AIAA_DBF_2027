# Copyright © 2026 Badr Obtel. All rights reserved.
"""Script 6: studies (R&D Sec. 4, Script 6). PROVISIONAL.

    python analysis/s6_studies.py

Written 13 Oct 2026; the team reviews and owns the numbers (rules
Sec. 1.3). Nothing here is a decision (user, 13 Oct): the outputs feed the
decision brief.

1. Total mission score of a complete design: wing family and area, accepted
   stall, payload unit = container + declared max sensor, simulators, drop
   height. M1 is waived and credited by M2; missions fly in order (Sec. 3.3.3);
   the M3 sensor mass is chosen per evaluation (<= declared max, Sec. 3.1.1);
   GM uses the declared max (Sec. 3.3.4). Physics: Script 4 (s4_sizing).
2. Robust design map: mean total over paired Monte Carlo draws on a wing-area x
   unit-mass grid, with P(M2 feasible). Its best cell is the REFERENCE POINT.
3. Tornado about the reference: each input +/-10 % and +/-20 %.
4. Carpet: deterministic total over wing area x unit mass, infeasible shaded.
5. Candidate designs compared on the same draws, each at its own robust unit.
6. Trade-study weights: normalised sensitivities of the criteria the trades
   score, plus mission completion from the attempt model (data/attempts.py).
Draws resample measured data where it exists (time factor: 24 lap/mission
pairs; pack Wh/kg: 9 packs; airframe factor: the fit's residual sd) and use the
ranges in inputs/studies.toml otherwise.
"""
import copy
import csv
import math
import sys

import numpy as np

import common
import s2_scoring as s2
import s4_sizing as s4
from common import OUT, RULES

ST = common.load("studies")
DATA = common.ANALYSIS / "data"
WINDOW = RULES["missions"]["window_s"]
EPS = 1e-9


# ---------------------------------------------------------------- pure helpers (tested)
def normalised_weights(deltas):
    """Weights proportional to |delta|, summing to 1 (dict in, dict out)."""
    total = sum(abs(v) for v in deltas.values())
    return {k: abs(v) / total for k, v in deltas.items()} if total else {k: 0.0 for k in deltas}


def expected_total(parts, p_attempt, attempts, gm_attempts):
    """Expected total mission score with completion risk (M1 waived, credited by M2).

    parts: {"M1", "M2", "M3", "GM"} scores if completed. M2 needs one success in
    `attempts`; M3 needs M2 then M3 in the same attempts; GM has its own tries.
    """
    sys.path.insert(0, str(DATA))
    from attempts import p_complete
    p2 = p_complete((p_attempt,), attempts)
    p3 = p_complete((p_attempt, p_attempt), attempts)
    pgm = 1.0 - (1.0 - p_attempt) ** gm_attempts
    return (parts["M1"] + parts["M2"]) * p2 + parts["M3"] * p3 + parts["GM"] * pgm


def arange(spec):
    start, stop, step = spec
    return np.round(np.arange(start, stop + EPS, step), 6)


# ---------------------------------------------------------------- evaluation
def fields(scale=1.0):
    return {sc: {k: v * scale for k, v in common.field_maxima(sc).items()} for sc in ("expected", "aggressive")}


def evaluate(fam, s, unit, P, field=None, n_sim=None, fine=False):
    """Every mission for one design under inputs P. Returns per-field parts and totals."""
    d = ST["design"]
    field = field or fields()
    sensor_max = unit - P.container_kg
    if sensor_max < d["sensor_min_kg"]:
        return None
    nsims = np.arange(0, d["n_sim_max"] + 1) if n_sim is None else np.array([n_sim])
    t2 = np.atleast_1d(s4.m2_fixed(fam, s, (1 + nsims) * unit, P, fine=fine))
    ms = np.unique(np.append(np.arange(0.5, sensor_max + EPS, 0.5), sensor_max))
    stow = s4.stow_time(ms, P) + d["t_stow_extra_s"]           # reel model + any added seconds
    laps = np.atleast_1d(s4.m3_search(fam, s, ms, P, stow_s=stow, fine=fine))
    prod = np.where(laps >= RULES["missions"]["m3_min_laps"], laps * ms, 0.0)
    j = int(np.argmax(prod))
    h = s2.declared_drop_height(d["drop_height_m"])
    out = {"sensor_max": sensor_max, "m3_mass": float(ms[j]), "laps": int(laps[j])}
    ok2 = np.isfinite(t2) & (t2 <= WINDOW)
    out["m2_feasible"] = bool(ok2.any())
    for sc, f in field.items():
        m2s = np.where(ok2, [s2.m2((1 + n) * unit, t if ok else 1.0, f["m2"], completed=ok)
                             for n, t, ok in zip(nsims, t2, ok2)], 0.0)
        i = int(np.argmax(m2s))
        done2 = bool(ok2[i])
        m3 = s2.m3(int(laps[j]), float(ms[j]), f["m3"], completed=done2 and prod[j] > 0)
        gm = s2.gm(sensor_max, h, f["gm"])
        parts = {"M1": 1.0, "M2": float(m2s[i]), "M3": m3, "GM": gm}   # M1 flown if M2 is impossible
        out[sc] = {**parts, "total": s2.total_mission(*parts.values()), "n_sim": int(nsims[i]),
                   "t2": float(t2[i]), "w": float((1 + nsims[i]) * unit)}
    return out


# ---------------------------------------------------------------- draws
def base_params():
    P = s4.Params(vs_max=ST["design"]["v_stall_max"])
    P.container_kg = ST["design"]["container_kg"]
    return P


def measured_time_factors():
    rows = csv.DictReader((DATA / "calibration.csv").open(encoding="utf-8"))
    return np.array([float(r["ratio"]) for r in rows
                     if r["param"] in ("lap_time", "first_lap_time", "mission_time", "turn360_time")])


def measured_pack_wh_per_kg():
    rows = csv.DictReader((DATA / "dbf_airframes.csv").open(encoding="utf-8"))
    return np.array([float(r["pack_wh_per_kg"]) for r in rows if r["pack_wh_per_kg"]])


def draws(n, seed):
    """n paired parameter sets: measured inputs resampled, the rest uniform in their range."""
    mc = ST["monte_carlo"]
    rng = np.random.default_rng(seed)
    _, _, sd, _ = s4.airframe_fit()
    tf, wh = measured_time_factors(), measured_pack_wh_per_kg()
    base = base_params()
    out = []
    for _ in range(n):
        P = copy.copy(base)
        P.f_body = rng.uniform(*mc["f_body_m2"])
        P.eta = rng.uniform(*mc["eta"])
        P.af_factor = math.exp(rng.normal(0.0, sd))
        P.t_to = rng.uniform(*mc["t_takeoff_s"])
        P.p_max = s4.SZ["battery"]["fuse_a"] * rng.uniform(*mc["pack_v_loaded"])
        P.rho = rng.uniform(*mc["rho"])
        P.e_factor = rng.uniform(*mc["e_factor"])
        P.clmax_factor = {"straight": rng.uniform(*mc["clmax_factor_straight"]),
                          "delta": rng.uniform(*mc["clmax_factor_delta"])}
        P.f_tow = rng.uniform(*mc["f_tow_m2"])
        P.container_kg = rng.uniform(*mc["container_kg"])
        P.time_cal = float(rng.choice(tf))
        P.wh_per_kg = float(rng.choice(wh))
        out.append(P)
    return out


# ---------------------------------------------------------------- studies
def robust_map(Ps, fam="straight"):
    g = ST["grid"]
    S, U = arange(g["wing_area_m2"]), arange(g["unit_kg"])
    mean = np.full((len(S), len(U)), np.nan)
    feas = np.zeros_like(mean)
    for i, s in enumerate(S):
        for j, u in enumerate(U):
            tot, ok = [], []
            for P in Ps:
                r = evaluate(fam, s, u, P)
                if r is None:
                    break
                tot.append(r["expected"]["total"])
                ok.append(r["m2_feasible"])
            if tot:
                mean[i, j], feas[i, j] = np.mean(tot), np.mean(ok)
    return S, U, mean, feas


def best_unit(fam, s, Ps, units):
    """Unit mass with the highest mean total over the draws (common random numbers)."""
    scores = []
    for u in units:
        r = [evaluate(fam, s, u, P) for P in Ps]
        scores.append(np.mean([x["expected"]["total"] for x in r]) if all(r) else -1)
    k = int(np.argmax(scores))
    return float(units[k]), scores[k]


TORNADO = [  # (label, kind, attribute or design key)
    ("Wing area", "decision", "s"), ("Payload unit mass", "decision", "unit"),
    ("Accepted stall speed", "decision", "vs_max"), ("Load-factor limit", "decision", "n_struct"),
    ("Drop height", "decision", "h"), ("Turn CL margin", "decision", "cl_margin"),
    ("Usable battery energy", "decision", "e_usable"),
    ("Airframe mass", "uncertainty", "af_factor"), ("Non-wing drag area", "uncertainty", "f_body"),
    ("Wing profile drag", "uncertainty", "cd_w"), ("CLmax", "uncertainty", "clmax"),
    ("Span efficiency e", "uncertainty", "e_factor"), ("Propulsive efficiency", "uncertainty", "eta"),
    ("Lap-time factor", "uncertainty", "time_cal"), ("Take-off time", "uncertainty", "t_to"),
    ("Air density", "uncertainty", "rho"), ("Pack specific energy", "uncertainty", "wh_per_kg"),
    ("Peak battery power", "uncertainty", "p_max"), ("Tow drag area", "uncertainty", "f_tow"),
    ("Container mass", "uncertainty", "container_kg"), ("Field maxima", "uncertainty", "field"),
]


def perturbed_total(ref, key, factor, fam="straight"):
    """Expected-field total with one input scaled by `factor` about the reference."""
    s, unit = ref["s"], ref["unit"]
    P = base_params()
    field = None
    h_saved = ST["design"]["drop_height_m"]
    if key == "s":
        s *= factor
    elif key == "unit":
        unit *= factor
    elif key == "clmax":
        P.clmax_factor = {fam: factor}
    elif key == "field":
        field = fields(factor)
    elif key == "h":
        ST["design"]["drop_height_m"] = min(h_saved * factor, RULES["ground"]["drop_height_max_m"])
    else:
        setattr(P, key, getattr(P, key) * factor)
    try:
        r = evaluate(fam, s, unit, P, field=field, fine=True)
    finally:
        ST["design"]["drop_height_m"] = h_saved
    return (r["expected"]["total"], r["m2_feasible"]) if r else (float("nan"), False)


def tornado(ref):
    base, _ = perturbed_total(ref, "s", 1.0)
    rows = []
    for label, kind, key in TORNADO:
        d = {}
        for step in ST["tornado"]["steps"]:
            for sgn in (-1, 1):
                tot, feas = perturbed_total(ref, key, 1 + sgn * step)
                d[sgn * step] = (tot - base, feas)
        rows.append((label, kind, key, d))
    rows.sort(key=lambda r: -max(abs(r[3][-0.1][0]), abs(r[3][0.1][0])))
    return base, rows


CRITERIA = {"Airframe mass": "af_factor", "Parasite drag": "f_body", "High lift (CLmax)": "clmax",
            "Induced drag (e)": "e_factor", "Propulsive efficiency": "eta",
            "Turn and lap performance": "time_cal", "Structural load capability": "n_struct"}


def region(ref):
    """The robust region: the reference and its neighbours on the map grid."""
    g = ST["grid"]
    ds, du = g["wing_area_m2"][2], g["unit_kg"][2]
    return [{"s": round(ref["s"] + a * ds, 6), "unit": ref["unit"] + b * du} for a in (-1, 0, 1) for b in (-1, 0, 1)]


def trade_weights(ref):
    """Weights of the trade criteria: mean |delta total| for +/-10 % of each criterion's
    input, averaged over the robust region (integer laps and simulators make one point
    lumpy), plus mission completion (+/-10 % on the per-attempt success probability)."""
    pts = region(ref)
    deltas = {}
    for c, key in CRITERIA.items():
        vals = []
        for pt in pts:
            b, _ = perturbed_total(pt, "s", 1.0)
            lo, _ = perturbed_total(pt, key, 0.9)
            hi, _ = perturbed_total(pt, key, 1.1)
            if all(np.isfinite([b, lo, hi])):
                vals.append((abs(lo - b) + abs(hi - b)) / 2)
        deltas[c] = float(np.mean(vals))
    rel = ST["reliability"]
    vals = []
    for pt in pts:
        r = evaluate("straight", pt["s"], pt["unit"], base_params(), fine=True)
        parts = {k: r["expected"][k] for k in ("M1", "M2", "M3", "GM")}
        e = [expected_total(parts, rel["p_attempt"] * f, rel["attempts"], rel["gm_attempts"]) for f in (0.9, 1.1)]
        vals.append(abs(e[1] - e[0]) / 2)
    deltas["Mission completion (reliability)"] = float(np.mean(vals))
    return deltas, normalised_weights(deltas)


DRAWN = {"Non-wing drag area": "f_body", "Propulsive efficiency": "eta", "Airframe mass": "af_factor",
         "Take-off time": "t_to", "Peak battery power": "p_max", "Air density": "rho", "Span efficiency e": "e_factor",
         "Tow drag area": "f_tow", "Container mass": "container_kg", "Lap-time factor": "time_cal",
         "Pack specific energy": "wh_per_kg"}


def spearman(x, y):
    rx, ry = np.argsort(np.argsort(x)), np.argsort(np.argsort(y))
    return float(np.corrcoef(rx, ry)[0, 1]) if np.std(rx) and np.std(ry) else 0.0


def global_sensitivity(ref, Ps):
    """Spearman rank correlation of the reference total with each drawn input (all draws)."""
    tot = np.array([evaluate("straight", ref["s"], ref["unit"], P)["expected"]["total"] for P in Ps])
    out = {label: spearman(np.array([getattr(P, k) for P in Ps]), tot) for label, k in DRAWN.items()}
    out["CLmax"] = spearman(np.array([P.clmax_factor["straight"] for P in Ps]), tot)
    return dict(sorted(out.items(), key=lambda kv: -abs(kv[1]))), tot


# ---------------------------------------------------------------- charts
def charts(S, U, mean, feas, ref, carpet, base, rows, comp, weights):
    sys.path.insert(0, str(common.REPO / "design-system" / "matplotlib"))
    import dbfplot as dp
    OUT.mkdir(exist_ok=True)
    dp.use()
    # robust map: grey bands of mean total, P(M2 feasible) lines
    title = dict(fontsize=5.6, family=dp.MONO, color=dp.GRAPHITE, loc="left")
    fig, ax = dp.figure("col", 2.4)
    lv = [2.5, 4.0, 5.0, 5.5, 6.0, 6.25, 6.6]
    grey = [dp.BONE, dp.MIST, "#CFD2D7", dp.FOG, "#8C929B", dp.STEEL]
    ax.contourf(U, S, mean, levels=lv, colors=grey)
    cs = ax.contour(U, S, mean, levels=lv[1:-1], colors=dp.INK, linewidths=0.4)
    ax.clabel(cs, fmt="%.2f", fontsize=4.6, inline_spacing=2)
    ax.contour(U, S, feas, levels=[0.9], colors=dp.INK, linewidths=1.2)
    ax.contour(U, S, feas, levels=[0.5], colors=dp.INK, linewidths=1.0, linestyles="--")
    ax.plot([], [], color=dp.INK, lw=1.2, label="P(M2 FEASIBLE) 90 %")
    ax.plot([], [], color=dp.INK, lw=1.0, ls="--", label="P(M2 FEASIBLE) 50 %")
    ax.plot(ref["unit"], ref["s"], "o", ms=4, color="white", mec=dp.INK, mew=1.0)
    ax.annotate("ROBUST BEST", (ref["unit"], ref["s"]), xytext=(-4, 5), textcoords="offset points", ha="right",
                fontsize=5, family=dp.MONO)
    leg = ax.legend(loc="lower right", fontsize=4.6, framealpha=1)
    for t in leg.get_texts():
        t.set_family(dp.MONO)
    ax.set_title("MEAN TOTAL MISSION SCORE OVER THE DRAWS, EXPECTED FIELD", **title)
    ax.set_xlabel("Payload unit mass: container + declared sensor (kg)")
    ax.set_ylabel("Wing area S (m²), straight wing")
    dp.save(fig, OUT / "s6_robust_map.pdf")
    # carpet (deterministic, baseline inputs)
    cS, cU, cT = carpet
    fig, ax = dp.figure("col", 2.4)
    bad = np.isnan(cT)
    ax.contourf(cU, cS, bad.astype(float), levels=[0.5, 1.5], colors=[dp.MIST])
    cs = ax.contour(cU, cS, np.ma.masked_invalid(cT), levels=[5.5, 6.0, 6.5, 7.0], colors=dp.INK, linewidths=0.6)
    ax.clabel(cs, fmt="%.1f", fontsize=4.6, inline_spacing=2)
    ax.plot(ref["unit"], ref["s"], "o", ms=4, color="white", mec=dp.INK, mew=1.0)
    ax.annotate("ROBUST BEST", (ref["unit"], ref["s"]), xytext=(-4, 5), textcoords="offset points", ha="right",
                fontsize=5, family=dp.MONO)
    ax.plot(3.5, 0.414, "s", ms=3.4, color="white", mec=dp.INK)
    ax.annotate("01 PLACEHOLDER", (3.5, 0.414), xytext=(5, 2), textcoords="offset points", fontsize=4.6, family=dp.MONO)
    ax.text(10.8, 0.52, "M2 NOT\nFEASIBLE", ha="right", fontsize=5, family=dp.MONO, color=dp.STEEL)
    ax.set_title("TOTAL MISSION SCORE, BASELINE INPUTS (NO UNCERTAINTY)", **title)
    ax.set_xlabel("Payload unit mass: container + declared sensor (kg)")
    ax.set_ylabel("Wing area S (m²), straight wing")
    dp.save(fig, OUT / "s6_carpet.pdf")
    # tornado
    fig, ax = dp.figure("col", 3.0)
    lim = 0.6
    for i, (label, kind, key, d) in enumerate(rows):
        y = len(rows) - 1 - i
        for step, shade in ((0.2, dp.MIST), (0.1, dp.INK if kind == "decision" else dp.STEEL)):
            for sgn in (-1, 1):
                v = d[sgn * step][0]
                if np.isfinite(v):
                    ax.barh(y, max(-lim, min(lim, v)), color=shade, height=0.62 if step == 0.2 else 0.42,
                            zorder=2 if step == 0.1 else 1)
                    if abs(v) > lim:
                        ax.text(-lim + 0.01 if v < 0 else lim - 0.01, y + 0.42,
                                f"{100 * sgn * step:+.0f} %: {v:+.2f}" + (" (M2 LOST)" if not d[sgn * step][1] else ""),
                                ha="left" if v < 0 else "right", va="center", fontsize=4.2, family=dp.MONO,
                                color=dp.INK, zorder=3)
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-0.7, len(rows) - 0.1)
    ax.axvline(0, color=dp.INK, lw=0.8)
    ax.set_yticks(range(len(rows)), [r[0].upper() for r in reversed(rows)], fontsize=4.6, family=dp.MONO)
    ax.set_xlabel(f"Change in total mission score (reference {base:.2f})")
    ax.set_title("±10 %: DARK = DECISION, GREY = UNCERTAINTY\nPALE = ±20 %", **title)
    ax.grid(axis="y", visible=False)
    dp.save(fig, OUT / "s6_tornado.pdf")
    # candidate comparison
    fig, ax = dp.figure("col", 2.0)
    labels = list(comp)
    ax.boxplot([comp[k]["totals"] for k in labels], vert=False, widths=0.5, showfliers=False,
               medianprops={"color": dp.INK}, boxprops={"color": dp.INK}, whiskerprops={"color": dp.INK},
               capprops={"color": dp.INK}, whis=(10, 90))
    ax.set_yticks(range(1, len(labels) + 1), [k.upper() for k in labels], fontsize=4.8, family=dp.MONO)
    ax.set_xlabel("Total mission score, expected field")
    ax.set_title("BOX P25–P75, WHISKERS P10–P90", fontsize=5.6, family=dp.MONO, color=dp.GRAPHITE, loc="left")
    ax.grid(axis="y", visible=False)
    dp.save(fig, OUT / "s6_candidates.pdf")
    # trade weights
    fig, ax = dp.figure("col", 1.9)
    items = sorted(weights.items(), key=lambda kv: kv[1])
    ax.barh(range(len(items)), [100 * v for _, v in items], color=dp.INK, height=0.55)
    ax.set_yticks(range(len(items)), [k.upper() for k, _ in items], fontsize=4.8, family=dp.MONO)
    ax.set_xlabel("Trade weight (%), from the sensitivities")
    ax.grid(axis="y", visible=False)
    dp.save(fig, OUT / "s6_trade_weights.pdf")


# ---------------------------------------------------------------- main
def main():
    sys.stdout.reconfigure(encoding="utf-8")
    mc = ST["monte_carlo"]
    Ps = draws(mc["draws"], mc["seed"])
    print(f"Script 6 (PROVISIONAL). {mc['draws']} paired draws; time factor resampled from "
          f"{len(measured_time_factors())} measured pairs, pack Wh/kg from {len(measured_pack_wh_per_kg())} packs.")
    S, U, mean, feas = robust_map(Ps)
    i, j = np.unravel_index(np.nanargmax(mean), mean.shape)
    ref = {"s": float(S[i]), "unit": float(U[j])}
    print("\nRobust design map, straight wing (mean total mission score, expected field; P(M2 feasible) in brackets):")
    print("  S m2 \\ unit kg " + "".join(f"{u:>12.0f}" for u in U))
    for a, s in enumerate(S):
        print(f"  {s:13.2f}  " + "".join(f"{mean[a, b]:7.2f} ({100 * feas[a, b]:3.0f})" if np.isfinite(mean[a, b])
                                         else f"{'-':>12}" for b in range(len(U))))
    print(f"  robust best: S {ref['s']:.2f} m2, unit {ref['unit']:.1f} kg, mean total {mean[i, j]:.2f}, "
          f"P(M2 feasible) {100 * feas[i, j]:.0f} %")
    r0 = evaluate("straight", ref["s"], ref["unit"], base_params(), fine=True)
    for sc in ("expected", "aggressive"):
        e = r0[sc]
        print(f"  reference, baseline inputs, {sc:10}: M1 {e['M1']:.2f} M2 {e['M2']:.2f} M3 {e['M3']:.2f} "
              f"GM {e['GM']:.2f} = {e['total']:.2f}  (W {e['w']:.1f} kg, N_sim {e['n_sim']}, M2 {e['t2']:.1f} s, "
              f"M3 {r0['laps']} laps x {r0['m3_mass']:.1f} kg, declared sensor {r0['sensor_max']:.1f} kg)")
    g = ST["grid"]
    cS, cU = arange(g["carpet_wing_area_m2"]), arange(g["carpet_unit_kg"])
    P0 = base_params()
    cT = np.full((len(cS), len(cU)), np.nan)
    for a, s in enumerate(cS):
        for b, u in enumerate(cU):
            r = evaluate("straight", s, u, P0)
            if r and r["m2_feasible"]:
                cT[a, b] = r["expected"]["total"]
    base, rows = tornado(ref)
    print(f"\nTornado about the reference (expected field; reference total {base:.2f}):")
    print("  input                         kind          -20 %    -10 %    +10 %    +20 %   M2 stays feasible")
    for label, kind, key, d in rows:
        print(f"  {label:28}  {kind:11}  " + "  ".join(f"{d[k][0]:+7.2f}" for k in (-0.2, -0.1, 0.1, 0.2))
              + f"   {'yes' if all(f for _, f in d.values()) else 'NO at ' + ', '.join(f'{100 * k:+.0f} %' for k, (_, f) in d.items() if not f)}")
    units = arange(g["unit_kg"])
    comp = {}
    for label, fam, s in (("straight 0.41 (01 placeholder)", "straight", 0.414), ("straight 0.60", "straight", 0.6),
                          ("straight 0.80", "straight", 0.8), ("straight 1.00", "straight", 1.0),
                          ("delta 0.83 (02)", "delta", 0.83)):
        u, _ = best_unit(fam, s, Ps, units)
        tots = np.array([evaluate(fam, s, u, P)["expected"]["total"] for P in Ps])
        comp[label] = {"unit": u, "totals": tots}
    ref_key = max(comp, key=lambda k: np.mean(comp[k]["totals"]))
    print("\nCandidates, each at its own robust unit mass (same draws); paired against the best mean:")
    for k, c in comp.items():
        t, b = c["totals"], comp[ref_key]["totals"]
        tail = "" if k == ref_key else (f"   {ref_key}: better {100 * np.mean(b > t + 1e-9):.0f} %, "
                                        f"tie {100 * np.mean(np.abs(b - t) <= 1e-9):.0f} %, worse {100 * np.mean(b < t - 1e-9):.0f} %, "
                                        f"mean gain {np.mean(b - t):+.2f}")
        print(f"  {k:32} unit {c['unit']:4.1f} kg   mean {np.mean(t):.2f}  P10 {np.percentile(t, 10):.2f}  "
              f"P50 {np.median(t):.2f}  P90 {np.percentile(t, 90):.2f}" + tail)
    gs, _ = global_sensitivity(ref, Ps)
    print("\nGlobal sensitivity at the reference (Spearman rank correlation, total vs each drawn input):")
    for k, v in gs.items():
        print(f"  {k:24} {v:+.2f}")
    deltas, weights = trade_weights(ref)
    print("\nTrade-study weights (normalised mean |delta total| at +/-10 % of each criterion's input, "
          "averaged over the 9-point robust region):")
    for k, w in sorted(weights.items(), key=lambda kv: -kv[1]):
        print(f"  {k:36} {100 * w:5.1f} %   (delta {deltas[k]:.3f})")
    with (OUT / "s6_trade_weights.csv").open("w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["criterion", "delta_total_at_10pct", "weight"])
        for k in weights:
            wr.writerow([k, f"{deltas[k]:.4f}", f"{weights[k]:.4f}"])
    charts(S, U, mean, feas, ref, (cS, cU, cT), base, rows, comp, weights)
    print("\nwrote out/s6_robust_map.pdf, s6_carpet.pdf, s6_tornado.pdf, s6_candidates.pdf, s6_trade_weights.pdf/.csv")


if __name__ == "__main__":
    main()
