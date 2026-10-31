"""Proposal P1 sensitivity study about Variant A (DB-02 rev B), 31 Oct 2026.

1. Tornado: one input at a time scaled by -20/-10/+10/+20 % about Variant A with the sensor declared at
   the DB-02 median (6.25 kg), scored on the same 120 paired draws as DB-02 (expected field), so every
   bar is a paired difference, not noise. Pattern of analysis/s6_studies.perturbed_total, routed through
   the DB-02 adapter (the perturbation is applied to the design's effective inputs Q = adapter.apply(d, P)).
2. Declared-mass sweep: Variant A's airframe with the sensor declared from 2 to 10 kg (container rebuilt for
   declarations above 8 kg). Per draw: the mission parts against the expected field, P(M2 feasible), and the
   per-attempt success of S2 p_attempt at the stall speed and T/W the declaration creates; completion is
   the finalists' attempt-budget mix (finalists._pc). Expected total = (1 + M2) P2 + M3 P23 + 0.9 GM, the
   DB-02 run2 objective.
Imports DB-02 and analysis code read-only. Writes proposal/data/p1_sens.json only.
Run: PYTHONDONTWRITEBYTECODE=1 python proposal/tools/p1_sensitivity.py
"""
from __future__ import annotations

import copy
import json
import math
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PROP = HERE.parent
DB02 = PROP.parent / "DB-02_aircraft_variants"
sys.path.insert(0, str(DB02 / "src"))

import numpy as np                                    # noqa: E402
from integration import adapter as A                  # noqa: E402
from integration import search as SE                  # noqa: E402
from integration import finalists as FI               # noqa: E402
from field import model as fm                         # noqa: E402

s6 = A.s6
G0 = A.G0
M_DECL = 6.25            # DB-02 median declaration for Variant A (finalists_rows base S10F8)
STEPS = (-0.2, -0.1, 0.1, 0.2)

# label, kind, key. kind: decision (team chooses) or uncertainty (the world chooses)
INPUTS = [
    ("Wing area", "decision", "s"),
    ("Drop height", "decision", "h"),
    ("Usable battery energy", "decision", "e_usable"),
    ("Airframe mass", "uncertainty", "af_kg"),
    ("Maximum lift (CLmax)", "uncertainty", "clmax"),
    ("Lap-time factor", "uncertainty", "time_cal"),
    ("Propulsive efficiency", "uncertainty", "power_factor"),
    ("Air density", "uncertainty", "rho"),
    ("Field maxima", "uncertainty", "field"),
    ("Non-wing drag area", "uncertainty", "f_body"),
    ("Span efficiency e", "uncertainty", "e_factor"),
    ("Container mass", "uncertainty", "container_kg"),
    ("Take-off time", "uncertainty", "t_to"),
]


def design(s=1.0, m_decl=M_DECL):
    d = SE.make(s, "fowler", max(8.0, m_decl), "8s")
    return d.with_(unit=m_decl + d.meta["container_kg"])


def run_one(d, P, key=None, f=1.0):
    """s6.evaluate for design d under draw P with one effective input scaled by f."""
    Q = A.apply(d, P)
    field = None
    if key in ("af_kg", "e_usable", "time_cal", "rho", "f_body", "e_factor", "container_kg", "t_to"):
        setattr(Q, key, getattr(Q, key) * f)
    elif key == "power_factor":                       # +10 % efficiency = 1/1.1 of the battery power
        Q.power_factor = Q.power_factor / f
    elif key == "clmax":
        k = Q.family_fn[1]
        Q.clmax_factor = {**Q.clmax_factor, k: Q.clmax_factor.get(k, 1.0) * f}
    elif key == "field":
        field = s6.fields(f)
    h_saved = s6.ST["design"]["drop_height_m"]
    if key == "h":
        s6.ST["design"]["drop_height_m"] = min(h_saved * f, 1.524)
    try:
        with A.st_patch(d.ops), A._thrust(Q):
            return s6.evaluate(d.family, d.s, d.unit, Q, field=field, fine=False)
    finally:
        s6.ST["design"]["drop_height_m"] = h_saved


def mean_total(d, Ps, key=None, f=1.0):
    rs = [run_one(d, P, key, f) for P in Ps]
    tot = np.array([r["expected"]["total"] if r else np.nan for r in rs])
    feas = np.mean([bool(r and r["m2_feasible"]) for r in rs])
    return tot, float(feas)


def perturbed(d, P, key, f):
    """Effective inputs Q for design d under draw P with one input scaled by f; plus field and drop height."""
    Q = A.apply(d, P)
    field, h = None, None
    if key in ("af_kg", "e_usable", "time_cal", "rho", "f_body", "e_factor", "container_kg", "t_to"):
        setattr(Q, key, getattr(Q, key) * f)
    elif key == "power_factor":
        Q.power_factor = Q.power_factor / f
    elif key == "clmax":
        k = Q.family_fn[1]
        Q.clmax_factor = {**Q.clmax_factor, k: Q.clmax_factor.get(k, 1.0) * f}
    elif key == "field":
        field = s6.fields(f)
    elif key == "h":
        h = min(1.524 * f, 1.524)
    return Q, field, h


def eval_q(d, Q, field, h):
    h_saved = s6.ST["design"]["drop_height_m"]
    if h is not None:
        s6.ST["design"]["drop_height_m"] = h
    try:
        with A.st_patch(d.ops), A._thrust(Q):
            return s6.evaluate(d.family, d.s, d.unit, Q, field=field)
    finally:
        s6.ST["design"]["drop_height_m"] = h_saved


def policy_rows(key=None, f=1.0, s_area=1.0):
    """DB-02 finalists.run2 policy (reliability-aware declaration at tech, M3 ballast per attempt),
    re-implemented with a perturbation hook. Base case reproduces F-A-MEAN."""
    d0 = SE.make(s_area, "fowler", 8.0, "8s")
    Ps = A.draws()
    cm = d0.meta["container_kg"]
    grid = SE.m_grid(8.0, 0.5)
    designs = {m: d0.with_(unit=m + cm) for m in grid}
    cx = d0.meta["complexity"]
    T0 = d0.propulsion.static_thrust_n
    clm0 = d0.meta["clmax_landing"]

    def assess(P, m_list, tech):
        ev = {}
        for m in m_list:
            k = None if (tech and key == "rho") else key
            Q, field, h = perturbed(designs[m], P, k, f)
            r = eval_q(designs[m], Q, field, h)
            if r is None:
                continue
            e = r["expected"]
            w = e["w"] if r["m2_feasible"] else designs[m].unit
            g2 = Q.empty(d0.s) + Q.battery() + w
            g3 = Q.empty(d0.s) + Q.battery() + r["m3_mass"]
            clm = clm0 * Q.clmax_factor.get(Q.family_fn[1], 1.0)
            vs2 = math.sqrt(2 * g2 * G0 / (SE.RHO_DESIGN * d0.s * clm))
            vs3 = math.sqrt(2 * g3 * G0 / (SE.RHO_DESIGN * d0.s * clm))
            p2 = fm.p_attempt({"v_stall": vs2, "tw_takeoff": T0 / (g2 * G0)}, cx, mission="M2") if r["m2_feasible"] else 0.0
            p3 = fm.p_attempt({"v_stall": vs3, "tw_takeoff": T0 / (g3 * G0)}, cx, mission="M3")
            ev[m] = dict(r=r, e=e, p2=max(0.01, min(0.99, p2)), p3=max(0.01, min(0.99, p3)))
        return ev

    rows = []
    for P in Ps:
        Pt = copy.copy(P)
        Pt.rho = SE.RHO_TECH
        ev = assess(Pt, grid, True)
        best, best_v = None, -1.0
        for m, x in ev.items():
            opts = [(y["p3"] * y["e"]["M3"], y) for mm, y in ev.items() if mm <= m + 1e-9]
            _, y3 = max(opts, key=lambda t: t[0])
            v = (1.0 + x["e"]["M2"]) * FI._pc(fm, (x["p2"],)) + y3["e"]["M3"] * FI._pc(fm, (x["p2"], y3["p3"]))                 + x["e"]["GM"] * 0.9
            if v > best_v:
                best, best_v = m, v
        evp = assess(P, [m for m in grid if m <= best + 1e-9], False)
        x = evp[best]
        y3 = max(evp.values(), key=lambda y: y["p3"] * y["e"]["M3"])
        rows.append({"m": best, "total": x["e"]["M1"] + x["e"]["M2"] + y3["e"]["M3"] + x["e"]["GM"],
                     "feas": bool(x["r"]["m2_feasible"])})
    return rows


def _task(args):
    key, st = args
    if key == "s":
        rows = policy_rows(s_area=1.0 + st)
    else:
        rows = policy_rows(key, 1.0 + st)
    return key, st, [r["total"] for r in rows], float(np.mean([r["feas"] for r in rows])),         float(np.median([r["m"] for r in rows]))


def tornado():
    from concurrent.futures import ProcessPoolExecutor
    tasks = [(None, 0.0)] + [(key, st) for _, _, key in INPUTS for st in STEPS]
    with ProcessPoolExecutor(max_workers=4) as ex:
        res = list(ex.map(_task, tasks))
    ref = np.array(res[0][2])
    out = {(k, st): (np.array(t), fe, md) for k, st, t, fe, md in res[1:]}
    rows = []
    for label, kind, key in INPUTS:
        row = {"label": label, "kind": kind, "key": key, "delta": {}, "feasible": {}, "m_decl_median": {}}
        for st in STEPS:
            t, fe, md = out[(key, st)]
            row["delta"][f"{st:+.1f}"] = float(np.mean(t - ref))           # paired, draw by draw
            row["feasible"][f"{st:+.1f}"] = fe
            row["m_decl_median"][f"{st:+.1f}"] = md
        rows.append(row)
    rows.sort(key=lambda r: -max(abs(r["delta"]["-0.1"]), abs(r["delta"]["+0.1"])))
    return {"ref_mean": float(ref.mean()), "ref_p10": float(np.percentile(ref, 10)), "ref_feasible": res[0][3],
            "ref_m_decl_median": res[0][4], "rows": rows}


def sweep(Ps, masses):
    out = []
    for m in masses:
        d = design(m_decl=m)
        cx = d.meta["complexity"]
        T0 = d.propulsion.static_thrust_n
        clm0 = d.meta["clmax_landing"]
        rec = {"m": m, "total": [], "M2": [], "M3": [], "GM": [], "feas": [], "p2": [], "p3": [], "exp": [],
               "vs2": [], "container_kg": d.meta["container_kg"], "ok_381": bool(d.meta["ok_381"])}
        for P in Ps:
            r = A.evaluate(d, P)
            if r is None:
                continue
            e = r["expected"]
            w = e["w"] if r["m2_feasible"] else d.unit
            g2, Q = SE._gross(d, P, w)
            g3, _ = SE._gross(d, P, r["m3_mass"])
            clm = clm0 * Q.clmax_factor.get(Q.family_fn[1], 1.0)
            vs2 = math.sqrt(2 * g2 * G0 / (SE.RHO_DESIGN * d.s * clm))
            vs3 = math.sqrt(2 * g3 * G0 / (SE.RHO_DESIGN * d.s * clm))
            p2 = fm.p_attempt({"v_stall": vs2, "tw_takeoff": T0 / (g2 * G0)}, cx, mission="M2") if r["m2_feasible"] else 0.0
            p3 = fm.p_attempt({"v_stall": vs3, "tw_takeoff": T0 / (g3 * G0)}, cx, mission="M3")
            P2 = FI._pc(fm, (p2,))
            P23 = FI._pc(fm, (p2, p3))
            rec["total"].append(e["total"]); rec["M2"].append(e["M2"]); rec["M3"].append(e["M3"])
            rec["GM"].append(e["GM"]); rec["feas"].append(bool(r["m2_feasible"])); rec["p2"].append(p2)
            rec["p3"].append(p3); rec["vs2"].append(vs2)
            rec["exp"].append((1.0 + e["M2"]) * P2 + e["M3"] * P23 + 0.9 * e["GM"])
        s = {"m": m, "container_kg": rec["container_kg"], "ok_381": rec["ok_381"], "n": len(rec["total"])}
        for k in ("total", "M2", "M3", "GM", "p2", "p3", "exp", "vs2"):
            a = np.array(rec[k], dtype=float)
            s[k] = float(a.mean()) if a.size else float("nan")
            s[k + "_p10"] = float(np.percentile(a, 10)) if a.size else float("nan")
        s["feas"] = float(np.mean(rec["feas"])) if rec["feas"] else 0.0
        out.append(s)
    return out


def main():
    t0 = time.time()
    Ps = A.draws()
    T = tornado()
    print(f"tornado ref mean {T['ref_mean']:.3f}  ({time.time() - t0:.0f} s)")
    for r in T["rows"]:
        print(f"  {r['label']:24s} {r['kind']:11s} " + "  ".join(f"{k}:{v:+.3f}" for k, v in r["delta"].items()))
    masses = [round(x, 2) for x in np.arange(2.0, 10.01, 0.5)]
    S = sweep(Ps, masses)
    print(f"sweep done ({time.time() - t0:.0f} s)")
    for s in S:
        print(f"  m {s['m']:4.1f}  total {s['total']:.3f}  exp {s['exp']:.3f}  M2 {s['M2']:.3f}  M3 {s['M3']:.3f}  "
              f"GM {s['GM']:.3f}  feas {s['feas']:.2f}  p2 {s['p2']:.3f}  p3 {s['p3']:.3f}  vs2 {s['vs2']:.2f}  "
              f"cont {s['container_kg']:.2f} ok381 {s['ok_381']}")
    out = {"generated": "proposal/tools/p1_sensitivity.py, 31 Oct 2026", "draws": len(Ps), "m_decl_ref": M_DECL,
           "tornado": T, "sweep": S}
    (PROP / "data" / "p1_sens.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
