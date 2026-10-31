"""Proposal P1: Variant A mission detail at baseline inputs and over the 120 DB-02 draws.

Mirrors analysis/s4_sizing.m2_fixed / m3_search (same grids, constraints and flown time base)
but returns the operating point (speed, bank, load factor, lap time, energy) the proposal quotes.
Design: DB-02 search.make(1.0, "fowler", 8, "8s") = Variant A, rev B (30 Oct 2026).
Imports DB-02 and analysis code read-only; writes nothing outside proposal/data/.
Run: PYTHONDONTWRITEBYTECODE=1 python proposal/tools/p1_nominal.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PROP = HERE.parent
REPO = PROP.parent
DB02 = REPO / "DB-02_aircraft_variants"
sys.path.insert(0, str(DB02 / "src"))

import numpy as np                                    # noqa: E402
from integration import adapter as A                  # noqa: E402
from integration import search as SE                  # noqa: E402

s3, s4, s6 = A.s3, A.s4, A.s6
G0 = A.G0
RULES = A.RULES


def variant(key):
    return {"A": SE.make(1.0, "fowler", 8.0, "8s"), "B": SE.make(1.2, "slotted", 6.0, "8s")}[key]


def m2_detail(d, P, payload):
    """Fastest feasible five-lap M2 carrying `payload` kg, with its operating point."""
    Q = A.apply(d, P)
    with A.st_patch(d.ops), A._thrust(Q):
        _, v, bank = s4.grids(True)
        ar, e, clf, clc = s4.family(d.family, d.s, Q)
        k = s3.induced_factor(ar, e * Q.e_factor)
        cd0 = Q.cd_w + Q.f_body / d.s
        m = Q.empty(d.s) + Q.battery() + payload
        V, B = v[:, None], bank[None, :]
        res = s3.mission(Q.rho, V, B, d.s, cd0, k, m, RULES["missions"]["m2_laps"], Q.eta, Q.t_to, G0)
        p_mean, p_peak, ok_p = s4.battery_power(Q, V, B, d.s, cd0, k, m)
        e_wh = p_mean * res["t"] / 3600.0 * Q.time_cal
        vs = s3.stall_speed(Q.rho, d.s, m, clf, G0)
        ok = ((m < RULES["aircraft"]["togw_max_kg"]) & (vs <= Q.vs_max) & (res["cl_turn"] <= Q.cl_margin * clc)
              & (res["n"] <= Q.n_struct) & ok_p & (e_wh <= Q.e_usable))
        t = np.where(ok, np.broadcast_to(res["t"], ok.shape) * Q.time_cal, np.inf)
        i, j = np.unravel_index(int(np.argmin(t)), t.shape)
        pick = lambda a: float(np.broadcast_to(a, t.shape)[i, j])
        return {"t5": float(t[i, j]), "v": float(v[i]), "bank": float(bank[j]), "n": pick(res["n"]),
                "t_lap": pick(res["t_lap"]) * Q.time_cal, "e_wh": pick(e_wh), "e_usable": float(Q.e_usable),
                "gross": float(m), "v_stall": float(vs), "cl_turn": pick(res["cl_turn"]), "clmax_land": float(clf),
                "cd0": float(cd0), "e": float(e), "ar": float(ar), "t_to": float(Q.t_to), "time_cal": float(Q.time_cal)}


def m3_detail(d, P, m_sensor):
    """Most whole M3 laps towing m_sensor (stow inside the window), with the operating point."""
    Q = A.apply(d, P)
    with A.st_patch(d.ops), A._thrust(Q):
        _, v, bank = s4.grids(True)
        ar, e, clf, clc = s4.family(d.family, d.s, Q)
        k = s3.induced_factor(ar, e * Q.e_factor)
        cd0 = Q.cd_w + (Q.f_body + Q.f_tow) / d.s
        m = Q.empty(d.s) + Q.battery() + m_sensor
        V, B = v[:, None], bank[None, :]
        t_lap, p_mean, n, cl = s3.lap(Q.rho, V, B, d.s, cd0, k, m, G0)
        t_lap = t_lap * Q.time_cal
        stow = float(s4.stow_time(m_sensor, Q)) + s6.ST["design"]["t_stow_extra_s"]
        window = RULES["missions"]["window_s"]
        t_first = Q.t_to + t_lap
        laps = np.where(t_first > window - stow + 1e-9, 0, 1 + np.floor((window - stow - t_first) / t_lap + 1e-9))
        p_batt, _, ok_p = s4.battery_power(Q, V, B, d.s, cd0, k, m)
        e_wh = p_batt * window / 3600.0
        ok = ((s3.stall_speed(Q.rho, d.s, m, clf, G0) <= Q.vs_max) & (cl <= Q.cl_margin * clc) & (n <= Q.n_struct)
              & ok_p & (e_wh <= Q.e_usable))
        L = np.where(ok, laps, -1)
        best = L.max()
        # among the max-lap points, the one with the most slack (shortest lap)
        tl = np.where(L == best, np.broadcast_to(t_lap, L.shape), np.inf)
        i, j = np.unravel_index(int(np.argmin(tl)), tl.shape)
        pick = lambda a: float(np.broadcast_to(a, L.shape)[i, j])
        return {"laps": int(best), "v": float(v[i]), "bank": float(bank[j]), "n": pick(n), "t_lap": pick(t_lap),
                "stow": stow, "e_wh": pick(e_wh), "gross": float(m), "t_to": float(Q.t_to)}


def main():
    out = {}
    for key in ("A", "B"):
        d = variant(key)
        cm = d.meta["container_kg"]
        P = A.base_params()
        rows = json.loads((DB02 / "out/integration/finalists_rows.json").read_text(encoding="utf-8"))["base"]
        R = rows["S10F8" if key == "A" else "S12S6"]["rows"]
        med = lambda f: float(np.median([r[f] for r in R]))
        m_decl = med("m_decl")
        du = d.with_(unit=m_decl + cm)
        r = A.evaluate(du, P, fine=True)
        m2 = m2_detail(du, P, r["expected"]["w"])
        m3 = m3_detail(du, P, r["m3_mass"])
        m3_med = m3_detail(du, P, med("m3"))
        out[key] = {"container_kg": cm, "m_decl_median": m_decl, "m3_at_median_mass": m3_med, "base_eval": {
            "sensor_max": r["sensor_max"], "m3_mass": r["m3_mass"], "laps": r["laps"],
            "expected": r["expected"], "aggressive": r["aggressive"]}, "m2": m2, "m3": m3,
            "stow_by_mass": {f"{m:g}": float(s4.stow_time(m, A.apply(du, P))) for m in (3.0, 3.4, 4.0, 6.0, 8.0)},
            "draws": {f: {"p10": float(np.percentile([x[f] for x in R], 10)), "p50": med(f),
                          "p90": float(np.percentile([x[f] for x in R], 90)),
                          "mean": float(np.mean([x[f] for x in R if np.isfinite(x[f])]))}
                      for f in ("m_decl", "total", "M2", "M3", "GM", "w", "t2", "laps", "m3", "g2", "g3",
                                "vs2", "vs3", "tw2", "tw3", "p2", "p3")}}
        out[key]["draws"]["prod3"] = {q: float(np.percentile([x["laps"] * x["m3"] for x in R], v))
                                      for q, v in (("p10", 10), ("p50", 50), ("p90", 90))}
    (PROP / "data").mkdir(exist_ok=True)
    (PROP / "data" / "p1_nominal.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({k: {"m2": v["m2"], "m3": v["m3"], "base": v["base_eval"], "stow": v["stow_by_mass"]}
                      for k, v in out.items()}, indent=1, default=float))


if __name__ == "__main__":
    main()
