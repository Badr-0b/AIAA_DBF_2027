# Copyright © 2026 the members of the AUM AIAA DBF team. All rights reserved.
"""Configuration trades from physics: the mass-for-drag exchange rate, the
retractable-gear break-even, and the body-shape test (PROVISIONAL).

    python analysis/config_trades.py

Written by Claude (Oct 13). Nothing here is a decision (user, 13 Oct).

At Script 6's robust reference (straight wing, payload = one unit plus one
simulator), the fastest feasible five-lap M2 (Script 4, flown time base) is
recomputed with the non-wing drag area and the airframe mass nudged. That gives
the exchange rate: how much drag area costs the same M2 time as a kilogram.
Then:
  - gear: the fixed-gear drag areas the top-3 reports printed (GT 2026 measured
    in a wind tunnel; Joanneum 2022 and WashU 2022 build-ups) set the break-even
    mass a retract system must stay under;
  - body: any candidate body (whale-like, MQ-4C-like, tube) is a (drag area,
    mass) change against the baseline; the same exchange rate scores it.
Field-practice counts and fly-off outcomes: data/config_evidence.py.
Writes analysis/out/config_exchange.pdf.
"""
import csv
import sys

import numpy as np

import common
import s4_sizing as s4
sys.path.insert(0, str(common.ANALYSIS / "data"))
import s6_studies as s6
from common import OUT

DATA = common.ANALYSIS / "data"


def ref_point():
    """Script 6's robust reference (re-derived from its inputs, no hand-picked numbers)."""
    rows = list(csv.reader((OUT / "s6_report.txt").open(encoding="utf-8")))
    for r in rows:
        line = ",".join(r)
        if line.strip().startswith("robust best:"):
            s = float(line.split("S ")[1].split(" m2")[0])
            unit = float(line.split("unit ")[1].split(" kg")[0])
            return s, unit
    raise SystemExit("run analysis/s6_studies.py first (needs out/s6_report.txt)")


def m2_time(s, payload, f_body=None, dm=0.0):
    P = s6.base_params()
    if f_body is not None:
        P.f_body = f_body
    k, p = P.k_af, P.p_af
    base_af = P.airframe(s)
    P.af_factor = (base_af + dm) / (k * s ** p)
    return s4.m2_fixed("straight", s, payload, P, fine=True)


def gear_drag_areas():
    """Fixed-gear drag areas (m2) from the verified dataset: CD on wing area x wing area."""
    rows = list(csv.DictReader((DATA / "dbf_aircraft.csv").open(encoding="utf-8")))
    area = {(r["year"], r["team"]): float(r["value_si"]) for r in rows if r["param"] == "wing_area"}
    out = []
    for r in rows:
        if r["param"] == "cd_gear":
            key = (r["year"], r["team"])
            out.append((r["team"], r["year"], r["kind"], float(r["value_si"]), float(r["value_si"]) * area[key]))
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    s, unit = ref_point()
    payload = 2 * unit                                 # one unit plus one simulator (Script 6 reference)
    P0 = s6.base_params()
    f0 = P0.f_body
    t0 = m2_time(s, payload)
    df, dm = 0.002, 0.2
    t_f = m2_time(s, payload, f_body=f0 + df)
    t_m = m2_time(s, payload, dm=dm)
    sec_per_m2 = (t_f - t0) / df
    sec_per_kg = (t_m - t0) / dm
    kg_per_m2 = sec_per_m2 / sec_per_kg
    fmax = common.field_maxima("expected")["m2"]
    dscore_per_s = payload / fmax * (1 / t0 - 1 / (t0 + 1))
    print(f"Reference: straight wing S {s} m2, payload {payload} kg (unit {unit} + 1 simulator), "
          f"baseline f_body {f0} m2; M2 {t0:.1f} s (flown time base)")
    print(f"  +{df} m2 non-wing drag area -> M2 +{t_f - t0:.2f} s;  +{dm} kg airframe -> M2 +{t_m - t0:.2f} s")
    print(f"  exchange rate: 10 cm2 (0.001 m2) of drag area costs the same M2 time as {kg_per_m2 * 0.001 * 1000:.0f} g "
          f"of airframe mass; 1 s of M2 time = {dscore_per_s:.4f} M2 points (expected field)")
    print("\nRetractable gear: break-even retract-system mass = fixed-gear drag area x exchange rate")
    for team, year, kind, cd, f in gear_drag_areas():
        be = f * kg_per_m2
        print(f"  {year} {team[:34]:34} gear CD {cd:.4f} ({kind:9}) -> drag area {f * 1e4:5.1f} cm2 -> "
              f"break-even {1000 * be:4.0f} g, and the M2 time saved at most {f * sec_per_m2:.1f} s")
    chart(kg_per_m2, sec_per_m2, f0, gear_drag_areas())


def chart(kg_per_m2, sec_per_m2, f0, gears):
    sys.path.insert(0, str(common.REPO / "design-system" / "matplotlib"))
    import dbfplot as dp
    OUT.mkdir(exist_ok=True)
    dp.use()
    fig, ax = dp.figure("col", 2.3)
    sec_per_kg = sec_per_m2 / kg_per_m2
    xs = np.linspace(-0.008, 0.008, 50)
    bottom = -0.55
    for dt in (-6, -3, 0, 3, 6):
        dm = (dt - sec_per_m2 * xs) / sec_per_kg
        ax.plot(1e4 * xs, dm, color=dp.INK if dt == 0 else dp.FOG, lw=1.2 if dt == 0 else 0.7, ls="-")
        x_b = (dt - sec_per_kg * bottom) / sec_per_m2
        if -0.008 < x_b < 0.008:
            ax.text(1e4 * x_b + 1.5, bottom, f"{dt:+d} S" if dt else "0 S", ha="left", va="center", fontsize=4.6,
                    family=dp.MONO, color=dp.INK if dt == 0 else dp.STEEL)
    for team, year, kind, cd, f in gears:
        if f < 0.006:
            be = f * kg_per_m2
            ax.plot(-1e4 * f, be, "o", ms=3.2, color="white", mec=dp.INK, mew=0.9, zorder=3)
            from aircraft_model import SHORT
            ax.annotate(f"RETRACT {SHORT.get(team, team)} {str(year)[2:]}-SIZE GEAR\nBREAK-EVEN {1000 * be:.0f} G",
                        (-1e4 * f, be), xytext=(6, 4 if f > 0.0015 else -6), textcoords="offset points",
                        fontsize=4.4, family=dp.MONO, va="center")
    ax.axhline(0, color=dp.STEEL, lw=0.5)
    ax.axvline(0, color=dp.STEEL, lw=0.5)
    ax.set_xlim(-80, 80)
    ax.set_ylim(-0.6, 0.9)
    ax.set_xlabel(f"Change in non-wing drag area (cm²), baseline {1e4 * f0:.0f} cm²")
    ax.set_ylabel("Change in airframe mass (kg)")
    ax.set_title("M2 TIME CHANGE; BELOW THE BOLD LINE = FASTER", fontsize=5.4,
                 family=dp.MONO, color=dp.GRAPHITE, loc="left")
    dp.save(fig, OUT / "config_exchange.pdf")


if __name__ == "__main__":
    main()
