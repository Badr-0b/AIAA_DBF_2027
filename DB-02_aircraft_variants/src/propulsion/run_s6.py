"""S6 study runs. Usage: PYTHONDONTWRITEBYTECODE=1 python run_s6.py <section> ...
Sections: gross, search, twin, m3, install, props, mc. Each writes JSON into W/out/propulsion/.
Reads REPO/analysis read-only; never calls an existing script's main()."""
import json
import math
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve()
W = HERE.parents[2]
sys.path.insert(0, str(W / "src"))
from propulsion import model as M      # noqa: E402

OUT = W / "out" / "propulsion"
OUT.mkdir(parents=True, exist_ok=True)
d = M.D()
np = d.np
sys.path.insert(0, str(M.ANALYSIS))


def dump(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=1, default=lambda o: float(o) if hasattr(o, "__float__") else str(o)),
                            encoding="utf-8", newline="\n")


def slim(r, keys=("feasible", "binding", "m2_clock_s", "v", "bank", "n", "t_lap_s", "d_turn_n", "p_turn_w", "p_mean_w",
                  "thrust_margin_end", "i_margin_end", "volt_margin_end", "power_margin_end", "e_m2_wh", "e_total_wh",
                  "frac_of_rated", "e_min_wh", "e_min_frac_rated", "v_stall_ms", "t_to_used_s", "usable_needed",
                  "e_m3_wh", "laps", "tw_static", "static_thrust_n", "turn_ok_end")):
    o = {k: r[k] for k in keys if k in r}
    if "takeoff" in r:
        o["roll_m"] = r["takeoff"].get("roll_m")
        o["roll_s"] = r["takeoff"].get("roll_s")
        o["to_total_s"] = r["takeoff"].get("to_total_s")
    return o


def max_gross(ps, S, aero, usable, lo=10.0, hi=24.9, **kw):
    """Largest M2 gross (kg) with a feasible 5-lap M2 inside `usable` x rated Wh (bisection, 0.05 kg)."""
    if not M.margins(ps, lo, S, aero, usable=usable, **kw)["feasible"]:
        return None
    for _ in range(9):
        mid = 0.5 * (lo + hi)
        if M.margins(ps, mid, S, aero, usable=usable, **kw)["feasible"]:
            lo = mid
        else:
            hi = mid
    return lo


def sec_gross():
    res = {}
    S_list = (1.0, 1.1, 1.3)
    names = ("8s", "8s_f80", "8s_mx", "12s", "13s", "twin")
    t0 = time.time()
    for S in S_list:
        aero = M.accepted_aero(S, "slotted")
        res[f"S{S}"] = {}
        for k in names:
            ps = M.system(k, "end")
            row = {"max_gross_kg": {}, "by_gross": {}}
            for u in (0.80, 0.85, 0.90):
                row["max_gross_kg"][f"{u:.2f}"] = max_gross(ps, S, aero, u)
            for g in (14, 15, 16, 17, 18, 19, 20):
                row["by_gross"][str(g)] = {f"{u:.2f}": slim(M.margins(ps, g, S, aero, usable=u)) for u in (0.80, 0.90)}
            res[f"S{S}"][k] = row
        print("gross", S, round(time.time() - t0), "s", flush=True)
    dump("gross_sweep.json", res)
    return res


def ref_from(m_best, mission="M2"):
    s1 = d.s1
    v, b = m_best["v"], m_best["bank"]
    r = s1.turn_radius(v, b, M.G0)
    turns = s1.TURN_ARC * r
    straight = s1.lap_length(r, s1.STRAIGHTS_M) - turns
    return {"v": v, "bank": b, "n": m_best["n"], "d1": m_best["d_straight_n"], "dn": m_best["d_turn_n"],
            "fs": straight / (straight + turns), "ft": turns / (straight + turns), "mass": m_best["m_gross_kg"]}


def sec_search():
    """Rank every motor x prop x pack at heavier M2 / M3 reference points (Script 3b screen)."""
    import prop_trade as pt
    motors, props, packs = pt.candidates()
    out = {}
    base = M.system("8s", "end")
    for S, g2, g3 in ((1.1, 16.0, 11.0), (1.1, 14.0, 10.0), (1.1, 17.0, 12.0)):
        aero = M.accepted_aero(S, "slotted")
        r2 = M.margins(base, g2, S, aero, usable=0.90)
        r3 = M.margins(base, g3, S, aero, mission="M3", n_laps_m3=6, usable=0.90)
        if not r2["feasible"] or not r3["feasible"]:
            out[f"S{S}_{g2}"] = {"skipped": True, "r2": slim(r2), "r3": slim(r3)}
            continue
        ref = {"M2": ref_from(r2), "M3": ref_from(r3)}
        rows = pt.screen(motors, props, packs, ref)
        ok = [r for r in rows if r["ok_end"] and r["prop"].D <= 22.5 * 0.0254]
        for r in ok:
            r["metric"] = (r["m2_w"] * 1.0) / r["pack"].energy_wh        # lap-mean battery W per rated Wh (smaller is better)
        ok.sort(key=lambda r: r["metric"])
        cell = {}
        for r in ok:
            cell.setdefault(r["pack"].cells, [])
            if len(cell[r["pack"].cells]) < 6:
                cell[r["pack"].cells].append(r)
        listing = {str(c): [{"motor": r["motor"].name, "prop": r["prop"].name, "pack": r["pack"].name, "m2_w": r["m2_w"],
                             "m3_w": r["m3_w"], "w_per_wh": r["metric"], "v_margin_end": r["v_margin_end"],
                             "i_margin_end": r["i_margin_end"], "D_in": r["prop"].D / 0.0254} for r in rs] for c, rs in cell.items()}
        out[f"S{S}_{g2}_{g3}"] = {"ref": ref, "n_ok_end": len(ok), "of": len(rows), "top_by_cells": listing}
        print("search", S, g2, g3, len(ok), "of", len(rows), flush=True)
    dump("search.json", out)
    return out


if __name__ == "__main__":
    for sec in sys.argv[1:]:
        globals()["sec_" + sec]()
