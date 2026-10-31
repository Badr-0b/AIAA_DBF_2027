# Copyright © 2026 Badr Obtel. All rights reserved.
"""Field statistics from five years of AIAA results (TOOLING).

    python analysis/data/field_stats.py

Input: dbf_results.csv (parse_results.py; every row arithmetic-checked).
Output: field_stats.csv, field_bonus.csv, and charts in analysis/out/:
  field_completion.pdf   how many teams complete each mission, 2022-2026
  field_bonus.pdf        each mission's bonus as a fraction of the field max
  field_proposal.pdf     proposal scores of the invited teams, 2025-2026

A mission counts as completed when its published score is above zero. The
bonus is score minus the completion credit (M2 - 1, M3 - 2), i.e. the
team's fraction of the field maximum; GM formulas changed every year, so GM
is reported as completion only.
"""
import csv
import statistics as st
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / "design-system" / "matplotlib"))
import dbfplot as dp  # noqa: E402
from common import OUT  # noqa: E402

YEARS = (2022, 2023, 2024, 2025, 2026)


def load():
    rows = list(csv.DictReader((HERE / "dbf_results.csv").open(encoding="utf-8")))
    for r in rows:
        r["year"] = int(r["year"])
        for k in ("p", "gm", "m1", "m2", "m3", "total", "proposal", "design", "report", "score"):
            r[k] = float(r[k]) if r.get(k) not in (None, "") else None
    assert all(r["check"] == "ok" for r in rows), "dbf_results.csv has unchecked rows"
    return rows


def stats(rows):
    out = []
    for y in YEARS:
        R = [r for r in rows if r["year"] == y]
        flew = [r for r in R if r["p"] == 3] if R[0]["p"] is not None else \
               [r for r in R if (r["m1"] or r["m2"] or r["m3"] or r["gm"])]
        done = {m: sum(1 for r in R if (r[m] or 0) > 0) for m in ("gm", "m1", "m2", "m3")}
        all4 = sum(1 for r in R if all((r[m] or 0) > 0 for m in ("gm", "m1", "m2", "m3")))
        out.append({
            "year": y, "reports": len(R),
            "passed_tech": sum(1 for r in R if (r["p"] or 0) >= 2) if R[0]["p"] is not None else "",
            "attempted_flight": len(flew) if R[0]["p"] is not None else "",
            "completed_m1": done["m1"], "completed_m2": done["m2"], "completed_m3": done["m3"],
            "completed_gm": done["gm"], "completed_all": all4,
            "m2_given_m1": round(done["m2"] / done["m1"], 3) if done["m1"] else "",
            "m3_given_m2": round(done["m3"] / done["m2"], 3) if done["m2"] else "",
        })
    return out


def bonus(rows):
    out = []
    for y in YEARS:
        for m, base in (("m2", 1.0), ("m3", 2.0)):
            b = sorted((r[m] - base for r in rows if r["year"] == y and (r[m] or 0) > 0), reverse=True)
            out.append({"year": y, "mission": m.upper(), "completers": len(b),
                        "max": round(b[0], 2), "second": round(b[1], 2),
                        "p75": round(st.quantiles(b, n=4)[2], 2), "median": round(st.median(b), 2),
                        "p25": round(st.quantiles(b, n=4)[0], 2), "values": b})
    return out


def write_csv(path, rows, drop=()):
    keys = [k for k in rows[0] if k not in drop]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def chart_completion(S):
    dp.use()
    fig, ax = dp.figure("col", 2.2)
    stages = (("reports", "REPORT"), ("completed_m1", "M1"), ("completed_m2", "M2"),
              ("completed_m3", "M3"), ("completed_all", "ALL 4"))
    x = range(len(stages))
    greys = {2022: dp.FOG, 2023: dp.FOG, 2024: dp.STEEL, 2025: dp.STEEL, 2026: dp.INK}
    styles = {2022: (0, (1, 1.5)), 2023: "--", 2024: (0, (1, 1.5)), 2025: "--", 2026: "-"}
    for s in S:
        ys = [100 * s[k] / s["reports"] for k, _ in stages]
        ax.plot(x, ys, color=greys[s["year"]], ls=styles[s["year"]], lw=1.0 if s["year"] == 2026 else 0.8,
                marker="o", ms=2.4, label=str(s["year"]))
    ax.set_xticks(list(x), [lab for _, lab in stages])
    ax.set_ylabel("Teams with a design report (%)")
    ax.set_ylim(0, 105)
    leg = ax.legend(loc="upper right", fontsize=5.4, ncol=2)
    for t in leg.get_texts():
        t.set_family(dp.MONO)
    dp.save(fig, OUT / "field_completion.pdf")


def chart_bonus(B):
    dp.use()
    fig, axes = dp.figure("col", 2.3, ncols=2, sharey=True)
    for ax, m in zip(axes, ("M2", "M3")):
        rows = [b for b in B if b["mission"] == m]
        for i, b in enumerate(rows):
            vals = b["values"]
            ax.scatter([i] * len(vals), vals, s=3, color=dp.STEEL, lw=0, zorder=2)
            ax.plot([i - 0.3, i + 0.3], [b["median"]] * 2, color=dp.INK, lw=1.2, zorder=3)
        ax.set_xticks(range(len(rows)), [str(b["year"])[2:] for b in rows])
        ax.set_xlabel(f"{m}: year (20xx)")
        ax.set_ylim(-0.02, 1.05)
    axes[0].set_ylabel("Bonus, fraction of the field max")   # bars: median completer
    dp.save(fig, OUT / "field_bonus.pdf")


def chart_proposal(rows):
    dp.use()
    fig, ax = dp.figure("col", 2.0)
    for y, colour in ((2025, dp.FOG), (2026, dp.INK)):
        vals = sorted(r["proposal"] for r in rows if r["year"] == y and r["proposal"] is not None)
        ax.hist(vals, bins=range(55, 95, 2), histtype="step", color=colour, lw=1.0, label=f"{y} (n={len(vals)})")
        ax.axvline(min(vals), color=colour, lw=0.6, ls="--")
    ax.set_xlabel("Proposal score of invited teams (out of 100)")
    ax.set_ylabel("Teams")
    leg = ax.legend(loc="upper right", bbox_to_anchor=(1.0, 0.88), fontsize=5.4)
    for t in leg.get_texts():
        t.set_family(dp.MONO)
    dp.tag(ax, "DASHED = LOWEST INVITED", "upper right")
    dp.save(fig, OUT / "field_proposal.pdf")


def main():
    rows = load()
    S, B = stats(rows), bonus(rows)
    write_csv(HERE / "field_stats.csv", S)
    write_csv(HERE / "field_bonus.csv", B, drop=("values",))
    OUT.mkdir(exist_ok=True)
    chart_completion(S)
    chart_bonus(B)
    chart_proposal(rows)
    print("year reports tech flew  M1  M2  M3  GM all4  M2|M1  M3|M2")
    for s in S:
        print(f"{s['year']} {s['reports']:7} {s['passed_tech']!s:>4} {s['attempted_flight']!s:>4} "
              f"{s['completed_m1']:3} {s['completed_m2']:3} {s['completed_m3']:3} {s['completed_gm']:3} "
              f"{s['completed_all']:4}  {s['m2_given_m1']:.2f}   {s['m3_given_m2']:.2f}")
    print("\nbonus (fraction of field max) among completers: max / 2nd / p75 / median / p25")
    for b in B:
        print(f"{b['year']} {b['mission']}  n={b['completers']:3}  {b['max']:.2f} / {b['second']:.2f} / "
              f"{b['p75']:.2f} / {b['median']:.2f} / {b['p25']:.2f}")
    for y in (2025, 2026):
        v = sorted(r["proposal"] for r in rows if r["year"] == y and r["proposal"] is not None)
        print(f"{y} proposal scores of invited teams: min {v[0]:.0f}, median {st.median(v):.0f}, max {v[-1]:.0f}, n={len(v)}")


if __name__ == "__main__":
    main()
