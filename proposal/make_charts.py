#!/usr/bin/env python3
"""Proposal charts from data files: Fig. 01 Gantt, Fig. 02 organization chart,
and the airfoil figure in Sec. 3.3.

    python make_charts.py          (./build.sh runs it)

Reads data/schedule.toml, data/team.toml and data/airfoil.toml (+ the XFoil
polars in data/airfoil_polars/ and nRho from data/numbers.tex) and writes
figures/gantt.pdf (7.00 x 1.85 in), figures/orgchart.pdf (3.35 x 1.35 in) and
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
dp.COL, dp.PAGE = 3.48, 7.26     # proposal P1.2: 0.62 in side margins (main.tex), column 3.48 in

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
    """Fig. 01 (P1.2, 31 Oct 2026, after the mock-judging readability notes): every label 7 pt; bars tall
    enough to carry their label inside, otherwise the label sits beside the bar on the same track; rules-fixed
    dates are OUTLINED bars and hollow diamonds, team-plan dates are FILLED, so the two read apart in print.
    Gate rail with hairlines through every lane. Optional `track = k` pins a task or milestone to a sub-track,
    `label = "left"` asks for a label left of its bar. Text widths are measured, not guessed."""
    data = tomllib.loads((DATA / "schedule.toml").read_text(encoding="utf-8"))
    lanes = data["lanes"]
    todo = []
    FS = 7.0                                  # 7.5 collides at this width (tried in P1.4)
    TRACK, BAR = 0.150, 0.120                                  # inches: sub-track pitch, bar height
    RAIL, HEAD, PAD = 0.22, 0.17, 0.03
    stop = dt.date(2027, 5, 11)
    items = []
    for t in data.get("task", []):
        a, b = day(t["start"]), day(t["end"])
        if a is None or b is None:
            todo.append(t["name"]); continue
        items.append(("task", a, b, t))
    for ms in data.get("milestone", []):
        d = day(ms["date"])
        if d is None:
            todo.append(ms["name"]); continue
        items.append(("ms", d, d, ms))
    x0n, x1n = mdates.date2num(START), mdates.date2num(stop)
    xn = mdates.date2num
    # sub-tracks: pinned items keep their track, other tasks pack greedily, milestones default to track 0
    track_end = {lane: {} for lane in lanes}
    track_of = {}
    for kind, a, b, it in sorted(items, key=lambda q: (q[1], q[0] != "task")):
        xa, xb = xn(a), xn(b + dt.timedelta(days=1))
        ends = track_end[it["lane"]]
        if "track" in it:
            k = it["track"]
        elif kind == "ms":
            k = 0
        else:
            k = next((i for i in sorted(ends) if ends[i] <= xa + 0.01), max(ends, default=-1) + 1)
        if kind == "task":
            ends[k] = max(ends.get(k, -1e9), xb)
        else:
            ends.setdefault(k, -1e9)
        track_of[id(it)] = k
    ntrack = {lane: max(1, len(track_end[lane])) for lane in lanes}
    H = RAIL + HEAD + TRACK * sum(ntrack.values()) + PAD
    fig = plt.figure(figsize=(dp.PAGE, H))
    fig.set_layout_engine(None)
    left, right = 0.088, 0.997
    ax = fig.add_axes([left, 0, right - left, 1])
    ax.axis("off")
    ax.set_xlim(x0n, x1n)
    ax.set_ylim(0, H)
    y_line = H - RAIL + 0.035                                  # rail line; gate diamonds sit on it
    y_month = H - RAIL - HEAD / 2 + 0.01
    top = H - RAIL - HEAD                                      # first lane's top edge
    lane_top, y = {}, top
    for lane in lanes:
        lane_top[lane] = y
        y -= TRACK * ntrack[lane]
    bottom = y

    def ty(lane, k):
        return lane_top[lane] - (k + 0.5) * TRACK

    # month columns (alternate Bone) and month names in the header
    m, k = dt.date(START.year, START.month, 1), 0
    while m <= stop:
        nxt = dt.date(m.year + (m.month == 12), m.month % 12 + 1, 1)
        a, b = xn(m), xn(min(nxt, stop + dt.timedelta(days=1)))
        if k % 2 == 1:
            ax.add_patch(Rectangle((a, bottom), b - a, top - bottom, color=dp.BONE, lw=0, zorder=0))
        lab = m.strftime("%b").upper() + (f" {m.strftime('%y')}" if m.month in (10, 1) else "")
        if b - a > 12:
            ax.text((a + b) / 2, y_month, lab, ha="center", va="center", fontsize=FS, family=dp.MONO,
                    color=dp.STEEL, zorder=2)
        m, k = nxt, k + 1
    for lane in lanes:
        ax.plot([x0n, x1n], [lane_top[lane]] * 2, color=dp.MIST, lw=0.5, ls="-", zorder=1)
        ax.text(x0n - 2.2, lane_top[lane] - TRACK * ntrack[lane] / 2, lane.upper(), ha="right", va="center",
                fontsize=FS, family=dp.MONO, color=dp.STEEL, clip_on=False)
    ax.plot([x0n, x1n], [bottom] * 2, color=dp.MIST, lw=0.5, ls="-", zorder=1)
    ax.plot([x0n, x1n], [y_line] * 2, color=dp.INK, lw=0.8, ls="-", zorder=1)
    ax.text(x0n - 2.2, y_line, "GATES", ha="right", va="center", fontsize=FS, family=dp.MONO, color=dp.INK,
            weight="bold", clip_on=False)

    renderer = fig.canvas.get_renderer()
    ppd = ax.get_window_extent(renderer).width / (x1n - x0n)          # pixels per day

    def width_days(text):
        t = ax.text(0, 0, text, fontsize=FS, family=dp.SANS)
        w = t.get_window_extent(renderer).width / ppd
        t.remove()
        return w

    def diamond(x, yv, rules, size=4.4):
        ax.plot([x], [yv], marker="D", ms=size, color="white" if rules else dp.INK, mec=dp.INK, mew=0.7, zorder=6)

    # gates on the rail; hairlines through the lanes, gapped around the month names
    gates = sorted(data.get("gate", []), key=lambda g: g["date"])
    used = []
    for i, g in enumerate(gates):
        d = day(g["date"])
        x = xn(d) + 0.5
        ax.plot([x, x], [bottom, top], color=dp.GRAPHITE, lw=0.5, ls=(0, (1, 1.6)), zorder=2)
        diamond(x, y_line, is_rules(g))
        lab = g.get("label", f"{g['name']} {d.day} {d.strftime('%b')}")
        w = width_days(lab)
        nxt = xn(day(gates[i + 1]["date"])) if i + 1 < len(gates) else x1n
        a, ha, xt = (x + 2.0, "left", x + 2.0) if x + 2.0 + w < nxt - 4.0 else (x - 2.0 - w, "right", x - 2.0)
        if a < x0n or any(a < q1 and a + w > q0 for q0, q1 in used):
            a, ha, xt = x + 2.0, "left", x + 2.0
        used.append((a, a + w))
        ax.text(xt, y_line + 0.075, lab, ha=ha, va="center", fontsize=FS, color=dp.INK, zorder=6)

    # bars and milestones; labels inside, else beside on the same sub-track (right, then left)
    occ = {}                                                    # (lane, track) -> [(x0, x1)]
    for kind, a, b, it in items:
        key = (it["lane"], track_of[id(it)])
        xa, xb = xn(a), xn(b + dt.timedelta(days=1))
        occ.setdefault(key, []).append((xa, xb) if kind == "task" else (xa - 1.8, xa + 2.8))

    def free(key, a, b):
        return a >= x0n and b <= x1n and not any(a < q1 - 0.01 and b > q0 + 0.01 for q0, q1 in occ.get(key, []))

    def beside(key, xa, xb, text, yv, prefer="right"):
        if prefer == "none":                                    # labelled by its neighbour
            return
        w = width_days(text)
        opts = [(xb + 1.4, xb + 1.4 + w, "left"), (xa - 1.4 - w, xa - 1.4, "right")]
        if prefer == "left":
            opts.reverse()
        for a, b, ha in opts:
            if free(key, a, b):
                break
        else:
            todo.append(f"label overlap: {text}")
        occ[key].append((a, b))
        ax.text(a if ha == "left" else b, yv, text, fontsize=FS, va="center", ha=ha, color=dp.INK, zorder=5)

    for kind, a, b, it in sorted(items, key=lambda q: (q[1], q[0])):
        key = (it["lane"], track_of[id(it)])
        yv = ty(*key)
        rules = is_rules(it)
        xa, xb = xn(a), xn(b + dt.timedelta(days=1))
        if kind == "task":
            ax.add_patch(Rectangle((xa, yv - BAR / 2), xb - xa, BAR, facecolor="white" if rules else dp.GRAPHITE,
                                   edgecolor=dp.INK, lw=0.7 if rules else 0, zorder=3))
            w = width_days(it["name"])
            if w + 2.6 <= xb - xa:
                ax.text(xa + 1.3, yv, it["name"], fontsize=FS, va="center", ha="left",
                        color=dp.INK if rules else "white", zorder=4)
            else:
                beside(key, xa, xb, it["name"], yv, it.get("label", "right"))
        else:
            diamond(xa + 0.5, yv, rules)
            beside(key, xa - 1.3, xa + 2.3, it["name"], yv, it.get("label", "right"))
    if todo:
        dp.tag(ax, f"{len(todo)} items to schedule", "upper right")
    dp.save(fig, OUT / "gantt.pdf")
    print(f"gantt {dp.PAGE:.2f} x {H:.2f} in")
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

    W, H = dp.COL, 1.06
    fig = plt.figure(figsize=(W, H), layout="none")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")

    bh, gap = 0.245, (H - 0.04 - levels * 0.245) / max(levels - 1, 1)
    pos = {}
    for lvl in range(levels):
        row = [u["id"] for u in units if depth[u["id"]] == lvl]
        par = [r for r in row if children.get(r)]                    # P1.4: a parent with a team goes in the middle
        if par and len(row) > 2:
            rest = [r for r in row if r not in par]
            row = rest[:len(rest) // 2] + par + rest[len(rest) // 2:]
        bw = min(0.80, (W - 0.05 * (len(row) - 1)) / len(row))
        step = W / len(row)
        y = H - 0.02 - bh - lvl * (bh + gap)
        for i, uid in enumerate(row):
            x = step * i + (step - bw) / 2
            pos[uid] = (x, y, bw)
    for uid, (x, y, bw) in pos.items():
        tech = uid == "chief" or uid in children.get("chief", [])     # P1.4: the chief engineer's team shaded
        ax.add_patch(Rectangle((x, y), bw, bh, facecolor=dp.BONE if tech else "white",
                               edgecolor=dp.INK if tech else dp.GRAPHITE, lw=0.6))
        ax.text(x + bw / 2, y + bh / 2, by_id[uid]["label"], ha="center", va="center",
                fontsize=7.0, family=dp.SANS, color=dp.INK, linespacing=1.05)
    for parent, kids in children.items():
        if not kids:
            continue
        px, py, pw = pos[parent]
        bus = py - gap / 2
        line = dict(color=dp.INK, lw=0.7, ls="-")        # the house cycle would dash them; P1.4: darker
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
