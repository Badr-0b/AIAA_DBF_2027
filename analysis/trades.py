# Copyright © 2026 the members of the AUM AIAA DBF team. All rights reserved.
"""Audit and re-weighting of the team's configuration trade matrices (PROVISIONAL).

    python analysis/trades.py          (after s6_studies.py)

Input: inputs/trades.toml. It holds the team's six matrices (Matrix_Tables/,
10 Oct), digitised verbatim with their printed totals, plus Claude's audit
entries (score changes, each with its evidence). Also out/s6_trade_weights.csv,
the Script 6 sensitivity weights.

For each matrix the script reports:
  1. arithmetic: printed total against the recomputed weighted sum;
  2. the totals as made, audited, and with sensitivity-derived weights. Each
     category total comes from Script 6 (renormalised over the categories
     present), split inside the category in the team's own proportions;
  3. robustness: Monte Carlo over the weights (Dirichlet about the weights used)
     and the scores (+/-1 with probability 1/4 each), as P(each option first).
Nothing here decides a configuration (user, 13 Oct). Writes out/trades_report.txt
and out/trades_robustness.pdf.
"""
import csv
import sys

import numpy as np

import common
from common import OUT

T = common.load("trades")
CATEGORY = {"Mission completion (reliability)": "completion", "Turn and lap performance": "turn",
            "High lift (CLmax)": "clmax", "Airframe mass": "mass", "Propulsive efficiency": "prop",
            "Induced drag (e)": "e", "Parasite drag": "drag", "Structural load capability": "structure"}


def sensitivity_category_weights():
    rows = csv.DictReader((OUT / "s6_trade_weights.csv").open(encoding="utf-8"))
    return {CATEGORY[r["criterion"]]: float(r["weight"]) for r in rows}


def totals(scores, weights):
    """Weighted score in percent of the maximum (scores 1-5, weights summing to 1)."""
    return 100 * (np.asarray(weights) @ np.asarray(scores, dtype=float)) / 5


def sensitivity_weights(matrix, cat_w):
    """Category totals from Script 6 (renormalised over the categories present); inside a
    category the team's own relative weights are kept, so their judgment of which
    reliability item matters more survives, while the balance between categories is data."""
    cats = [c[3] for c in matrix["criteria"]]
    w0 = np.array([c[1] for c in matrix["criteria"]], dtype=float)
    present = {c: cat_w.get(c, 0.0) for c in set(cats)}
    total = sum(present.values())
    within = {c: w0[[k for k, x in enumerate(cats) if x == c]].sum() for c in present}
    return np.array([present[c] / total * w0[k] / within[c] for k, c in enumerate(cats)])


def audited_scores(matrix):
    scores = [list(c[2]) for c in matrix["criteria"]]
    changes = []
    for a in T.get("audit", []):
        if a["matrix"] == matrix["id"]:
            i = [c[0] for c in matrix["criteria"]].index(a["criterion"])
            changes.append((a["criterion"], scores[i], a["scores"], a["reason"]))
            scores[i] = a["scores"]
    return np.array(scores, dtype=float), changes


def p_first(scores, weights, rng, n=5000, alpha=40.0):
    """P(each option ranks first) under weight and score perturbation."""
    k, m = scores.shape
    wins = np.zeros(m)
    W = rng.dirichlet(alpha * np.asarray(weights) + 1e-9, size=n)
    noise = rng.choice([-1, 0, 1], p=[0.25, 0.5, 0.25], size=(n, k, m))
    S = np.clip(scores[None, :, :] + noise, 1, 5)
    tot = np.einsum("nk,nkm->nm", W, S)
    for row in tot:
        best = np.flatnonzero(row == row.max())
        wins[best] += 1.0 / len(best)                 # ties share the win
    return wins / n


VERDICT = {
    "tail": "Do not use as made. Its decisive criterion (line clearance, 25 %) is set by the exit location, not the "
            "tail type (hang angle 31-86 deg), and it rates the T-tail strongest structurally, the reverse of "
            "standard practice. After the audit the three options are close. Field practice: conventional 16 of 19.",
    "wing_position": "Usable framework; the as-made 91 vs 51 overstates certainty. Low-wing top-3 teams chose low wing "
                     "for payload access, and low-wing designs completed M3 5 of 6 times (high 4 of 9, p = 0.29). "
                     "Decide on the sensor exit path, staging access and the pilot.",
    "fuselage_structure": "Arithmetic fixed (68 / 64 / 90); ranking unchanged. Missing a structural-mass criterion, "
                          "although airframe mass is the second-strongest global sensitivity (Spearman -0.62). "
                          "Belongs in the manufacturing plan and the design report, not Table 05.",
    "airfoil": "Drop. The arithmetic error flips the winner (E423 76 over S1223 74), and the proposal already "
               "chooses the airfoil quantitatively (Fig. 05: 13 sections, XFoil, race-envelope c_l/c_d).",
    "planform": "Drop. Four of its five criteria are copied from the wing-position matrix and do not depend on "
                "planform; planform is set by span efficiency, stall behaviour, root bending and manufacturing "
                "(Scripts 3-4, XFLR5).",
    "landing_gear": "Usable; it is a tie (4.00 each) once the arithmetic is fixed. Field outcomes do not separate the "
                    "two (p = 1.00); the pilot's preference, crosswind handling and the sensor exit decide it. "
                    "Fixed rather than retractable (break-even 120-240 g).",
}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    rng = np.random.default_rng(2027)
    cat_w = sensitivity_category_weights()
    print("Category weights from Script 6: " + ", ".join(f"{k} {100 * v:.1f} %" for k, v in cat_w.items()))
    results = {}
    for m in T["matrix"]:
        opts = m["options"]
        w0 = np.array([c[1] for c in m["criteria"]], dtype=float) / 100
        s0 = np.array([c[2] for c in m["criteria"]], dtype=float)
        sa, changes = audited_scores(m)
        ws = sensitivity_weights(m, cat_w)
        t_made, t_aud, t_sens = totals(s0, w0), totals(sa, w0), totals(sa, ws)
        printed = np.array(m["printed_total"], dtype=float) * (20 if m["total_scale"] == "of5" else 1)
        p_made = p_first(s0, w0, rng)
        p_ev = p_first(sa, ws, rng)
        results[m["id"]] = (opts, p_made, p_ev)
        print(f"\n== {m['title']} ({m['file']})")
        print("  option              printed  recomputed  audited  audited + sensitivity weights | P(first) as made / evidence-weighted")
        for i, o in enumerate(opts):
            flag = "  ARITHMETIC ERROR" if abs(printed[i] - t_made[i]) > 0.6 else ""
            print(f"  {o:18} {printed[i]:7.1f}  {t_made[i]:10.1f}  {t_aud[i]:7.1f}  {t_sens[i]:29.1f} | "
                  f"{100 * p_made[i]:5.0f} % / {100 * p_ev[i]:5.0f} %{flag}")
        print("  sensitivity weights: " + ", ".join(f"{c[0]} {100 * w:.0f} %" for c, w in zip(m["criteria"], ws)))
        for crit, old, new, reason in changes:
            print(f"  audit: '{crit}' {old} -> {new}: {' '.join(reason.split())}")
        print(f"  VERDICT: {VERDICT[m['id']]}")
    chart(results)


def chart(results):
    sys.path.insert(0, str(common.REPO / "design-system" / "matplotlib"))
    import dbfplot as dp
    OUT.mkdir(exist_ok=True)
    dp.use()
    fig, ax = dp.figure("page", 3.2)
    y, ticks, labels = 0, [], []
    for mid, (opts, p_made, p_ev) in results.items():
        for i, o in enumerate(opts):
            ax.barh(y + 0.18, 100 * p_made[i], height=0.34, color=dp.FOG)
            ax.barh(y - 0.18, 100 * p_ev[i], height=0.34, color=dp.INK)
            ticks.append(y)
            labels.append(f"{mid.replace('_', ' ').upper()}: {o.upper()}")
            y -= 1
        y -= 0.6
    ax.set_yticks(ticks, labels, fontsize=4.4, family=dp.MONO)
    ax.set_xlim(0, 100)
    ax.set_xlabel("P(option ranks first), perturbed weights and scores (%)")
    ax.set_title("GREY = AS MADE   BLACK = AUDITED, DATA WEIGHTS", fontsize=5.2, family=dp.MONO,
                 color=dp.GRAPHITE, loc="left")
    ax.grid(axis="y", visible=False)
    dp.save(fig, OUT / "trades_robustness.pdf")


if __name__ == "__main__":
    main()
