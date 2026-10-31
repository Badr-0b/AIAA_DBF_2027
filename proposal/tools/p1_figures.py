"""Proposal P1 figures (31 Oct 2026). House style: design-system/matplotlib/dbfplot.py (light) and the
DB-02 dark layer for ink plates. Vector PDF at exact print size (3.35 in column / 7.00 in page).

  fig_tornado.pdf     sensitivity of Variant A's mean mission total (data/p1_sens.json)
  fig_declared.pdf    frozen declaration vs declaring at tech (data/p1_sens.json, DB-02 F-A-*)
  fig_screen.pdf      P(top) vs wing area by flap type, 8S finalists (DB-02 out/integration/finalists.json)
  fig_payload.pdf     M2 simulators and M3 ballast trades (data/p1_payload.json, tools/p1_payload.py)
  fig_constraint.pdf  T/W vs W/S for Variant A at the hot-day density (DB-02 adapter, data/p1_nominal.json)
  fig_threeview.pdf   dark 3-view plate, top / side / front (DB-02 out/variants/variants_geometry.json)
  fig_glance.pdf      dark top-view thumbnail for the page-1 panel

Run: PYTHONDONTWRITEBYTECODE=1 python proposal/tools/p1_figures.py [name ...]
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PROP = HERE.parent
REPO = PROP.parent
DB02 = REPO / "DB-02_aircraft_variants"
sys.path.insert(0, str(REPO / "design-system" / "matplotlib"))
sys.path.insert(0, str(DB02 / "report"))

import dbfplot as dp                                   # noqa: E402
dp.COL, dp.PAGE = 3.48, 7.26     # proposal P1.2: 0.62 in side margins (main.tex), column 3.48 in
import dbfplot_dark as dd                              # noqa: E402
import matplotlib.pyplot as plt                        # noqa: E402
import numpy as np                                     # noqa: E402
from matplotlib.patches import Circle, Polygon, Rectangle  # noqa: E402

FIG = PROP / "figures"
DATA = PROP / "data"
G0 = 9.80665


def J(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def F(key):
    return J(DB02 / "out/finalists/F_results.json")["items"][key]["value"]


# ------------------------------------------------------------------ house style, proposal sizes
FS = 7.0          # smallest text in any proposal figure (mock-judging readability note, 31 Oct 2026)


def use():
    dp.use()
    plt.rcParams.update({"font.size": 7.5, "axes.labelsize": 7.5, "xtick.labelsize": 7, "ytick.labelsize": 7,
                         "legend.fontsize": 7})


def note(ax, x, y, text, **kw):
    """Mono annotation at the house minimum size."""
    kw.setdefault("color", dp.STEEL)
    ax.text(x, y, text, fontsize=FS, family=dp.MONO, **kw)


# ------------------------------------------------------------------ tornado
TORNADO = [("DESIGN PARAMETERS", None),
           ("Propulsive efficiency", "power_factor"), ("Airframe mass", "af_kg"), ("Span efficiency $e$", "e_factor"),
           (r"Max. lift $C_{L,\max}$", "clmax"), ("Non-wing drag area", "f_body"), ("Wing area", "s"),
           ("CONDITIONS", None),
           ("Lap-time factor (pilot)", "time_cal"), ("Air density", "rho"), ("Rival field maxima", "field"),
           ("Take-off time", "t_to")]


def tornado():
    """Design parameters (what the team builds) against conditions (pilot, weather, rivals), +-10 % each.
    Usable battery energy moves the score exactly as propulsive efficiency does, so it is not drawn twice."""
    use()
    S = J(DATA / "p1_sens.json")["tornado"]
    by = {r["key"]: r for r in S["rows"]}
    fig, ax = dp.figure("col", 1.36)
    n = len(TORNADO)
    for i, (label, key) in enumerate(TORNADO):
        y = n - 1 - i
        if key is None:
            ax.text(-0.62, y, label, fontsize=FS, family=dp.MONO, color=dp.INK, va="center", ha="left",
                    weight="bold")
            continue
        lo, hi = by[key]["delta"]["-0.1"], by[key]["delta"]["+0.1"]
        ax.barh(y, lo, height=0.64, color=dp.FOG, lw=0)
        ax.barh(y, hi, height=0.64, color=dp.INK, lw=0)
    ys = [n - 1 - i for i, (_, k) in enumerate(TORNADO) if k]
    ax.set_yticks(ys, [lab for lab, k in TORNADO if k], fontsize=FS, fontfamily=dp.SANS)
    ax.tick_params(axis="y", length=0)
    ax.axvline(0, color=dp.INK, lw=0.6)
    ax.set_xlabel("Change in mean mission total (points)")
    ax.grid(axis="y", visible=False)
    ax.set_xlim(-0.62, 0.32)
    ax.set_ylim(-0.6, n - 0.4)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=dp.FOG, label="Input −10 %"), Patch(color=dp.INK, label="Input +10 %")],
              loc="lower left", ncol=1, fontsize=FS, handlelength=1.0, borderaxespad=0.3)
    dp.save(fig, FIG / "fig_tornado.pdf")


# ------------------------------------------------------------------ declared mass
def declared():
    use()
    D = J(DATA / "p1_sens.json")
    sw = D["sweep"]
    m = np.array([s["m"] for s in sw])
    tot = np.array([s["total"] for s in sw])
    feas = np.array([s["feas"] for s in sw])
    rows = J(DB02 / "out/integration/finalists_rows.json")["base"]["S10F8"]["rows"]
    md = np.array([r["m_decl"] for r in rows])
    mean_tech = F("F-A-MEAN")
    fig, ax = dp.figure("col", 1.26)
    ax.axvspan(3.0, 8.0, color=dp.BONE, lw=0, zorder=0)
    ax.plot(m, tot, color=dp.STEEL, lw=1.0, marker="o", ms=2.6, mfc="white", mec=dp.STEEL, mew=0.7,
            label="Frozen at design")
    ax.hlines(mean_tech, 3.0, 8.0, color=dp.INK, lw=1.6, label="Declared at tech")
    i = int(np.argmax(tot))
    ax.annotate("", xy=(m[i], mean_tech), xytext=(m[i], tot[i]),
                arrowprops=dict(arrowstyle="-|>", lw=0.6, color=dp.INK, mutation_scale=6))
    ax.text(m[i] - 0.12, 0.5 * (mean_tech + tot[i]) - 0.03, f"+{mean_tech - tot[i]:.2f}", fontsize=FS,
            family=dp.MONO, va="center", ha="right", color=dp.INK)
    vals, cnt = np.unique(md, return_counts=True)            # rug: where the 120 draws declare
    base = 3.4
    for v, c in zip(vals, cnt):
        ax.plot([v, v], [base, base + 0.0075 * c], color=dp.INK, lw=1.4, solid_capstyle="butt")
    note(ax, 8.15, base + 0.03, "DECLARED\nAT TECH", va="bottom", linespacing=1.1)
    ax2 = ax.twinx()
    ax2.plot(m, feas, color=dp.FOG, lw=0.9, ls=(0, (3, 2)))
    ax2.set_ylim(0, 1.05)
    ax2.set_ylabel("P(M2 feasible), frozen", color=dp.STEEL, fontsize=FS)
    ax2.tick_params(labelfontfamily=dp.MONO, labelsize=FS, colors=dp.STEEL)
    ax2.spines["right"].set_visible(True); ax2.spines["right"].set_color(dp.FOG); ax2.grid(False)
    ax.set_xlim(2, 10); ax.set_ylim(base, 7.0)
    ax.set_xlabel("Declared sensor mass (kg)")
    ax.set_ylabel("Mission total (of 7.5)")
    ax.legend(loc="lower left", fontsize=FS, bbox_to_anchor=(0.0, 0.15))
    dp.save(fig, FIG / "fig_declared.pdf")


# ------------------------------------------------------------------ area x flap, finalists
def screen():
    """P(top) of the finalists on the full 120 paired draws (DB-02 out/integration/finalists.json, base case),
    best declared range per wing area and flap, single 8S motor. The same numbers as Table 07."""
    use()
    Fb = J(DB02 / "out/integration/finalists.json")["base"]
    ctrl = Fb["CTRL"]["p_mission_top"]
    fin = {k: v for k, v in Fb.items() if k != "CTRL" and v["prop"] == "8s"}
    fig, ax = dp.figure("col", 1.18)
    style = {"fowler": (dp.INK, "o", "Fowler flap"), "slotted": (dp.STEEL, "D", "Slotted flap"),
             "plain": (dp.FOG, "s", "Plain flap")}
    for fl, (col, mk, lab) in style.items():
        best = {}
        for v in fin.values():
            if v["flap"] == fl and v["p_mission_top"] > best.get(v["s"], -1):
                best[v["s"]] = v["p_mission_top"]
        xs = sorted(best)
        ax.plot(xs, [best[x] for x in xs], color=col, lw=1.0, marker=mk, ms=3.6, mfc=col, mec=col, label=lab,
                zorder=3)
    a, b = Fb["S10F8"]["p_mission_top"], Fb["S12S6"]["p_mission_top"]
    ax.annotate("A", (1.0, a), xytext=(-4, 5), textcoords="offset points", ha="right", fontsize=FS,
                family=dp.MONO, color=dp.INK, weight="bold")
    ax.annotate("B", (1.2, b), xytext=(-4, -9), textcoords="offset points", ha="right", fontsize=FS,
                family=dp.MONO, color=dp.INK, weight="bold")
    # direct labels at the line ends (the legend sat on the 1.2 m2 points)
    ends = {}
    for fl in style:
        pts = sorted((v["s"], v["p_mission_top"]) for v in fin.values() if v["flap"] == fl)
        best = {}
        for s_, p_ in pts:
            best[s_] = max(p_, best.get(s_, -1))
        ends[fl] = max(best.items())
    sl = sorted(s_ for s_ in {v["s"] for v in fin.values() if v["flap"] == "slotted"})
    s_mid = sl[len(sl) // 2] if sl else None
    for fl, (x, y) in ends.items():
        col, _, lab = style[fl]
        if fl == "slotted" and s_mid is not None:            # under the middle of its own line
            x = s_mid
            y = max(v["p_mission_top"] for v in fin.values() if v["flap"] == "slotted" and v["s"] == s_mid)
        dx, dy, ha = {"fowler": (5, 3, "left"), "slotted": (5, -5, "left"), "plain": (0, -6, "center")}[fl]
        ax.annotate(lab, (x, y), xytext=(dx, dy), textcoords="offset points", ha=ha,
                    va="bottom" if dy > 0 else "top", fontsize=FS, color=col if fl != "plain" else dp.STEEL)
    ax.set_xlabel("Wing area (m²), span 1.82 m")
    ax.set_ylabel("P(top of field)")
    ax.set_xlim(0.85, 1.35); ax.set_ylim(0.265, 0.320)
    for yy in (0.030, 0.058):                                # axis break: the y axis does not start at zero
        ax.plot((-0.014, 0.014), (yy - 0.012, yy + 0.012), transform=ax.transAxes, color=dp.INK, lw=0.7,
                ls="-", clip_on=False, zorder=6)
    note(ax, 0.02, 0.04, f"FIRST ITERATION {ctrl:.3f}, BELOW SCALE", transform=ax.transAxes, va="bottom")
    dp.save(fig, FIG / "fig_screen.pdf")


# ------------------------------------------------------------------ payload trades (new, P1.2)
def payload():
    """(a) M2: expected M1 + M2 points against the declared mass for 0, 1 and 2 simulators.
    (b) M3: points against the sensor mass flown at the median declaration, if completed and per attempt.
    Data: data/p1_payload.json (tools/p1_payload.py), same draws and field as the headline score."""
    use()
    D = J(DATA / "p1_payload.json")
    fig = plt.figure(figsize=(dp.COL, 1.32))
    fig.set_layout_engine(None)
    axa = fig.add_axes([0.125, 0.24, 0.35, 0.625])
    axb = fig.add_axes([0.615, 0.24, 0.35, 0.625])
    for ax in (axa, axb):
        ax.grid(True, color=dp.MIST, lw=0.4)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
    # (a)
    sty = {0: (dp.INK, "-", 1.3, "Sensor only"), 1: (dp.STEEL, (0, (4, 2)), 1.0, "+1 sim."),
           2: (dp.FOG, (0, (1, 1.5)), 1.0, "+2 sims")}
    for n, (col, ls, lw, lab) in sty.items():
        r = sorted((x for x in D["m2"] if x["n_sim"] == n), key=lambda x: x["m"])
        axa.plot([x["m"] for x in r], [x["exp"] for x in r], color=col, ls=ls, lw=lw, label=lab)
    r0 = {x["m"]: x["exp"] for x in D["m2"] if x["n_sim"] == 0}
    md = D["m_decl"]
    ya = np.interp(md, sorted(r0), [r0[k] for k in sorted(r0)])
    axa.plot([md], [ya], marker="o", ms=4.0, color=dp.INK, zorder=5)
    axa.annotate("PLAN", (md, ya), xytext=(0, 6), textcoords="offset points", ha="center", fontsize=FS,
                 family=dp.MONO, color=dp.INK)
    axa.set_xlim(2, 8); axa.set_ylim(0, 2.4)
    axa.set_xticks([2, 4, 6, 8])
    axa.set_xlabel("Declared sensor (kg)")
    axa.set_ylabel("Expected points")
    for x, y, text, col in ((2.1, 2.24, "sensor only", dp.INK), (4.3, 0.98, "+1 simulator", dp.STEEL),
                            (3.05, 0.55, "+2", dp.STEEL)):
        axa.text(x, y, text, fontsize=FS, color=col, va="bottom", ha="left")
    note(axa, 0.0, 1.05, "(A) M1 + M2", transform=axa.transAxes, va="bottom", color=dp.INK)
    # (b)
    r = sorted(D["m3"], key=lambda x: x["m"])
    m = np.array([x["m"] for x in r])
    axb.plot(m, [x["pts"] for x in r], color=dp.STEEL, lw=1.0, ls=(0, (4, 2)), label="If completed")
    e1 = np.array([x["exp1"] for x in r])
    axb.plot(m, e1, color=dp.INK, lw=1.3, label="Per attempt")
    plan = 3.4                                                    # median flown mass (Table 07)
    yb = float(np.interp(plan, m, e1))
    axb.plot([plan], [yb], marker="o", ms=4.0, color=dp.INK, zorder=5)
    axb.annotate("PLAN", (plan, yb), xytext=(0, -11), textcoords="offset points", ha="center", fontsize=FS,
                 family=dp.MONO, color=dp.INK)
    axb.axvline(md, color=dp.FOG, lw=0.7, ls=(0, (1, 1.5)))
    laps = [x["laps_p50"] for x in r]                            # median laps bands along the top
    edges = [0] + [i for i in range(1, len(m)) if laps[i] != laps[i - 1]] + [len(m)]
    for a, b in zip(edges[:-1], edges[1:]):
        x0, x1 = m[a], m[b - 1]
        if x1 - x0 >= 1.5:
            axb.text(0.5 * (x0 + x1), 3.12, f"{laps[a]:.0f} LAPS", ha="center", va="bottom", fontsize=FS,
                     family=dp.MONO, color=dp.STEEL)
        if b < len(m):
            axb.plot([0.5 * (m[b - 1] + m[b])] * 2, [3.08, 3.24], color=dp.STEEL, lw=0.5)
    axb.set_xlim(1, 8); axb.set_ylim(1.0, 3.25)
    axb.set_xticks([2, 4, 6, 8])
    axb.set_xlabel("Sensor flown (kg)")
    axb.legend(loc="center right", fontsize=FS, handlelength=1.6, borderaxespad=0.1, labelspacing=0.25,
               bbox_to_anchor=(1.0, 0.55))
    note(axb, 0.0, 1.05, "(B) M3", transform=axb.transAxes, va="bottom", color=dp.INK)
    dp.save(fig, FIG / "fig_payload.pdf")


# ------------------------------------------------------------------ constraint diagram
def constraint():
    use()
    N = J(DATA / "p1_nominal.json")["A"]
    m2, m3 = N["m2"], N["m3_at_median_mass"]
    sys.path.insert(0, str(DB02 / "src"))
    from integration import adapter as A
    rho = 1.064
    S, AR, e = 1.0, m2["ar"], m2["e"]
    k = 1.0 / (math.pi * e * AR)
    cd0 = m2["cd0"]
    clmax = m2["clmax_land"]
    ws = np.linspace(40, 230, 300)
    fig, ax = dp.figure("col", 1.26)

    def turn(V, n, c0):
        q = 0.5 * rho * V ** 2
        return q * c0 / ws + k * n ** 2 * ws / q

    ax.plot(ws, turn(m2["v"], m2["n"], cd0), color=dp.INK, lw=1.0,
            label=f"M2 turn, {m2['v']:.0f} m/s, n {m2['n']:.2f}")
    ax.plot(ws, turn(m3["v"], m3["n"], cd0), color=dp.STEEL, lw=0.9, ls=(0, (4, 2)),
            label=f"M3 turn, {m3['v']:.0f} m/s, n {m3['n']:.2f}")
    ax.plot(ws, turn(m2["v"], 1.0, cd0), color=dp.FOG, lw=0.8, label="Level flight, M2 speed")
    ax.legend(loc="upper left", bbox_to_anchor=(0.0, 1.0), fontsize=FS, handlelength=1.6, labelspacing=0.25,
              borderaxespad=0.2)
    ws14 = 0.5 * rho * 14.0 ** 2 * clmax
    ws12 = 0.5 * rho * 12.0 ** 2 * clmax
    ax.fill_betweenx([0, 1.25], ws14, 240, color=dp.MIST, lw=0, zorder=0)
    ax.axvline(ws14, color=dp.GRAPHITE, lw=0.8)
    note(ax, 0.5 * (ws14 + 230), 1.21, "STALL\n>14 M/S", ha="center", va="top", color=dp.GRAPHITE, linespacing=1.1)
    ax.axvline(ws12, color=dp.FOG, lw=0.7, ls=(0, (1, 2)))
    note(ax, ws12 + 3, 1.21, "12 M/S", va="top", ha="left")
    bund = A.prop_bundle("8s")                                # thrust available at the turn speed
    Dm = J(DATA / "p1_nominal.json")["A"]["draws"]
    for g, V, lab in ((Dm["g2"]["p50"], m2["v"], "M2"), (Dm["g3"]["p50"], m3["v"], "M3")):
        W = g * G0
        tw = float(bund.thrust(V)) / W
        ax.plot(W / S, tw, marker="o", ms=4.2, color=dp.INK, mfc=dp.INK if lab == "M2" else "white", mew=0.9, zorder=5)
        ax.annotate(f"{lab} {g:.1f} KG", (W / S, tw), xytext=(5, -11 if lab == "M2" else -2),
                    textcoords="offset points", ha="left", fontsize=FS, family=dp.MONO, color=dp.INK)
    ax.set_xlim(40, 230); ax.set_ylim(0, 1.25)
    ax.set_xlabel("Wing loading W/S (N/m²)")
    ax.set_ylabel("T/W")
    note(ax, 0.02, 0.03, f"HOT DAY {rho} KG/M³", transform=ax.transAxes, va="bottom")
    dp.save(fig, FIG / "fig_constraint.pdf")
    return {"ws_stall12": ws12, "ws_stall14": ws14}


# ------------------------------------------------------------------ 3-view (dark plate)
def _geo(key="A"):
    return J(DB02 / "out/variants/variants_geometry.json")[key]


def _draw_top(ax, V, ink, fog, mist, bg, lw=0.7, labels=True):
    g, t, m = V["geometry"], V["tails"], V["mass"]
    half = 0.91
    xr, cr, ct = g["x_le"], g["cr"], g["ct"]
    xt = xr + 0.25 * (cr - ct)
    L_f, wf = g["fus_len"], g["fus_w"]
    x_end = t["x_ach"] + 0.6 * t["crh"]

    def P(pts, **kw):
        ax.add_patch(Polygon(pts, closed=True, fill=kw.pop("fill", False), **kw))
    P([(-half, -xt), (0, -xr), (half, -xt), (half, -(xt + ct)), (0, -(xr + cr)), (-half, -(xt + ct))],
      ec=ink, lw=lw, fc=mist, fill=True, zorder=3)
    fs = g["flap_span"] * half
    for sgn in (-1, 1):
        for (y0, y1, cf) in ((0.17 * sgn, fs * sgn, g["cf"]), ((fs + 0.02) * sgn, 0.97 * half * sgn, 0.25)):
            c0 = cr - (cr - ct) * abs(y0) / half; c1 = cr - (cr - ct) * abs(y1) / half
            x0 = xr + 0.25 * (cr - c0) + c0; x1 = xr + 0.25 * (cr - c1) + c1
            P([(y0, -x0), (y1, -x1), (y1, -(x1 - cf * c1)), (y0, -(x0 - cf * c0))], ec=fog, lw=0.4, zorder=4)
    P([(-wf / 2 * 0.8, -0.03), (wf / 2 * 0.8, -0.03), (wf / 2, -0.10), (-wf / 2, -0.10)], ec=ink, lw=lw, fc=bg, fill=True)
    P([(-wf / 2, -0.10), (wf / 2, -0.10), (wf / 2, -L_f), (0.06, -(x_end - 0.02)), (-0.06, -(x_end - 0.02)),
       (-wf / 2, -L_f)], ec=ink, lw=lw, fc=bg, fill=True)
    bh, crh, cth, xh = t["bh"], t["crh"], t["cth"], t["xh"]
    xht = xh + 0.25 * (crh - cth)
    P([(-bh / 2, -xht), (0, -xh), (bh / 2, -xht), (bh / 2, -(xht + cth)), (0, -(xh + crh)), (-bh / 2, -(xht + cth))],
      ec=ink, lw=lw, fc=mist, fill=True)
    xb = m["x_bay"]; cl, cw = 0.288, 0.303
    ax.add_patch(Rectangle((-cw / 2, -(xb + cl / 2)), cw, cl, fill=False, ec=fog, lw=0.5, ls=(0, (3, 2)), zorder=5))
    ax.plot([-0.254, 0.254], [0.0, 0.0], color=ink, lw=1.2)
    xc = t["x_cg_design"]
    ax.add_patch(Circle((0, -xc), 0.028, fill=False, ec=ink, lw=0.6, zorder=6))
    ax.plot([-0.045, 0.045], [-xc, -xc], color=ink, lw=0.6, zorder=6)
    ax.plot([0, 0], [-xc - 0.045, -xc + 0.045], color=ink, lw=0.6, zorder=6)
    if labels:
        yd = 0.16
        ax.annotate("", xy=(-half, yd), xytext=(half, yd), arrowprops=dict(arrowstyle="<->", lw=0.4, color=fog))
        ax.text(0, yd + 0.03, "SPAN 1.820 M", ha="center", va="bottom", fontfamily=dp.MONO, fontsize=5.4, color=fog)
    ax.set_xlim(-1.0, 1.0); ax.set_ylim(-(x_end + 0.12), 0.30)
    return x_end


def threeview():
    V = _geo("A")
    g, t = V["geometry"], V["tails"]
    ink, fog, mist, bg = "#E4E6E9", dp.FOG, "#2B2E33", dp.INK
    dp.use()
    fig = plt.figure(figsize=(dp.PAGE, 1.80), facecolor=bg)
    fig.set_layout_engine(None)
    axT = fig.add_axes([0.005, 0.03, 0.30, 0.94])
    axS = fig.add_axes([0.33, 0.10, 0.36, 0.80])
    axF = fig.add_axes([0.70, 0.10, 0.295, 0.80])
    for ax in (axT, axS, axF):
        ax.set_facecolor(bg); ax.set_aspect("equal"); ax.axis("off")
    x_end = _draw_top(axT, V, ink, fog, mist, bg)
    lw = 0.7
    half = 0.91
    xr, cr = g["x_le"], g["cr"]
    L_f, wf, hf = g["fus_len"], g["fus_w"], g["fus_h"]
    zf0 = 0.369 - hf / 2
    xc = t["x_cg_design"]
    xb = V["mass"]["x_bay"]

    def P(ax, pts, **kw):
        ax.add_patch(Polygon(pts, closed=True, fill=kw.pop("fill", False), **kw))
    P(axS, [(0.03, zf0 + 0.04), (0.10, zf0), (L_f, zf0 + 0.05), (x_end - 0.02, zf0 + hf * 0.62),
            (x_end - 0.02, zf0 + hf * 0.75), (L_f, zf0 + hf), (0.10, zf0 + hf), (0.03, zf0 + hf - 0.04)],
      ec=ink, lw=lw, fc=bg, fill=True)
    zw = zf0 + hf
    P(axS, [(xr, zw), (xr + cr, zw), (xr + cr, zw + 0.012), (xr + 0.1 * cr, zw + 0.05), (xr, zw + 0.03)],
      ec=ink, lw=lw, fc=mist, fill=True)
    zt = zf0 + hf * 0.68
    xh, crh = t["xh"], t["crh"]
    P(axS, [(xh, zt), (xh + crh, zt), (xh + crh, zt + 0.012), (xh, zt + 0.012)], ec=ink, lw=lw, fc=mist, fill=True)
    bv, crv, ctv = t["bv"], t["crv"], t["ctv"]
    xv = t["x_ach"] - 0.25 * crv
    P(axS, [(xv, zt), (xv + crv, zt), (xv + 0.35 * (crv - ctv) + ctv, zt + bv), (xv + 0.35 * (crv - ctv), zt + bv)],
      ec=ink, lw=lw, fc=mist, fill=True)
    axS.plot([0, 0], [0.369 - 0.254, 0.369 + 0.254], color=ink, lw=1.2)
    axS.plot([-0.1, x_end + 0.1], [0, 0], color=fog, lw=0.4)
    for xg, r in ((0.16, 0.045), (xc + 0.16, 0.055)):
        axS.plot([xg, xg], [r, zf0], color=ink, lw=0.8)
        axS.add_patch(Circle((xg, r), r, fill=False, ec=ink, lw=0.6))
    axS.add_patch(Rectangle((xb - 0.144, zf0 + 0.02), 0.288, 0.303, fill=False, ec=fog, lw=0.5, ls=(0, (3, 2))))
    axS.plot([xb + 0.05, xb + 0.62], [zf0, zf0 - 0.13], color=fog, lw=0.5, ls=(0, (1, 2)))
    axS.text(xb + 0.64, zf0 - 0.13, "TOW LINE ≥ 2.73 M (M3)", fontfamily=dp.MONO, fontsize=5.0, color=fog, va="center")
    axS.plot([xc, xc], [zf0 + hf + 0.10, zf0 - 0.04], color=fog, lw=0.4, ls=(0, (6, 2, 1, 2)))
    axS.text(xc, zf0 + hf + 0.11, "CG, ALL LOADINGS", ha="center", fontfamily=dp.MONO, fontsize=5.0, color=fog)
    axS.text(0.0, -0.06, f"LENGTH {x_end:.2f} M  /  S {g['S']:.2f} M²  /  AR {g['AR']:.2f}", ha="left", va="top",
             fontfamily=dp.MONO, fontsize=5.2, color=fog)
    axS.set_xlim(-0.15, x_end + 0.15); axS.set_ylim(-0.16, 0.86)
    dz = half * math.tan(math.radians(2.0))
    P(axF, [(-wf / 2, zf0), (wf / 2, zf0), (wf / 2, zf0 + hf), (-wf / 2, zf0 + hf)], ec=ink, lw=lw, fc=bg, fill=True)
    P(axF, [(-half, zw + dz), (0, zw), (half, zw + dz), (half, zw + dz + 0.04), (0, zw + 0.05), (-half, zw + dz + 0.04)],
      ec=ink, lw=lw, fc=mist, fill=True)
    bh = t["bh"]
    P(axF, [(-bh / 2, zt), (bh / 2, zt), (bh / 2, zt + 0.012), (-bh / 2, zt + 0.012)], ec=ink, lw=lw, fc=mist, fill=True)
    P(axF, [(-0.006, zt), (0.006, zt), (0.006, zt + bv), (-0.006, zt + bv)], ec=ink, lw=lw, fc=mist, fill=True)
    axF.add_patch(Circle((0, 0.369), 0.254, fill=False, ec=fog, lw=0.5))
    for yg, r in ((0, 0.045), (-0.30, 0.055), (0.30, 0.055)):
        axF.plot([yg, yg * 0.5], [r, zf0], color=ink, lw=0.8)
        axF.add_patch(Rectangle((yg - 0.012, 0), 0.024, 2 * r, fill=False, ec=ink, lw=0.6))
    axF.plot([-1.0, 1.0], [0, 0], color=fog, lw=0.4)
    axF.text(0, -0.06, "PROPELLER 508 MM, AXIS 0.369 M", ha="center", va="top", fontfamily=dp.MONO, fontsize=5.0,
             color=fog)
    axF.set_xlim(-1.0, 1.0); axF.set_ylim(-0.16, 0.86)
    for ax, lab in ((axT, "TOP"), (axS, "SIDE"), (axF, "FRONT")):
        ax.text(0.0, 1.0, lab, transform=ax.transAxes, fontfamily=dp.MONO, fontsize=5.6, color=dp.STEEL, va="top")
    fig.savefig(FIG / "fig_threeview.pdf", facecolor=bg)
    plt.close(fig)


def glance():
    V = _geo("A")
    dp.use()
    bg = dp.INK
    fig = plt.figure(figsize=(1.55, 1.55), facecolor=bg)
    fig.set_layout_engine(None)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(bg); ax.set_aspect("equal"); ax.axis("off")
    _draw_top(ax, V, "#E4E6E9", dp.STEEL, "#2B2E33", bg, lw=0.55, labels=False)
    ax.set_ylim(-1.68, 0.06)
    fig.savefig(FIG / "fig_glance.pdf", facecolor=bg)
    plt.close(fig)


def ga():
    """General arrangement and glance thumbnail from the team's own drawings (tools/p1_ga.py).
    The DB-02 drawing functions above (threeview, glance) are kept for reference only and are not run:
    the team lead asked for the team's own drawings, 31 Oct 2026."""
    sys.path.insert(0, str(HERE))
    import p1_ga
    p1_ga.main()


ALL = {"tornado": tornado, "declared": declared, "screen": screen, "payload": payload, "constraint": constraint,
       "ga": ga}

if __name__ == "__main__":
    names = sys.argv[1:] or list(ALL)
    for n in names:
        r = ALL[n]()
        print("wrote", n, r or "")
