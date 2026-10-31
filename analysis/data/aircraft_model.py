# Copyright © 2026 Badr Obtel. All rights reserved.
"""Airframe evidence table, structural-mass fit and calibration factors (TOOLING).

    python analysis/data/aircraft_model.py

Input: dbf_aircraft.csv (every value verified against its AIAA source by
verify.py). One row per top-3 aircraft, SI units, written to dbf_airframes.csv.

Derivations (documented here and nowhere else):
  wing area   printed, else span x mean chord (UCLA 2025), span x chord for a
              rectangular wing (VT 2024), or an 8.0 in centre section at root
              chord plus two 22.0 in panels tapering at 0.78 (VT 2023).
  airframe    the printed empty mass without batteries when there is one,
              else M1 flying mass - propulsion battery - M1 ballast.
              Receiver batteries stay in the airframe (they fly every mission).
  CD0         printed CD0, else build-up total - induced (Joanneum 2022), else
              wing CD0 / wing share (GT 2026). A total CD at cruise (UW 2023,
              Ljubljana 2024) is shown as an upper bound, not as CD0.
Calibration pairs: measured / predicted of the same quantity, same aircraft.
Speeds are inverted (predicted / measured) so every ratio reads as time: > 1
means slower than predicted.

Writes dbf_airframes.csv, calibration.csv and, in analysis/out/:
  airframe_mass_area.pdf, calibration_time.pdf, calibration_other.pdf, drag_cd0.pdf
"""
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / "design-system" / "matplotlib"))

IN2 = 0.00064516
G0 = 9.80665
SHORT = {"University of Southern California": "USC", "University of Ljubljana": "LJUBLJANA",
         "Georgia Institute of Technology": "GT", "University of New South Wales": "UNSW",
         "University of California, Los Angeles": "UCLA",
         "Embry-Riddle Aeronautical University, Daytona Beach": "ERAU",
         "University of Michigan": "MICHIGAN", "Dayananda Sagar College of Engineering": "DSCE",
         "University of Central Florida": "UCF", "FH JOANNEUM University of Applied Sciences": "JOANNEUM",
         "Massachusetts Institute of Technology": "MIT", "Washington University in St. Louis": "WASHU",
         "University of Washington": "UW",
         "Virginia Polytechnic Institute and State University": "VT"}
KIND_ORDER = {"measured": 0, "design": 1, "predicted": 2}


def load():
    rows = list(csv.DictReader((HERE / "dbf_aircraft.csv").open(encoding="utf-8")))
    by = defaultdict(list)
    for r in rows:
        r["year"] = int(r["year"])
        r["value_si"] = float(r["value_si"]) if r["unit_si"] != "text" else r["value"]
        by[(r["year"], r["team"])].append(r)
    return by


def pick(rs, param, mission=None, kinds=("measured", "design", "predicted")):
    """Best available value: measured before design before predicted."""
    hit = [r for r in rs if r["param"] == param and (mission is None or r["mission"] == mission)
           and r["kind"] in kinds]
    hit.sort(key=lambda r: KIND_ORDER[r["kind"]])
    return hit[0] if hit else None


def val(r):
    return None if r is None else r["value_si"]


def wing_area(key, rs):
    r = pick(rs, "wing_area")
    if r:
        return r["value_si"], "printed"
    span, chord = val(pick(rs, "span")), val(pick(rs, "mean_chord"))
    if span and chord:
        return span * chord, "span x mean chord"
    root, taper = val(pick(rs, "root_chord")), val(pick(rs, "taper_ratio"))
    if key == (2023, "Virginia Polytechnic Institute and State University") and root and taper:
        centre, panel = 8.0 * 0.0254, 22.0 * 0.0254           # executive summary, p127
        return centre * root + 2 * panel * root * (1 + taper) / 2, "centre + tapered panels"
    if key == (2024, "Virginia Polytechnic Institute and State University") and span and root:
        return span * root, "rectangular, span x chord"
    return None, ""


def airframe(rs):
    r = pick(rs, "empty_mass_nobatt")
    if r:
        return r["value_si"], f"printed empty, no battery ({r['kind']})"
    m1, batt = pick(rs, "gross_mass", "M1"), pick(rs, "battery_mass", "M1") or pick(rs, "battery_mass")
    if m1 and batt:
        ballast = val(pick(rs, "ballast_mass", "M1")) or 0.0
        return m1["value_si"] - batt["value_si"] - ballast, f"M1 ({m1['kind']}) - battery - ballast"
    return None, ""


def cd0(rs):
    r = pick(rs, "cd0")
    if r:
        return r["value_si"], f"printed ({r['kind']})"
    tot, ind = pick(rs, "cd_total", "M2"), pick(rs, "cd_induced", "M2")
    if tot and ind:
        return tot["value_si"] - ind["value_si"], "build-up total - induced"
    w, share = pick(rs, "cd0_wing"), pick(rs, "cd0_wing_share")
    if w and share:
        return w["value_si"] / (share["value_si"] / 100.0), "wing CD0 / wing share"
    if tot:
        return tot["value_si"], "upper bound: total CD at cruise"
    return None, ""


def table(by):
    out = []
    for key in sorted(by):
        rs = by[key]
        year, team = key
        S, s_how = wing_area(key, rs)
        m_af, af_how = airframe(rs)
        grosses = [g for g in (pick(rs, "gross_mass", m) for m in ("M1", "M2", "M3")) if g]
        m_max = max((g["value_si"] for g in grosses), default=None)
        batt, wh = None, None
        for m in ("M2", "M3", "M1", ""):          # energy and mass of the same pack (same mission)
            w, b = pick(rs, "battery_wh", m), pick(rs, "battery_mass", m)
            if w and b:
                wh, batt = w["value_si"], b["value_si"]
                break
        c, c_how = cd0(rs)
        out.append({
            "year": year, "team": team, "short": SHORT.get(team, team),
            "span_m": val(pick(rs, "span")), "wing_area_m2": S, "area_source": s_how,
            "aspect_ratio": val(pick(rs, "aspect_ratio")) or (val(pick(rs, "span")) ** 2 / S if S and pick(rs, "span") else None),
            "airframe_kg": m_af, "airframe_source": af_how,
            "m1_kg": val(pick(rs, "gross_mass", "M1")), "gross_max_kg": m_max,
            "battery_kg": batt, "battery_wh": wh, "pack_wh_per_kg": wh / batt if (wh and batt) else None,
            "cd0": c, "cd0_source": c_how,
            "wing_loading_max_n_m2": m_max * G0 / S if (m_max and S) else None,
            "airframe_per_area_kg_m2": m_af / S if (m_af and S) else None,
        })
    return out


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.6g}" if isinstance(v, float) else v) for k, v in r.items()})


def fit_power(xs, ys):
    """Least squares on logs: y = k x^p. Returns k, p, r2, residual sd (log)."""
    lx, ly = [math.log(x) for x in xs], [math.log(y) for y in ys]
    n = len(lx)
    mx, my = sum(lx) / n, sum(ly) / n
    sxx = sum((a - mx) ** 2 for a in lx)
    sxy = sum((a - mx) * (b - my) for a, b in zip(lx, ly))
    p = sxy / sxx
    k = math.exp(my - p * mx)
    res = [b - (math.log(k) + p * a) for a, b in zip(lx, ly)]
    sst = sum((b - my) ** 2 for b in ly)
    r2 = 1 - sum(e * e for e in res) / sst
    sd = math.sqrt(sum(e * e for e in res) / (n - 2))
    return k, p, r2, sd


CAL = {  # param -> (category, invert): invert speeds so > 1 = slower than predicted
    "lap_time": ("time", False), "first_lap_time": ("time", False), "mission_time": ("time", False),
    "turn360_time": ("time", False), "cruise_speed": ("time", True), "max_speed": ("time", True),
    "gross_mass": ("mass", False), "empty_mass": ("mass", False), "empty_mass_nobatt": ("mass", False),
    "static_thrust": ("thrust", False), "power_avg": ("power", False), "energy_used": ("power", False),
    "cd0": ("drag", False), "oswald_e": ("drag", False),
}


def calibration(by):
    pairs = []
    for key, rs in by.items():
        groups = defaultdict(dict)
        for r in rs:
            if r["param"] in CAL and r["kind"] in ("predicted", "measured", "design"):
                kind = "predicted" if r["kind"] in ("predicted", "design") else "measured"
                groups[(r["param"], r["mission"])].setdefault(kind, r)
        for (param, mission), g in groups.items():
            if "predicted" in g and "measured" in g:
                cat, inv = CAL[param]
                p, m = g["predicted"]["value_si"], g["measured"]["value_si"]
                pairs.append({"year": key[0], "team": key[1], "short": SHORT.get(key[1], key[1]),
                              "param": param, "mission": mission, "category": cat,
                              "predicted": p, "measured": m, "ratio": (p / m) if inv else (m / p)})
    return sorted(pairs, key=lambda d: (d["category"], d["ratio"]))


def charts(rows, pairs, fit):
    import dbfplot as dp
    from common import OUT
    OUT.mkdir(exist_ok=True)
    dp.use()
    # 1. airframe mass vs wing area
    fig, ax = dp.figure("col", 2.4)
    pts = [r for r in rows if r["airframe_kg"] and r["wing_area_m2"]]
    k, p, r2, sd = fit
    xs = [0.2 + i * 0.01 for i in range(120)]
    ax.fill_between(xs, [k * x ** p * math.exp(-sd) for x in xs], [k * x ** p * math.exp(sd) for x in xs],
                    color=dp.MIST, lw=0, zorder=0)
    ax.plot(xs, [k * x ** p for x in xs], color=dp.STEEL, lw=0.9, zorder=1)
    offsets = {"ERAU 23": (-3, 3, "right"), "VT 24": (-3, 2, "right"), "JOANNEUM 22": (4, 4, "left"),
               "USC 24": (4, -6, "left"), "MIT 22": (-3, 4, "right"), "UNSW 25": (4, -6, "left"),
               "UW 23": (4, -2, "left"), "LJUBLJANA 24": (4, -3, "left")}
    for r in pts:
        name = f"{r['short']} {str(r['year'])[2:]}"
        dx, dy, ha = offsets.get(name, (3, 2, "left"))
        ax.plot(r["wing_area_m2"], r["airframe_kg"], "o", ms=3.2, color=dp.INK, zorder=2)
        ax.annotate(name, (r["wing_area_m2"], r["airframe_kg"]), xytext=(dx, dy), textcoords="offset points",
                    ha=ha, fontsize=4.6, family=dp.MONO, color=dp.INK)
    ax.set_xlim(0.2, 1.2)
    ax.set_ylim(0, 7)
    ax.set_xlabel("Wing area S (m²)")
    ax.set_ylabel("Airframe mass, no battery or payload (kg)")
    dp.tag(ax, f"FIT m = {k:.2f} S^{p:.2f}   R² {r2:.2f}   BAND ±1 SD", "upper left")
    dp.save(fig, OUT / "airframe_mass_area.pdf")
    # 2. calibration: time and speed; then mass, thrust, power and drag
    for fname, cats, height, xlim, xlabel in (
            ("calibration_time.pdf", ("time",), 3.0, (0.7, 1.6), "Measured ÷ predicted time (speeds inverted)"),
            ("calibration_other.pdf", ("mass", "thrust", "power", "drag"), 2.2, (0.8, 2.6), "Measured ÷ predicted")):
        sel = [d for d in pairs if d["category"] in cats]
        fig, ax = dp.figure("col", height)
        for i, d in enumerate(sel):
            speed = d["param"] in ("cruise_speed", "max_speed")
            ax.plot([1.0, d["ratio"]], [i, i], color=dp.FOG, lw=0.8, ls="-", zorder=1)
            ax.plot(d["ratio"], i, "o", ms=3.0, color="white" if speed else dp.INK, mec=dp.INK, mew=0.8, zorder=2)
        ax.axvline(1.0, color=dp.INK, lw=0.8)
        names = [f"{d['short']} {str(d['year'])[2:]} {d['mission']} {d['param'].replace('_', ' ')}".upper() for d in sel]
        ax.set_yticks(range(len(sel)), names, fontsize=4.4, family=dp.MONO)
        ax.set_xlim(*xlim)
        ax.set_xlabel(xlabel)
        ax.grid(axis="y", visible=False)
        if cats == ("time",):
            dp.tag(ax, "FILLED = TIME   OPEN = SPEED", "lower right")
        dp.save(fig, OUT / fname)
    # 3. CD0
    cds = sorted([r for r in rows if r["cd0"]], key=lambda r: r["cd0"])
    fig, ax = dp.figure("col", 2.0)
    for i, r in enumerate(cds):
        bound = r["cd0_source"].startswith("upper bound")
        ax.barh(i, r["cd0"], color=dp.FOG if bound else dp.INK, height=0.6)
        ax.text(r["cd0"] + 0.002, i, r["cd0_source"].upper(), va="center", fontsize=4.4, family=dp.MONO, color=dp.STEEL)
    ax.set_yticks(range(len(cds)), [f"{r['short']} {str(r['year'])[2:]}" for r in cds], fontsize=5.0, family=dp.MONO)
    ax.set_xlim(0, 0.2)
    ax.set_xlabel("Zero-lift drag coefficient CD0 (wing reference)")
    ax.grid(axis="y", visible=False)
    dp.save(fig, OUT / "drag_cd0.pdf")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    by = load()
    rows = table(by)
    write_csv(HERE / "dbf_airframes.csv", rows)
    pts = [r for r in rows if r["airframe_kg"] and r["wing_area_m2"]]
    fit = fit_power([r["wing_area_m2"] for r in pts], [r["airframe_kg"] for r in pts])
    pairs = calibration(by)
    write_csv(HERE / "calibration.csv", pairs)
    print(f"{'aircraft':16} {'b m':>5} {'S m2':>6} {'AR':>5} {'airframe kg':>11} {'kg/m2':>6} {'max kg':>7} {'W/S N/m2':>8} {'CD0':>7}  sources")
    for r in rows:
        f = lambda v, w, d: f"{v:{w}.{d}f}" if isinstance(v, float) else " " * (w - 1) + "-"
        print(f"{r['short'] + ' ' + str(r['year']):16} {f(r['span_m'], 5, 2)} {f(r['wing_area_m2'], 6, 3)} "
              f"{f(r['aspect_ratio'], 5, 2)} {f(r['airframe_kg'], 11, 2)} {f(r['airframe_per_area_kg_m2'], 6, 2)} "
              f"{f(r['gross_max_kg'], 7, 2)} {f(r['wing_loading_max_n_m2'], 8, 0)} {f(r['cd0'], 7, 4)}  "
              f"{r['area_source']}; {r['airframe_source']}; {r['cd0_source']}")
    packs = sorted(r["pack_wh_per_kg"] for r in rows if r["pack_wh_per_kg"])
    print(f"\nbattery packs (energy and mass of the same pack): n={len(packs)}, "
          f"median {median(packs):.0f} Wh/kg, range {packs[0]:.0f}-{packs[-1]:.0f}")
    k, p, r2, sd = fit
    print(f"\nairframe mass fit over {len(pts)} aircraft: m = {k:.3f} S^{p:.3f} (S in m2, m in kg), "
          f"R2 = {r2:.2f}, residual sd {sd:.2f} in ln (x{math.exp(sd):.2f})")
    print("\ncalibration (measured / predicted; speeds inverted):")
    for cat in ("time", "mass", "thrust", "power", "drag"):
        rs = [d["ratio"] for d in pairs if d["category"] == cat]
        teams = {(d["year"], d["team"]) for d in pairs if d["category"] == cat}
        if rs:
            print(f"  {cat:7} n={len(rs):2} from {len(teams):2} aircraft: median {median(rs):.2f}, "
                  f"range {min(rs):.2f}-{max(rs):.2f}, above 1: {sum(x > 1 for x in rs)}")
    for d in pairs:
        print(f"    {d['short']:9} {d['year']} {d['mission']:2} {d['param']:18} {d['predicted']:9.4g} -> {d['measured']:9.4g}  x{d['ratio']:.2f}")
    print("\ntime split (pairs within one aircraft are not independent, so per-aircraft medians too):")
    for name, params in (("lap and mission times", ("lap_time", "first_lap_time", "mission_time", "turn360_time")),
                         ("straight-line speeds", ("cruise_speed", "max_speed"))):
        sel = [d for d in pairs if d["param"] in params]
        per = defaultdict(list)
        for d in sel:
            per[(d["year"], d["short"])].append(d["ratio"])
        meds = sorted(median(v) for v in per.values())
        print(f"  {name:22} {len(sel):2} pairs, median {median(d['ratio'] for d in sel):.2f}; "
              f"{len(meds)} aircraft, median of aircraft medians {median(meds):.2f}, "
              f"slower than predicted {sum(m > 1 for m in meds)} of {len(meds)}, range {meds[0]:.2f}-{meds[-1]:.2f}")
    charts(rows, pairs, fit)


if __name__ == "__main__":
    main()
