# Copyright © 2026 Badr Obtel. All rights reserved.
"""What the measured wing CLmax does to the Script 6 robust optimum (E03 impact study).

    PYTHONIOENCODING=utf-8 python analysis/clmax_impact.py     (after wing_clmax.py)

Script 6 draws the straight wing's CLmax factor from U(0.90, 1.0625) about
sizing.toml's ESTIMATES (1.6 flapped, 1.25 clean). wing_clmax.py now gives
measured-data ranges for an SD7037 wing. This script re-runs the robust design
map on the SAME 120 draws (common random numbers) with only that factor replaced,
one scenario per evidence range. Nothing in sizing.toml or studies.toml changes.
Writes out/clmax_impact_report.txt.
"""
import copy
import csv
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
import s6_studies as s6  # noqa: E402

OUT = HERE / "out"
SIZING_FLAPPED = 1.6
AREAS = [0.8, 0.9, 1.0, 1.1, 1.2]
UNITS = [3.0, 4.0, 5.0, 6.0]


def wing_rows():
    return list(csv.DictReader((OUT / "wing_clmax.csv").open(encoding="utf-8")))


def pick(rows, taper, span, delta, col):
    for r in rows:
        if (r["section"] == "SD7037" and float(r["S"]) == 0.9 and float(r["taper"]) == taper
                and float(r["flap_span"]) == span and float(r["delta"]) == delta):
            return float(r[col])
    raise KeyError((taper, span, delta, col))


def scenarios(rows):
    """(name, factor range) on the flapped 1.6; the same factor scales the clean 1.25 (Script 4)."""
    f = lambda v: v / SIZING_FLAPPED
    t, s, d = 0.7, 0.6, 30.0
    return [
        ("Script 6 as is: U(0.90, 1.0625)", (0.90, 1.0625)),
        (f"SD7037, taper {t}, flap {s:.0%} semispan, {d:.0f} deg, untrimmed",
         (f(pick(rows, t, s, d, "cl_conservative")), f(pick(rows, t, s, d, "cl_calibrated")))),
        (f"SD7037, taper {t}, flap {s:.0%} semispan, {d:.0f} deg, trimmed",
         (f(pick(rows, t, s, d, "cl_trim_lo")), f(pick(rows, t, s, d, "cl_trim_hi")))),
        (f"SD7037, taper {t}, flap 70% semispan, 40 deg, untrimmed",
         (f(pick(rows, t, 0.7, 40.0, "cl_conservative")), f(pick(rows, t, 0.7, 40.0, "cl_calibrated")))),
    ]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    rows = wing_rows()
    base = s6.draws(s6.ST["monte_carlo"]["draws"], s6.ST["monte_carlo"]["seed"])
    rng = np.random.default_rng(20271015)
    u01 = rng.uniform(size=len(base))                # one quantile per draw, reused in every scenario
    L = ["What the measured wing CLmax does to the robust optimum (clmax_impact.py, PROVISIONAL)",
         f"Same {len(base)} draws as Script 6; only the straight wing's CLmax factor is replaced (flapped 1.6 x factor,",
         "clean 1.25 x factor). Mean total score, expected field; P(M2 feasible) in brackets.", ""]
    for name, (lo, hi) in scenarios(rows):
        Ps = []
        for P, q in zip(base, u01):
            Q = copy.copy(P)
            Q.clmax_factor = dict(P.clmax_factor)
            Q.clmax_factor["straight"] = lo + (hi - lo) * q
            Ps.append(Q)
        L.append(f"{name}: factor {lo:.3f}-{hi:.3f} (flapped CLmax {lo*SIZING_FLAPPED:.2f}-{hi*SIZING_FLAPPED:.2f})")
        L.append("   S m2 \\ unit kg " + "".join(f"{u:>13.0f}" for u in UNITS))
        best = (-1, None)
        for s in AREAS:
            cells = []
            for u in UNITS:
                res = [s6.evaluate("straight", s, u, P) for P in Ps]
                if not all(res):
                    cells.append(f"{'-':>13}")
                    continue
                m = float(np.mean([r["expected"]["total"] for r in res]))
                ok = float(np.mean([r["m2_feasible"] for r in res]))
                cells.append(f"{m:>7.2f} ({ok:>3.0%})")
                if m > best[0]:
                    best = (m, (s, u, ok))
            L.append(f"   {s:>15.1f} " + "".join(cells))
        m, (s, u, ok) = best
        L.append(f"   best on this grid: {s:.1f} m2, {u:.0f} kg unit, mean {m:.2f}, P(M2) {ok:.0%}")
        L.append("")
        print("\n".join(L[-len(AREAS) - 4:]), flush=True)
    L.append("Notes: grid only (0.1 m2, 1 kg); the full Script 6 map is out/s6_report.txt. The stall bound stays")
    L.append("14 m/s. Trim uses the ESTIMATE band in inputs/wing_clmax.toml (tail not sized).")
    (OUT / "clmax_impact_report.txt").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
