"""Figures for the showcase (ILLUSTRATIVE DATA, not analysis).

Also the reference pattern for real figures: import dbfplot, call use(),
build at exact grid size, keep the accent for the design point only.
"""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "matplotlib"))
import dbfplot as dp  # noqa: E402

OUT = HERE / "figures"


def sensitivity():
    fig, ax = dp.figure("col", 2.15)
    x = np.linspace(-40, 40, 81)
    series = [
        ("Sensor weight", 0.31 * x, dict(color=dp.ACCENT, lw=1.9, ls="-")),
        ("Payload units", 0.22 * x, dict(color=dp.GRAPHITE, lw=1.0, ls="-")),
        ("5-lap time", -0.18 * x, dict(color=dp.STEEL, lw=1.0, ls="-")),
        ("M3 laps", 0.12 * x, dict(color=dp.STEEL, lw=1.0, ls="--")),
        ("Drop height", np.where(x < 0, 0.10 * x, 0.0), dict(color=dp.FOG, lw=1.0, ls="-")),
        ("Empty weight", -0.06 * x, dict(color=dp.FOG, lw=1.0, ls="--")),
    ]
    for name, y, st in series:
        ax.plot(x, y, **st)
        ax.annotate(name, (x[-1], y[-1]), xytext=(4, 0), textcoords="offset points",
                    va="center", fontsize=6.6,
                    color=dp.STEEL if st["color"] == dp.FOG else st["color"],
                    fontweight="semibold" if st["color"] == dp.ACCENT else "normal")
    ax.axhline(0, color=dp.GRAPHITE, lw=0.6)
    ax.axvline(0, color=dp.GRAPHITE, lw=0.6)
    ax.set_xlim(-40, 40)
    ax.set_ylim(-14, 14)
    ax.set_xticks([-40, -20, 0, 20, 40])
    ax.set_xlabel("Change in parameter from baseline (%)")
    ax.set_ylabel("Change in total mission score (%)")
    dp.tag(ax, "Illustrative data", "upper left")
    fig.get_layout_engine().set(rect=(0, 0, 0.80, 1))
    dp.save(fig, OUT / "sensitivity.pdf")


def constraint():
    fig, ax = dp.figure("col", 2.15)
    ws = np.linspace(0.35, 2.2, 300)
    rho, cd0, k = 0.00205, 0.040, 1 / (np.pi * 0.78 * 6.0)

    def q(v):
        return 0.5 * rho * v ** 2

    cruise = q(75) * cd0 / ws + k * ws / q(75)
    turn = q(70) * cd0 / ws + k * 3.0 ** 2 * ws / q(70)
    climb = 15 / 50 + q(50) * cd0 / ws + k * ws / q(50)
    stall_ws = 0.5 * rho * 32 ** 2 * 1.4
    req = np.maximum.reduce([cruise, turn, climb])
    ok = ws <= stall_ws
    ax.fill_between(ws[ok], req[ok], 1.3, color=dp.BONE, lw=0, zorder=0)
    ax.plot(ws, cruise, color=dp.STEEL, ls="--", label="Cruise, 75 ft/s")
    ax.plot(ws, turn, color=dp.INK, label="Turn, n = 3")
    ax.plot(ws, climb, color=dp.STEEL, label="Climb, 15 ft/s")
    ax.axvline(stall_ws, color=dp.GRAPHITE, ls=":", label="Stall, 32 ft/s")
    ax.plot([1.30], [0.62], marker="s", ms=5.5, color=dp.ACCENT, mec="white", mew=0.8, zorder=5)
    dp.label(ax, (1.30, 0.62), "Design point\nW/S 1.30  T/W 0.62")
    ax.text(0.62, 1.12, "FEASIBLE", fontsize=6.0, family=dp.MONO, color=dp.STEEL)
    ax.set_xlim(0.35, 2.2)
    ax.set_ylim(0, 1.3)
    ax.set_xlabel("Wing loading, W/S (lb/ft²)")
    ax.set_ylabel("Thrust-to-weight, T/W")
    ax.legend(loc="upper right", borderaxespad=0.2)
    dp.tag(ax, "Illustrative data", "lower right")
    dp.save(fig, OUT / "constraint.pdf")


if __name__ == "__main__":
    dp.use()
    sensitivity()
    constraint()
    print("figures written to", OUT)
