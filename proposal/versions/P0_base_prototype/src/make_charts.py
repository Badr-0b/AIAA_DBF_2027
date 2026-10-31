#!/usr/bin/env python3
"""Proposal charts from data files: Fig. 01 Gantt, Fig. 02 organization chart,
and the airfoil figure in Sec. 3.3.

    python make_charts.py          (./build.sh runs it)

Reads data/schedule.toml, data/team.toml and data/airfoil.toml (+ the XFoil
polars in data/airfoil_polars/ and nRho from data/numbers.tex) and writes
figures/gantt.pdf (7.00 x 1.50 in), figures/orgchart.pdf (3.35 x 1.35 in) and
figures/airfoil.pdf (3.35 x 2.00 in), the exact sizes of their slots in
sections/, plus data/airfoil.tex (the airfoil caption's numbers). Edit the
TOML, never the PDFs or the generated .tex.
Uses the house plot style (design-system/matplotlib/dbfplot.py) and the standard
library's tomllib, so nothing extra to install.
"""
import csv
import datetime as dt
import math
import re
import sys
import tomllib
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "design-system" / "matplotlib"))
import dbfplot as dp  # noqa: E402

DATA = HERE / "data"
OUT = HERE / "figures"
START, STOP = dt.date(2026, 10, 1), dt.date(2027, 4, 30)


def day(s):
    return None if str(s).upper() == "TBD" else dt.date.fromisoformat(str(s))


def is_rules(item):
    return item.get("source", "").startswith("rules")


# --------------------------------------------------------------------------
# Fig. 01 Gantt
# --------------------------------------------------------------------------
def gantt():
    data = tomllib.loads((DATA / "schedule.toml").read_text(encoding="utf-8"))
    lanes = data["lanes"]
    y_of = {name: len(lanes) - 1 - i for i, name in enumerate(lanes)}   # first lane on top
    todo = []

    fig, ax = dp.figure("page", 1.50)
    ax.grid(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    # month grid
    m = dt.date(START.year, START.month, 1)
    while m <= STOP:
        ax.axvline(mdates.date2num(m), color=dp.MIST, lw=0.5, zorder=0)
        m = dt.date(m.year + (m.month == 12), m.month % 12 + 1, 1)
    for y in range(len(lanes) - 1):
        ax.axhline(y + 0.5, color=dp.MIST, lw=0.5, zorder=0)

    # Labels go right of their bar or diamond (left of it near the right edge).
    # Within a lane, a label that would overlap an earlier one moves to the next
    # free level: on the bar line, then above it, then below it.
    placed = {lane: [] for lane in lanes}   # (x_from, x_to, level)
    shapes = {lane: [] for lane in lanes}   # bars and diamonds, which sit on level 0
    days_per_char = (STOP - START).days / (6.2 / 0.040)   # axis ~6.2 in, ~0.040 in per char
    x_stop = mdates.date2num(STOP)

    def blocked(lane, a, b, level):
        if any(a < x1 and b > x0 and lvl == level for x0, x1, lvl in placed[lane]):
            return True
        return level == 0 and any(a < x1 and b > x0 for x0, x1 in shapes[lane])

    def put_label(lane, x_right, x_left, text):
        width = len(text) * days_per_char
        sides = [(x_right, x_right + width, x_right, "left"), (x_left - width, x_left, x_left, "right")]
        if x_right + width >= x_stop:
            sides.reverse()
        # first free (level, side): right side preferred, then the other side, then stack
        choice = next(((lvl, s) for lvl in range(3) for s in sides
                       if s[0] > mdates.date2num(START) and not blocked(lane, s[0], s[1], lvl)),
                      (2, sides[0]))
        level, (a, b, x, ha) = choice
        placed[lane].append((a, b, level))
        y = y_of[lane] + (0.0, 0.31, -0.31)[level]
        ax.text(x, y, text, fontsize=5.6, va="center", ha=ha, color=dp.INK, zorder=4)

    items = []
    for t in data.get("task", []):
        a, b = day(t["start"]), day(t["end"])
        if a is None or b is None:
            todo.append(t["name"])
            continue
        items.append(("task", a, b, t))
    for ms in data.get("milestone", []):
        d = day(ms["date"])
        if d is None:
            todo.append(ms["name"])
            continue
        items.append(("ms", d, d, ms))
    for kind, a, b, it in items:   # register every shape before placing any label
        x0, x1 = mdates.date2num(a), mdates.date2num(b + dt.timedelta(days=1))
        shapes[it["lane"]].append((x0, x1) if kind == "task" else (x0 - 1.5, x0 + 2.5))
    for kind, a, b, it in sorted(items, key=lambda k: k[1]):
        y = y_of[it["lane"]]
        colour = dp.INK if is_rules(it) else dp.STEEL
        x0, x1 = mdates.date2num(a), mdates.date2num(b + dt.timedelta(days=1))
        if kind == "task":
            ax.add_patch(Rectangle((x0, y - 0.13), x1 - x0, 0.26, color=colour, lw=0, zorder=3))
            put_label(it["lane"], x1 + 1.5, x0 - 1.5, it["name"])
        else:
            ax.plot([x0 + 0.5], [y], marker="D", ms=3.6, color=colour, mec="white", mew=0.5, zorder=5)
            put_label(it["lane"], x0 + 3.0, x0 - 2.0, it["name"])

    ax.set_ylim(-0.6, len(lanes) - 0.4)
    ax.set_yticks(range(len(lanes)))
    ax.set_yticklabels([lane.upper() for lane in reversed(lanes)], fontsize=5.6,
                       family=dp.MONO, color=dp.STEEL)
    ax.set_xlim(mdates.date2num(START), mdates.date2num(STOP))
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(
        plt.FuncFormatter(lambda v, _: mdates.num2date(v).strftime("%b %Y").upper()))
    ax.tick_params(axis="x", labelsize=5.8, length=2)
    if todo:
        dp.tag(ax, f"{len(todo)} items to schedule", "upper right")
    dp.save(fig, OUT / "gantt.pdf")
    return todo


# --------------------------------------------------------------------------
# Fig. 02 organization chart
# --------------------------------------------------------------------------
def orgchart():
    data = tomllib.loads((DATA / "team.toml").read_text(encoding="utf-8"))
    units = data["unit"]
    by_id = {u["id"]: u for u in units}
    children = {u["id"]: [] for u in units}
    roots = []
    for u in units:
        parent = u.get("reports_to")
        if parent:
            if parent not in by_id:
                sys.exit(f"team.toml: {u['id']} reports_to unknown unit '{parent}'")
            children[parent].append(u["id"])
        else:
            roots.append(u["id"])

    depth = {}

    def walk(uid, d):
        depth[uid] = d
        for c in children[uid]:
            walk(c, d + 1)
    for r in roots:
        walk(r, 0)
    levels = max(depth.values()) + 1

    W, H = dp.COL, 1.35
    fig = plt.figure(figsize=(W, H), layout="none")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")

    bh, gap = 0.21, (H - 0.04 - levels * 0.21) / max(levels - 1, 1)
    pos = {}
    for lvl in range(levels):
        row = [u["id"] for u in units if depth[u["id"]] == lvl]
        bw = min(0.80, (W - 0.06 * (len(row) - 1)) / len(row))
        step = W / len(row)
        y = H - 0.02 - bh - lvl * (bh + gap)
        for i, uid in enumerate(row):
            x = step * i + (step - bw) / 2
            pos[uid] = (x, y, bw)
    for uid, (x, y, bw) in pos.items():
        lead_role = depth[uid] in (1,) or uid == "chief"
        ax.add_patch(Rectangle((x, y), bw, bh, facecolor=dp.BONE if lead_role else "white",
                               edgecolor=dp.GRAPHITE, lw=0.5))
        ax.text(x + bw / 2, y + bh / 2, by_id[uid]["label"].upper(), ha="center", va="center",
                fontsize=5.5, family=dp.MONO, color=dp.INK, linespacing=1.1)
    for parent, kids in children.items():
        if not kids:
            continue
        px, py, pw = pos[parent]
        bus = py - gap / 2
        line = dict(color=dp.GRAPHITE, lw=0.5, ls="-")   # the house cycle would dash them
        ax.plot([px + pw / 2] * 2, [py, bus], **line)
        xs = [pos[k][0] + pos[k][2] / 2 for k in kids]
        ax.plot([min(xs + [px + pw / 2]), max(xs + [px + pw / 2])], [bus, bus], **line)
        for k, kx in zip(kids, xs):
            ax.plot([kx, kx], [bus, pos[k][1] + bh], **line)
    if not data.get("confirmed", False):
        ax.text(W - 0.01, H - 0.01, "DRAFT: CONFIRM ROLES", ha="right", va="top",
                fontsize=4.6, family=dp.MONO, color=dp.STEEL)
    dp.save(fig, OUT / "orgchart.pdf")
    return data.get("confirmed", False)


# --------------------------------------------------------------------------
# Sec. 3.3 airfoil figure: section L/D vs c_l with the race envelope
# --------------------------------------------------------------------------
G0 = 9.80665   # m/s^2


def number(macro):
    """A plain numeric macro from data/numbers.tex (the proposal's one source of numbers)."""
    tex = (DATA / "numbers.tex").read_text(encoding="utf-8")
    m = re.search(r"\\newcommand\\" + macro + r"\{([0-9.]+)\}", tex)
    if not m:
        sys.exit(f"data/numbers.tex: \\{macro} is missing or not a plain number")
    return float(m.group(1))


def polar(key, re):
    """Attached branch of an XFoil polar: lowest c_l up to Cl_max, c_l > 0.

    Post-stall points are dropped (unreliable in XFoil; study METHODS.md Sec. 7).
    """
    path = DATA / "airfoil_polars" / f"{key}_Re{re // 1000}k_N9_P240.csv"
    if not path.exists():
        sys.exit(f"airfoil.toml: no polar {path.name} in data/airfoil_polars/ "
                 "(copy it from the airfoil study's polars/raw/)")
    with path.open(newline="") as f:
        rows = sorted(csv.DictReader(f), key=lambda r: float(r["alpha"]))
    cl = np.array([float(r["CL"]) for r in rows])
    cd = np.array([float(r["CD"]) for r in rows])
    top = int(np.argmax(cl))
    low = int(np.argmin(cl[:top + 1]))
    cl, cd = cl[low:top + 1], cd[low:top + 1]
    keep = cl > 0
    return cl[keep], cl[keep] / cd[keep]


def ld_at(cl, ld, x):
    """L/D at section c_l x (NaN outside the converged range). Interpolates on
    the rising points only, skipping XFoil's wiggles of a few thousandths."""
    rising = cl >= np.maximum.accumulate(cl)
    return np.interp(x, cl[rising], ld[rising], left=np.nan, right=np.nan)


def airfoil():
    data = tomllib.loads((DATA / "airfoil.toml").read_text(encoding="utf-8"))
    band, names = data["band"], data["names"]
    sel, base, re = data["selected"], data["baseline"], int(data["re"])

    # Race envelope: c_l = 2 n (W/S) / (rho V^2), cruise n = 1, turn n = 1/cos(bank)
    ws = band["wing_loading_kgpm2"] * G0
    rho = number("nRho")
    q = 0.5 * rho * band["v"] ** 2
    n_turn = 1 / math.cos(math.radians(band["bank_deg"]))
    cl_cruise, cl_turn = ws / q, n_turn * ws / q

    fig, ax = dp.figure("col", 2.00)
    ax.axvspan(cl_cruise, cl_turn, color=dp.BONE, lw=0, zorder=0)
    for x, text in ((cl_cruise, "CRUISE  n = 1"), (cl_turn, f"TURN  n = {n_turn:.1f}")):
        ax.axvline(x, color=dp.FOG, lw=0.4, zorder=1)
        ax.text(x + 0.012, 0.97, text, transform=ax.get_xaxis_transform(), rotation=90,
                ha="left", va="top", fontsize=5.0, family=dp.MONO, color=dp.STEEL)

    greys = iter([(dp.STEEL, 0.9), (dp.FOG, 0.9)])
    series = [k for k in data["shortlist"] if k != sel] + [base] + \
             ([sel] if sel in data["shortlist"] else [])        # "ours" drawn last, on top
    handles, readout, grid = {}, [], np.linspace(cl_cruise, cl_turn, 50)
    for key in series:
        cl, ld = polar(key, re)
        if key == sel:
            style, mfc, z = dict(color=dp.INK, lw=1.4, ls="-"), dp.INK, 4
        elif key == base:
            style, mfc, z = dict(color=dp.GRAPHITE, lw=0.8, ls=(0, (3.5, 2))), "white", 2
        else:
            c, w = next(greys)
            style, mfc, z = dict(color=c, lw=w, ls="-"), "white", 3
        ax.plot(cl, ld, solid_capstyle="round", zorder=z, **style)
        ax.plot(cl[-1], ld[-1], "o", ms=2.6, mfc=mfc, mec=style["color"], mew=0.7, zorder=z)
        handles[key] = Line2D([], [], **style)
        lo, hi = ld_at(cl, ld, cl_cruise), ld_at(cl, ld, cl_turn)
        readout.append((key, lo, hi, np.nanmean(ld_at(cl, ld, grid))))
        if key == sel and not np.isnan(hi):            # the design point
            ax.plot(cl_turn, hi, "o", ms=3.2, mfc=dp.INK, mec="white", mew=0.6, zorder=5)
            dp.label(ax, (cl_turn, hi), f"L/D {hi:.0f}", dx=-4, dy=5, ha="right")
        elif key == data.get("compare") and not np.isnan(hi):   # contrast, in grey
            ax.plot(cl_turn, hi, "o", ms=2.6, mfc="white", mec=style["color"], mew=0.7, zorder=5)
            ax.annotate(f"{hi:.0f}", (cl_turn, hi), xytext=(4, -7), textcoords="offset points",
                        ha="left", fontsize=6.0, family=dp.MONO, color=dp.STEEL)

    order = [k for k in [sel] + data["shortlist"] + [base] if k in handles]
    order = list(dict.fromkeys(order))
    leg = ax.legend([handles[k] for k in order], [names[k].upper() for k in order],
                    loc="lower right", ncol=2, fontsize=5.4, handlelength=2.2,
                    columnspacing=1.2, borderaxespad=0.2)
    for t in leg.get_texts():
        t.set_family(dp.MONO)

    ax.set_xlim(0, 1.95)
    ax.xaxis.set_major_locator(plt.MultipleLocator(0.5))
    ax.xaxis.set_major_formatter(plt.FormatStrFormatter("%.1f"))
    ax.set_ylim(0, 150)
    ax.set_xlabel("Section lift coefficient, $c_l$")
    ax.set_ylabel("Lift-to-drag ratio, $c_l/c_d$")
    if not band["confirmed"]:
        dp.tag(ax, "PRELIMINARY", "upper right")
    dp.save(fig, OUT / "airfoil.pdf")

    # Guard: does another shortlist section beat "ours" inside the band?
    mean = {k: m for k, _, _, m in readout if k in data["shortlist"]}
    best = max(mean, key=lambda k: -np.inf if np.isnan(mean[k]) else mean[k])
    warn = ""
    if sel not in mean:
        warn = f"selected '{sel}' is not in the shortlist"
    elif mean[best] > 1.05 * mean[sel]:
        warn = f"{names[best]} beats {names[sel]} by {mean[best] / mean[sel] - 1:.0%} in the band"
    cells = "; ".join(f"{names[k].replace('–', '-')} {lo:.0f}/{hi:.0f}".replace("nan", "n/a")
                      for k, lo, hi, _ in readout)

    # Caption numbers, generated so the caption can never disagree with the figure.
    # \nAfCheck prints as an unfinished value (and fails the final build) while
    # the band is unconfirmed or the caption's claim no longer holds.
    turn = {k: hi for k, _, hi, _ in readout}
    cmp_ = data.get("compare")
    check = (f"recheck caption: {warn}" if warn else
             "" if band["confirmed"] else "confirm W/S and V in airfoil.toml")
    tex = lambda k: names[k].replace(" ", "~")
    macros = {
        "nAfCheck": rf"\dbftbd{{{check}}} " if check else "",
        "nAfSel": tex(sel), "nAfCmp": tex(cmp_),
        "nAfLDsel": f"{turn[sel]:.0f}", "nAfLDcmp": f"{turn[cmp_]:.0f}",
        "nAfRatio": f"{turn[sel] / turn[cmp_]:.1f}",
        "nAfRe": rf"{re / 1e5:.1f}\times10^{{5}}", "nAfNturn": f"{n_turn:.1f}",
        "nAfClCruise": f"{cl_cruise:.2f}", "nAfClTurn": f"{cl_turn:.2f}",
    }
    lines = ["% GENERATED by make_charts.py from data/airfoil.toml and data/numbers.tex.",
             "% Do not edit: edit those files and rebuild."]
    lines += [rf"\newcommand\{k}{{{v}}}" for k, v in macros.items()]
    (DATA / "airfoil.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return (cl_cruise, cl_turn, band["confirmed"], cells, warn)


def main():
    dp.use()
    todo = gantt()
    confirmed = orgchart()
    cl_c, cl_t, band_ok, cells, warn = airfoil()
    print(f"ok    figures/gantt.pdf  | items to schedule: {len(todo)}"
          + (f" ({'; '.join(todo)})" if todo else ""))
    print(f"ok    figures/orgchart.pdf  | structure confirmed: {'yes' if confirmed else 'NO (draft)'}")
    print(f"ok    figures/airfoil.pdf  | band c_l {cl_c:.2f}-{cl_t:.2f}"
          f" ({'confirmed' if band_ok else 'PRELIMINARY'}) | c_l/c_d at band edges: {cells}")
    if warn:
        print(f"WARN  figures/airfoil.pdf  | {warn}")


if __name__ == "__main__":
    main()
