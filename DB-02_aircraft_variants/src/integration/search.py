"""DB-02 integrated design search (orchestrator, 29 Oct 2026).

Design = wing area x flap type x declared-sensor range (one physical container built for the top of the
range) x propulsion system x gear.  Per DB-01 draw (120, seed 2027):
  1. TECH: choose the declared sensor mass in [M_LO, m_hi] from what is known at tech (the draw's airframe,
     CLmax, eta, container, lap factor; the day's density is NOT known: planned at the hot-day 1.04).
  2. FLY: score that declaration under the draw's own inputs (adapter.evaluate = s6.evaluate).
  3. RELIABILITY: per-attempt success from S2 p_attempt(margins, complexity), margins from the draw.
  4. FIELD: pair our draws with S2 simulated fields (5,000) -> P(highest mission total), P(1st), rank.
Aero: S3 aero(geom) for e and CLmax (trimmed); CD0 stays at DB-01 (0.0086 + 0.013/S; orchestrator override,
ledger 05). Payload: S8 container (150 g sensor, tungsten, savox drum) sized at m_hi.
Writes only to W/out/integration/.  Run:  python src/integration/search.py [screen|finalists]
"""
from __future__ import annotations

import copy
import itertools
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.dont_write_bytecode = True
W = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(W / "src"))

import numpy as np                                    # noqa: E402
from integration import adapter as A                  # noqa: E402

OUT = W / "out" / "integration"
G0 = 9.80665
RHO_TECH = 1.04             # plan the declaration for a hot day (S8 memo: planning at 1.075 drops P10 to 2.5)
RHO_DESIGN = 1.064          # \nRho, for stall margins
M_LO = 3.0
H_DROP = 1.524
N_FIELD = 5000
REPORT = 90.0               # assumed Total Report Score for P(1st overall); the selection uses P(mission top)


# ------------------------------------------------------------------ design construction
# Flap definitions exactly as S3 quotes them (aero_mono/run_results.py FL, S3-R12..R14). Until 30 Oct the screen passed
# only the type, so the model default (25 % chord, 30 deg) was scored while the spec and the S3 numbers were 30 % chord.
FL = {"plain": dict(type="plain", span_frac=0.6, chord_frac=0.25, defl_land_deg=30.0),
      "slotted": dict(type="slotted", span_frac=0.6, chord_frac=0.30, defl_land_deg=30.0),
      "fowler": dict(type="fowler", span_frac=0.6, chord_frac=0.30, defl_land_deg=35.0)}
TRIM_GEO = W / "out" / "variants" / "trim_geometry.json"


def trim_geo(s, flap):
    """Real tail arm and CG (mean chords) of the laid-out aircraft: geometry_variants.py trim (30 Oct 2026)."""
    tab = json.loads(TRIM_GEO.read_text(encoding="utf-8"))
    k = f"{s:.2f}|{flap}"
    if k not in tab:
        raise KeyError(f"{k} not in {TRIM_GEO}; run: python src/variants/geometry_variants.py trim")
    return {"lt_c": tab[k]["lt_c"], "h": tab[k]["h"]}


def mass_for(s, flap):
    """Family airframe mass (variants/mass_family.py): only the wing and tail scale with S. The fit's scatter is kept.
    Larger wings keep a 1.89-chord tail arm, so the boom lengthening's mass (trim_geometry.json) is added."""
    from variants import mass_family as MF
    tab = json.loads(TRIM_GEO.read_text(encoding="utf-8"))
    return {"airframe": {"median": MF.airframe(s)}, "extra_kg": tab[f"{s:.2f}|{flap}"]["boom_kg"]}


def aero_for(s, flap, keep_cd0=False):
    """S3 aero at the laid-out geometry. keep_cd0=True keeps S3's drag build-up (the upside sensitivity of card C-02)."""
    from aero_mono import model as AM
    a = AM.aero({"S": s, "flap": FL[flap], "trim": trim_geo(s, flap)})
    a = dict(a)
    if keep_cd0:
        return a
    a.pop("cd0_parts", None)               # CD0 override: keep DB-01 drag (ledger 05)
    a.pop("cd0", None)
    rg = dict(a.get("ranges", {}))
    rg.pop("f_body_m2", None)
    a["ranges"] = rg
    return a


def payload_for(m_hi, drive="savox_2290"):
    from payload import model as PM
    pl = PM.payload_for_adapter(m_hi, 150.0, drive, ballast="tungsten", as_function=False)
    meta = pl.pop("_meta")
    cm = meta["container_kg_at_max"]
    pl["container_kg"] = cm                # ONE container, built for m_hi, serves every declaration
    pl["container_range_kg"] = [0.85 * cm, 1.15 * cm]
    return pl, cm, meta


def make(s, flap, m_hi, prop, gear="fixed_tricycle", keep_cd0=False):
    a = aero_for(s, flap, keep_cd0)
    pl, cm, meta = payload_for(m_hi)
    cx = "simple" + {"plain": "", "slotted": "+slotted_flap", "fowler": "+fowler"}[flap] + \
         ("+twin" if prop == "twin" else "")
    d = A.Design(id=f"S{s:.1f}|{flap}|m{m_hi:g}|{prop}", s=s, unit=m_hi + cm, aero=a, payload=pl, mass=mass_for(s, flap),
                 propulsion=A.prop_bundle(prop),
                 meta={"flap": flap, "m_hi": m_hi, "prop": prop, "gear": gear, "complexity": cx,
                       "container_kg": cm, "container_dims": meta["container"], "ok_381": meta["ok_381"],
                       "clmax_landing": a["clmax_landing"]})
    return d


def m_grid(m_hi, step):
    g = list(np.arange(M_LO, m_hi + 1e-9, step))
    if abs(g[-1] - m_hi) > 1e-6:
        g.append(m_hi)
    return [round(x, 3) for x in g]


# ------------------------------------------------------------------ per-design evaluation
def _gross(d, P, w_payload):
    Q = A.apply(d, P)
    return Q.empty(d.s) + Q.battery() + w_payload, Q


def run_design(args):
    s, flap, m_hi, prop, step = args
    from field import model as fm
    d0 = make(s, flap, m_hi, prop)
    Ps = A.draws()
    cm = d0.meta["container_kg"]
    grid = m_grid(m_hi, step)
    designs = {m: d0.with_(unit=m + cm) for m in grid}
    rows = []
    for P in Ps:
        Pt = copy.copy(P)
        Pt.rho = RHO_TECH
        best, best_v = grid[0], -1.0
        for m in grid:
            r = A.evaluate(designs[m], Pt)
            v = r["expected"]["total"] if r else -1.0
            if v > best_v + 1e-9:
                best, best_v = m, v
        r = A.evaluate(designs[best], P)
        e = r["expected"]
        w = e["w"] if r["m2_feasible"] else (designs[best].unit)
        g2, Q = _gross(designs[best], P, w)
        g3, _ = _gross(designs[best], P, r["m3_mass"])
        clm = d0.meta["clmax_landing"] * Q.clmax_factor.get(Q.family_fn[1], 1.0)
        vs2 = math.sqrt(2 * g2 * G0 / (RHO_DESIGN * s * clm))
        vs3 = math.sqrt(2 * g3 * G0 / (RHO_DESIGN * s * clm))
        T0 = d0.propulsion.static_thrust_n
        rows.append({"m_decl": best, "total": e["total"], "M2": e["M2"], "M3": e["M3"], "GM": e["GM"],
                     "agg_total": r["aggressive"]["total"], "feas": bool(r["m2_feasible"]),
                     "w": e["w"], "t2": e["t2"], "n_sim": e["n_sim"], "laps": r["laps"], "m3": r["m3_mass"],
                     "sensor_max": r["sensor_max"], "g2": g2, "g3": g3, "vs2": vs2, "vs3": vs3,
                     "tw2": T0 / (g2 * G0), "tw3": T0 / (g3 * G0)})
    cx = d0.meta["complexity"]
    pm2 = np.array([fm.p_attempt({"v_stall": r["vs2"], "tw_takeoff": r["tw2"]}, cx, mission="M2") for r in rows])
    pm3 = np.array([fm.p_attempt({"v_stall": r["vs3"], "tw_takeoff": r["tw3"]}, cx, mission="M3") for r in rows])
    out = {"id": d0.id, "s": s, "flap": flap, "m_hi": m_hi, "prop": prop, "complexity": cx,
           "container_kg": cm, "container_dims": d0.meta["container_dims"], "ok_381": d0.meta["ok_381"],
           "clmax_landing": d0.meta["clmax_landing"], "rows": rows,
           "pm2": pm2.tolist(), "pm3": pm3.tolist()}
    return out


N_BOOT = 2000


def by_draw(x, idx, n_draws):
    """Per-draw mean of a per-field array (field i is paired with our draw i % n_draws) and the field counts."""
    cnt = np.bincount(idx, minlength=n_draws).astype(float)
    return np.bincount(idx, weights=np.asarray(x, dtype=float), minlength=n_draws) / cnt, cnt


def cluster_ci(means, cnt, n_boot=N_BOOT, seed=2027):
    """95 % interval of a field-averaged probability that resamples OUR draws (with their fields) as well as the
    fields: a cluster bootstrap over the draws. The Wilson interval over 5,000 fields alone ignores that only
    len(means) distinct aircraft draws exist (review of 30 Oct 2026)."""
    rng = np.random.default_rng(seed)
    k = rng.integers(0, len(means), size=(n_boot, len(means)))
    est = (means[k] * cnt[k]).sum(axis=1) / cnt[k].sum(axis=1)
    return [float(np.percentile(est, 2.5)), float(np.percentile(est, 97.5))]


def field_stats(res, rivals, seed=11):
    """Pair our draws with the simulated fields; completion sampled from per-attempt probabilities."""
    from field import model as fm
    n = rivals.n
    rows = res["rows"]
    idx = np.arange(n) % len(rows)
    feas = np.array([r["feas"] for r in rows])[idx]
    rng = np.random.default_rng(seed)
    pm2 = np.array(res["pm2"])[idx] * feas
    pm3 = np.array(res["pm3"])[idx]
    comp = fm.sample_completion(pm2, pm3, rng, n)
    m2wt = np.array([r["w"] / r["t2"] if r["feas"] and r["t2"] > 0 else 0.0 for r in rows])[idx]
    m3 = np.array([r["laps"] * r["m3"] for r in rows])[idx]
    gm = np.array([r["sensor_max"] * H_DROP for r in rows])[idx]
    our = {"m2_wt": m2wt, "m3_lxs": m3, "gm_wh": gm, "done_m1": comp["done_m1"], "done_m2": comp["done_m2"] & (feas > 0),
           "done_m3": comp["done_m3"] & (feas > 0), "done_gm": comp["done_gm"]}
    pf = fm.p_first(our, rivals, REPORT)
    top_d, cnt = by_draw(pf["top"], idx, len(rows))
    first_d, _ = by_draw(pf["rank"] == 1, idx, len(rows))
    return {"p_mission_top": pf["p_mission_top"], "p_mission_top_ci95": cluster_ci(top_d, cnt),
            "p_mission_top_ci95_fields": pf["p_mission_top_ci95"],
            "p_first": pf["p_first"], "p_first_ci95": cluster_ci(first_d, cnt),
            "p_first_ci95_fields": pf["p_first_ci95"], "top_by_draw": top_d.tolist(),
            "first_by_draw": first_d.tolist(), "field_count_by_draw": cnt.tolist(), "rank_mean": pf["rank_mean"],
            "rank_p50": pf.get("rank_p50"), "p_m2_done": float(np.mean(our["done_m2"])),
            "p_m3_done": float(np.mean(our["done_m3"])),
            "our_total_mean": float(np.mean(pf["our_total"]))}


def summarise(res, fs):
    rows = res["rows"]
    tot = np.array([r["total"] for r in rows])
    m = np.array([r["m_decl"] for r in rows])
    return {"id": res["id"], "s": res["s"], "flap": res["flap"], "m_hi": res["m_hi"], "prop": res["prop"],
            "complexity": res["complexity"], "container_kg": res["container_kg"], "ok_381": res["ok_381"],
            "mean": float(tot.mean()), "p10": float(np.percentile(tot, 10)),
            "p_feas": float(np.mean([r["feas"] for r in rows])),
            "m_decl_mean": float(m.mean()), "m_decl_p10": float(np.percentile(m, 10)),
            "m_decl_p90": float(np.percentile(m, 90)),
            "M2": float(np.mean([r["M2"] for r in rows])), "M3": float(np.mean([r["M3"] for r in rows])),
            "GM": float(np.mean([r["GM"] for r in rows])),
            "vs2": float(np.median([r["vs2"] for r in rows])), "g2": float(np.median([r["g2"] for r in rows])),
            "pm2": float(np.mean(res["pm2"])), "pm3": float(np.mean(res["pm3"])), **fs}


def control(rivals):
    """DB-01 control: REF-D01 as DB-01 assumed it (plain flap 1.6, frozen 4 kg unit, lumped propulsion)."""
    from field import model as fm
    Ps = A.draws()
    rs = [A.evaluate(A.REF_D01, P) for P in Ps]
    rows = []
    for P, r in zip(Ps, rs):
        e = r["expected"]
        w = e["w"] if r["m2_feasible"] else A.REF_D01.unit
        g2, Q = _gross(A.REF_D01, P, w)
        g3, _ = _gross(A.REF_D01, P, r["m3_mass"])
        vs2 = math.sqrt(2 * g2 * G0 / (RHO_DESIGN * 0.9 * 1.44))     # S3 trimmed plain-flap CLmax, honest
        vs3 = math.sqrt(2 * g3 * G0 / (RHO_DESIGN * 0.9 * 1.44))
        rows.append({"m_decl": 3.4, "total": e["total"], "M2": e["M2"], "M3": e["M3"], "GM": e["GM"],
                     "agg_total": r["aggressive"]["total"], "feas": bool(r["m2_feasible"]), "w": e["w"],
                     "t2": e["t2"], "n_sim": e["n_sim"], "laps": r["laps"], "m3": r["m3_mass"],
                     "sensor_max": r["sensor_max"], "g2": g2, "g3": g3, "vs2": vs2, "vs3": vs3,
                     "tw2": 0.7, "tw3": 1.0})
    pm2 = [fm.p_attempt({"v_stall": r["vs2"], "tw_takeoff": 0.7}, "simple", mission="M2") for r in rows]
    pm3 = [fm.p_attempt({"v_stall": r["vs3"], "tw_takeoff": 1.0}, "simple", mission="M3") for r in rows]
    res = {"id": "CONTROL DB-01", "s": 0.9, "flap": "plain(1.6)", "m_hi": 3.4, "prop": "lumped",
           "complexity": "simple", "container_kg": 0.6, "ok_381": None, "clmax_landing": 1.6,
           "rows": rows, "pm2": pm2, "pm3": pm3}
    return res


def screen(step=1.0, workers=3):
    from field import model as fm
    OUT.mkdir(parents=True, exist_ok=True)
    S = [0.8, 0.9, 1.0, 1.1, 1.2, 1.3]
    flaps = ["plain", "slotted", "fowler"]
    ranges = [4.4, 6.0, 8.0]
    props = ["8s", "12s", "twin"]
    jobs = [(s, f, m, p, step) for s, f, m, p in itertools.product(S, flaps, ranges, props)]
    t0 = time.time()
    rivals = fm.simulate(N_FIELD, 2027)
    ctl = control(rivals)
    summ = [summarise(ctl, field_stats(ctl, rivals))]
    print(f"control: mean {summ[0]['mean']:.3f} p10 {summ[0]['p10']:.3f} P(top) {summ[0]['p_mission_top']:.3f}",
          flush=True)
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for k, res in enumerate(ex.map(run_design, jobs)):
            fs = field_stats(res, rivals)
            sm = summarise(res, fs)
            summ.append(sm)
            print(f"{k+1:3d}/{len(jobs)} {sm['id']:28s} mean {sm['mean']:.3f} p10 {sm['p10']:.3f} "
                  f"feas {sm['p_feas']:.2f} m {sm['m_decl_mean']:.1f} pm2 {sm['pm2']:.2f} pm3 {sm['pm3']:.2f} "
                  f"P(top) {sm['p_mission_top']:.3f} P(1st) {sm['p_first']:.3f} [{time.time()-t0:.0f} s]",
                  flush=True)
            (OUT / "screen_rows").mkdir(exist_ok=True)
            (OUT / "screen_rows" / (sm["id"].replace("|", "_") + ".json")).write_text(
                json.dumps(res), encoding="utf-8")
    (OUT / "screen.json").write_text(json.dumps(summ, indent=1), encoding="utf-8")
    print(f"done in {time.time()-t0:.0f} s -> {OUT/'screen.json'}")
    return summ


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "screen"
    if mode == "screen":
        screen()
