"""Matplotlib style for DBF team documents (Geist / Geist Mono, monochrome).

Produces vector PDF figures at their exact printed size, in the same fonts
and palette as dbfdoc.cls, so 8 pt in a figure is 8 pt on the page.

    import sys; sys.path.insert(0, "../design-system/matplotlib")
    import dbfplot as dp
    dp.use()
    fig, ax = dp.figure("col", 2.2)      # 'col' = 3.35 in, 'page' = 7.0 in
    ax.plot(x, y)                        # grey cycle; dp.ACCENT for "ours"
    dp.save(fig, "figures/sensitivity.pdf")

Rules: no titles inside plots (the caption is the title); axis labels carry
units; the design point / selected option is the only element in ACCENT.
"""
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from cycler import cycler
from matplotlib import font_manager

FONTS = Path(__file__).resolve().parents[1] / "fonts"

# Grid (inches): one column, or the full text width
COL = 3.35
PAGE = 7.00

INK = "#0B0C0E"
GRAPHITE = "#2B2E33"
STEEL = "#5B616B"
FOG = "#A9AEB6"
MIST = "#E4E6E9"
BONE = "#F3F2EE"
ACCENT = INK  # monochrome system: "ours" = ink, heavier line / filled marker

SANS = "Geist"
MONO = "Geist Mono"


def use():
    """Register the bundled fonts and apply the house rcParams."""
    for d in ("Geist", "GeistMono"):
        for ttf in (FONTS / d).glob("*.ttf"):
            font_manager.fontManager.addfont(str(ttf))
    greys = cycler(color=[INK, STEEL, FOG, GRAPHITE, STEEL, FOG]) + cycler(
        linestyle=["-", "-", "-", "--", "--", ":"])
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": [SANS],
        "font.size": 8,
        "axes.labelsize": 8,
        "axes.titlesize": 8,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "legend.fontsize": 7,
        "mathtext.fontset": "custom",
        "mathtext.rm": SANS,
        "mathtext.it": f"{SANS}:italic",
        "mathtext.bf": f"{SANS}:semibold",
        "text.color": INK,
        "axes.labelcolor": INK,
        "axes.edgecolor": GRAPHITE,
        "axes.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "axes.prop_cycle": greys,
        "axes.labelpad": 3,
        "grid.color": MIST,
        "grid.linewidth": 0.5,
        "xtick.color": GRAPHITE,
        "ytick.color": GRAPHITE,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "xtick.major.size": 2.5,
        "ytick.major.size": 2.5,
        "lines.linewidth": 1.0,
        "lines.markersize": 4,
        "legend.frameon": False,
        "legend.handlelength": 1.8,
        "figure.facecolor": "white",
        "figure.dpi": 150,
        "figure.constrained_layout.use": True,
        "figure.constrained_layout.h_pad": 0.02,
        "figure.constrained_layout.w_pad": 0.02,
        "savefig.facecolor": "white",
        "pdf.fonttype": 42,
    })
    return ACCENT


def figure(width="col", height=2.2, **kw):
    """Figure at exact print width: 'col' (3.35 in), 'page' (7.0 in) or inches."""
    w = {"col": COL, "page": PAGE}.get(width, width)
    fig, ax = plt.subplots(figsize=(w, height), **kw)
    for a in (ax.flat if hasattr(ax, "flat") else [ax]):
        style_axes(a)
    return fig, ax


def style_axes(ax):
    """Mono tick labels; quiet axes."""
    ax.tick_params(labelfontfamily=MONO)


def label(ax, xy, text, dx=-6, dy=8, ha="right"):
    """Mono call-out (e.g. 'DESIGN POINT') next to a data point."""
    ax.annotate(text.upper(), xy, xytext=(dx, dy), textcoords="offset points",
                ha=ha, fontsize=6.0, family=MONO, color=INK)


def tag(ax, text, loc="upper right"):
    """Small mono tag inside the axes (e.g. 'PRELIMINARY')."""
    x, ha = (0.98, "right") if "right" in loc else (0.02, "left")
    y, va = (0.97, "top") if "upper" in loc else (0.03, "bottom")
    ax.text(x, y, text.upper(), transform=ax.transAxes, ha=ha, va=va,
            fontsize=5.8, color=STEEL, family=MONO)


def save(fig, path):
    """Vector PDF, fonts embedded (TrueType), exact figure size."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, format="pdf")
    plt.close(fig)
