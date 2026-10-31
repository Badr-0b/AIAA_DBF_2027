# Copyright © 2026 Badr Obtel. All rights reserved.
"""Configuration field practice of the AIAA top-3 design reports, with fly-off outcomes (TOOLING).

    python analysis/data/config_evidence.py

Input: dbf_aircraft.csv (every configuration value is a verified verbatim quote)
and dbf_results.csv (verified AIAA results, 2022-2026). Writes dbf_config.csv and
analysis/out/config_practice.pdf.

Categories are read from the quoted wording (e.g. "high-wing", "high rectangular
wing" -> high). Outcome = the same team's result at that year's fly-off; 2021
had no comparable fly-off in the dataset. Fisher's exact test (two-sided) is
computed directly from the hypergeometric distribution. The samples are small
and confounded by team experience and each year's missions, so the tests say
whether a pattern is distinguishable from chance, not why.
"""
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / "design-system" / "matplotlib"))

RESULT_NAME = {  # (year, team in dbf_aircraft) -> team as printed in that year's results
    (2022, "FH JOANNEUM University of Applied Sciences"): "FH JOANNEUM University of Applied Sciences",
    (2022, "Massachusetts Institute of Technology"): "Massachusetts Institute of Technology",
    (2022, "Washington University in St. Louis"): "Washington University in St. Louis",
    (2023, "University of Washington"): "University of Washington Seattle",
    (2023, "Embry-Riddle Aeronautical University, Daytona Beach"): "Embry-Riddle Aeronautical University, Daytona Beach",
    (2023, "Virginia Polytechnic Institute and State University"): "Virginia Polytechnic Institute and State University",
    (2024, "University of Southern California"): "University of Southern California",
    (2024, "University of Ljubljana"): "University of Ljubljana",
    (2024, "Virginia Polytechnic Institute and State University"): "Virginia Polytechnic Institute and State University",
    (2025, "University of New South Wales"): "University of New South Wales",
    (2025, "University of California, Los Angeles"): "University of California, Los Angeles",
    (2025, "Embry-Riddle Aeronautical University, Daytona Beach"): "Embry-Riddle Aeronautical University, Daytona Beach",
    (2026, "University of Southern California"): "University of Southern California",
    (2026, "University of Ljubljana"): "University of Ljubljana",
    (2026, "Georgia Institute of Technology"): "Georgia Institute of Technology",
}


def category(param, text):
    t = text.lower()
    if param == "wing_position":
        return "high" if "high" in t else "low" if "low" in t else "mid" if "mid" in t else "?"
    if param == "gear":
        return ("taildragger" if ("tail" in t and "drag" in t) else "tricycle" if ("tricycle" in t or "nose gear" in t)
                else "quadricycle" if "quadricycle" in t else "?")
    if param == "tail":
        return ("T-tail" if t.endswith("t-tail") or t == "t-tail" else "inverted V" if "inverted" in t
                else "conventional" if ("conventional" in t or "traditional" in t) else "?")
    if param == "propulsion":
        motors = 2 if any(w in t for w in ("twin", "dual")) else 1 if any(w in t for w in ("single", "tractor")) else None
        return {1: "single motor", 2: "twin motors"}.get(motors, "?")
    return text


def fisher_two_sided(a, b, c, d):
    """Fisher's exact test, two-sided, for the 2x2 table [[a, b], [c, d]]."""
    n1, n2, k, n = a + b, c + d, a + c, a + b + c + d
    def p(x):
        return math.comb(n1, x) * math.comb(n2, k - x) / math.comb(n, k)
    p0 = p(a)
    lo, hi = max(0, k - n2), min(k, n1)
    return min(1.0, sum(p(x) for x in range(lo, hi + 1) if p(x) <= p0 * (1 + 1e-9)))


def build():
    rows = list(csv.DictReader((HERE / "dbf_aircraft.csv").open(encoding="utf-8")))
    res = {(int(r["year"]), r["team"]): r for r in csv.DictReader((HERE / "dbf_results.csv").open(encoding="utf-8"))}
    cfg = defaultdict(dict)
    for r in rows:
        if r["param"] in ("wing_position", "gear", "tail", "propulsion", "fuselage"):
            cfg[(int(r["year"]), r["team"])][r["param"]] = r["value"]
    out = []
    for (year, team), c in sorted(cfg.items()):
        row = {"year": year, "team": team, **{p: c.get(p, "") for p in ("wing_position", "gear", "tail", "propulsion", "fuselage")}}
        for p in ("wing_position", "gear", "tail", "propulsion"):
            row[p + "_cat"] = category(p, c[p]) if c.get(p) else "not stated"
        r = res.get((year, RESULT_NAME.get((year, team), "")))
        row.update({"rank": r["rank"] if r else "", "score": r["score"] if r else "",
                    "completed_m2": (float(r["m2"]) > 0) if r else "", "completed_m3": (float(r["m3"]) > 0) if r else ""})
        out.append(row)
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    rows = build()
    with (HERE / "dbf_config.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{'aircraft':10} {'wing':5} {'gear':12} {'tail':13} {'propulsion':13} rank  M2  M3")
    for r in rows:
        print(f"{r['year']} {r['team'][:22]:22} {r['wing_position_cat']:5} {r['gear_cat']:12} {r['tail_cat']:13} "
              f"{r['propulsion_cat']:13} {str(r['rank']):>4}  {'' if r['completed_m2'] == '' else ('yes' if r['completed_m2'] else 'NO'):3} "
              f"{'' if r['completed_m3'] == '' else ('yes' if r['completed_m3'] else 'NO')}")
    flown = [r for r in rows if r["completed_m3"] != ""]
    print(f"\nAll 19 aircraft, counts:")
    for p in ("wing_position", "gear", "tail", "propulsion"):
        counts = defaultdict(int)
        for r in rows:
            counts[r[p + "_cat"]] += 1
        print(f"  {p:14} " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1])))
    print(f"\nFly-off outcome, 2022-2026 ({len(flown)} aircraft): completed M3 "
          f"{sum(r['completed_m3'] for r in flown)} of {len(flown)}")
    tests = (("wing_position", "high", "low"), ("propulsion", "single motor", "twin motors"),
             ("gear", "tricycle", "taildragger"))
    for p, a_cat, b_cat in tests:
        A = [r for r in flown if r[p + "_cat"] == a_cat]
        B = [r for r in flown if r[p + "_cat"] == b_cat]
        a, b = sum(r["completed_m3"] for r in A), len(A) - sum(r["completed_m3"] for r in A)
        c, d = sum(r["completed_m3"] for r in B), len(B) - sum(r["completed_m3"] for r in B)
        print(f"  {p:14} {a_cat:12} completed M3 {a} of {a + b};  {b_cat:12} {c} of {c + d};  "
              f"Fisher exact p = {fisher_two_sided(a, b, c, d):.2f}")
    chart(rows)


LABEL = {"taildragger": "tail-dr.", "tricycle": "tricycle", "quadricycle": "quad", "conventional": "conv.",
         "inverted V": "inv. V", "single motor": "1", "twin motors": "2", "not stated": "n/s"}


def chart(rows):
    import dbfplot as dp
    from common import OUT
    OUT.mkdir(exist_ok=True)
    dp.use()
    cols = [("wing_position_cat", "WING"), ("gear_cat", "GEAR"), ("tail_cat", "TAIL"), ("propulsion_cat", "MOTORS")]
    fig, ax = dp.figure("col", 3.0)
    for i, r in enumerate(rows):
        y = len(rows) - 1 - i
        for j, (k, _) in enumerate(cols):
            ax.text(j, y, LABEL.get(r[k], r[k]).upper(), ha="center", va="center",
                    fontsize=4.6, family=dp.MONO, color=dp.INK)
        out = r["completed_m3"]
        mark, txt = (("o", "M3 DONE") if out is True else ("x", "M3 FAILED") if out is False else ("", "NO FLY-OFF DATA"))
        if mark:
            ax.plot(len(cols) - 0.35, y, mark, ms=3.4, color=dp.INK, mfc=dp.INK if out else "none")
        ax.text(len(cols) - 0.15, y, f"{txt}{'  #' + str(r['rank']) if r['rank'] else ''}", va="center", fontsize=4.4,
                family=dp.MONO, color=dp.STEEL)
    from aircraft_model import SHORT
    ax.set_yticks(range(len(rows)), [f"{SHORT.get(r['team'], r['team'])} {str(r['year'])[2:]}" for r in reversed(rows)],
                  fontsize=4.6, family=dp.MONO)
    ax.set_xticks(range(len(cols)), [c[1] for c in cols], fontsize=5, family=dp.MONO)
    ax.xaxis.tick_top()
    ax.set_xlim(-0.6, len(cols) + 1.6)
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.grid(False)
    for s in ("left", "right", "bottom", "top"):
        ax.spines[s].set_visible(False)
    dp.save(fig, OUT / "config_practice.pdf")


if __name__ == "__main__":
    main()
