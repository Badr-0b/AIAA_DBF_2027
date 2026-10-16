# Copyright © 2026 the members of the AUM AIAA DBF team. All rights reserved.
"""Airframe mass by component from the top-3 weight-and-balance tables (evidence gap E02).

    PYTHONIOENCODING=utf-8 python analysis/mass_breakdown.py

Question: Script 4 sizes the airframe from one fit, m = 5.96 S^0.94 kg (14 aircraft,
scatter x1.31 at 1 sd), and that scatter is the second-largest driver of the score
(Script 6, Spearman -0.64). What is the airframe made of, component by component,
and what does a bottom-up budget for the 0.9 m2 reference design give?

Data: data/dbf_components.toml, 17 weight-and-balance tables, 2021-2026 top-3 reports.
Every text-layer row is checked against its cached page (verify.find); IMAGE rows
were read on the rendered page. Each table's rows are summed against its own
printed total: a mismatch is reported, never corrected.
Airframe = everything except propulsion battery, payload and ballast (the same
definition as aircraft_model.py: receiver batteries and payload mechanisms stay in).
Writes out/mass_breakdown_report.txt, mass_breakdown.csv, mass_breakdown.pdf.
"""
import csv
import statistics as st
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "data"))
from verify import TO_SI, find  # noqa: E402

OUT = HERE / "out"
DATA = HERE / "data"
CATS = ["wing", "fuselage", "empennage", "gear", "propulsion", "avionics", "payload_system", "other"]
NOT_AIRFRAME = {"battery", "payload", "ballast"}
SHORT = {"University of Michigan": "MICHIGAN", "Dayananda Sagar College of Engineering": "DSCE",
         "University of Central Florida": "UCF", "FH JOANNEUM University of Applied Sciences": "JOANNEUM",
         "Washington University in St. Louis": "WASHU", "University of Washington": "UW",
         "Embry-Riddle Aeronautical University, Daytona Beach": "ERAU",
         "Virginia Polytechnic Institute and State University": "VT",
         "University of Southern California": "USC", "University of Ljubljana": "LJUBLJANA",
         "University of New South Wales": "UNSW", "Georgia Institute of Technology": "GT"}
# Reference design (Script 6 robust optimum, s6_report.txt): wing 0.9 m2 on 1.82 m,
# 4 kg payload unit, M2 gross 14.42 kg with one simulator; one tractor motor.
REF = {"S": 0.9, "gross_max": 14.42}


def load():
    return tomllib.loads((DATA / "dbf_components.toml").read_text(encoding="utf-8"))["aircraft"]


def kg(value, unit):
    return float(value) * TO_SI[unit][0]


def airframes():
    rows = csv.DictReader((DATA / "dbf_airframes.csv").open(encoding="utf-8"))
    return {(int(r["year"]), r["short"]): r for r in rows}


def check(acs):
    """Quote checks and the sum check. Returns problems and the per-table sum report."""
    bad, sums = [], []
    for a in acs:
        tag = f"{a['year']} {SHORT[a['team']]} p{a['page']}"
        for label, cat, value, quote, *pg in a["rows"]:
            if cat not in CATS and cat not in NOT_AIRFRAME:
                bad.append(f"{tag} {label}: unknown category {cat}")
            if quote == "IMAGE":
                continue
            hit = find(a["source"], pg[0] if pg else a["page"], quote)
            if hit is not True:
                bad.append(f"{tag} {label}: quote not on page ({hit})")
            elif value not in quote:
                bad.append(f"{tag} {label}: value not inside its quote")
        tv, tq = a["total"]
        if tq != "IMAGE" and find(a["source"], a.get("total_page", a["page"]), tq) is not True:
            bad.append(f"{tag} total: quote not on page")
        skip = set(a.get("not_in_total", []))
        s = sum(float(r[2]) for r in a["rows"] if r[1] in a["total_rows"] and r[0] not in skip)
        sums.append((tag, a["unit"], s, tv, s - tv, (s - tv) / tv))
    return bad, sums


def per_aircraft(acs, af):
    out = []
    for a in acs:
        u = a["unit"]
        m = {c: 0.0 for c in CATS}
        for label, cat, value, *_ in a["rows"]:
            if cat in m:
                m[cat] += kg(value, u)
        frame = sum(m.values())
        ref = af.get((a["year"], SHORT[a["team"]]), {})
        S = float(ref["wing_area_m2"]) if ref.get("wing_area_m2") else None
        gmax = float(ref["gross_max_kg"]) if ref.get("gross_max_kg") else None
        out.append({"year": a["year"], "short": SHORT[a["team"]], "aircraft": a["aircraft"], "basis": a["basis"],
                    "lumped": "+".join(a["lumped"]), **{f"{c}_kg": m[c] for c in CATS}, "airframe_kg": frame,
                    "S_m2": S, "gross_max_kg": gmax,
                    "airframe_fit_dataset_kg": float(ref["airframe_kg"]) if ref.get("airframe_kg") else None})
    return out


def q(vals, p):
    v = sorted(vals)
    k = (len(v) - 1) * p
    i = int(k)
    return v[i] + (v[min(i + 1, len(v) - 1)] - v[i]) * (k - i)


def stats(vals):
    return {"n": len(vals), "min": min(vals), "p25": q(vals, 0.25), "med": st.median(vals), "p75": q(vals, 0.75),
            "max": max(vals)}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    acs = load()
    bad, sums = check(acs)
    rows = per_aircraft(acs, airframes())
    with (OUT / "mass_breakdown.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    def ok(r, cat):
        return cat not in r["lumped"].split("+")
    # normalised component masses (drivers: wing area for wing and tail, max gross mass for gear
    # and fuselage, absolute for propulsion of one motor and avionics)
    norm = {
        "wing_kg_per_m2": [r["wing_kg"] / r["S_m2"] for r in rows if r["S_m2"] and ok(r, "propulsion") and ok(r, "avionics")],
        "empennage_kg_per_m2_wing": [r["empennage_kg"] / r["S_m2"] for r in rows if r["S_m2"] and r["empennage_kg"]],
        "gear_frac_of_gross_max": [r["gear_kg"] / r["gross_max_kg"] for r in rows
                                   if r["gross_max_kg"] and ok(r, "gear") and r["gear_kg"]],
        "fuselage_frac_of_gross_max": [r["fuselage_kg"] / r["gross_max_kg"] for r in rows
                                       if r["gross_max_kg"] and ok(r, "gear") and ok(r, "propulsion") and ok(r, "avionics")],
        "avionics_kg": [r["avionics_kg"] for r in rows if ok(r, "avionics") and r["avionics_kg"]],
        "propulsion_kg": [r["propulsion_kg"] for r in rows if ok(r, "propulsion") and r["propulsion_kg"]],
        "payload_system_kg": [r["payload_system_kg"] for r in rows if r["payload_system_kg"]],
    }
    S = {k: stats(v) for k, v in norm.items() if v}
    fit = 5.96 * REF["S"] ** 0.94
    parts = {
        "wing": [S["wing_kg_per_m2"][k] * REF["S"] for k in ("p25", "med", "p75")],
        "empennage": [S["empennage_kg_per_m2_wing"][k] * REF["S"] for k in ("p25", "med", "p75")],
        "fuselage": [S["fuselage_frac_of_gross_max"][k] * REF["gross_max"] for k in ("p25", "med", "p75")],
        "gear": [S["gear_frac_of_gross_max"][k] * REF["gross_max"] for k in ("p25", "med", "p75")],
        "propulsion": [S["propulsion_kg"][k] for k in ("p25", "med", "p75")],
        "avionics": [S["avionics_kg"][k] for k in ("p25", "med", "p75")],
    }
    lo, mid, hi = (sum(v[i] for v in parts.values()) for i in range(3))
    report(rows, bad, sums, S, parts, (lo, mid, hi), fit)
    chart(rows, S)


def report(rows, bad, sums, S, parts, tot, fit):
    L = []
    p = L.append
    p("Airframe mass by component, AIAA top-3 weight-and-balance tables (mass_breakdown.py, PROVISIONAL)")
    p(f"{len(rows)} aircraft, 2021-2026 (data/dbf_components.toml). Quote checks: "
      + ("all text rows found on their pages" if not bad else f"{len(bad)} PROBLEMS"))
    for b in bad:
        p("   " + b)
    p("")
    p("Sum check: rows against each table's own printed total (a mismatch is the table's, reported as is):")
    for tag, u, s, tv, d, r in sums:
        flag = "" if abs(r) <= 0.01 else "   <-- table does not add up"
        p(f"   {tag:<20} rows {s:>9.3f} {u:<2} printed {tv:>9.3f}  diff {d:+.3f} ({r:+.1%}){flag}")
    p("")
    p("Per aircraft, kg (airframe = all but propulsion battery, payload, ballast); 'lumped' = merged by the team:")
    p(f"   {'aircraft':<16}{'wing':>6}{'fuse':>6}{'emp':>6}{'gear':>6}{'prop':>6}{'avio':>6}{'payl':>6}{'oth':>5}"
      f"{'frame':>7}{'S m2':>6}{'kg/m2':>6}  lumped / basis")
    for r in rows:
        p(f"   {r['year']} {r['short']:<11}{r['wing_kg']:>6.2f}{r['fuselage_kg']:>6.2f}{r['empennage_kg']:>6.2f}"
          f"{r['gear_kg']:>6.2f}{r['propulsion_kg']:>6.2f}{r['avionics_kg']:>6.2f}{r['payload_system_kg']:>6.2f}"
          f"{r['other_kg']:>5.2f}{r['airframe_kg']:>7.2f}{r['S_m2'] or 0:>6.2f}"
          f"{(r['airframe_kg'] / r['S_m2']) if r['S_m2'] else 0:>6.2f}  {r['lumped'] or '-'} / {r['basis']}")
    shares = {c: [r[f"{c}_kg"] / r["airframe_kg"] for r in rows if not r["lumped"]] for c in
              ("wing", "fuselage", "empennage", "gear", "propulsion", "avionics", "payload_system")}
    p("   Share of airframe, aircraft with nothing lumped (n = %d): " % len(shares["wing"]) + ", ".join(
        f"{c} {st.median(v):.0%}" for c, v in shares.items()))
    p("")
    p("Normalised (median, P25-P75, min-max, n):")
    for k, s in S.items():
        p(f"   {k:<28} {s['med']:.3f}  ({s['p25']:.3f}-{s['p75']:.3f}; {s['min']:.3f}-{s['max']:.3f}; n {s['n']})")
    p("")
    p(f"Bottom-up budget for the reference design (S {REF['S']} m2, M2 gross {REF['gross_max']} kg), P25 / median / P75, kg:")
    for c, v in parts.items():
        p(f"   {c:<11} {v[0]:.2f} / {v[1]:.2f} / {v[2]:.2f}")
    p(f"   total       {tot[0]:.2f} / {tot[1]:.2f} / {tot[2]:.2f}   (without the payload mechanism; Script 4 adds")
    p("               the 0.32 kg reel separately, sizing.toml [dr])")
    p(f"   Script 4 fit 5.96 S^0.94 = {fit:.2f} kg at S {REF['S']} (scatter x1.31 at 1 sd: {fit/1.31:.2f}-{fit*1.31:.2f})")
    p("")
    p("Notes:")
    p("- Drivers are assumptions: wing and tail scale with wing area, fuselage and gear with the heaviest")
    p("  gross mass, propulsion and avionics are taken as absolute (one motor; the twin aircraft are in the")
    p("  propulsion sample, so its upper quartile is high). Our own parts (motor, ESC, servos) replace these")
    p("  medians once chosen.")
    p("- Bases differ: 'measured' tables were weighed; 'design' and 'mixed' are CAD or estimates.")
    p("- The fit's airframe masses include each team's payload mechanism; Script 4 also adds our reel")
    p("  (0.32 kg) on top. The payload_system column shows what the field's mechanisms weighed.")
    (OUT / "mass_breakdown_report.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


def chart(rows, S):
    sys.path.insert(0, str(HERE.parent / "design-system" / "matplotlib"))
    import dbfplot as dp
    dp.use()
    title = dict(fontsize=5.6, family=dp.MONO, color=dp.GRAPHITE, loc="left")
    fig, (a1, a2) = dp.figure("page", 2.7, ncols=2, gridspec_kw={"width_ratios": [1.6, 1]})
    order = sorted(rows, key=lambda r: r["airframe_kg"])
    shades = {"wing": dp.INK, "fuselage": dp.GRAPHITE, "empennage": dp.STEEL, "gear": dp.FOG,
              "propulsion": "#C9CDD3", "avionics": dp.MIST, "payload_system": dp.BONE, "other": "white"}
    x = range(len(order))
    base = [0.0] * len(order)
    for c, col in shades.items():
        v = [r[f"{c}_kg"] for r in order]
        a1.bar(x, v, bottom=base, color=col, edgecolor=dp.INK, linewidth=0.3, width=0.75,
               label=c.replace("_", " ").upper())
        base = [b + y for b, y in zip(base, v)]
    a1.set_xticks(list(x))
    a1.set_xticklabels([f"{r['short']} {str(r['year'])[2:]}" + ("*" if r["lumped"] else "") for r in order],
                       rotation=60, ha="right", fontsize=4.6)
    a1.set_ylabel("Airframe mass (kg)")
    leg = a1.legend(loc="upper left", fontsize=4.2, frameon=False, ncol=2)
    for t in leg.get_texts():
        t.set_family(dp.MONO)
    a1.set_title("AIRFRAME BY COMPONENT, TOP-3 W&B TABLES (* = LUMPED ROWS)", **title)
    pts = [r for r in rows if r["S_m2"] and "propulsion" not in r["lumped"] and "avionics" not in r["lumped"]]
    a2.plot([r["S_m2"] for r in pts], [r["wing_kg"] for r in pts], "o", ms=3, mfc="white", mec=dp.INK)
    for r in pts:
        a2.annotate(f"{r['short']} {str(r['year'])[2:]}", (r["S_m2"], r["wing_kg"]), xytext=(3, 2),
                    textcoords="offset points", fontsize=4.0, family=dp.MONO)
    s = S["wing_kg_per_m2"]
    xs = [0.2, 1.05]
    a2.plot(xs, [s["med"] * v for v in xs], "-", color=dp.INK, lw=0.8)
    a2.fill_between(xs, [s["p25"] * v for v in xs], [s["p75"] * v for v in xs], color=dp.FOG, alpha=0.35, lw=0)
    a2.axvline(REF["S"], color=dp.STEEL, lw=0.6, ls=":")
    a2.set_xlabel("Wing area (m²)")
    a2.set_ylabel("Wing mass (kg)")
    a2.set_title(f"WING: MEDIAN {s['med']:.2f} KG/M² (BAND P25-P75)", **title)
    fig.tight_layout()
    dp.save(fig, OUT / "mass_breakdown.pdf")
    print("wrote out/mass_breakdown.pdf")


if __name__ == "__main__":
    main()
