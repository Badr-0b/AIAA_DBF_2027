"""Proposal P1.2: the two payload trades behind the mission plan (31 Oct 2026).

(a) Mission 2: units carried (the sensor in its container plus 0-2 simulators, each at the declared mass) against
    the declared sensor mass. Per draw: five-lap time (s4.m2_fixed), M2 score against the expected field, and
    P(M2 completed) from S2 p_attempt at the stall speed and T/W the payload creates, over the finalists'
    attempt budget (finalists._pc). Points shown: M1 credit + M2, if completed and expected.
(b) Mission 3: sensor mass flown (ballast) at the median declaration. Per draw: whole laps (s4.m3_search, stow
    charged inside the window as in DB-02), M3 score, P(M2 then M3 completed); M2 at the design unit.
Same 120 paired draws, design (Variant A) and expected field as DB-02 finalists and tools/p1_sensitivity.py.
Imports DB-02 and analysis code read-only. Writes proposal/data/p1_payload.json only.
(c) The stow-window assumption: the policy mean with the stow charged inside the window (DB-02) and outside it.
Run: PYTHONDONTWRITEBYTECODE=1 python proposal/tools/p1_payload.py   (about 1 minute)
"""
from __future__ import annotations

import json
import math
import sys
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

s2, s4, s6 = A.s2, A.s4, A.s6
G0 = A.G0
M_DECL = 6.25                                         # DB-02 median declaration, Variant A
DECL = [round(x, 2) for x in np.arange(2.0, 8.01, 0.5)]
N_SIM = (0, 1, 2)
M3_GRID = [round(x, 2) for x in np.arange(1.0, 8.01, 0.25)]
TOGW = A.RULES["aircraft"]["togw_max_kg"]


def p_ok(g, Q, d, mission):
    clm = d.meta["clmax_landing"] * Q.clmax_factor.get(Q.family_fn[1], 1.0)
    vs = math.sqrt(2 * g * G0 / (SE.RHO_DESIGN * d.s * clm))
    p = fm.p_attempt({"v_stall": vs, "tw_takeoff": d.propulsion.static_thrust_n / (g * G0)},
                     d.meta["complexity"], mission=mission)
    return max(0.01, min(0.99, p)), vs


def main():
    d0 = SE.make(1.0, "fowler", 8.0, "8s")
    cm = d0.meta["container_kg"]
    Ps = A.draws()
    f = s6.fields()["expected"]
    m2 = {(m, n): {"pts": [], "pc": [], "exp": [], "feas": []} for m in DECL for n in N_SIM}
    m3 = {ms: {"laps": [], "prod": [], "pts": [], "pc": [], "exp": [], "p3": [], "exp1": []} for ms in M3_GRID}
    for P in Ps:
        for m in DECL:
            d = d0.with_(unit=m + cm)
            Q = A.apply(d, P)
            with A.st_patch(d.ops), A._thrust(Q):
                pay = np.array([(1 + n) * d.unit for n in N_SIM])
                t2 = np.atleast_1d(s4.m2_fixed(d.family, d.s, pay, Q, fine=False))
                for n, w, t in zip(N_SIM, pay, t2):
                    g = Q.empty(d.s) + Q.battery() + w
                    ok = bool(np.isfinite(t) and t <= s6.WINDOW and g < TOGW)
                    pts = 1.0 + s2.m2(w, t, f["m2"], completed=True) if ok else 0.0
                    pc = FI._pc(fm, (p_ok(g, Q, d, "M2")[0],)) if ok else 0.0
                    r = m2[(m, n)]
                    r["pts"].append(pts); r["pc"].append(pc); r["exp"].append(pts * pc); r["feas"].append(ok)
        # Mission 3 at the median declaration; M2 flown with the design unit
        d = d0.with_(unit=M_DECL + cm)
        Q = A.apply(d, P)
        with A.st_patch(d.ops), A._thrust(Q):
            g2 = Q.empty(d.s) + Q.battery() + d.unit
            p2 = p_ok(g2, Q, d, "M2")[0]
            ms = np.array(M3_GRID)
            stow = s4.stow_time(ms, Q) + s6.ST["design"]["t_stow_extra_s"]
            laps = np.atleast_1d(s4.m3_search(d.family, d.s, ms, Q, stow_s=stow, fine=False))
            for x, L in zip(M3_GRID, laps):
                ok = L >= s6.RULES["missions"]["m3_min_laps"]
                pts = s2.m3(int(L), x, f["m3"], completed=True) if ok else 0.0
                g3 = Q.empty(d.s) + Q.battery() + x
                p3 = p_ok(g3, Q, d, "M3")[0]
                pc = FI._pc(fm, (p2, p3)) if ok else 0.0
                r = m3[x]
                r["p3"].append(p3 if ok else 0.0); r["exp1"].append(pts * p3 if ok else 0.0)
                r["laps"].append(int(L)); r["prod"].append(L * x if ok else 0.0)
                r["pts"].append(pts); r["pc"].append(pc); r["exp"].append(pts * pc)
    mean = lambda a: float(np.mean(a))
    # DB-02 charges the stow inside the M3 window (conservative until the Q&A); rules 3.3.3.3 lets laps count
    # when the line is crossed in the air, so the stow can fall outside it. Paired change in the mean total:
    sys.path.insert(0, str(HERE))
    import p1_sensitivity as PS
    base = np.array([r["total"] for r in PS.policy_rows()])
    saved = s4.stow_time
    s4.stow_time = lambda ms, P: np.zeros_like(np.atleast_1d(np.asarray(ms, dtype=float)))
    try:
        free = np.array([r["total"] for r in PS.policy_rows()])
    finally:
        s4.stow_time = saved
    out = {"generated": "proposal/tools/p1_payload.py, 31 Oct 2026", "draws": len(Ps), "m_decl": M_DECL,
           "container_kg": cm, "field": f, "stow_free_delta": float(np.mean(free - base)),
           "ref_mean": float(base.mean()),
           "m2": [{"m": m, "n_sim": n, "payload": (1 + n) * (m + cm), "pts": mean(r["pts"]), "pc": mean(r["pc"]),
                   "exp": mean(r["exp"]), "feas": mean(r["feas"])} for (m, n), r in m2.items()],
           "m3": [{"m": x, "laps_p50": float(np.median(r["laps"])), "laps_mean": mean(r["laps"]),
                   "prod": mean(r["prod"]), "pts": mean(r["pts"]), "pc": mean(r["pc"]), "exp": mean(r["exp"]),
                   "p3": mean(r["p3"]), "exp1": mean(r["exp1"])}
                  for x, r in m3.items()]}
    (PROP / "data" / "p1_payload.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    for r in out["m2"]:
        print(f"M2 m {r['m']:4.1f} n {r['n_sim']} pay {r['payload']:5.2f}  pts {r['pts']:.3f}  pc {r['pc']:.3f}  "
              f"exp {r['exp']:.3f}  feas {r['feas']:.2f}")
    for r in out["m3"]:
        print(f"M3 m {r['m']:4.2f}  laps {r['laps_p50']:.0f} ({r['laps_mean']:.2f})  prod {r['prod']:5.2f}  "
              f"pts {r['pts']:.3f}  pc {r['pc']:.3f}  exp {r['exp']:.3f}  p3 {r['p3']:.3f}  exp1 {r['exp1']:.3f}")


if __name__ == "__main__":
    main()
