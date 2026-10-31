# Copyright © 2026 Badr Obtel. All rights reserved.
"""House-style figures for Scripts 1-2 (TOOLING). They call your functions in
s1_course.py, so they draw once those are written. Output: analysis/out/*.pdf
at the exact printed size (dbfplot: Geist, monochrome).
"""
import sys

import numpy as np
from matplotlib.ticker import MultipleLocator

from common import G0, OUT, REPO, RULES

sys.path.insert(0, str(REPO / "design-system" / "matplotlib"))
import dbfplot as dp  # noqa: E402

BANKS = (60.0, 63.0, 65.0, 70.0, 75.0)

# Lap-time references. Different definitions, labelled as such:
#   UCF 2021, flown, GPS, take-off excluded, same course: 28.33 s empty, 31.33 s
#     at 5.73 kg gross (2020-21 winning reports, UCF Sec. 8.2).
#   RMIT 2026 target: 9 laps in 300 s, take-off included (2026 top-3 PDF).
REFERENCES = ((31.33, "UCF '21 FLOWN"), (300 / 9, "RMIT '26 TARGET"))


def lap_time_vs_speed(s1, path=OUT / "s1_lap_time_vs_speed.pdf"):
    """Lap time against speed at 60-75 deg bank, the lap-time floor, references."""
    dp.use()
    fig, ax = dp.figure("col", 2.4)
    v = np.linspace(15.0, 45.0, 301)
    for bank in BANKS:
        t = [s1.lap_time(x, bank, G0) for x in v]
        line, = ax.plot(v, t, lw=0.9)
        ax.annotate(f"{bank:.0f}°", (v[-1], t[-1]), xytext=(2, 0), textcoords="offset points",
                    fontsize=5.6, family=dp.MONO, color=line.get_color(), va="center")
    banks = np.linspace(55.0, 78.0, 47)
    ax.plot([s1.best_speed(b, G0) for b in banks], [s1.min_lap_time(b, G0) for b in banks],
            color=dp.INK, lw=1.2, ls=(0, (1, 1.5)), label="FLOOR  V*, t_min")
    ax.set_xlim(15, 47)
    ax.set_ylim(25, 70)
    key = ax.twinx()                     # reference labels in the right margin, clear of the curves
    key.set_ylim(ax.get_ylim())
    key.spines["right"].set_visible(False)
    key.grid(False)
    key.tick_params(axis="y", length=0, labelsize=4.8, labelcolor=dp.STEEL, labelfontfamily=dp.MONO)
    key.set_yticks([t for t, _ in REFERENCES], [text for _, text in REFERENCES])
    for t_ref, _ in REFERENCES:
        ax.axhline(t_ref, color=dp.FOG, lw=0.5, zorder=0)
    ax.set_xlabel("Speed, $V$ (m/s)")
    ax.set_ylabel("Lap time (s)")
    leg = ax.legend(loc="upper right", fontsize=5.4)
    for text in leg.get_texts():
        text.set_family(dp.MONO)
    dp.save(fig, path)
    return path


def m3_staircase(s1, t_stow, stow_counts, path=OUT / "s1_m3_laps_staircase.pdf"):
    """Whole M3 laps in the window against the steady towed lap time, for three
    take-off overheads (extra time of lap 1). The steps are the integer cliffs."""
    dp.use()
    fig, ax = dp.figure("col", 2.2)
    window = RULES["missions"]["window_s"]
    t_lap = np.linspace(25.0, 50.0, 1001)
    for overhead, colour in ((0.0, dp.INK), (10.0, dp.STEEL), (20.0, dp.FOG)):
        laps = [s1.laps_in_window(t + overhead, t, window, t_stow, stow_counts) for t in t_lap]
        ax.step(t_lap, laps, where="post", color=colour, lw=0.9, ls="-",
                label=f"TAKE-OFF +{overhead:.0f} S")
    dp.tag(ax, f"STOW {t_stow:.0f} S {'IN' if stow_counts else 'OUTSIDE'} WINDOW", "lower left")
    ax.set_xlim(25, 50)
    ax.set_xlabel("Steady towed lap time (s)")
    ax.set_ylabel("M3 laps in 300 s")
    ax.yaxis.set_major_locator(MultipleLocator(1))
    leg = ax.legend(loc="upper right", fontsize=5.4)
    for text in leg.get_texts():
        text.set_family(dp.MONO)
    dp.save(fig, path)
    return path
