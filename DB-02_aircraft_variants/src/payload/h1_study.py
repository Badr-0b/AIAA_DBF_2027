"""H1 study v2: value of declaring the sensor mass at tech with ONE physical container built before tech.

One sensor body, one container and one set of simulators are frozen at design time for a range [m_lo, m_hi] of declared
masses (payload.model.design_for_range). The declared mass is then chosen at tech on a 0.25 kg grid using only what
tech reveals (airframe mass, CLmax, eta, f_body, container mass, lap factor; NOT the day's density) against freezing one
declared mass at design time on the same hardware. Writes only to W/out/payload/. Import-safe.

Known bias (inherited from s6.evaluate through the adapter): the simulators flown and the M3 ballast are picked per
draw with full knowledge of that draw. The integration agent removes this in phase 1b.
"""
from __future__ import annotations

import copy
import json
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
W = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(W / "src"))

import numpy as np                                    # noqa: E402
from integration import adapter as A                  # noqa: E402
from payload import model as M                        # noqa: E402

RHO_TECH = 1.075                                      # tech knows the density distribution, not the day's value


def hw_design(c, s, m_decl, drive, base=None):
    """Adapter Design for declared sensor m_decl on the one built container c (mass fixed by the hardware)."""
    base = base or A.REF_D01
    cm = c["mass_for"](m_decl)
    pl = {"container_kg": cm, "container_range_kg": [0.75 * cm, 1.25 * cm],
          "dr": {"mass_kg": M.dr(c["m_hi"], drive)["mass_kg"], "stow_s": M.stow_fn_factory(c["m_hi"], drive)},
          "extra_kg": 0.0, "f_m2": 0.0}
    return base.with_(id=f"S{s}-m{m_decl}", s=s, unit=m_decl + cm, payload=pl)


def stats(rs, sc="expected"):
    ok = [r for r in rs if r]
    parts = np.mean([[r[sc]["M2"], r[sc]["M3"], r[sc]["GM"], r[sc]["total"]] for r in ok], axis=0)
    return {"M2": float(parts[0]), "M3": float(parts[1]), "GM": float(parts[2]), "total": float(parts[3]),
            "p_m2": float(np.mean([r["m2_feasible"] for r in ok])), "n_sim_mean": float(np.mean([r[sc]["n_sim"] for r in ok])),
            "laps_mean": float(np.mean([r["laps"] for r in ok])), "m3_mass_mean": float(np.mean([r["m3_mass"] for r in ok]))}


def run(m_lo, m_hi, recut, drive, s_list=(0.9, 1.0, 1.1), draws_n=120, sling=15.0, out=None):
    Ps = A.draws(draws_n)
    c = M.design_for_range(m_lo, m_hi, recut=recut, sling_deg=sling)
    grid = c["servable"]
    res = {"range": [m_lo, m_hi], "recut": recut, "drive": drive, "sling_deg": sling, "rho_tech": RHO_TECH, "draws": draws_n,
           "container": {"dims_m": c["dims_m"], "mass_kg": c["mass_kg"], "foam_mm": c["foam_mm"], "ok_381": c["ok_381"],
                         "worst_rtb_m": c["ring_to_bottom_m"]["worst"], "g_margin": c["g_margin"],
                         "mass_at_lo": c["mass_for"](m_lo), "mass_at_hi": c["mass_for"](m_hi)},
           "grid": grid, "rows": {}}
    t0 = time.time()
    for s in s_list:
        tot, rsall = {}, {}
        for m in grid:
            d = hw_design(c, s, m, drive)
            rs = [A.evaluate(d, P) for P in Ps]
            rsall[m] = rs
            tot[m] = np.array([r["expected"]["total"] if r else 0.0 for r in rs])
        frozen_m = max(grid, key=lambda m: tot[m].mean())
        pick = []
        for i, P in enumerate(Ps):
            Q = copy.copy(P)
            Q.rho = RHO_TECH
            v = [(A.evaluate(hw_design(c, s, m, drive), Q) or {"expected": {"total": 0.0}})["expected"]["total"] for m in grid]
            pick.append(grid[int(np.argmax(v))])
        real = np.array([tot[m][i] for i, m in enumerate(pick)])
        oracle = np.max(np.array([tot[m] for m in grid]), axis=0)
        tech_rs = [rsall[m][i] for i, m in enumerate(pick)]
        counts = {}
        for m in pick:
            counts[str(m)] = counts.get(str(m), 0) + 1
        res["rows"][f"S{s}"] = {
            "frozen_m": frozen_m, "frozen": stats(rsall[frozen_m]), "frozen_p10": float(np.percentile(tot[frozen_m], 10)),
            "tech": stats(tech_rs), "tech_p10": float(np.percentile(real, 10)), "oracle_mean": float(oracle.mean()),
            "tech_pick_counts": counts, "tech_pick_mean_kg": float(np.mean(pick)),
            "mean_by_m": {str(m): float(tot[m].mean()) for m in grid[::2]}}
        r = res["rows"][f"S{s}"]
        print(drive, [m_lo, m_hi], "recut" if recut else "built", f"S{s}", "frozen", frozen_m, round(r["frozen"]["total"], 3),
              "tech", round(r["tech"]["total"], 3), "oracle", round(r["oracle_mean"], 3), "pick", round(r["tech_pick_mean_kg"], 2),
              round(time.time() - t0), "s", flush=True)
    res["ref_d01_mean"] = A.robust(A.REF_D01, Ps)["mean"]
    if out:
        Path(out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


if __name__ == "__main__":
    lo, hi, rc, drive, tag = float(sys.argv[1]), float(sys.argv[2]), sys.argv[3] == "recut", sys.argv[4], sys.argv[5]
    sling = float(sys.argv[6]) if len(sys.argv) > 6 else 15.0
    if len(sys.argv) > 7:
        RHO_TECH = float(sys.argv[7])      # conservative planning density at tech (hot afternoon)
    run(lo, hi, rc, drive, sling=sling, out=W / "out" / "payload" / f"h1_{tag}.json")
