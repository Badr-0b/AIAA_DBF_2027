"""Proposal P1.1: general-arrangement plate and glance thumbnail from the TEAM'S OWN drawings.

Drop the drawings in proposal/figures/user/ as
    ga_top.(pdf|png)   ga_side.(pdf|png)   ga_front.(pdf|png)   [ga_iso.(pdf|png), optional]
Dark lines on a white or transparent background, all views exported at the SAME scale (and, for PNG,
the same dpi), no text or dimensions. PDFs are rasterised at 600 dpi with pdftoppm.
Line art is re-inked: luminance -> alpha, drawn in Mist on the Ink plate, so any line colour works.

Writes figures/fig_threeview.pdf (7.00 x 1.80 in plate), figures/fig_glance.pdf (thumbnail, only when a
top or iso view exists) and data/ga.tex:
    \\gaStatus  empty when the drawings are in, else an unfinished-value flag (\\dbftbd) for the build check
    \\gaThumb   the thumbnail \\includegraphics, or empty
Never falls back to the DB-02 drawing (team lead, 31 Oct 2026).

31 Oct 2026 (P1.3): SVG views from assets/SVGs/ga_svg.py (true-scale DB-02 Variant A line art, copied to
figures/user/ga_{top,side,front}.svg) are drawn as VECTORS on a one-column plate: TOP on the left, SIDE over
FRONT on the right, one common scale, with a scale bar. The SVG must be ga_svg.py output (absolute M/L/Z
paths in mm, one <g id=class> per line class). PDF/PNG drawings still go through the raster strip plate.
"""
from __future__ import annotations

import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PROP = HERE.parent
sys.path.insert(0, str(PROP.parent / "design-system" / "matplotlib"))

import dbfplot as dp                                   # noqa: E402
dp.COL, dp.PAGE = 3.48, 7.26     # proposal P1.2: 0.62 in side margins (main.tex), column 3.48 in
import matplotlib.image as mpimg                       # noqa: E402
import matplotlib.pyplot as plt                        # noqa: E402
import numpy as np                                     # noqa: E402

USER = PROP / "figures" / "user"
FIG = PROP / "figures"
MIST_RGB = np.array([0xE4, 0xE6, 0xE9]) / 255.0
PLATE_W, PLATE_H = dp.PAGE, 1.36


def find(name):
    for ext in (".svg", ".pdf", ".png"):
        p = USER / f"{name}{ext}"
        if p.exists():
            return p
    return None


def load_rgba(path, dpi=600):
    """Line art as an RGBA array, re-inked to Mist with alpha from darkness."""
    if path.suffix.lower() == ".pdf":
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "page"
            subprocess.run(["pdftoppm", "-r", str(dpi), "-png", "-singlefile", str(path), str(out)], check=True)
            img = mpimg.imread(str(out) + ".png")
    else:
        img = mpimg.imread(str(path))
    img = img.astype(float)
    if img.max() > 1.0:
        img /= 255.0
    rgb = img[..., :3] if img.ndim == 3 else np.repeat(img[..., None], 3, axis=2)
    a0 = img[..., 3] if img.ndim == 3 and img.shape[2] == 4 else np.ones(rgb.shape[:2])
    lum = rgb @ np.array([0.2126, 0.7152, 0.0722])
    alpha = np.clip((1.0 - lum) * a0 * 1.15, 0, 1)
    ys, xs = np.nonzero(alpha > 0.04)                     # trim empty margins
    if len(xs):
        alpha = alpha[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    out = np.zeros(alpha.shape + (4,))
    out[..., :3] = MIST_RGB
    out[..., 3] = alpha
    return out


def plate(views):
    """Compose top / side / front on the Ink plate at one common scale."""
    dp.use()
    fig = plt.figure(figsize=(PLATE_W, PLATE_H), facecolor=dp.INK)
    fig.set_layout_engine(None)
    slots = {"top": (0.01, 0.30), "side": (0.33, 0.38), "front": (0.73, 0.26)}   # x0, width (fractions)
    top, bot = 0.86, 0.08
    imgs = {k: load_rgba(p) for k, p in views.items()}
    # one scale for every view: the largest that fits each into its slot (pixels per figure-inch)
    s = min(min(slots[k][1] * PLATE_W / im.shape[1], (top - bot) * PLATE_H / im.shape[0]) for k, im in imgs.items())
    for k, im in imgs.items():
        x0, w = slots[k]
        wi, hi = im.shape[1] * s / PLATE_W, im.shape[0] * s / PLATE_H
        ax = fig.add_axes([x0 + (w - wi) / 2, bot + (top - bot - hi) / 2, wi, hi])
        ax.imshow(im, interpolation="lanczos")
        ax.axis("off")
        fig.text(x0, 0.95, k.upper(), fontfamily=dp.MONO, fontsize=7.0, color=dp.STEEL, va="top")
    fig.text(0.995, 0.03, "COMMON SCALE", ha="right", fontfamily=dp.MONO, fontsize=7.0,
             color=dp.STEEL)
    fig.savefig(FIG / "fig_threeview.pdf", facecolor=dp.INK)
    plt.close(fig)


# ------------------------------------------------------------------ vector plate from ga_svg.py SVGs
LINE = {   # class: (colour, width pt, dash)   outline/edges in Mist, construction lines dimmer
    "outline": (dp.MIST, 0.70, None),
    "edge": (dp.MIST, 0.45, None),
    "panel": (dp.FOG, 0.28, None),
    "ref": (dp.STEEL, 0.30, (0, (6, 2, 1, 2))),
    "hidden": (dp.STEEL, 0.30, (0, (2.2, 1.6))),
    "payload": (dp.FOG, 0.45, (0, (2.4, 1.3))),
    "cg": (dp.MIST, 0.40, None),
}
ORDER = ["hidden", "ref", "panel", "payload", "edge", "outline", "cg"]
DIM = dict(color=dp.FOG, lw=0.35)
TXT = dict(fontfamily=dp.MONO, fontsize=7.0, color=dp.FOG)
LAB = dict(fontfamily=dp.MONO, fontsize=7.0, color=dp.STEEL)
REPO = PROP.parent
DB02 = REPO / "DB-02_aircraft_variants"


def svg_lines(path):
    """{class: [N x 2 arrays in mm, SVG y down]} from a ga_svg.py drawing."""
    txt = Path(path).read_text(encoding="utf-8")
    out = {}
    for gid, body in re.findall(r'<g id="(\w+)"[^>]*>(.*?)</g>', txt, re.S):
        polys = []
        for d in re.findall(r'd="([^"]+)"', body):
            pts = np.array(re.findall(r"(-?[\d.]+),(-?[\d.]+)", d), float)
            if d.rstrip().endswith("Z"):
                pts = np.r_[pts, pts[:1]]
            polys.append(pts)
        out[gid] = polys
    if not out:
        raise ValueError(f"{path}: no <g id=class> line groups; export with assets/SVGs/ga_svg.py")
    return out


def bounds(lines):
    allp = np.vstack([p for v in lines.values() for p in v])
    return allp[:, 0].min(), allp[:, 1].min(), allp[:, 0].max(), allp[:, 1].max()


class View:
    """One ga_svg.py view placed on the plate: model metres -> plate inches."""

    def __init__(self, kind, lines, x0, y0, s):
        self.kind, self.lines, self.x0, self.y0, self.s = kind, lines, x0, y0, s
        self.bx0, self.by0, self.bx1, self.by1 = bounds(lines)

    def __call__(self, a, b):
        """top: (y, x); side: (x, z); front: (y, z)."""
        X, Y = {"top": (a * 1000, b * 1000), "side": (a * 1000, -b * 1000), "front": (-a * 1000, -b * 1000)}[self.kind]
        return self.x0 + (X - self.bx0) * self.s, self.y0 + (self.by1 - Y) * self.s

    def draw(self, ax):
        T = lambda p: (self.x0 + (p[:, 0] - self.bx0) * self.s, self.y0 + (self.by1 - p[:, 1]) * self.s)  # noqa: E731
        for k in ORDER:
            col, lw, dash = LINE[k]
            for p in self.lines.get(k, []):
                ax.plot(*T(p), color=col, lw=lw, ls=dash if dash else "-", solid_capstyle="round",
                        solid_joinstyle="round", dash_capstyle="butt")
        for p in self.lines.get("cgfill", []):
            ax.fill(*T(p), color=dp.MIST, lw=0, ls="solid")      # explicit: the house cycle would dash it


def ext(ax, p, q):
    ax.plot([p[0], q[0]], [p[1], q[1]], color=dp.STEEL, lw=0.3, solid_capstyle="butt")


def dim(ax, p, q, text, side):
    """Dimension line p-q with filled arrowheads; text below ('b'), above ('a') or left ('l') of it."""
    ax.annotate("", p, q, arrowprops=dict(arrowstyle="<|-|>", mutation_scale=4.0, shrinkA=0, shrinkB=0, **DIM))
    mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
    if side == "b":
        ax.text(mx, my - 0.022, text, ha="center", va="top", **TXT)
    elif side == "a":
        ax.text(mx, my + 0.018, text, ha="center", va="bottom", **TXT)
    else:
        ax.text(mx - 0.022, my, text, ha="right", va="center", rotation=90, **TXT)


def section_detail(ax, x0, y0, width):
    """Wing root section: SD7037 (same spline as the views), chord line, fuselage datum, incidence."""
    sys.path.insert(0, str(REPO / "assets" / "SVGs"))
    import ga_svg as G                                                  # noqa: E402
    x_le, z_le, c, tw = G.wing_at(0.0)
    k = (width - 0.22) / c                                              # inches per metre, room for "2°"
    sec = G.place(G.AF, 0.0, 0.0, c, tw)
    zmax = sec[:, 1].max()
    P = lambda x, z: (x0 + x * k, y0 + (z - sec[:, 1].min()) * k)        # noqa: E731
    xs, ys = zip(*[P(x, z) for x, z in sec])
    ax.plot(xs, ys, color=dp.MIST, lw=0.55, solid_joinstyle="round")
    te = (c * math.cos(math.radians(tw)), -c * math.sin(math.radians(tw)))
    ax.plot(*zip(P(0, 0), P(*te)), color=dp.STEEL, lw=0.3, ls=(0, (6, 2, 1, 2)))          # chord line
    ax.plot(*zip(P(0, 0), P(c * 1.12, 0)), color=dp.FOG, lw=0.35)                         # fuselage datum
    a = np.radians(np.linspace(-tw, 0, 12))
    r = c * 1.06
    ax.plot([P(r * math.cos(t), r * math.sin(t))[0] for t in a], [P(r * math.cos(t), r * math.sin(t))[1] for t in a],
            color=dp.FOG, lw=0.35)
    ax.text(x0, P(0, zmax)[1] + 0.03, "WING ROOT, SD7037", va="bottom", **LAB)
    raw = G.SD_RAW
    i = int(raw[:, 0].argmin())
    up, lo = raw[:i + 1][::-1], raw[i:]
    xg = np.linspace(0.0, 1.0, 401)
    tc = float((np.interp(xg, up[:, 0], up[:, 1]) - np.interp(xg, lo[:, 0], lo[:, 1])).max())
    ax.text(x0, y0 - 0.02, f"CHORD {c:.3f} M, {100 * tc:.1f} % THICK", va="top", ha="left", **TXT)
    ax.text(P(c * 1.13, 0)[0], P(0, -0.008)[1], f"{tw:.0f} DEG", ha="left", va="center", **TXT)
    return c


def sensor_detail(ax, x0, y0, height):
    """Sensor dart (8 kg design) in its container, side section, from DB-02's payload model."""
    sys.path.insert(0, str(DB02 / "src"))
    from payload import model as PM                                    # noqa: E402
    import json as _j
    sel = _j.loads((DB02 / "out" / "variants" / "selection.json").read_text(encoding="utf-8"))["A"]
    c = PM.container(sel["m_hi"], 150.0, 1.524, ballast="tungsten", fins="cruciform", sling_deg=15.0)
    s_ = c["sensor"]
    Lo, Ho = c["dims_m"][0], c["dims_m"][2]
    Li, Hi = c["inner_m"][0], c["inner_m"][2]
    k = height / Ho
    R = lambda x, z: (x0 + x * k, y0 + z * k)                           # noqa: E731
    def box(a, b, w, h, ec, lw):
        pts = [R(a, b), R(a + w, b), R(a + w, b + h), R(a, b + h), R(a, b)]
        ax.plot(*zip(*pts), color=ec, lw=lw, solid_joinstyle='miter')
    box(0, 0, Lo, Ho, ec=dp.MIST, lw=0.5)
    xi, zi = (Lo - Li) / 2, (Ho - Hi) / 2
    box(xi, zi, Li, Hi, ec=dp.FOG, lw=0.3)
    # foam hatch between box and cavity
    from shapely.geometry import LineString as LS, box as sbox
    foam = sbox(0, 0, Lo, Ho).difference(sbox(xi, zi, xi + Li, zi + Hi))
    for t in np.arange(-Ho, Lo, 0.022):
        seg = LS([(t, 0), (t + Ho, Ho)]).intersection(foam)
        for g_ in getattr(seg, "geoms", [seg]):
            if not g_.is_empty:
                ax.plot(*zip(*[R(*p) for p in g_.coords]), color=dp.STEEL, lw=0.25)
    # dart, nose left, centred in the cavity
    L, d = s_["length_m"], s_["diameter_m"]
    rad, nose, sf = d / 2, PM.NOSE_M, (s_["fin_span_m"] - d) / 2
    cx0, cz = xi + (Li - L) / 2, Ho / 2
    xo = np.linspace(0, nose, 20)
    rho = (rad * rad + nose * nose) / (2 * rad)                          # tangent ogive
    ro = np.sqrt(np.clip(rho ** 2 - (nose - xo) ** 2, 0, None)) + rad - rho
    up = [(cx0 + x, cz + r) for x, r in zip(xo, ro)] + [(cx0 + L, cz + rad)]
    lo = [(cx0 + L, cz - rad)] + [(cx0 + x, cz - r) for x, r in zip(xo[::-1], ro[::-1])]
    ax.plot(*zip(*[R(*p) for p in up + lo + up[:1]]), color=dp.MIST, lw=0.5, solid_joinstyle="round")
    cr, ct = 0.060, 0.030                                               # model fin chords (dart_stability)
    for sg in (1, -1):
        fin = [(cx0 + L - cr, cz + sg * rad), (cx0 + L - cr, cz + sg * (rad + sf)), (cx0 + L - cr + ct, cz + sg * (rad + sf)),
               (cx0 + L, cz + sg * rad)]
        ax.plot(*zip(*[R(*p) for p in fin]), color=dp.MIST, lw=0.5, solid_joinstyle="round")
    ax.plot(*zip(R(cx0 + L - cr, cz), R(cx0 + L, cz)), color=dp.FOG, lw=0.3)                 # side fins edge-on
    xcg = cx0 + s_["cg_from_nose_m"]
    tt = np.linspace(0, 2 * np.pi, 40)
    ax.plot(*zip(*[R(xcg + 0.006 * np.cos(a), cz + rad + 0.007 + 0.006 * np.sin(a)) for a in tt]), color=dp.MIST, lw=0.4)
    for xb in (0.75 * nose, s_["cg_from_nose_m"] + 0.012, L - cr - 0.012):                  # three LED bands
        rb = np.interp(xb, xo, ro) if xb < nose else rad
        ax.plot(*zip(R(cx0 + xb, cz - rb), R(cx0 + xb, cz + rb)), color=dp.FOG, lw=0.3)
    ax.text(x0 + Lo * k, y0 + height + 0.03, "SENSOR IN CONTAINER", va="bottom", ha="right", **LAB)
    return dict(L=L, d=d, span=s_["fin_span_m"], foam=c["foam_mm"], outer=c["dims_m"], k=k)


def plate_vector(paths):
    """One-column plate: TOP left, SIDE over FRONT right at one scale with key dimensions; a bottom strip with
    the wing root section (SD7037, incidence) and the sensor dart in its container; scale bar."""
    dp.use()
    L = {k: svg_lines(p) for k, p in paths.items()}
    B = {k: bounds(v) for k, v in L.items()}
    w = {k: b[2] - b[0] for k, b in B.items()}
    h = {k: b[3] - b[1] for k, b in B.items()}
    W, m, g, lab, pl, dl = dp.COL, 0.06, 0.12, 0.13, 0.15, 0.17
    s = min((W - 2 * m - g - pl) / (w["top"] + w["side"]), (W - 2 * m - g) / (w["top"] + w["front"]))   # in/mm
    left = lab + h["top"] * s + dl
    right = lab + h["side"] * s + dl + lab + h["front"] * s
    strip = 0.54
    H = m + max(left, right) + 0.10 + strip + m
    fig = plt.figure(figsize=(W, H), facecolor=dp.INK)
    fig.set_layout_engine(None)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W); ax.set_ylim(0, H); ax.set_aspect("equal"); ax.axis("off")
    ax.set_facecolor(dp.INK)
    ax.set_prop_cycle(color=[dp.MIST], linestyle=["-"])            # the house cycle dashes plain plots
    top_y = H - m
    # TOP with the span
    ax.text(m, top_y, "TOP", va="top", **LAB)
    vt = View("top", L["top"], m, top_y - lab - h["top"] * s, s)
    vt.draw(ax)
    b2 = 0.91
    yd = vt.y0 - 0.075
    for sy in (-1, 1):
        p = vt(sy * b2, 0.80)
        ext(ax, (p[0], p[1] - 0.02), (p[0], yd - 0.03))
    dim(ax, (vt(-b2, 0)[0], yd), (vt(b2, 0)[0], yd), "1.82 M", "b")
    # SIDE with prop diameter and length from the propeller plane
    xr = m + w["top"] * s + g
    colw = W - m - xr
    ax.text(xr, top_y, "SIDE", va="top", **LAB)
    vs = View("side", L["side"], xr + pl, top_y - lab - h["side"] * s, s)
    vs.draw(ax)
    R_ = 0.254
    xp = vs(-0.075, 0)[0]
    for sz in (-1, 1):
        a_ = vs(-0.012, sz * R_)
        ext(ax, (a_[0] - 0.01, a_[1]), (xp - 0.03, a_[1]))
    dim(ax, (xp, vs(0, -R_)[1]), (xp, vs(0, R_)[1]), "DIA 0.51 M", "l")
    yl = vs.y0 - 0.075
    x_te = 1.6637
    for (xa, za) in ((0.0, -R_ - 0.012), (x_te, 0.05)):
        p = vs(xa, za)
        ext(ax, p, (p[0], yl - 0.03))
    dim(ax, (vs(0, 0)[0], yl), (vs(x_te, 0)[0], yl), "1.66 M", "b")
    # FRONT
    yfl = vs.y0 - dl
    ax.text(xr, yfl, "FRONT", va="top", **LAB)
    vf = View("front", L["front"], xr + (colw - w["front"] * s) / 2, yfl - lab - h["front"] * s, s)
    vf.draw(ax)
    # bottom strip: root section, sensor, scale bar
    ys0 = m + 0.12
    ax.plot([m, W - m], [m + strip + 0.04] * 2, color=dp.GRAPHITE, lw=0.4)
    section_detail(ax, m, ys0, 1.52)
    hs = strip - 0.20
    sd = sensor_detail(ax, W - m - 0.288 / 0.3033 * hs, ys0 - 0.05, hs)
    xb0 = m + 1.92
    yb = ys0 + 0.10
    ax.text(xb0, yb + 0.18, "COMMON SCALE", va="top", **LAB)
    for i in range(4):
        ax.add_patch(plt.Rectangle((xb0 + i * 250 * s, yb), 250 * s, 0.022, lw=0.4, ec=dp.FOG,
                                   fc=dp.FOG if i % 2 == 0 else dp.INK))
    for v, t in ((0, "0"), (500, "0.5"), (1000, "1 m")):
        ax.text(xb0 + v * s, yb - 0.025, t, va="top", ha="left" if v == 0 else ("center" if v == 500 else "right"),
                **TXT)
    fig.savefig(FIG / "fig_threeview.pdf", facecolor=dp.INK)
    plt.close(fig)
    print(f"GA: sensor detail dart {sd['L'] * 1000:.0f} x {sd['d'] * 1000:.0f} mm, fins {sd['span'] * 1000:.0f} mm, "
          f"foam {sd['foam']:.0f} mm, box {' x '.join(f'{v * 1000:.0f}' for v in sd['outer'])} mm")
    return s * 1000                                                         # inches per metre


def placeholder():
    dp.use()
    fig = plt.figure(figsize=(PLATE_W, PLATE_H), facecolor=dp.INK)
    fig.set_layout_engine(None)
    ax = fig.add_axes([0.01, 0.06, 0.98, 0.88])
    ax.set_facecolor(dp.INK); ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_color(dp.GRAPHITE); sp.set_linewidth(0.5); sp.set_linestyle((0, (2, 2)))
    for x, lab in ((0.16, "TOP"), (0.52, "SIDE"), (0.86, "FRONT")):
        ax.text(x, 0.5, lab, transform=ax.transAxes, ha="center", va="center", fontfamily=dp.MONO, fontsize=6,
                color=dp.GRAPHITE)
    ax.text(0.5, 0.12, "TEAM GENERAL-ARRANGEMENT DRAWING  /  DROP FILES IN proposal/figures/user/",
            transform=ax.transAxes, ha="center", fontfamily=dp.MONO, fontsize=5.2, color=dp.STEEL)
    fig.savefig(FIG / "fig_threeview.pdf", facecolor=dp.INK)
    plt.close(fig)


def thumb(path):
    dp.use()
    im = load_rgba(path)
    h_in = 1.30
    w_in = min(2.0, h_in * im.shape[1] / im.shape[0])
    fig = plt.figure(figsize=(w_in, h_in), facecolor=dp.INK)
    fig.set_layout_engine(None)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.imshow(im, interpolation="lanczos", aspect="equal")
    ax.axis("off")
    fig.savefig(FIG / "fig_glance.pdf", facecolor=dp.INK)
    plt.close(fig)


def main():
    USER.mkdir(parents=True, exist_ok=True)
    views = {k: find(f"ga_{k}") for k in ("top", "side", "front")}
    have = {k: p for k, p in views.items() if p}
    status = ""
    if len(have) == 3 and all(p.suffix.lower() == ".svg" for p in have.values()):
        ipm = plate_vector(have)
        print(f"GA: vector plate, {ipm:.3f} in/m (1:{39.37 / ipm:.0f} on the page)")
    elif len(have) == 3:
        plate(have)
    else:
        placeholder()
        status = r"\dbftbd{team GA drawing}"
    t = find("ga_iso") or views["top"]
    thumb_tex = ""
    if t and t.suffix.lower() == ".svg":                                   # page 1 no longer shows a thumbnail
        t = None
    if t:
        thumb(t)
        thumb_tex = r"\centering\includegraphics[width=0.70\linewidth]{figures/fig_glance.pdf}\par\vspace{4pt}\raggedright"
    else:
        (FIG / "fig_glance.pdf").unlink(missing_ok=True)
    (PROP / "data" / "ga.tex").write_text(
        "% GENERATED by tools/p1_ga.py: team GA drawings present or not.\n"
        f"\\newcommand\\gaStatus{{{status}}}\n\\newcommand\\gaThumb{{{thumb_tex}}}\n", encoding="utf-8")
    print(f"GA: {len(have)}/3 views from figures/user/" + ("" if len(have) == 3 else " -> placeholder plate")
          + (f"; thumbnail from {t.name}" if t else "; no thumbnail"))


if __name__ == "__main__":
    main()
