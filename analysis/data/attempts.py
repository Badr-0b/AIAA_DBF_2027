# Copyright © 2026 Badr Obtel. All rights reserved.
"""Should we waive Mission 1? Attempt-budget model (TOOLING + rough decision).

    python analysis/data/attempts.py

Rules (2026-27 draft, Sec. 3.3.3): missions are flown in order; a new mission
needs a successful score on the preceding one; M1 may be waived, and a
successful M2 then credits M1, but after waiving, a failed M2 cannot fall back
to M1. Field data (AIAA summaries, verified in dbf_results / the summaries):
teams that passed tech got 2.4-2.9 official attempts each in 2022-2026, and
57-73 % of all attempts scored.

Model: a team has A attempts; each attempt at mission i succeeds with
probability p_i, independently; a failed attempt is retried while attempts
remain. Output: P(M3 completed) for "fly M1" vs "waive M1", over p and A.
Writes analysis/out/attempts_waiver.pdf.
"""
import sys
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / "design-system" / "matplotlib"))

# Field statistics, AIAA competition summaries (official attempts / teams that passed tech)
FIELD = {2022: (152, 87, 58), 2023: (203, 124, 74), 2024: (236, 156, 85),
         2025: (267, 164, 92), 2026: (197, 143, 83)}   # attempts, successful, passed tech


def p_complete(probs, attempts):
    """P(all missions in `probs` completed, in order, within `attempts` tries)."""
    @lru_cache(maxsize=None)
    def go(i, left):
        if i == len(probs):
            return 1.0
        if left == 0:
            return 0.0
        p = probs[i]
        return p * go(i + 1, left - 1) + (1 - p) * go(i, left - 1)
    return go(0, attempts)


def main():
    import dbfplot as dp
    from common import OUT
    for y, (a, s, t) in FIELD.items():
        print(f"{y}: {a / t:.1f} attempts per team that passed tech, {100 * s / a:.0f} % of attempts scored")
    p1 = 0.95                       # M1: 73 of 74 teams that flew in 2026 completed it (dbf_results.csv)
    print("\nP(M3 completed)  [p_M1 = 0.95; p_M2 = p_M3 = p]")
    print("   p    A=3 fly  A=3 waive   A=4 fly  A=4 waive")
    for p in (0.5, 0.6, 0.7, 0.8, 0.9):
        f3, w3 = p_complete((p1, p, p), 3), p_complete((p, p), 3)
        f4, w4 = p_complete((p1, p, p), 4), p_complete((p, p), 4)
        print(f"  {p:.1f}   {f3:.2f}     {w3:.2f}       {f4:.2f}     {w4:.2f}")
    dp.use()
    fig, ax = dp.figure("col", 2.1)
    ps = [i / 100 for i in range(40, 100)]
    for a, colour in ((3, dp.INK), (4, dp.STEEL)):
        ax.plot(ps, [100 * p_complete((p, p), a) for p in ps], color=colour, ls="-", lw=1.1,
                label=f"WAIVE M1, {a} ATTEMPTS")
        ax.plot(ps, [100 * p_complete((p1, p, p), a) for p in ps], color=colour, ls="--", lw=1.0,
                label=f"FLY M1, {a} ATTEMPTS")
    ax.axvspan(0.57, 0.73, color=dp.BONE, lw=0, zorder=0)
    ax.text(0.65, 3, "FIELD 2022-26", ha="center", fontsize=5.0, family=dp.MONO, color=dp.STEEL)
    ax.set_xlim(0.4, 0.99)
    ax.set_ylim(0, 100)
    ax.set_xlabel("Success probability per attempt, M2 and M3")
    ax.set_ylabel("P(Mission 3 completed) (%)")
    leg = ax.legend(loc="upper left", fontsize=5.0)
    for t in leg.get_texts():
        t.set_family(dp.MONO)
    dp.save(fig, OUT / "attempts_waiver.pdf")


if __name__ == "__main__":
    main()
