"""DB-02 figures for the PDF (S11). Run from anywhere:

    PYTHONDONTWRITEBYTECODE=1 python DB-02_aircraft_variants/report/make_figures.py [--only cfd|sample]

Writes only inside report/figures/:
  figures/cfd/      CFD renders cropped to one consistent frame per view,
                    plus vector legend strips rebuilt from the render's own
                    colour bar (REPO/cfd/... is read, never written)
  figures/sample/   SAMPLE charts and a SAMPLE three-view with dummy data, to
                    prove the layout. Every one carries a "SAMPLE DATA" tag.
                    Real charts replace them, built the same way.

Conventions every chart follows (from dbfplot / the design-system README):
  * vector PDF at final print size: 'col' 3.35 in or 'page' 7.00 in wide
  * no title inside the plot (the caption states the takeaway)
  * units on every axis, SI only
  * only the recommended variant / design point is emphasised (Ink on light,
    Bone on the ink ground); DB-01 control is always Fog dashed
"""
from pathlib import Path
import argparse
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import dbfplot_dark as dk  # noqa: E402

import numpy as np  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402

OUT = HERE / "figures"
CFD_SRC = REPO / "cfd" / "cases" / "rq4_mock" / "results"

SAMPLE = "Sample data"


# ---------------------------------------------------------------------------
#  Sample data (dummy, seeded). Shapes only; no number here is a result.
# ---------------------------------------------------------------------------
def _draws(rng, mu, sd, p_fail, n=5000):
    x = rng.normal(mu, sd, n)
    fail = rng.random(n) < p_fail
    x[fail] = rng.normal(2.6, 0.25, fail.sum())          # M2 lost: M1 + GM only
    return np.clip(x, 0, 7.5)


def sample_score_dist():
    """Page-wide: mission-total distributions (left), P(1st) vs report (right)."""
    dk.use()
    rng = np.random.default_rng(27)
    a = _draws(rng, 6.48, 0.30, 0.07)
    b = _draws(rng, 6.22, 0.26, 0.05)
    c = _draws(rng, 6.10, 0.36, 0.08)
    f = rng.normal(6.18, 0.42, 5000)

    fig, (ax, bx) = plt.subplots(1, 2, figsize=(dk.PAGE, 2.25),
                                 gridspec_kw=dict(width_ratios=[1.75, 1]))
    for x in (ax, bx):
        dk.dp.style_axes(x)
    bins = np.arange(2.0, 7.55, 0.1)
    ax.hist(f, bins, histtype="stepfilled", color=dk.MIST, lw=0)
    ax.hist(c, bins, histtype="step", color=dk.FOG, lw=0.9, ls=(0, (3, 2)))
    ax.hist(b, bins, histtype="step", color=dk.STEEL, lw=0.9)
    ax.hist(a, bins, histtype="step", color=dk.INK, lw=1.5)
    ax.set_xlim(4.5, 7.5)
    ax.set_xlabel("Total mission score, M1 + M2 + M3 + GM (of 7.5)")
    ax.set_ylabel("Draws per 0.1 bin")
    for arr, name, col, dy in ((a, "Variant A", dk.INK, 10), (b, "Variant B", dk.STEEL, 10),
                               (c, "DB-01 control", dk.STEEL, 4)):
        p50 = np.median(arr[arr > 4])
        h, e = np.histogram(arr, bins)
        k = np.searchsorted(e, p50) - 1
        dk.label(ax, (p50, h[k]), name, dx=4, dy=dy, ha="left", color=col)
    ax.annotate("FIELD WINNER", (5.55, 120), fontsize=6.0, family=dk.MONO, color=dk.STEEL)
    dk.tag(ax, SAMPLE, "upper left")

    r = np.linspace(80, 96, 81)
    for k0, mid, col, ls, lw, name in ((0.55, 88.0, dk.INK, "-", 1.5, "A"),
                                       (0.50, 90.5, dk.STEEL, "-", 0.9, "B"),
                                       (0.48, 92.0, dk.FOG, (0, (3, 2)), 0.9, "DB-01")):
        p = 0.78 / (1 + np.exp(-k0 * (r - mid)))
        bx.plot(r, p, color=col, ls=ls, lw=lw)
        bx.annotate(name, (r[-1], p[-1]), xytext=(3, 0), textcoords="offset points",
                    va="center", fontsize=6.2, family=dk.MONO, color=col if col != dk.FOG else dk.STEEL)
    bx.axvline(90.6, color=dk.GRAPHITE, lw=0.5)
    bx.annotate("2022-26 BEST REPORT 90.6", (90.6, 0.03), xytext=(-3, 0), textcoords="offset points",
                ha="right", fontsize=5.6, family=dk.MONO, color=dk.STEEL)
    bx.set_xlim(80, 96)
    bx.set_ylim(0, 1)
    bx.set_xlabel("Our Total Report score (of 100)")
    bx.set_ylabel("P(1st overall)")
    fig.get_layout_engine().set(w_pad=0.06)
    dk.save(fig, OUT / "sample" / "score_dist.pdf")


def sample_regret():
    """Column: expected regret vs field aggressiveness, with the break-even."""
    dk.use()
    fig, ax = dk.figure("col", 2.15)
    s = np.linspace(0.6, 1.2, 61)
    ra = np.clip(0.02 + 0.55 * (s - 0.80) ** 2 * (s > 0.8) * 6, 0, None)
    rb = 0.06 + 0.02 * (s - 0.6)
    be = s[np.argmin(np.abs(ra - rb) + (s < 0.85))]
    ax.axvspan(be, 1.2, color=dk.BONE, lw=0)
    ax.plot(s, rb, color=dk.STEEL, lw=0.9)
    ax.plot(s, ra, color=dk.INK, lw=1.5)
    ax.axvline(be, color=dk.GRAPHITE, lw=0.5)
    dk.label(ax, (be, 0.25), f"Break-even {be:.2f}", dx=-4, dy=0, ha="right")
    ax.annotate("A", (s[-1], ra[-1]), xytext=(3, 0), textcoords="offset points", va="center",
                fontsize=6.2, family=dk.MONO, color=dk.INK)
    ax.annotate("B", (s[-1], rb[-1]), xytext=(3, 0), textcoords="offset points", va="center",
                fontsize=6.2, family=dk.MONO, color=dk.STEEL)
    ax.annotate("B PREFERRED", (1.18, 0.30), ha="right", fontsize=5.6, family=dk.MONO, color=dk.STEEL)
    ax.set_xlim(0.6, 1.2)
    ax.set_ylim(0, 0.32)
    ax.set_xlabel("Field strength, multiple of the aggressive anchors")
    ax.set_ylabel("Expected regret (points)")
    dk.tag(ax, SAMPLE, "upper left")
    dk.save(fig, OUT / "sample" / "regret.pdf")


def sample_tornado():
    """Column: change in P(1st) for each uncertain input at its P10 and P90."""
    dk.use()
    rows = [("Accepted stall speed", -9.0, 7.5), ("Lap-time factor", -7.2, 5.0),
            ("Airframe mass", -6.1, 4.2), ("Wing CL,max", -4.8, 2.9),
            ("Field maxima", -3.9, 3.1), ("Propulsive efficiency", -2.2, 2.0),
            ("Container mass", -1.5, 0.9), ("Air density", -0.9, 0.8)]
    rows = rows[::-1]
    fig, ax = dk.figure("col", 2.35)
    y = np.arange(len(rows))
    lo = np.array([r[1] for r in rows])
    hi = np.array([r[2] for r in rows])
    ax.barh(y, hi, height=0.62, color=dk.INK, lw=0)
    ax.barh(y, lo, height=0.62, color=dk.FOG, lw=0)
    ax.axvline(0, color=dk.GRAPHITE, lw=0.6)
    ax.set_yticks(y, [r[0] for r in rows])
    for t in ax.get_yticklabels():
        t.set_fontfamily(dk.SANS)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(-10, 10)
    ax.set_xlabel("Change in P(1st), percentage points")
    ax.annotate("P10", (-9.6, len(rows) - 0.35), fontsize=5.8, family=dk.MONO, color=dk.STEEL)
    ax.annotate("P90", (9.6, len(rows) - 0.35), ha="right", fontsize=5.8, family=dk.MONO, color=dk.INK)
    ax.set_ylim(-0.6, len(rows) + 0.1)
    dk.tag(ax, SAMPLE, "lower right")
    dk.save(fig, OUT / "sample" / "tornado.pdf")


def sample_score_dark():
    """Spread panel (ink ground): this variant's mission total vs the field winner."""
    dk.use_dark()
    rng = np.random.default_rng(11)
    a = _draws(rng, 6.48, 0.30, 0.07)
    f = rng.normal(6.18, 0.42, 5000)
    fig, ax = dk.figure("col", 1.55)
    bins = np.arange(4.0, 7.55, 0.1)
    ax.hist(f, bins, histtype="stepfilled", color=dk.GRAPHITE, lw=0)
    ax.hist(a, bins, histtype="step", color=dk.D_OURS, lw=1.3)
    ax.set_xlim(4.5, 7.5)
    ax.set_xlabel("Total mission score (of 7.5)")
    ax.set_ylabel("Draws per 0.1")
    ax.annotate("FIELD WINNER", (5.0, 60), fontsize=5.8, family=dk.MONO, color=dk.FOG)
    ax.annotate("THIS VARIANT", (6.62, 330), fontsize=5.8, family=dk.MONO, color=dk.BONE)
    dk.tag(ax, SAMPLE, "upper left")
    dk.save(fig, OUT / "sample" / "score_dist_dark.pdf", dark=True)


# ---------------------------------------------------------------------------
#  SAMPLE three-view (REF-D01 proportions) to prove the spread's slot.
#  S9 supplies the real drawings in W/out/geometry/.
# ---------------------------------------------------------------------------
def _ref_d01():
    b, S, lam = 1.82, 0.90, 0.70
    cr = 2 * S / (b * (1 + lam))
    ct = lam * cr
    return dict(b=b, cr=cr, ct=ct)


def _three_view(ax, dark, plan_only=False):
    g = _ref_d01()
    b, cr, ct = g["b"], g["cr"], g["ct"]
    s2 = b / 2
    line = dk.BONE if dark else dk.INK
    thin = dk.STEEL if dark else dk.FOG
    dim = dk.FOG if dark else dk.STEEL
    fill = (0.169, 0.180, 0.200, 0.55) if dark else (0.953, 0.949, 0.933, 1)
    lw, lt = 0.75, 0.4

    def poly(xs, ys, ox=0.0, oy=0.0, f=True, **kw):
        xs = np.asarray(xs) + ox
        ys = np.asarray(ys) + oy
        if f:
            ax.fill(xs, ys, color=fill, lw=0, zorder=1)
        ax.plot(np.r_[xs, xs[0]], np.r_[ys, ys[0]], color=kw.get("c", line),
                lw=kw.get("lw", lw), zorder=3, solid_joinstyle="miter")

    def hdim(x0, x1, y, text, tick=0.03):
        ax.plot([x0, x1], [y, y], color=dim, lw=0.35)
        for x in (x0, x1):
            ax.plot([x, x], [y - tick, y + tick], color=dim, lw=0.35)
        ax.text((x0 + x1) / 2, y + 0.035, text, ha="center", va="bottom", fontsize=6.0,
                family=dk.MONO, color=dim)

    # PLAN VIEW, nose up. x (span) right, y (aft) down => plot -x_aft.
    def c(yy):
        return cr - (cr - ct) * abs(yy) / s2

    def xle(yy):
        return 0.25 * (cr - c(yy))

    ys = np.array([-s2, 0, s2])
    le = np.array([xle(v) for v in ys])
    te = np.array([xle(v) + c(v) for v in ys])
    wing_x = np.r_[ys, ys[::-1]]
    wing_y = -np.r_[le, te[::-1]]
    oy = 0.0
    poly(wing_x, wing_y, oy=oy)
    # flap (60 % semispan) and aileron hinge lines at 75 % chord
    for side in (-1, 1):
        yy = np.linspace(0.09, s2, 2) * side
        hx = [xle(v) + 0.75 * c(v) for v in yy]
        ax.plot(yy, -np.array(hx), color=thin, lw=lt, zorder=4)
        ym = 0.6 * s2 * side
        ax.plot([ym, ym], [-(xle(ym) + 0.75 * c(ym)), -(xle(ym) + c(ym))], color=thin, lw=lt, zorder=4)
    # fuselage
    fx = np.array([-0.62, -0.60, -0.52, -0.40, 0.35, 0.95, 0.95, 0.35, -0.40, -0.52, -0.60, -0.62])
    fw = np.array([0.0, 0.045, 0.080, 0.090, 0.090, 0.030, -0.030, -0.090, -0.090, -0.080, -0.045, 0.0])
    poly(fw, -fx, oy=oy)
    # horizontal tail
    hs, hcr, hct, hx0 = 0.32, 0.20, 0.15, 0.76
    hy = np.array([-hs, 0, hs])
    hle = hx0 + 0.25 * (hcr - (hcr - (hcr - hct) * np.abs(hy) / hs))
    hte = hle + (hcr - (hcr - hct) * np.abs(hy) / hs)
    poly(np.r_[hy, hy[::-1]], -np.r_[hle, hte[::-1]], oy=oy)
    # propeller disc (edge-on) and centreline
    ax.plot([-0.254, 0.254], [0.64, 0.64], color=line, lw=lw, zorder=3)
    ax.plot([0, 0], [0.72, -1.02], color=thin, lw=lt, ls=(0, (6, 2, 1, 2)), zorder=2)
    hdim(-s2, s2, 0.80, "1.820 m")
    ax.text(-s2, 0.98, "PLAN", fontsize=6.0, family=dk.MONO, color=dim, va="bottom")
    if plan_only:
        return

    # FRONT VIEW (right column, top), origin at (2.10, 0.05)
    ox, oz = 2.13, -0.20
    zw = 0.20
    poly([-s2, s2, s2, -s2], [zw, zw, zw + 0.045, zw + 0.045], ox=ox, oy=oz)
    poly([-0.09, 0.09, 0.09, -0.09], [0.0, 0.0, 0.20, 0.20], ox=ox, oy=oz)
    poly([-hs, hs, hs, -hs], [0.10, 0.10, 0.115, 0.115], ox=ox, oy=oz)
    poly([-0.008, 0.008, 0.008, -0.008], [0.115, 0.115, 0.33, 0.33], ox=ox, oy=oz)
    th = np.linspace(0, 2 * np.pi, 120)
    ax.plot(ox + 0.254 * np.cos(th), oz + 0.10 + 0.254 * np.sin(th), color=thin, lw=lt,
            ls=(0, (3, 2)), zorder=2)
    for xw in (-0.20, 0.0, 0.20):
        ax.plot([ox + xw * 0.6, ox + xw], [oz, oz - 0.14], color=line, lw=lw, zorder=3)
        poly([xw - 0.012, xw + 0.012, xw + 0.012, xw - 0.012], [-0.20, -0.20, -0.12, -0.12], ox=ox, oy=oz)
    ax.plot([ox - s2 - 0.05, ox + s2 + 0.05], [oz - 0.20, oz - 0.20], color=thin, lw=lt, zorder=2)
    ax.text(ox - s2, oz + 0.43, "FRONT", fontsize=6.0, family=dk.MONO, color=dim, va="bottom")

    # SIDE VIEW (right column, bottom), nose left, origin at (ox2, oz2)
    ox2, oz2 = 2.13 - 0.15, -1.05
    sx = np.array([-0.62, -0.58, -0.45, 0.30, 0.95, 0.95, 0.40, -0.45, -0.58, -0.62])
    sz = np.array([0.08, 0.15, 0.20, 0.20, 0.16, 0.12, 0.0, 0.0, 0.02, 0.08])
    poly(sx, sz, ox=ox2, oy=oz2)
    poly([0.0, cr, cr - 0.03, 0.02], [0.20, 0.20, 0.235, 0.245], ox=ox2, oy=oz2)
    poly([0.74, 0.98, 0.98, 0.86], [0.16, 0.16, 0.38, 0.38], ox=ox2, oy=oz2)
    poly([0.76, 0.96, 0.96, 0.76], [0.10, 0.10, 0.115, 0.115], ox=ox2, oy=oz2)
    ax.plot([ox2 - 0.64, ox2 - 0.64], [oz2 + 0.10 - 0.254, oz2 + 0.10 + 0.254], color=line, lw=lw, zorder=3)
    for xg, r in ((-0.40, 0.04), (0.12, 0.045)):
        ax.plot([ox2 + xg, ox2 + xg], [oz2, oz2 - 0.14], color=line, lw=lw, zorder=3)
        ax.add_patch(plt.Circle((ox2 + xg, oz2 - 0.155), r, fill=False, ec=line, lw=lw, zorder=3))
    ax.plot([ox2 - 0.75, ox2 + 1.05], [oz2 - 0.20, oz2 - 0.20], color=thin, lw=lt, zorder=2)
    hdim(ox2 - 0.64, ox2 + 0.95, oz2 - 0.32, "1.590 m")
    ax.text(ox2 - 0.75, oz2 + 0.43, "SIDE", fontsize=6.0, family=dk.MONO, color=dim, va="bottom")
    # scale bar, bottom right
    x0, yb = ox + s2 - 1.0, -1.62
    for i, v in enumerate((0, 0.5, 1.0)):
        ax.plot([x0 + v, x0 + v], [yb, yb + 0.03], color=dim, lw=0.35)
        ax.text(x0 + v, yb + 0.05, f"{v:.1f}", ha="center", fontsize=5.6, family=dk.MONO, color=dim)
    ax.plot([x0, x0 + 1.0], [yb, yb], color=dim, lw=0.35)
    ax.text(x0 + 1.06, yb + 0.05, "m", fontsize=5.6, family=dk.MONO, color=dim)


def sample_three_view():
    for dark, name in ((True, "threeview_dark.pdf"), (False, "threeview_light.pdf")):
        (dk.use_dark if dark else dk.use)()
        fig = plt.figure(figsize=(dk.PAGE, 3.45))
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_axis_off()
        _three_view(ax, dark)
        ax.set_aspect("equal")
        ax.set_xlim(-1.02, 3.14)
        ax.set_ylim(-1.70, 1.05 - 0.0)
        ax.text(3.12, 1.0, "SAMPLE GEOMETRY  REF-D01 PROPORTIONS", ha="right", va="top", fontsize=5.8,
                family=dk.MONO, color=dk.FOG if dark else dk.STEEL)
        dk.save(fig, OUT / "sample" / name, dark=dark)
    dk.use_dark()
    fig = plt.figure(figsize=(4.9, 2.8))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    _three_view(ax, True, plan_only=True)
    ax.set_aspect("equal")
    ax.set_xlim(-1.02, 1.02)
    ax.set_ylim(-1.02, 1.0)
    dk.save(fig, OUT / "sample" / "plan_dark.pdf", dark=True)


# ---------------------------------------------------------------------------
#  CFD renders (S10's ParaView output, read-only): one crop frame per view so
#  every angle of attack sits in an identical window; the baked-in caption and
#  colour bar are cut away and replaced by the page's own labels and a vector
#  legend strip rebuilt from the render's colour-bar pixels.
# ---------------------------------------------------------------------------
ASPECT = 2.04                      # every plate: width / height
CROPS = {                           # x0, y0, width (px in the 1800 x 1000 render)
    "cp_top": (97, None, 1605), "cp_bottom": (97, None, 1605),
    "cf_top": (97, None, 1605), "yplus_top": (97, None, 1605),
    "cp_iso": (0, 160, 1600), "u_centreline": (100, 118, 1600),
    "wake_cp0": (40, 60, 1720),
}
CENTRE_Y = 499.5                   # planform views: centred on the aircraft
FIELDS = {                          # legend: symbol, lo, hi, ticks (render_aero.py LUTs)
    "cp": ("C_p", -1.2, 1.0, [-1.2, -0.8, -0.4, 0.0, 0.4, 0.8, 1.0]),
    "cf": ("C_f", 0.0, 0.010, [0, 0.0025, 0.005, 0.0075, 0.010]),
    "yplus": ("y+", 0.0, 2.0, [0, 0.5, 1.0, 1.5, 2.0]),
    "u": ("V/V_inf", 0.0, 1.3, [0, 0.25, 0.5, 0.75, 1.0, 1.3]),
    "cp0": ("C_p0", 0.6, 1.0, [0.6, 0.7, 0.8, 0.9, 1.0]),
}
VIEW_FIELD = {"cp_top": "cp", "cp_bottom": "cp", "cp_iso": "cp", "cf_top": "cf",
              "yplus_top": "yplus", "u_centreline": "u", "wake_cp0": "cp0"}


def _bar_colours(img):
    """Read the render's horizontal colour bar (row 987) left to right."""
    row = img[987]
    ink = np.where(np.abs(row.astype(int) - 255).sum(-1) > 6)[0]
    ink = ink[ink > 1100]
    x0, x1 = ink.min() + 2, ink.max() - 2
    return row[x0:x1 + 1] / 255.0


def cfd():
    from PIL import Image
    dst = OUT / "cfd"
    dst.mkdir(parents=True, exist_ok=True)
    bars = {}
    n = 0
    for adir in sorted(CFD_SRC.glob("alpha+*")):
        a = float(adir.name.split("+")[1])
        for view, (x0, y0, w) in CROPS.items():
            src = adir / "images" / f"{view}.png"
            if not src.exists():
                continue
            im = Image.open(src).convert("RGB")
            h = round(w / ASPECT)
            if y0 is None:
                y0 = round(CENTRE_Y - h / 2)
            tag = f"a{'p' if a >= 0 else 'm'}{abs(round(a)):02d}"      # ap04, am02
            im.crop((x0, y0, x0 + w, y0 + h)).save(dst / f"{tag}_{view}.png", optimize=True)
            n += 1
            fld = VIEW_FIELD[view]
            if fld not in bars:
                bars[fld] = _bar_colours(np.asarray(im))
    dk.use()
    for fld, cols in bars.items():
        sym, lo, hi, ticks = FIELDS[fld]
        fig = plt.figure(figsize=(2.30, 0.36))
        ax = fig.add_axes([0.02, 0.50, 0.96, 0.22])
        cmap = ListedColormap(cols)
        ax.pcolormesh(np.linspace(lo, hi, len(cols) + 1), [0, 1], np.linspace(lo, hi, len(cols))[None, :],
                      cmap=cmap, shading="flat", rasterized=False, lw=0)
        ax.set_xlim(lo, hi)
        ax.set_yticks([])
        ax.set_xticks(ticks, [f"{t:g}".replace("-", "−") for t in ticks])
        ax.tick_params(axis="x", length=2, width=0.4, pad=1.5, labelsize=5.8, labelfontfamily=dk.MONO,
                       colors=dk.GRAPHITE)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.grid(False)
        fig.set_layout_engine(None)
        dk.save(fig, dst / f"legend_{fld}.pdf")
    print(f"cfd: {n} plates, legends {sorted(bars)} -> {dst}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["cfd", "sample"])
    args = ap.parse_args()
    if args.only in (None, "sample"):
        sample_score_dist()
        sample_regret()
        sample_tornado()
        sample_score_dark()
        sample_three_view()
        print("sample: score_dist, regret, tornado, score_dist_dark, threeview_{dark,light}, plan_dark")
    if args.only in (None, "cfd"):
        cfd()


if __name__ == "__main__":
    main()
