"""DB-02 finalist and regret analysis (orchestrator, 30 Oct 2026).

Re-scores the shortlist from screen.json under scenarios that attack Variant A's weak points:
  base         : as the screen.
  fowler_low   : Fowler landing CLmax at the bottom of its range (x0.917) and the Fowler mechanism
                 hazard doubled (per-attempt logit -0.2 extra), i.e. the tracks underdeliver.
  mass_up      : every airframe 15 % heavier than the fit (systematic growth bias).
  reliab_low   : every per-attempt success probability 0.08 lower (thin reliability data).
  combined     : fowler_low + mass_up.
Candidates come from W/out/integration/shortlist.json (integration/select.py). After scoring, the pre-registered
rule (brief section 9) is applied with PAIRED statistics: per-draw P(top) differences between candidates, cluster-
bootstrapped over the 120 draws (30 Oct 2026 review: the earlier Wilson intervals counted the 5,000 fields only).
Writes W/out/integration/finalists.json (summaries + "selection") and W/out/variants/selection.json.
Run: PYTHONDONTWRITEBYTECODE=1 python src/integration/finalists.py
"""
from __future__ import annotations

import copy
import json
import math
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
W = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(W / "src"))

import numpy as np                                    # noqa: E402
from integration import adapter as A                  # noqa: E402
from integration import search as SE                  # noqa: E402

G0 = 9.80665


def tag(s, flap, m_hi, prop):
    """Short candidate tag used in result IDs, e.g. S09F6 = 0.9 m2 Fowler, 3-6 kg, 8S; suffix T = twin, X = 12S."""
    return f"S{round(s * 10):02d}{flap[0].upper()}{m_hi:g}".replace(".", "p") + {"8s": "", "twin": "T", "12s": "X"}[prop]


def candidates():
    sl = json.loads((W / "out" / "integration" / "shortlist.json").read_text(encoding="utf-8"))["shortlist"]
    return [(tag(d["s"], d["flap"], d["m_hi"], d["prop"]), d["s"], d["flap"], d["m_hi"], d["prop"]) for d in sl]
SCEN = {
    "base": {},
    "fowler_low": {"fowler_clmax": 0.917, "fowler_logit": -0.2},
    "mass_up": {"mass": 1.15},
    "reliab_low": {"p_shift": -0.08},
    "combined": {"fowler_clmax": 0.917, "fowler_logit": -0.2, "mass": 1.15},
}


def _logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def run(args):
    cid, s, flap, m_hi, prop, mods, step = args
    from field import model as fm
    d0 = SE.make(s, flap, m_hi, prop)
    if flap == "fowler" and "fowler_clmax" in mods:
        a = dict(d0.aero)
        k = mods["fowler_clmax"]
        a["clmax_landing"] = a["clmax_landing"] * k
        d0 = d0.with_(aero=a, meta={**d0.meta, "clmax_landing": a["clmax_landing"]})
    Ps = A.draws()
    if "mass" in mods:
        Ps2 = []
        for P in Ps:
            Q = copy.copy(P)
            Q.af_factor = P.af_factor * mods["mass"]
            Ps2.append(Q)
        Ps = Ps2
    cm = d0.meta["container_kg"]
    grid = SE.m_grid(m_hi, step)
    designs = {m: d0.with_(unit=m + cm) for m in grid}
    rows = []
    for P in Ps:
        Pt = copy.copy(P)
        Pt.rho = SE.RHO_TECH
        best, best_v = grid[0], -1.0
        for m in grid:
            r = A.evaluate(designs[m], Pt)
            v = r["expected"]["total"] if r else -1.0
            if v > best_v + 1e-9:
                best, best_v = m, v
        r = A.evaluate(designs[best], P)
        e = r["expected"]
        w = e["w"] if r["m2_feasible"] else designs[best].unit
        g2, Q = SE._gross(designs[best], P, w)
        g3, _ = SE._gross(designs[best], P, r["m3_mass"])
        clm = d0.meta["clmax_landing"] * Q.clmax_factor.get(Q.family_fn[1], 1.0)
        vs2 = math.sqrt(2 * g2 * G0 / (SE.RHO_DESIGN * s * clm))
        vs3 = math.sqrt(2 * g3 * G0 / (SE.RHO_DESIGN * s * clm))
        T0 = d0.propulsion.static_thrust_n
        rows.append({"m_decl": best, "total": e["total"], "M2": e["M2"], "M3": e["M3"], "GM": e["GM"],
                     "agg_total": r["aggressive"]["total"], "feas": bool(r["m2_feasible"]), "w": e["w"],
                     "t2": e["t2"], "n_sim": e["n_sim"], "laps": r["laps"], "m3": r["m3_mass"],
                     "sensor_max": r["sensor_max"], "g2": g2, "g3": g3, "vs2": vs2, "vs3": vs3,
                     "tw2": T0 / (g2 * G0), "tw3": T0 / (g3 * G0)})
    cx = d0.meta["complexity"]
    pm2 = np.array([fm.p_attempt({"v_stall": r["vs2"], "tw_takeoff": r["tw2"]}, cx, mission="M2") for r in rows])
    pm3 = np.array([fm.p_attempt({"v_stall": r["vs3"], "tw_takeoff": r["tw3"]}, cx, mission="M3") for r in rows])
    if flap == "fowler" and "fowler_logit" in mods:
        pm2 = 1 / (1 + np.exp(-(_logit(pm2) + mods["fowler_logit"])))
        pm3 = 1 / (1 + np.exp(-(_logit(pm3) + mods["fowler_logit"])))
    if "p_shift" in mods:
        pm2 = np.clip(pm2 + mods["p_shift"], 0.01, 0.99)
        pm3 = np.clip(pm3 + mods["p_shift"], 0.01, 0.99)
    return {"cid": cid, "id": d0.id, "s": s, "flap": flap, "m_hi": m_hi, "prop": prop, "complexity": cx,
            "container_kg": cm, "container_dims": d0.meta["container_dims"], "ok_381": d0.meta["ok_381"],
            "clmax_landing": d0.meta["clmax_landing"], "rows": rows, "pm2": pm2.tolist(), "pm3": pm3.tolist()}


ATT = ((3, 0.3), (4, 0.4), (5, 0.3))     # S2 v0 attempt budget distribution (estimate)


def _pc(fm, probs):
    return sum(w * fm.p_complete(probs, a) for a, w in ATT)


def run2(args):
    """Reliability-aware policy (orchestrator, 30 Oct). At tech the declared mass maximises the EXPECTED
    total, (M1+M2) P(M2 done) + M3 P(M3 done) + GM p_gm, with per-attempt success from S2 p_attempt at the
    margins the declaration creates; per M3 attempt the ballast is chosen among lighter options to
    maximise p3 x M3. Mods as in run()."""
    cid, s, flap, m_hi, prop, mods, step = args
    from field import model as fm
    d0 = SE.make(s, flap, m_hi, prop, keep_cd0=bool(mods.get("cd0_buildup")))
    if flap == "fowler" and "fowler_clmax" in mods:
        a = dict(d0.aero)
        a["clmax_landing"] = a["clmax_landing"] * mods["fowler_clmax"]
        d0 = d0.with_(aero=a, meta={**d0.meta, "clmax_landing": a["clmax_landing"]})
    Ps = A.draws()
    if "mass" in mods:
        Ps = [copy.copy(P) for P in Ps]
        for P in Ps:
            P.af_factor = P.af_factor * mods["mass"]
    cm = d0.meta["container_kg"]
    grid = SE.m_grid(m_hi, step)
    designs = {m: d0.with_(unit=m + cm) for m in grid}
    cx = d0.meta["complexity"]
    T0 = d0.propulsion.static_thrust_n
    lg = mods.get("fowler_logit", 0.0) if flap == "fowler" else 0.0
    sh = mods.get("p_shift", 0.0)

    def padj(p):
        if lg:
            p = 1 / (1 + math.exp(-(math.log(p / (1 - p)) + lg)))
        return min(0.99, max(0.01, p + sh))

    def assess(P, m_list):
        """Evaluate each declaration in m_list under P; return per-m dict with M3 options folded in."""
        ev = {}
        for m in m_list:
            r = A.evaluate(designs[m], P)
            if r is None:
                continue
            e = r["expected"]
            w = e["w"] if r["m2_feasible"] else designs[m].unit
            g2, Q = SE._gross(designs[m], P, w)
            clm = d0.meta["clmax_landing"] * Q.clmax_factor.get(Q.family_fn[1], 1.0)
            vs2 = math.sqrt(2 * g2 * G0 / (SE.RHO_DESIGN * s * clm))
            g3, _ = SE._gross(designs[m], P, r["m3_mass"])
            vs3 = math.sqrt(2 * g3 * G0 / (SE.RHO_DESIGN * s * clm))
            p2 = padj(fm.p_attempt({"v_stall": vs2, "tw_takeoff": T0 / (g2 * G0)}, cx, mission="M2")) \
                if r["m2_feasible"] else 0.0
            p3 = padj(fm.p_attempt({"v_stall": vs3, "tw_takeoff": T0 / (g3 * G0)}, cx, mission="M3"))
            ev[m] = dict(r=r, e=e, w=w, g2=g2, g3=g3, vs2=vs2, vs3=vs3, p2=p2, p3=p3, clm=clm)
        return ev

    rows = []
    for P in Ps:
        Pt = copy.copy(P)
        Pt.rho = SE.RHO_TECH
        ev = assess(Pt, grid)
        best, best_v = None, -1.0
        for m, x in ev.items():
            # M3 ballast option: best p3*M3 among declarations <= m (their evaluate picks lighter ballast)
            opts = [(y["p3"] * y["e"]["M3"], y) for mm, y in ev.items() if mm <= m + 1e-9]
            p3x, y3 = max(opts, key=lambda t: t[0])
            P2 = _pc(fm, (x["p2"],))
            P3 = _pc(fm, (x["p2"], y3["p3"]))
            v = (1.0 + x["e"]["M2"]) * P2 + y3["e"]["M3"] * P3 + x["e"]["GM"] * 0.9
            if v > best_v:
                best, best_v = m, v
        evp = assess(P, [m for m in grid if m <= best + 1e-9])
        x = evp[best]
        y3 = max((y for y in evp.values()), key=lambda y: y["p3"] * y["e"]["M3"])
        rows.append({"m_decl": best, "total": x["e"]["M1"] + x["e"]["M2"] + y3["e"]["M3"] + x["e"]["GM"],
                     "M2": x["e"]["M2"], "M3": y3["e"]["M3"], "GM": x["e"]["GM"], "feas": bool(x["r"]["m2_feasible"]),
                     "w": x["e"]["w"], "t2": x["e"]["t2"], "n_sim": x["e"]["n_sim"], "laps": y3["r"]["laps"],
                     "m3": y3["r"]["m3_mass"], "sensor_max": x["r"]["sensor_max"], "g2": x["g2"], "g3": y3["g3"],
                     "vs2": x["vs2"], "vs3": y3["vs3"], "tw2": T0 / (x["g2"] * G0), "tw3": T0 / (y3["g3"] * G0),
                     "p2": x["p2"], "p3": y3["p3"]})
    pm2 = [r["p2"] for r in rows]
    pm3 = [r["p3"] for r in rows]
    return {"cid": cid, "id": d0.id, "s": s, "flap": flap, "m_hi": m_hi, "prop": prop, "complexity": cx,
            "container_kg": cm, "container_dims": d0.meta["container_dims"], "ok_381": d0.meta["ok_381"],
            "clmax_landing": d0.meta["clmax_landing"], "static_thrust_n": T0, "rows": rows, "pm2": pm2, "pm3": pm3}


def control_rows(mods, rivals):
    res = SE.control(rivals)
    pm2, pm3 = np.array(res["pm2"]), np.array(res["pm3"])
    if "p_shift" in mods:
        res["pm2"] = np.clip(pm2 + mods["p_shift"], 0.01, 0.99).tolist()
        res["pm3"] = np.clip(pm3 + mods["p_shift"], 0.01, 0.99).tolist()
    return res


def main(step=0.5):
    from concurrent.futures import ProcessPoolExecutor
    from field import model as fm
    out = SE.OUT
    out.mkdir(parents=True, exist_ok=True)
    rivals = fm.simulate(SE.N_FIELD, 2027)
    t0 = time.time()
    jobs = [(c[0], c[1], c[2], c[3], c[4], SCEN[sc], step, sc) for sc in SCEN for c in candidates()]
    res_all = {}
    with ProcessPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(run2, j[:7]): j for j in jobs}
        for f, j in futs.items():
            r = f.result()
            sc = j[7]
            fs = SE.field_stats(r, rivals)
            sm = SE.summarise(r, fs)
            sm["cid"] = r["cid"]
            sm["clmax_landing"] = r["clmax_landing"]
            res_all.setdefault(sc, {})[r["cid"]] = {"summary": sm, "rows": r["rows"], "pm2": r["pm2"], "pm3": r["pm3"]}
            print(f"{sc:11s} {r['cid']:6s} mean {sm['mean']:.3f} p10 {sm['p10']:.2f} pM3 {sm['p_m3_done']:.2f} "
                  f"P(top) {sm['p_mission_top']:.3f} P(1st) {sm['p_first']:.3f} [{time.time()-t0:.0f} s]", flush=True)
    for sc in SCEN:
        ctl = control_rows(SCEN[sc], rivals)
        sm = SE.summarise(ctl, SE.field_stats(ctl, rivals))
        sm["cid"] = "CTRL"
        res_all[sc]["CTRL"] = {"summary": sm}
    summ = {sc: {k: v["summary"] for k, v in d.items()} for sc, d in res_all.items()}
    summ["selection"] = select(summ)
    (out / "finalists.json").write_text(json.dumps(summ, indent=1), encoding="utf-8")
    (out / "finalists_rows.json").write_text(json.dumps(
        {sc: {k: {kk: v[kk] for kk in ("rows", "pm2", "pm3")} for k, v in d.items() if "rows" in v}
         for sc, d in res_all.items()}), encoding="utf-8")
    print("done", time.time() - t0)


# ------------------------------------------------------------------ the pre-registered rule, paired
N_BOOT = 4000
CX = {"plain": 0, "slotted": 1, "fowler": 2}


def complexity(s):
    return CX[s["flap"]] + (2 if s["prop"] == "twin" else 0)


def paired_ci(a, b, cnt, seed=7):
    """Mean and 95 % interval of P_a - P_b from per-draw P(top) arrays on the same draws and fields (cluster
    bootstrap over the draws)."""
    a, b, cnt = np.asarray(a), np.asarray(b), np.asarray(cnt)
    d = a - b
    rng = np.random.default_rng(seed)
    k = rng.integers(0, len(d), size=(N_BOOT, len(d)))
    est = (d[k] * cnt[k]).sum(axis=1) / cnt[k].sum(axis=1)
    return float((d * cnt).sum() / cnt.sum()), [float(np.percentile(est, 2.5)), float(np.percentile(est, 97.5))]


def select(F):
    base = {k: v for k, v in F["base"].items() if k != "CTRL"}
    ctrl = F["base"]["CTRL"]
    cnt = next(iter(base.values()))["field_count_by_draw"]
    best_m3 = max(s["p_m3_done"] for s in base.values())
    gate = {k: {"complete": s["p_m3_done"] >= 0.90 * best_m3, "p10": s["p10"] >= ctrl["p10"] - 1e-9}
            for k, s in base.items()}
    gated = [k for k in base if all(gate[k].values())]
    lead = max(gated, key=lambda k: base[k]["p_mission_top"])
    vs_lead = {k: paired_ci(base[lead]["top_by_draw"], base[k]["top_by_draw"], cnt) for k in gated}
    tied = [k for k in gated if k == lead or vs_lead[k][1][0] <= 0.0]
    A = min(tied, key=lambda k: (complexity(base[k]), -base[k]["p_mission_top"]))
    scen = [sc for sc in F if sc not in ("selection",)]
    reg = {}
    for sc in scen:
        cs = {k: v for k, v in F[sc].items() if k != "CTRL"}
        best = max(cs, key=lambda k: cs[k]["p_mission_top"])
        for k in cs:
            m, ci = paired_ci(cs[best]["top_by_draw"], cs[k]["top_by_draw"], cnt)
            reg.setdefault(k, {})[sc] = {"regret": m, "ci95": ci, "leader": best}
    worst = sorted(scen, key=lambda sc: -reg[A][sc]["regret"])[:2]
    a_loses = [sc for sc in scen if reg[A][sc]["regret"] > 1e-12]

    def cover(k):
        return max(reg[k][sc]["regret"] for sc in worst)

    others = [k for k in base if k != A]
    frozen = [k for k in others if (base[k]["prop"] == "twin") != (base[A]["prop"] == "twin")]
    B_strict = min(frozen, key=cover) if frozen else None
    same_prop = [k for k in others if base[k]["prop"] == base[A]["prop"] and
                 (base[k]["s"], base[k]["flap"]) != (base[A]["s"], base[A]["flap"])]
    B_wing = min(same_prop, key=lambda k: (round(cover(k), 4), complexity(base[k]), -base[k]["p_mission_top"]))
    strict_covers = B_strict is not None and cover(B_strict) < max(reg[A][sc]["regret"] for sc in worst) - 1e-12
    B = B_strict if strict_covers else B_wing
    a_beats_b_everywhere = all(F[sc][A]["p_mission_top"] >= F[sc][B]["p_mission_top"] for sc in scen)
    ab = {sc: paired_ci(F[sc][A]["top_by_draw"], F[sc][B]["top_by_draw"], cnt) for sc in scen}
    sel = {"gate_complete_need": 0.90 * best_m3, "gate_p10_need": ctrl["p10"], "gates": gate, "gated": gated,
           "leader": lead, "vs_leader": vs_lead, "tied_with_leader": tied, "A": A,
           "A_worst_scenarios": worst, "A_loses_in": a_loses, "regret": reg,
           "B_strict_frozen_item": B_strict, "B_strict_covers": strict_covers, "B_wing_alternative": B_wing, "B": B,
           "A_beats_B_everywhere": a_beats_b_everywhere, "A_minus_B": ab}
    spec = {}
    for role, k in (("A", A), ("B", B)):
        s = base[k]
        spec[role] = {"cid": k, "S": s["s"], "flap": s["flap"], "m_hi": s["m_hi"], "prop": s["prop"],
                      "container_kg": s["container_kg"]}
    (W / "out" / "variants").mkdir(parents=True, exist_ok=True)
    (W / "out" / "variants" / "selection.json").write_text(json.dumps(spec, indent=1), encoding="utf-8")
    print("SELECTION: leader", lead, "tied", tied, "-> A", A, "| A worst", worst, "| B strict", B_strict,
          "covers" if strict_covers else "does not cover", "| B wing", B_wing, "-> B", B, flush=True)
    return sel


def cd0_upside():
    """Card C-02: mean-total change for the selected A and B if S3's drag build-up proved right in flight."""
    from field import model as fm
    F = json.loads((W / "out/integration/finalists.json").read_text(encoding="utf-8"))
    rivals = fm.simulate(SE.N_FIELD, 2027)
    out = {}
    for role in ("A", "B"):
        s = F["base"][F["selection"][role]]
        r = run2((role, s["s"], s["flap"], s["m_hi"], s["prop"], {"cd0_buildup": True}, 0.5))
        sm = SE.summarise(r, SE.field_stats(r, rivals))
        out[role] = {"mean": sm["mean"], "p_mission_top": sm["p_mission_top"], "d_mean": sm["mean"] - s["mean"],
                     "d_p_top": sm["p_mission_top"] - s["p_mission_top"]}
        print(role, {k: round(v, 3) for k, v in out[role].items()}, flush=True)
    (W / "out/integration/cd0_upside.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "cd0":
        cd0_upside()
    elif len(sys.argv) > 1 and sys.argv[1] == "select":
        F = json.loads((W / "out/integration/finalists.json").read_text(encoding="utf-8"))
        F.pop("selection", None)
        F["selection"] = select(F)
        (W / "out/integration/finalists.json").write_text(json.dumps(F, indent=1), encoding="utf-8")
    else:
        main()
