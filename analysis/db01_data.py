# Copyright © 2026 Badr Obtel. All rights reserved.
"""Numbers for decision brief DB-01 that no other report prints (PROVISIONAL).

    python analysis/db01_data.py          (after s6_studies.py)

Uses Script 6's model and its 120 paired draws (the D&R mechanism included:
sizing.toml [dr]). Writes out/db01_report.txt and out/db01_stall.pdf:
  1. stall-bound sweep: the robust best wing area and payload unit for each
     accepted 1 g stall speed, on a wider wing-area grid than Script 6's map;
  2. payload-unit comparison at the robust reference wing: mean, spread,
     P(M2 feasible) and the mission parts for each unit mass;
  3. the M1 waiver: P(M3 completed) flying M1 against waiving it.
Nothing here decides anything (user, 13 Oct).
"""
import copy
import sys

import numpy as np

import common
from common import OUT
import s6_studies as s6
from config_trades import ref_point

sys.path.insert(0, str(common.ANALYSIS / "data"))
from attempts import p_complete  # noqa: E402

STALLS = [11.0, 12.0, 13.0, 14.0, 15.0, 16.0]
AREAS = np.round(np.arange(0.6, 1.4 + 1e-9, 0.1), 6)
UNITS = np.arange(2.0, 9.0 + 1e-9, 1.0)


def stall_sweep(Ps):
    rows = []
    for vs in STALLS:
        Pv = []
        for P in Ps:
            Q = copy.copy(P)
            Q.vs_max = vs
            Pv.append(Q)
        best = None
        for s in AREAS:
            for u in UNITS:
                r = [s6.evaluate("straight", s, u, Q) for Q in Pv]
                if not all(r):
                    continue
                tot = np.array([x["expected"]["total"] for x in r])
                feas = np.mean([x["m2_feasible"] for x in r])
                if best is None or tot.mean() > best["mean"]:
                    best = {"vs": vs, "s": float(s), "unit": float(u), "mean": float(tot.mean()),
                            "p10": float(np.percentile(tot, 10)), "p90": float(np.percentile(tot, 90)),
                            "feas": float(feas), "edge": bool(s >= AREAS[-1] - 1e-9)}
        rows.append(best)
    return rows


def unit_table(Ps, s):
    rows = []
    for u in UNITS:
        r = [s6.evaluate("straight", s, u, P) for P in Ps]
        if not all(r):
            continue
        tot = np.array([x["expected"]["total"] for x in r])
        part = {k: float(np.mean([x["expected"][k] for x in r])) for k in ("M2", "M3", "GM")}
        rows.append({"unit": float(u), "sensor": float(u - s6.ST["design"]["container_kg"]), "mean": float(tot.mean()),
                     "p10": float(np.percentile(tot, 10)), "p50": float(np.median(tot)),
                     "p90": float(np.percentile(tot, 90)),
                     "feas": float(np.mean([x["m2_feasible"] for x in r])), **part,
                     "nsim": float(np.mean([x["expected"]["n_sim"] for x in r]))})
    return rows


def chart(sweep):
    sys.path.insert(0, str(common.REPO / "design-system" / "matplotlib"))
    import dbfplot as dp
    dp.use()
    fig, ax = dp.figure("col", 2.2)
    vs = [r["vs"] for r in sweep]
    ax.plot(vs, [r["mean"] for r in sweep], color=dp.INK, lw=1.2, marker="o", ms=3)
    ax.fill_between(vs, [r["p10"] for r in sweep], [r["p90"] for r in sweep], color=dp.MIST, lw=0)
    for r in sweep:
        ax.annotate(f"{r['s']:.1f} m²\n{r['unit']:.0f} kg unit", (r["vs"], r["mean"]), xytext=(0, 7),
                    textcoords="offset points", ha="center", fontsize=4.6, family=dp.MONO, color=dp.GRAPHITE)
    ax.set_ylim(top=7.7)
    ax.set_xlabel("Accepted 1 g stall speed at M2 weight (m/s)")
    ax.set_ylabel("Total mission score, robust best")
    dp.tag(ax, "BAND: P10-P90 OVER 120 DRAWS", "lower right")
    dp.save(fig, OUT / "db01_stall.pdf")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    mc = s6.ST["monte_carlo"]
    Ps = s6.draws(mc["draws"], mc["seed"])
    s_ref, u_ref = ref_point()
    out = ["DB-01 numbers (Script 6 model with the D&R mechanism; 120 paired draws; expected field)."]
    sweep = stall_sweep(Ps)
    out.append(f"\n1. Stall-bound sweep (wing area {AREAS[0]}-{AREAS[-1]} m2, unit {UNITS[0]:.0f}-{UNITS[-1]:.0f} kg):")
    out.append("  stall m/s   best S m2   unit kg   mean   P10    P90    P(M2 feasible)")
    for r in sweep:
        out.append(f"  {r['vs']:8.0f}   {r['s']:9.1f}   {r['unit']:7.0f}   {r['mean']:.2f}   {r['p10']:.2f}   "
                   f"{r['p90']:.2f}   {100 * r['feas']:5.0f} %" + ("   (grid edge)" if r["edge"] else ""))
    units = unit_table(Ps, s_ref)
    out.append(f"\n2. Payload unit at the reference wing S {s_ref:.2f} m2 (14 m/s stall):")
    out.append(f"  (sensor = unit - {s6.ST['design']['container_kg']} kg baseline container; draws vary the container 0.4-1.0 kg)")
    out.append("  unit kg  sensor kg  mean   P10    P50    P90    P(M2)   M2     M3     GM     mean N_sim")
    for r in units:
        out.append(f"  {r['unit']:6.0f}   {r['sensor']:8.1f}   {r['mean']:.2f}   {r['p10']:.2f}   {r['p50']:.2f}   "
                   f"{r['p90']:.2f}   {100 * r['feas']:4.0f} %  {r['M2']:.2f}   {r['M3']:.2f}   {r['GM']:.2f}   "
                   f"{r['nsim']:.2f}")
    rel = s6.ST["reliability"]
    out.append("\n3. M1 waiver, P(M3 completed) (M1 0.95 per attempt: 73 of 74 teams that flew in 2026):")
    for p in (0.55, 0.65, 0.75):
        for a in (3, 4):
            fly, waive = p_complete((0.95, p, p), a), p_complete((p, p), a)
            out.append(f"  p {p:.2f}, {a} attempts: fly M1 {100 * fly:4.0f} %   waive {100 * waive:4.0f} %")
    out.append(f"  (Script 6 uses p {rel['p_attempt']} and {rel['attempts']} attempts.)")
    text = "\n".join(out)
    print(text)
    (OUT / "db01_report.txt").write_text(text + "\n", encoding="utf-8")
    chart(sweep)
    print("\nwrote out/db01_report.txt, out/db01_stall.pdf")


if __name__ == "__main__":
    main()
