"""DB-02 plot helper: the house style (light) plus an ink-ground variant.

Wraps design-system/matplotlib/dbfplot.py READ-ONLY. Same print sizes
(COL 3.35 in, PAGE 7.00 in), same fonts (Geist, Geist Mono), same rules:
vector PDF at final size, no titles inside plots, units on every axis,
only "ours" / the design point is emphasised.

    import sys; sys.path.insert(0, r"...\\DB-02_aircraft_variants\\report")
    import dbfplot_dark as dk

    dk.use()                       # light body pages (identical to dbfplot)
    fig, ax = dk.figure("col", 2.2)
    ...; dk.save(fig, "figures/x.pdf")

    dk.use_dark()                  # dark spec spreads (ink ground)
    fig, ax = dk.figure("col", 1.6)
    ax.plot(x, y, color=dk.D_OURS) # Bone = "ours" on ink
    dk.save(fig, "figures/x_dark.pdf", dark=True)   # transparent ground

Colour roles on the ink ground (monochrome, no signal colour):
    D_OURS  Bone      the design point / recommended variant
    D_ALT   Fog       the other variant
    D_CTRL  Steel     DB-01 control, field, reference lines
    D_RULE  Graphite  grid, quiet rules
    D_TEXT  Fog       tick labels and axis labels
"""
from pathlib import Path
import sys

sys.dont_write_bytecode = True  # never write __pycache__ into design-system/

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "design-system" / "matplotlib"))
import dbfplot as dp  # noqa: E402  (read-only import)

import matplotlib as mpl  # noqa: E402
from cycler import cycler  # noqa: E402

# Grid and palette, re-exported so callers import one module
COL, PAGE = dp.COL, dp.PAGE
INK, GRAPHITE, STEEL, FOG, MIST, BONE = (dp.INK, dp.GRAPHITE, dp.STEEL,
                                         dp.FOG, dp.MIST, dp.BONE)
ACCENT = dp.ACCENT
SANS, MONO = dp.SANS, dp.MONO

# Roles on the light ground (body pages)
L_OURS, L_ALT, L_CTRL, L_FIELD = INK, STEEL, FOG, GRAPHITE
# Roles on the ink ground (spec spreads)
D_OURS, D_ALT, D_CTRL, D_RULE, D_TEXT = BONE, FOG, STEEL, GRAPHITE, FOG

_dark = False


def use():
    """Light house style (exactly dbfplot.use())."""
    global _dark
    _dark = False
    return dp.use()


def use_dark():
    """House style on an ink ground: same sizes, fonts and weights."""
    global _dark
    dp.use()
    _dark = True
    cyc = cycler(color=[BONE, FOG, STEEL, MIST, FOG, STEEL]) + cycler(
        linestyle=["-", "-", "-", "--", "--", ":"])
    mpl.rcParams.update({
        "text.color": MIST,
        "axes.labelcolor": FOG,
        "axes.edgecolor": STEEL,
        "axes.facecolor": "none",
        "axes.prop_cycle": cyc,
        "grid.color": GRAPHITE,
        "grid.linewidth": 0.5,
        "xtick.color": FOG,
        "ytick.color": FOG,
        "xtick.labelcolor": FOG,
        "ytick.labelcolor": FOG,
        "figure.facecolor": "none",
        "savefig.facecolor": "none",
        "legend.labelcolor": FOG,
    })
    return D_OURS


def figure(width="col", height=2.2, **kw):
    """Figure at exact print width: 'col' (3.35 in), 'page' (7.0 in) or inches."""
    return dp.figure(width, height, **kw)


def label(ax, xy, text, dx=-6, dy=8, ha="right", color=None):
    """Mono call-out next to a point (e.g. 'BREAK-EVEN 0.93')."""
    ax.annotate(text.upper(), xy, xytext=(dx, dy), textcoords="offset points",
                ha=ha, fontsize=6.0, family=MONO,
                color=color or (BONE if _dark else INK))


def tag(ax, text, loc="upper right"):
    """Small mono tag inside the axes (e.g. 'SAMPLE DATA')."""
    x, ha = (0.98, "right") if "right" in loc else (0.02, "left")
    y, va = (0.97, "top") if "upper" in loc else (0.03, "bottom")
    ax.text(x, y, text.upper(), transform=ax.transAxes, ha=ha, va=va,
            fontsize=5.8, color=FOG if _dark else STEEL, family=MONO)


def save(fig, path, dark=None):
    """Vector PDF, fonts embedded. Dark figures get a transparent ground so
    they sit on the page's ink fill without a seam."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    dark = _dark if dark is None else dark
    fig.savefig(path, format="pdf", transparent=bool(dark))
    mpl.pyplot.close(fig)
