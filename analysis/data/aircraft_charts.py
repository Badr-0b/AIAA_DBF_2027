# Copyright © 2026 the members of the AUM AIAA DBF team. All rights reserved.
"""Charts from the verified top-3 design-report dataset (TOOLING).

    python analysis/data/aircraft_charts.py      (after verify.py)

Input: dbf_aircraft.csv (every value verified against its AIAA source).
Output in analysis/out/:
  (predicted vs flight-test calibration moved to aircraft_model.py: calibration_time.pdf)
  aircraft_m2_rate.pdf        M2 payload / time evidence (2025, weight/time year),
                              converted to 5 laps, against our competitor scenarios
  aircraft_lap_vs_mass.pdf    measured lap time against gross mass
"""
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / "design-system" / "matplotlib"))
import dbfplot as dp  # noqa: E402
import common  # noqa: E402
from common import OUT, SCENARIOS  # noqa: E402

SHORT = {"University of Southern California": "USC", "University of Ljubljana": "LJUBLJANA",
         "Georgia Institute of Technology": "GT", "University of New South Wales": "UNSW",
         "University of California, Los Angeles": "UCLA",
         "Embry-Riddle Aeronautical University, Daytona Beach": "ERAU",
         "University of Michigan": "MICHIGAN", "Dayananda Sagar College of Engineering": "DSCE",
         "University of Central Florida": "UCF"}


def load():
    rows = list(csv.DictReader((HERE / "dbf_aircraft.csv").open(encoding="utf-8")))
    for r in rows:
        r["year"] = int(r["year"])
        r["value_si"] = float(r["value_si"]) if r["unit_si"] != "text" else None
    return rows


def get(rows, **kw):
    return [r for r in rows if all(r[k] == v for k, v in kw.items())]


def label(r):
    return f"{SHORT.get(r['team'], r['team'])} {str(r['year'])[2:]}"


def five_lap(rate_3lap, three_lap_s, lap_s):
    """3-lap payload rate -> 5-lap rate with the team's own lap structure."""
    return rate_3lap * three_lap_s / (three_lap_s + 2 * lap_s)


def chart_m2_rate(rows):
    """2025 weight/time evidence, each converted to 5 laps with ERAU's measured lap structure
    (124 s for 3 laps, 32 s laps) unless the team's own lap time is known."""
    c = common.load("competitor")["m2"]
    ev = []
    for team, kind in (("University of New South Wales", "predicted"),
                       ("University of California, Los Angeles", "predicted"),
                       ("Embry-Riddle Aeronautical University, Daytona Beach", "predicted"),
                       ("Embry-Riddle Aeronautical University, Daytona Beach", "measured")):
        pay = get(rows, team=team, year=2025, param="payload_mass", mission="M2")
        tim = [r for r in get(rows, team=team, year=2025, param="mission_time", mission="M2") if r["kind"] == kind]
        if not tim:
            continue
        payload = pay[0]["value_si"]
        t3 = tim[0]["value_si"]
        lap = [r for r in get(rows, team=team, year=2025, param="lap_time", mission="M2") if r["kind"] == kind]
        lap_s = lap[0]["value_si"] if lap else c["lap_s"] * t3 / c["three_lap_s"]
        ev.append((f"{SHORT[team]} 25 {kind[:4].upper()}", five_lap(payload / t3, t3, lap_s), kind))
    fm = get(rows, param="payload_rate_field_max", year=2025)[0]["value_si"]
    ev.append(("ERAU 25 EST. FIELD MAX", five_lap(fm, c["three_lap_s"], c["lap_s"]), "estimate"))
    ucla = [e for e in ev if e[0].startswith("UCLA")]
    if ucla:
        ev.append(("UCLA-IMPLIED MAX", ucla[0][1] / 0.42, "inferred"))
    ev.sort(key=lambda e: e[1])
    dp.use()
    fig, ax = dp.figure("col", 2.2)
    for i, (name, v, kind) in enumerate(ev):
        ax.barh(i, v * 1000, color=dp.INK if kind == "measured" else dp.FOG, height=0.6)
        ax.text(v * 1000 + 1, i, f"{v * 1000:.0f}", va="center", fontsize=5.2, family=dp.MONO, color=dp.INK)
    for sc, ls in zip(SCENARIOS, ("-", "--", ":")):
        x = common.field_maxima(sc)["m2"] * 1000
        ax.axvline(x, color=dp.STEEL, lw=0.8, ls=ls)
        ax.text(x, len(ev) - 0.3, sc[:4].upper(), rotation=90, va="top", ha="right",
                fontsize=4.8, family=dp.MONO, color=dp.STEEL)
    ax.set_yticks(range(len(ev)), [e[0] for e in ev], fontsize=5.2, family=dp.MONO)
    ax.set_xlabel("M2 payload / 5-lap time (g/s)")
    ax.grid(axis="y", visible=False)
    dp.save(fig, OUT / "aircraft_m2_rate.pdf")
    return ev


def chart_lap_vs_mass(rows):
    """Measured lap times against the gross mass flown in the same test."""
    pts = []
    for team, year, mission, lap_param in (
            ("Georgia Institute of Technology", 2026, "M2", "first_lap_time"),
            ("Embry-Riddle Aeronautical University, Daytona Beach", 2025, "M2", "lap_time"),
            ("University of Central Florida", 2021, "M2", "lap_time"),
            ("Embry-Riddle Aeronautical University, Daytona Beach", 2021, "M2", "lap_time")):
        lap = [r for r in get(rows, team=team, year=year, param=lap_param, mission=mission) if r["kind"] == "measured"]
        m = [r for r in get(rows, team=team, year=year, param="gross_mass", mission=mission)
             if r["kind"] in ("measured", "design")]
        if lap and m:
            pts.append((label(lap[0]), m[0]["value_si"], lap[0]["value_si"]))
    dp.use()
    fig, ax = dp.figure("col", 2.0)
    for name, mass, lap in pts:
        ax.plot(mass, lap, "o", ms=3.4, color=dp.INK)
        ax.annotate(name, (mass, lap), xytext=(4, -2), textcoords="offset points",
                    fontsize=5.0, family=dp.MONO, color=dp.STEEL)
    ax.set_xlim(0, 20)
    ax.set_ylim(20, 50)
    ax.set_xlabel("Gross mass flown (kg)")
    ax.set_ylabel("Measured M2 lap time (s)")
    dp.save(fig, OUT / "aircraft_lap_vs_mass.pdf")
    return pts


def main():
    rows = load()
    OUT.mkdir(exist_ok=True)
    ev = chart_m2_rate(rows)
    print("M2 payload rate over 5 laps (kg/s):")
    for name, v, kind in ev:
        print(f"  {name:24} {v:.4f}  ({kind})")
    for name, mass, lap in chart_lap_vs_mass(rows):
        print(f"  lap vs mass: {name:12} {mass:5.2f} kg  {lap:5.2f} s")


if __name__ == "__main__":
    main()
