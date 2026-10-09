#!/usr/bin/env python3
"""Proposal charts from data files: Fig. 01 Gantt and Fig. 02 organization chart.

    python make_charts.py          (./build.sh runs it)

Reads data/schedule.toml and data/team.toml and writes figures/gantt.pdf
(7.00 x 1.50 in) and figures/orgchart.pdf (3.35 x 1.35 in), the exact sizes of
their slots in sections/02_management_summary.tex. Edit the TOML, never the PDFs.
Uses the house plot style (design-system/matplotlib/dbfplot.py) and the standard
library's tomllib, so nothing extra to install.
"""
import datetime as dt
import sys
import tomllib
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
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


def main():
    dp.use()
    todo = gantt()
    confirmed = orgchart()
    print(f"ok    figures/gantt.pdf  | items to schedule: {len(todo)}"
          + (f" ({'; '.join(todo)})" if todo else ""))
    print(f"ok    figures/orgchart.pdf  | structure confirmed: {'yes' if confirmed else 'NO (draft)'}")


if __name__ == "__main__":
    main()
