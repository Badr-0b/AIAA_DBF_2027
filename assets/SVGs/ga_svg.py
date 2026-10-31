"""DB-02 Variant A general-arrangement line art: top view and side view as layered SVG (31 Oct 2026).

Run:  python assets/SVGs/ga_svg.py        -> top_view.svg, side_view.svg, front_view.svg, sd7037_profile.svg
      then copy the three views to proposal/figures/user/ga_{top,side,front}.svg (Fig. 08, tools/p1_ga.py)

What it draws
  The aircraft only (no text, dimensions or centre lines), in the style of the reference blueprint
  REFERENCE_ DB-02 Variant A UAV Blueprint.png, but at TRUE SCALE. The reference is not to scale: its own
  labels give 765 px/m across the span, 427 px/m along the length and 192 px/m on the scale bar.
  Every primary dimension therefore comes from the design files, not from the picture:
    wing, tail, fin      DB-02_aircraft_variants/out/variants/variants_geometry.json ["A"]
                         (AVL 3.52 model out/variants/avl/variant_A.avl, checked below)
    incidence 2.0 deg, washout 2.0 deg, dihedral 2.0 deg   geometry_variants.py (ANGLE, WASHOUT, DIHEDRAL)
    wing section         SD7037 (sd7037.dat in this folder = DB-02 src/geometry/airfoils/sd7037.dat)
    tail sections        NACA 0009 (AVL model)
    fuselage box         1.20 m x 0.345 m x 0.355 m, wing root LE on the top (z_wing = fus_h / 2)
    propeller            APC 20x15E, D 0.508 m, pitch 0.381 m; prop axis 0.369 m above ground (S6 install)
    motor                T-Motor AT7215, 81.4 mm x 57.9 mm (store.tmotor.com, read 31 Oct 2026)
    flap                 Fowler, 30 % chord, root to 60 % semispan (DB-02)
  DRAWING ESTIMATES (not in the design files; chosen to look like the reference and to be buildable):
    ailerons 60-95 % semispan, 25 % chord (DB-02 REF-D01 values); elevator and rudder 35 % chord
    (DB-02 build.py tail() defaults); tip caps over the outer 5 % of each surface (chamfered LE corner,
    rounded TE corner, as in the reference); flap split at mid-span; two-piece wing joint on the centre
    line; fuselage nose taper (firewall 0.29 x 0.27 m at x 0.105), tail cone from x 0.68 (behind the
    D&R drum) to a 50 mm boom clamp at x 1.20, side wall cut to the wing's lower surface (saddle);
    32 mm carbon boom (REF-D01) and tail saddle; motor standoffs; gear: nose wheel 0.10 m at x 0.17,
    mains 0.11 m at x 0.53, track 0.50 m (REF-D01 sizes), tip-back about 15 deg at the design CG.
  Left out of the reference on purpose: the LE/TE root fillets (they would add wing area the design does
  not have) and the top hatch (the bay, centred at x 0.433, sits under the wing, which would cover it).
Frame: x aft from the propeller plane, y to starboard, z up, fuselage centre line z = 0; metres.
SVG units are millimetres at full scale; the documents are sized at 1:20.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
from scipy.interpolate import PchipInterpolator, splev, splprep
from shapely.geometry import GeometryCollection, LineString, MultiLineString, Point, Polygon
from shapely.ops import linemerge, unary_union

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DB02 = REPO / "DB-02_aircraft_variants"
VAR = json.loads((DB02 / "out" / "variants" / "variants_geometry.json").read_text(encoding="utf-8"))["A"]
G, T = VAR["geometry"], VAR["tails"]

SCALE = 20                       # document scale 1:20 (the reference's title block says 1:20)
EPS = 0.0002                     # occluders are shrunk by 0.2 mm so coincident edges survive

# ------------------------------------------------------------------ design numbers
B2 = math.sqrt(G["AR"] * G["S"]) / 2          # 0.910 m semispan (span 1.82 m)
CR, CT = G["cr"], G["ct"]
XLE_R = G["x_le"]
Z_W = G["z_wing"]
INC, WASH, DIH = 2.0, 2.0, 2.0                # deg: AVL ANGLE, tip twist -2, dihedral (geometry_variants.py)
XLE_T = XLE_R + 0.25 * (CR - CT)              # straight quarter-chord line (AVL tip section)
FUS_L, FUS_W, FUS_H = G["fus_len"], G["fus_w"], G["fus_h"]
FLAP_CF, FLAP_END = G["cf"], G["flap_span"]   # 0.30 chord, to 60 % semispan

XH, CRH, CTH, BH2 = T["xh"], T["crh"], T["cth"], T["bh"] / 2
XLEH_T = XH + 0.25 * (CRH - CTH)
ZT = T["zt"]
CRV, CTV, BV = T["crv"], T["ctv"], T["bv"]
XLEV_R = T["x_ach"] - 0.25 * CRV
XLEV_T = XLEV_R + 0.35 * (CRV - CTV)

PROP_D, PROP_P = 0.508, 0.381                 # APC 20x15E
AXIS_H = 0.369                                # prop axis above ground (0.115 m tip clearance)
Z_GROUND = -AXIS_H

# drawing estimates
AIL_START, AIL_END, AIL_CF = 0.60, 0.95, 0.25
SEAM = 0.95                                    # tip-cap joint, fraction of semispan (all surfaces)
FLAP_SPLIT_Y = 0.36
ELEV_CF, RUD_CF = 0.35, 0.35
X_FW = 0.105                                   # firewall (fuselage front face)
X_NOSE = 0.20                                  # end of the nose taper
X_CONE = 0.68                                  # tail cone starts behind the D&R drum (x 0.633, dia 0.07)
FW_W, FW_H = 0.29, 0.27                        # firewall face
CONE_END = dict(w=0.05, z0=0.005, z1=0.055)    # boom clamp, centred on the boom
BOOM_R, BOOM_Z, BOOM_X0, BOOM_X1 = 0.016, 0.030, 1.17, 1.645
X_MAIN, Y_MAIN, D_MAIN, W_MAIN = 0.53, 0.25, 0.110, 0.035
X_NOSEW, D_NOSEW = 0.17, 0.100


def check_against_avl():
    """The AVL file AVL actually ran must match the JSON numbers used here (4-decimal file)."""
    txt = (DB02 / "out" / "variants" / "avl" / "variant_A.avl").read_text()
    secs = re.findall(r"SECTION\s*\n\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)", txt)
    s = [[float(v) for v in row] for row in secs]
    want = [[XLE_R, 0, Z_W, CR, 0], [XLE_T, B2, Z_W + B2 * math.tan(math.radians(DIH)), CT, -WASH],
            [XH, 0, ZT, CRH, 0], [XLEH_T, BH2, ZT, CTH, 0],
            [XLEV_R, 0, ZT, CRV, 0], [XLEV_T, 0, ZT + BV, CTV, 0]]
    for a, b in zip(s, want):
        assert all(abs(p - q) < 6e-5 for p, q in zip(a, b)), (a, b)
    assert re.search(r"ANGLE\s*\n\s*2\.0", txt)


# ------------------------------------------------------------------ sections
def load_dat(path):
    pts = []
    for line in Path(path).read_text().splitlines():
        p = line.split()
        if len(p) >= 2:
            try:
                pts.append((float(p[0]), float(p[1])))
            except ValueError:
                pass
    return np.array(pts)


SD_RAW = load_dat(HERE / "sd7037.dat")


def sd7037(n=1600):
    """Closed SD7037 loop (TE upper -> LE -> TE lower), cubic spline through all 61 points."""
    x, y = SD_RAW[:, 0], SD_RAW[:, 1]
    d = np.r_[0, np.cumsum(np.hypot(np.diff(x), np.diff(y)))]
    tck, u = splprep([x, y], u=d / d[-1], s=0, k=3)
    w = np.linspace(0, 1, n)
    ule = u[np.argmin(x)]
    uu = np.where(w < 0.5, ule * (1 - np.cos(np.pi * w)) , ule + (1 - ule) * (1 - np.cos(np.pi * (w - 0.5))))
    uu = np.clip(uu, 0, 1)
    xs, ys = splev(uu, tck)
    xs[0], ys[0], xs[-1], ys[-1] = 1.0, 0.0, 1.0, 0.0
    return np.c_[xs, ys], tck


AF, AF_TCK = sd7037()


def naca00(t=0.09, n=400):
    b = 0.5 * (1 - np.cos(np.linspace(0, np.pi, n)))
    yt = 5 * t * (0.2969 * np.sqrt(b) - 0.1260 * b - 0.3516 * b ** 2 + 0.2843 * b ** 3 - 0.1036 * b ** 4)
    up = np.c_[b[::-1], yt[::-1]]
    lo = np.c_[b[1:], -yt[1:]]
    return np.r_[up, lo]


N09 = naca00()


def place(af, x_le, z_le, c, twist_deg=0.0):
    """Section in the x-z plane: scale, pitch nose-up by twist about the LE, translate."""
    th = math.radians(twist_deg)
    dx, dz = af[:, 0] * c, af[:, 1] * c
    return np.c_[x_le + dx * math.cos(th) + dz * math.sin(th), z_le - dx * math.sin(th) + dz * math.cos(th)]


def wing_at(s):
    """Station s = |y| / semispan: LE x, LE z, chord, twist (AVL linear interpolation)."""
    return (XLE_R + s * (XLE_T - XLE_R), Z_W + s * B2 * math.tan(math.radians(DIH)),
            CR + s * (CT - CR), INC - s * WASH)


def htail_at(s):
    return XH + s * (XLEH_T - XH), CRH + s * (CTH - CRH)


def fin_at(s):
    return XLEV_R + s * (XLEV_T - XLEV_R), CRV + s * (CTV - CRV)


# ------------------------------------------------------------------ 2-D helpers
def arc(c, r, a0, a1, n=40):
    a = np.linspace(a0, a1, n)
    return np.c_[c[0] + r * np.cos(a), c[1] + r * np.sin(a)]


def fillet(pts, radii, n=24):
    """Replace vertex i of a closed polygon by a tangent arc of radius radii[i]."""
    P = [np.asarray(p, float) for p in pts]
    out = []
    m = len(P)
    for i, p in enumerate(P):
        r = radii.get(i, 0.0)
        if r <= 0:
            out.append(p)
            continue
        a, b = P[i - 1], P[(i + 1) % m]
        u1 = (a - p) / np.linalg.norm(a - p)
        u2 = (b - p) / np.linalg.norm(b - p)
        phi = math.acos(np.clip(np.dot(u1, u2), -1, 1)) / 2
        d = r / math.tan(phi)
        t1, t2 = p + u1 * d, p + u2 * d
        bis = (u1 + u2) / np.linalg.norm(u1 + u2)
        c = p + bis * (r / math.sin(phi))
        a0 = math.atan2(*(t1 - c)[::-1])
        a1 = math.atan2(*(t2 - c)[::-1])
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        out.extend(arc(c, r, a0, a0 + da, n))
    return np.array(out)


def poly(pts):
    p = Polygon(pts)
    return p if p.is_valid else p.buffer(0)


def ring(pts):
    pts = np.asarray(pts)
    return LineString(np.r_[pts, pts[:1]])


def line(*pts):
    return LineString(np.asarray(pts, float))


def circle(c, r, n=180):
    return arc(c, r, 0, 2 * math.pi, n)[:-1]


class Part:
    """A component in one view: region it hides, lines it shows, by class."""

    def __init__(self, name, region, lines=None, hidden_lines=False):
        self.name = name
        self.region = region
        self.lines = lines or []          # [(LineString, cls)]
        self.hidden_lines = hidden_lines  # also emit the parts hidden by nearer parts as dashed lines

    def add(self, geom, cls="edge"):
        self.lines.append((geom, cls))
        return self


# ------------------------------------------------------------------ propeller and motor (axisymmetric)
def nose_assembly(view):
    """Prop, nut, hub, motor and mount in a local (a = axial x, r = lateral) frame.
    Top view: blades along y.  Side view: blades along z (drafting convention: full diameter in each view)."""
    R = PROP_D / 2
    rr = np.linspace(0.016, R, 400)
    tab_r = np.array([0.06, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.92, 1.0])
    tab_c = np.array([0.080, 0.130, 0.165, 0.185, 0.190, 0.185, 0.170, 0.150, 0.122, 0.098, 0.075])  # c/R, APC-like
    c = PchipInterpolator(tab_r, tab_c)(rr / R) * R
    tip = rr / R > 0.86
    c[tip] *= np.sqrt(np.clip(1 - ((rr[tip] / R - 0.86) / 0.14) ** 2, 0, 1))
    beta = np.arctan(PROP_P / (2 * np.pi * rr))
    tc = 0.12 - 0.05 * (rr / R)
    t = tc * c
    a_le = -0.35 * c * np.sin(beta) - 0.5 * t * np.cos(beta)
    a_te = 0.65 * c * np.sin(beta) + 0.5 * t * np.cos(beta)
    blade = np.r_[np.c_[a_le, rr], np.c_[a_te, rr][::-1]]

    def m(pts):                      # local (a, r) -> view (u, v)
        pts = np.asarray(pts, float)
        a, r = pts[:, 0], pts[:, 1]
        return np.c_[r, a] if view == "top" else np.c_[a, -r]

    def rect(a0, a1, r0, r1, rad=None):
        p = [(a0, r0), (a1, r0), (a1, r1), (a0, r1)]
        return fillet(p, {i: rad for i in range(4)}) if rad else np.array(p)

    parts = []
    nut = np.r_[[(-0.012, 0.009)], np.array([(-0.022 - 0.008 * math.sin(a), 0.009 * math.cos(a))
                                            for a in np.linspace(0, math.pi, 31)]), [(-0.012, -0.009)]]
    parts.append(Part("prop nut", poly(m(nut))).add(ring(m(nut))))
    hub = rect(-0.012, 0.012, -0.018, 0.018, 0.004)
    parts.append(Part("prop hub", poly(m(hub))).add(ring(m(hub))))
    adapter = rect(0.012, 0.019, -0.013, 0.013)                  # stands proud of the blade roots
    parts.append(Part("prop adapter", poly(m(adapter))).add(ring(m(adapter))))
    for sgn in (1, -1):
        bl = blade * [1, sgn]
        parts.append(Part("blade", poly(m(bl))).add(ring(m(bl))))
    can = fillet([(0.019, -0.0407), (0.0605, -0.0407), (0.0605, 0.0407), (0.019, 0.0407)], {0: 0.004, 3: 0.004})
    p = Part("motor can", poly(m(can))).add(ring(m(can)))
    for a in (0.0275, 0.0335, 0.0395, 0.0455, 0.0515):
        p.add(LineString(m([(a, -0.0407), (a, 0.0407)])), "panel")
    parts.append(p)
    base = rect(0.0605, 0.0769, -0.034, 0.034)
    parts.append(Part("motor base", poly(m(base))).add(ring(m(base))))
    plate = rect(0.0769, 0.0809, -0.050, 0.050, 0.0015)
    parts.append(Part("mount plate", poly(m(plate))).add(ring(m(plate))))
    for sgn in (1, -1):
        so = np.array([(0.0809, 0.032), (0.0809, 0.040), (X_FW, 0.050), (X_FW, 0.042)]) * [1, sgn]
        parts.append(Part("standoff", poly(m(so))).add(ring(m(so))))
    return parts


# ------------------------------------------------------------------ top view
def top_view():
    parts = []                                                 # view u = y, v = x (nose up)

    # wing planform with tip caps (starboard half, mirrored)
    def chord_x(s, f):
        x, _, c, tw = wing_at(s)
        return x + f * c * math.cos(math.radians(tw))

    ys = B2 * SEAM
    ss = np.linspace(0, SEAM, 40)
    le = [(s * B2, chord_x(s, 0)) for s in ss]
    tip = [(ys, chord_x(SEAM, 0)), (B2, chord_x(1, 0) + 0.060), (B2, chord_x(1, 1))]
    te = [(s * B2, chord_x(s, 1)) for s in np.linspace(1, 0, 41)]
    half = le + tip[1:] + te[1:]
    corner = len(le) + 1                                       # index of (B2, TE tip)
    half = np.array(fillet(half, {corner: 0.020}))
    full = np.r_[half, (half * [-1, 1])[::-1]]
    wing = Part("wing", poly(full)).add(ring(full))
    for sgn in (1, -1):
        y0 = 0.1725 * sgn
        s0 = FUS_W / 2 / B2
        yy = lambda s: s * B2 * sgn                            # noqa: E731
        # tip-cap joint
        wing.add(line((yy(SEAM), chord_x(SEAM, 0)), (yy(SEAM), chord_x(SEAM, 1))), "panel")
        # aileron hinge and ends
        sa = np.linspace(AIL_START, AIL_END, 20)
        wing.add(LineString([(yy(s), chord_x(s, 1 - AIL_CF)) for s in sa]), "panel")
        # flap (Fowler, 30 %), fuselage side to 60 % semispan, split at mid-span
        sf = np.linspace(s0, FLAP_END, 20)
        wing.add(LineString([(yy(s), chord_x(s, 1 - FLAP_CF)) for s in sf]), "panel")
        for s in (s0, FLAP_SPLIT_Y / B2, FLAP_END):
            wing.add(line((yy(s), chord_x(s, 1 - FLAP_CF)), (yy(s), chord_x(s, 1))), "panel")
    wing.add(line((0, chord_x(0, 0)), (0, chord_x(0, 1))), "panel")        # two-piece wing joint
    xq = XLE_R + 0.25 * CR
    wing.add(line((-ys, xq), (ys, xq)), "ref")                              # straight quarter-chord (spar)
    parts.append(wing)

    # fin, seen from above: NACA 0009 root lens, tip-cap joint lens
    fr = place(N09, XLEV_R, 0, CRV)
    fin = Part("fin", poly(np.c_[fr[:, 1], fr[:, 0]])).add(ring(np.c_[fr[:, 1], fr[:, 0]]))
    parts.append(fin)

    # horizontal tail
    def hx(s, f):
        x, c = htail_at(s)
        return x + f * c

    hs = BH2 * SEAM
    le = [(s * BH2, hx(s, 0)) for s in np.linspace(0, SEAM, 20)]
    tipp = [(BH2, hx(1, 0) + 0.040), (BH2, hx(1, 1))]
    te = [(s * BH2, hx(s, 1)) for s in np.linspace(1, 0, 21)]
    half = le + tipp + te[1:]
    half = np.array(fillet(half, {len(le) + 1: 0.015}))
    full = np.r_[half, (half * [-1, 1])[::-1]]
    ht = Part("htail", poly(full)).add(ring(full))
    for sgn in (1, -1):
        ht.add(line((sgn * hs, hx(SEAM, 0)), (sgn * hs, hx(SEAM, 1))), "panel")
        se = np.linspace(0.02 / BH2, SEAM, 12)
        ht.add(LineString([(sgn * s * BH2, hx(s, 1 - ELEV_CF)) for s in se]), "panel")
        ht.add(line((sgn * 0.02, hx(0.02 / BH2, 1 - ELEV_CF)), (sgn * 0.02, hx(0.02 / BH2, 1))), "panel")
    ht.add(line((-hs, XH + 0.25 * CRH), (hs, XH + 0.25 * CRH)), "ref")
    parts.append(ht)

    # fuselage: tapered nose, box, tail cone
    w2, f2 = FUS_W / 2, FW_W / 2
    ol = [(-f2, X_FW), (f2, X_FW), (w2, X_NOSE), (w2, X_CONE), (CONE_END["w"] / 2, FUS_L),
          (-CONE_END["w"] / 2, FUS_L), (-w2, X_CONE), (-w2, X_NOSE)]
    ol = fillet(ol, {0: 0.022, 1: 0.022})
    fus = Part("fuselage", poly(ol), hidden_lines=True).add(ring(ol))
    fus.add(line((-w2, X_NOSE), (w2, X_NOSE)))
    fus.add(line((-w2, X_CONE), (w2, X_CONE)))                              # under the wing: dashed
    parts.append(fus)

    # boom (32 mm carbon) and its end cap
    bm = np.r_[[(-BOOM_R, BOOM_X0), (BOOM_R, BOOM_X0)],
               np.array([(BOOM_R * math.cos(a), BOOM_X1 - BOOM_R + BOOM_R * math.sin(a))
                         for a in np.linspace(0, math.pi, 31)])]
    parts.append(Part("boom", poly(bm)).add(ring(bm)))

    parts += nose_assembly("top")
    return parts


# ------------------------------------------------------------------ side view (port side, nose left)
def side_view():
    S2 = lambda pts: np.c_[np.asarray(pts)[:, 0], -np.asarray(pts)[:, 1]]   # noqa: E731  (x, z) -> (u, v)
    parts = []
    afs = AF[::4]

    # main gear, port side: wheel, then the bent aluminium leg behind it
    zc = Z_GROUND + D_MAIN / 2
    wh = circle((X_MAIN, zc), D_MAIN / 2)
    p = Part("main wheel", poly(S2(wh))).add(ring(S2(wh)))
    p.add(ring(S2(circle((X_MAIN, zc), 0.021))), "panel")
    p.add(ring(S2(circle((X_MAIN, zc), 0.006, 40))), "panel")
    parts.append(p)
    leg = [(X_MAIN - 0.024, -FUS_H / 2), (X_MAIN + 0.020, -FUS_H / 2), (X_MAIN + 0.016, zc), (X_MAIN - 0.016, zc)]
    parts.append(Part("main leg", poly(S2(leg))).add(ring(S2(leg))))

    # wing, near (port) panel from the fuselage side to the tip: union of SD7037 sections
    s0 = FUS_W / 2 / B2
    secs = [place(afs, *wing_at(s)) for s in np.linspace(s0, SEAM, 90)]
    env = unary_union([poly(S2(q)) for q in secs]).buffer(0)
    env = env.buffer(1e-5).buffer(-1e-5)
    wp = Part("wing panel", env).add(ring(np.asarray(env.exterior.coords)[:-1]))
    seam = place(AF, *wing_at(SEAM))
    wp.add(ring(S2(seam[:-1])), "edge")                                   # tip-cap joint: true SD7037
    parts.append(wp)

    # horizontal tail, near half: root lens is the envelope; tip-cap joint inside it
    hr = place(N09, XH, ZT, CRH)
    ht = Part("htail", poly(S2(hr))).add(ring(S2(hr[:-1])))
    x, c = htail_at(SEAM)
    ht.add(ring(S2(place(N09, x, ZT, c)[:-1])), "edge")
    parts.append(ht)

    # fuselage side. The wing root LE sits on the box top (z_wing = fus_h / 2) at 2 deg incidence, so
    # under the wing the side wall stops at the wing's lower surface (a saddle) and the aft deck runs
    # from the wing TE down to the boom; otherwise the TE would sit 11-23 mm below the box top line.
    h2, fh2 = FUS_H / 2, FW_H / 2
    ce = CONE_END
    sw = place(AF, *wing_at(s0))
    lo = sw[np.argmin(sw[:, 0]):]                                         # lower surface, LE -> TE
    i = int(np.argmax(lo[:, 1] <= h2))
    xa = float(np.interp(h2, lo[i - 1:i + 1, 1][::-1], lo[i - 1:i + 1, 0][::-1]))
    top = [(X_NOSE, h2), (xa, h2)] + [tuple(p) for p in lo[i:]]
    ol = [(X_FW, -fh2), (X_FW, fh2)] + top + [(FUS_L, ce["z1"]), (FUS_L, ce["z0"]), (X_CONE, -h2), (X_NOSE, -h2)]
    ol = fillet(ol, {0: 0.022, 1: 0.022})
    fus = Part("fuselage", poly(S2(ol))).add(ring(S2(ol)))
    fus.add(LineString(S2([(X_NOSE, -h2), (X_NOSE, h2)])))
    fus.add(LineString(S2([(X_CONE, -h2), (X_CONE, h2)])))
    parts.append(fus)

    # wing centre section (between the fuselage sides): shows only where it rises above the box
    cen = unary_union([poly(S2(place(afs, *wing_at(s)))) for s in np.linspace(0, s0, 12)]).buffer(0)
    parts.append(Part("wing centre", cen).add(ring(np.asarray(cen.exterior.coords)[:-1])))

    # fin with rudder and tip cap
    def fx(s, f):
        x, c = fin_at(s)
        return x + f * c

    zs = ZT + SEAM * BV
    zr = ZT + 0.018                                                       # rudder foot, clear of the elevator
    le = [(fx(s, 0), ZT + s * BV) for s in np.linspace(0, SEAM, 12)]
    tipp = [(fx(1, 0) + 0.035, ZT + BV), (fx(1, 1), ZT + BV)]
    te = [(fx(s, 1), ZT + s * BV) for s in np.linspace(1, 0, 13)]
    ol = fillet(le + tipp + te[1:], {len(le) + 1: 0.015})
    fin = Part("fin", poly(S2(ol))).add(ring(S2(ol)))
    fin.add(LineString(S2([(fx(SEAM, 0), zs), (fx(SEAM, 1), zs)])), "panel")
    sr = (zr - ZT) / BV
    fin.add(LineString(S2([(fx(s, 1 - RUD_CF), ZT + s * BV) for s in np.linspace(sr, SEAM, 8)])), "panel")
    fin.add(LineString(S2([(fx(sr, 1 - RUD_CF), zr), (fx(sr, 1), zr)])), "panel")
    parts.append(fin)

    # boom with end cap, and the saddle that carries the stabiliser
    zt, zb = BOOM_Z + BOOM_R, BOOM_Z - BOOM_R
    cap = [(BOOM_X1 - BOOM_R + BOOM_R * math.sin(a), BOOM_Z + BOOM_R * math.cos(a)) for a in np.linspace(0, math.pi, 31)]
    bm = [(BOOM_X0, zt)] + cap + [(BOOM_X0, zb)]
    xs = np.linspace(1.40, 1.635, 40)
    lower = np.interp((xs - XH) / CRH, N09[N09[:, 1] <= 0][:, 0], N09[N09[:, 1] <= 0][:, 1]) * CRH + ZT
    sad = [(xs[0], zt)] + list(zip(xs, lower)) + [(xs[-1], zt)]
    sad_poly = poly(S2(sad))
    boom = Part("boom", unary_union([poly(S2(bm)), sad_poly]).buffer(0)).add(ring(S2(bm)))
    boom.add(LineString(S2([(xs[-1], zt), (xs[-1], lower[-1])])))
    parts.append(boom)

    # nose gear: fork arm (near side, over the wheel), wheel, steering strut; 10 mm trail
    zn = Z_GROUND + D_NOSEW / 2
    xs0 = X_NOSEW - 0.010                                                  # strut axis
    fork = fillet([(xs0 - 0.009, -0.250), (xs0 + 0.009, -0.250), (X_NOSEW + 0.008, zn), (X_NOSEW - 0.008, zn)],
                  {2: 0.0079, 3: 0.0079})
    p = Part("nose fork", poly(S2(fork))).add(ring(S2(fork)))
    p.add(ring(S2(circle((X_NOSEW, zn), 0.004, 30))), "panel")
    parts.append(p)
    nw = circle((X_NOSEW, zn), D_NOSEW / 2)
    p = Part("nose wheel", poly(S2(nw))).add(ring(S2(nw)))
    p.add(ring(S2(circle((X_NOSEW, zn), 0.019))), "panel")
    parts.append(p)
    st = [(xs0 - 0.005, -0.10), (xs0 + 0.005, -0.10), (xs0 + 0.005, -0.252), (xs0 - 0.005, -0.252)]  # into the nose
    parts.append(Part("nose strut", poly(S2(st))).add(ring(S2(st))))
    collar = [(xs0 - 0.010, -0.236), (xs0 + 0.010, -0.236), (xs0 + 0.010, -0.250), (xs0 - 0.010, -0.250)]
    parts.insert(len(parts) - 1, Part("nose collar", poly(S2(collar))).add(ring(S2(collar))))

    parts += nose_assembly("side")
    return parts


# ------------------------------------------------------------------ front view (from ahead, starboard on the left)
def front_view():
    """Viewer at -x looking aft: view u = -y, v = -z. Prop drawn with one blade up (as in the side view),
    blades face-on (projected chord c cos(beta)); the lower blade is the upper one turned through 180 deg."""
    F2 = lambda pts: np.c_[-np.asarray(pts)[:, 0], -np.asarray(pts)[:, 1]]   # noqa: E731  (y, z) -> (u, v)
    parts = []

    # propeller: nut, hub, blades, then the motor and mount behind them
    R = PROP_D / 2
    parts.append(Part("prop nut", poly(F2(circle((0, 0), 0.009, 60)))).add(ring(F2(circle((0, 0), 0.009, 60)))))
    hub = circle((0, 0), 0.018, 90)
    parts.append(Part("prop hub", poly(F2(hub))).add(ring(F2(hub))))
    rr = np.linspace(0.016, R, 300)
    tab_r = np.array([0.06, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.92, 1.0])
    tab_c = np.array([0.080, 0.130, 0.165, 0.185, 0.190, 0.185, 0.170, 0.150, 0.122, 0.098, 0.075])
    c = PchipInterpolator(tab_r, tab_c)(rr / R) * R
    tip = rr / R > 0.86
    c[tip] *= np.sqrt(np.clip(1 - ((rr[tip] / R - 0.86) / 0.14) ** 2, 0, 1))
    beta = np.arctan(PROP_P / (2 * np.pi * rr))
    w_le, w_te = 0.35 * c * np.cos(beta), 0.65 * c * np.cos(beta)
    up = np.r_[np.c_[-w_le, rr], np.c_[w_te, rr][::-1]]                    # (y, z), blade along +z
    for bl in (up, -up):
        parts.append(Part("blade", poly(F2(bl))).add(ring(F2(bl))))
    can = circle((0, 0), 0.0407, 120)
    parts.append(Part("motor can", poly(F2(can))).add(ring(F2(can))))
    plate = fillet([(-0.05, -0.05), (0.05, -0.05), (0.05, 0.05), (-0.05, 0.05)], {i: 0.006 for i in range(4)})
    parts.append(Part("mount plate", poly(F2(plate))).add(ring(F2(plate))))

    # fuselage: firewall face, nose taper faces, box outline (wing root sits on the box top)
    f2w, f2h, w2, h2 = FW_W / 2, FW_H / 2, FUS_W / 2, FUS_H / 2
    fw = fillet([(-f2w, -f2h), (f2w, -f2h), (f2w, f2h), (-f2w, f2h)], {i: 0.022 for i in range(4)})
    box = np.array([(-w2, -h2), (w2, -h2), (w2, h2), (-w2, h2)])
    fus = Part("fuselage", poly(F2(box))).add(ring(F2(box))).add(ring(F2(fw)))
    for sy, sz in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        k = 0.022 * (1 - 1 / math.sqrt(2))                                 # fillet corner point on the face
        fus.add(LineString(F2([(sy * (f2w - k), sz * (f2h - k)), (sy * w2, sz * h2)])))
    parts.append(fus)

    # nose gear: fork crown and arms, wheel, collar, strut
    zn = Z_GROUND + D_NOSEW / 2
    wn = 0.030 / 2
    for sy in (1, -1):
        arm = [(sy * (wn + 0.003), -0.250), (sy * (wn + 0.011), -0.250), (sy * (wn + 0.011), zn - 0.006),
               (sy * (wn + 0.003), zn - 0.006)]
        parts.append(Part("fork arm", poly(F2(arm))).add(ring(F2(arm))))
    crown = [(-(wn + 0.011), -0.244), (wn + 0.011, -0.244), (wn + 0.011, -0.252), (-(wn + 0.011), -0.252)]
    parts.append(Part("fork crown", poly(F2(crown))).add(ring(F2(crown))))
    nwf = fillet([(-wn, Z_GROUND), (wn, Z_GROUND), (wn, Z_GROUND + D_NOSEW), (-wn, Z_GROUND + D_NOSEW)],
                 {i: 0.011 for i in range(4)})
    parts.append(Part("nose wheel", poly(F2(nwf))).add(ring(F2(nwf))))
    col = [(-0.010, -0.236), (0.010, -0.236), (0.010, -0.244), (-0.010, -0.244)]
    parts.append(Part("nose collar", poly(F2(col))).add(ring(F2(col))))
    st = [(-0.005, -h2), (0.005, -h2), (0.005, -0.236), (-0.005, -0.236)]
    parts.append(Part("nose strut", poly(F2(st))).add(ring(F2(st))))

    # wing: envelope of the SD7037 sections seen from ahead, tip rounded, joints as panel lines
    ss = np.linspace(0, 1, 121)
    zmax, zmin = [], []
    for s in ss:
        q = place(AF[::4], *wing_at(s))
        zmax.append(q[:, 1].max()); zmin.append(q[:, 1].min())
    ys = ss * B2
    zt_, zb_ = zmax[-1], zmin[-1]
    rt = 0.5 * (zt_ - zb_)
    capc = (B2 - rt * 0.9, 0.5 * (zt_ + zb_))
    cap = [(capc[0] + 0.9 * rt * math.cos(a), capc[1] + rt * math.sin(a)) for a in np.linspace(math.pi / 2, -math.pi / 2, 25)]
    keep = ys < capc[0]
    half_up = list(zip(ys[keep], np.array(zmax)[keep]))
    half_lo = list(zip(ys[keep], np.array(zmin)[keep]))[::-1]
    star = half_up + cap + half_lo                                          # +y half, root to tip and back
    full = np.r_[np.array(star), (np.array(star) * [-1, 1])[::-1]]
    wing = Part("wing", poly(F2(full))).add(ring(F2(full)))
    for sy in (1, -1):
        s = SEAM
        q = place(AF[::4], *wing_at(s))
        wing.add(LineString(F2([(sy * s * B2, q[:, 1].min()), (sy * s * B2, q[:, 1].max())])), "panel")
    q = place(AF[::4], *wing_at(0))
    wing.add(LineString(F2([(0, q[:, 1].min()), (0, q[:, 1].max())])), "panel")
    parts.append(wing)

    # main gear: wheels (edge-on), then the bent aluminium bow, 8 mm thick
    for sy in (1, -1):
        y0, y1 = sy * (Y_MAIN - W_MAIN / 2), sy * (Y_MAIN + W_MAIN / 2)
        wh = fillet([(min(y0, y1), Z_GROUND), (max(y0, y1), Z_GROUND), (max(y0, y1), Z_GROUND + D_MAIN),
                     (min(y0, y1), Z_GROUND + D_MAIN)], {i: 0.012 for i in range(4)})
        parts.append(Part("main wheel", poly(F2(wh))).add(ring(F2(wh))))
    zc = Z_GROUND + D_MAIN / 2
    yb = Y_MAIN - W_MAIN / 2 - 0.006
    cl = LineString([(-yb, zc), (-yb + 0.004, zc + 0.012), (-0.10, -h2 - 0.004), (0.10, -h2 - 0.004),
                     (yb - 0.004, zc + 0.012), (yb, zc)])
    bow = cl.buffer(0.004, cap_style=2, join_style=1)
    parts.append(Part("main gear", Polygon(F2(np.asarray(bow.exterior.coords)))).add(
        ring(F2(np.asarray(bow.exterior.coords)[:-1]))))
    for sy in (1, -1):
        ax_ = [(sy * yb, zc - 0.006), (sy * (Y_MAIN - W_MAIN / 2), zc - 0.006), (sy * (Y_MAIN - W_MAIN / 2), zc + 0.006),
               (sy * yb, zc + 0.006)]
        parts.append(Part("axle", poly(F2(ax_))).add(ring(F2(ax_))))

    # horizontal tail (NACA 0009 thickness, rounded tips) and fin, behind everything else
    sh = np.linspace(0, 1, 41)
    th = 0.045 * (CRH + sh * (CTH - CRH))
    yy = sh * BH2
    rt = th[-1]
    keep = yy < BH2 - rt
    up_ = list(zip(yy[keep], ZT + th[keep]))
    capc = (BH2 - rt, ZT)
    cap = [(capc[0] + rt * math.cos(a), ZT + rt * math.sin(a)) for a in np.linspace(math.pi / 2, -math.pi / 2, 19)]
    lo_ = list(zip(yy[keep], ZT - th[keep]))[::-1]
    star = np.array(up_ + cap + lo_)
    full = np.r_[star, (star * [-1, 1])[::-1]]
    ht = Part("htail", poly(F2(full))).add(ring(F2(full)))
    for sy in (1, -1):
        s = SEAM
        t_ = 0.045 * (CRH + s * (CTH - CRH))
        ht.add(LineString(F2([(sy * s * BH2, ZT - t_), (sy * s * BH2, ZT + t_)])), "panel")
    parts.append(ht)
    sv = np.linspace(0, 1, 21)
    tv = 0.045 * (CRV + sv * (CTV - CRV))
    zz = ZT + sv * BV
    rt = tv[-1]
    zc = ZT + BV - 0.6 * rt                                                # rounded cap ends at the design tip
    keep = zz < zc
    zk, tk = np.r_[zz[keep], zc], np.r_[tv[keep], rt]
    fin_pts = ([(tk[i], zk[i]) for i in range(len(zk))]
               + [(rt * math.cos(a), zc + 0.6 * rt * math.sin(a)) for a in np.linspace(0, math.pi, 13)][1:-1]
               + [(-tk[i], zk[i]) for i in range(len(zk))][::-1])
    parts.append(Part("fin", poly(F2(fin_pts))).add(ring(F2(fin_pts))))
    return parts


# ------------------------------------------------------------------ mission items (P1.4): bay, drum, tow exit, CG
def payload_geometry():
    """Container (8 kg design, DB-02 payload model), bay centre, drum and tow exit (geometry_variants.masses())."""
    import sys as _s
    _s.path.insert(0, str(DB02 / "src"))
    from payload import model as PM                     # noqa: E402
    sel = json.loads((DB02 / "out" / "variants" / "selection.json").read_text(encoding="utf-8"))["A"]
    c = PM.container(sel["m_hi"], 150.0, 1.524, ballast="tungsten", fins="cruciform", sling_deg=15.0)
    L, W, H = c["dims_m"]
    x_bay, x_cg = VAR["mass"]["x_bay"], T["x_cg_design"]
    return dict(L=L, W=W, H=H, x_bay=x_bay, x_cg=x_cg, z_floor=-FUS_H / 2 + 0.005,
                x_drum=x_cg + 0.20, d_drum=0.07, w_drum=0.05, z_drum=-0.10,   # drum: REF-D01 size, z ESTIMATE
                x_exit=x_bay + 0.05)                                         # model: weight acts at bay + 0.05 m


def cg_symbol(c, r):
    """Standard CG mark: circle, cross, two filled quadrants (in view coordinates)."""
    circ = ring(circle(c, r, 72))
    cross = [LineString([(c[0] - r, c[1]), (c[0] + r, c[1])]), LineString([(c[0], c[1] - r), (c[0], c[1] + r)])]
    q1 = Polygon([c] + [tuple(p) for p in arc(c, r, 0, math.pi / 2, 16)])
    q3 = Polygon([c] + [tuple(p) for p in arc(c, r, math.pi, 1.5 * math.pi, 16)])
    return [circ] + cross, [q1, q3]


def mission_marks(view):
    """{class: [geoms]} drawn on top of the hidden-line result (they sit inside the fuselage)."""
    g = payload_geometry()
    out = {"payload": [], "cg": [], "cgfill": []}
    x0, x1 = g["x_bay"] - g["L"] / 2, g["x_bay"] + g["L"] / 2
    if view == "top":                                        # u = y, v = x
        out["payload"].append(ring([(-g["W"] / 2, x0), (g["W"] / 2, x0), (g["W"] / 2, x1), (-g["W"] / 2, x1)]))
        xd0, xd1 = g["x_drum"] - g["d_drum"] / 2, g["x_drum"] + g["d_drum"] / 2
        out["payload"].append(ring([(-g["w_drum"] / 2, xd0), (g["w_drum"] / 2, xd0), (g["w_drum"] / 2, xd1),
                                    (-g["w_drum"] / 2, xd1)]))
        out["payload"].append(ring(circle((0, g["x_exit"]), 0.011, 48)))
        lines, fills = cg_symbol((0.0, g["x_cg"]), 0.024)
    else:                                                    # side: u = x, v = -z
        zb, zt = g["z_floor"], g["z_floor"] + g["H"]
        out["payload"].append(ring([(x0, -zb), (x1, -zb), (x1, -zt), (x0, -zt)]))
        out["payload"].append(ring(circle((g["x_drum"], -g["z_drum"]), g["d_drum"] / 2, 72)))
        out["payload"].append(ring(circle((g["x_exit"], FUS_H / 2), 0.011, 48)))
        lines, fills = cg_symbol((g["x_cg"], 0.0), 0.024)
    out["cg"] += lines
    out["cgfill"] += fills
    return out


# ------------------------------------------------------------------ hidden lines and classes
def lines_of(g):
    if g.is_empty:
        return []
    if isinstance(g, LineString):
        return [g]
    if isinstance(g, (MultiLineString, GeometryCollection)):
        out = []
        for h in g.geoms:
            out += lines_of(h)
        return out
    return []


def compose(parts, min_len=0.0008):
    """Painter's order (parts listed nearest first): each part's lines are clipped by the union of
    every nearer part. The outer silhouette of the whole aircraft is promoted to class 'outline'."""
    occ = Polygon()
    out = {"outline": [], "edge": [], "panel": [], "ref": [], "hidden": []}
    for p in parts:
        occ_s = occ.buffer(-EPS) if not occ.is_empty else occ
        for geom, cls in p.lines:
            vis = geom.difference(occ_s) if not occ.is_empty else geom
            out[cls] += lines_of(vis)
            if p.hidden_lines and cls == "edge" and not occ.is_empty:
                out["hidden"] += lines_of(geom.intersection(occ_s))
        occ = unary_union([occ, p.region]) if not occ.is_empty else p.region
    sil = occ.boundary.buffer(0.0004)
    edges = []
    for ln in out["edge"]:
        out["outline"] += lines_of(ln.intersection(sil))
        edges += lines_of(ln.difference(sil))
    out["edge"] = edges
    for k in out:
        merged = linemerge(MultiLineString([ln for ln in out[k] if ln.length > 0])) if out[k] else None
        ls = lines_of(merged) if merged is not None else []
        out[k] = [ln.simplify(0.00002) for ln in ls if ln.length >= min_len]
    return out, occ


# ------------------------------------------------------------------ SVG
STYLE = {   # stroke widths in full-scale mm (0.35 / 0.20 / 0.13 / 0.11 mm when printed at 1:20)
    "outline": dict(w=7.0, label="Outline (silhouette)"),
    "edge": dict(w=4.0, label="Edges"),
    "panel": dict(w=2.6, label="Panel lines"),
    "ref": dict(w=2.2, label="Quarter-chord lines", dash="28 8 4 8"),
    "hidden": dict(w=2.6, label="Hidden (fuselage under wing)", dash="14 9"),
    "payload": dict(w=2.6, label="Mission items (container, drum, tow exit)", dash="8 6"),
    "cg": dict(w=2.6, label="Centre of gravity"),
    "cgfill": dict(w=0, label="Centre of gravity (fill)", fill=True),
}
ORDER = ["hidden", "ref", "panel", "payload", "edge", "outline", "cg", "cgfill"]


def svg(classes, bounds, title, desc, path, pad=0.03, px_width=None):
    x0, y0, x1, y1 = bounds
    x0, y0, x1, y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
    W, H = (x1 - x0) * 1000, (y1 - y0) * 1000
    size = (f'width="{px_width}" height="{px_width * H / W:.0f}"' if px_width else
            f'width="{W / SCALE:.2f}mm" height="{H / SCALE:.2f}mm"')
    o = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
         f'version="1.1" {size} viewBox="{x0 * 1000:.2f} {y0 * 1000:.2f} {W:.2f} {H:.2f}">',
         f"<title>{title}</title>", f"<desc>{desc}</desc>"]
    for k in ORDER:
        if not classes.get(k):
            continue
        st = STYLE[k]
        dash = f' stroke-dasharray="{st["dash"]}"' if "dash" in st else ""
        if st.get("fill"):
            o.append(f'<g id="{k}" inkscape:groupmode="layer" inkscape:label="{st["label"]}" fill="#000000" stroke="none">')
        else:
            o.append(f'<g id="{k}" inkscape:groupmode="layer" inkscape:label="{st["label"]}" fill="none" stroke="#000000" '
                     f'stroke-width="{st["w"]}" stroke-linecap="round" stroke-linejoin="round"{dash}>')
        for ln in classes[k]:
            if isinstance(ln, Polygon):
                ln = LineString(np.asarray(ln.exterior.coords))
            c = np.asarray(ln.coords) * 1000
            closed = ln.is_ring and len(c) > 3
            if closed:
                c = c[:-1]
            d = "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in c) + ("Z" if closed else "")
            o.append(f'<path d="{d}"/>')
        o.append("</g>")
    o.append("</svg>")
    Path(path).write_text("\n".join(o) + "\n", encoding="utf-8")


DESC = ("DB-02 Variant A (AIAA DBF 2026-27), true scale, units mm, document scale 1:20. Primary geometry from "
        "DB-02 variants_geometry.json / variant_A.avl; wing section SD7037. Generated by ga_svg.py.")


def airfoil_svg(path):
    pts = AF * [1, -1]
    ls = LineString(np.r_[pts, pts[:1]]).simplify(0.000005)
    c = np.asarray(ls.coords) * 1000
    d = "M" + " L".join(f"{x:.3f},{y:.3f}" for x, y in c[:-1]) + "Z"
    o = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="200mm" height="24mm" viewBox="-10 -85 1020 102">',
         "<title>SD7037 section, unit chord = 1000</title>",
         "<desc>SD7037-092-88 (UIUC coordinates, sd7037.dat), cubic spline through all 61 points; "
         "chord along +x, upper surface up.</desc>",
         f'<path d="{d}" fill="none" stroke="#000000" stroke-width="2" stroke-linejoin="round"/>', "</svg>"]
    Path(path).write_text("\n".join(o) + "\n", encoding="utf-8")


def run(preview_dir=None):
    check_against_avl()
    res = {}
    for name, fn, title in (("top_view", top_view, "DB-02 Variant A, top view"),
                            ("side_view", side_view, "DB-02 Variant A, side view (port)"),
                            ("front_view", front_view, "DB-02 Variant A, front view")):
        classes, sil = compose(fn())
        if name in ("top_view", "side_view"):
            for k, v in mission_marks(name.split("_")[0]).items():
                classes[k] = v
        b = sil.bounds
        svg(classes, b, title, DESC, HERE / f"{name}.svg")
        if preview_dir:
            svg(classes, b, title, DESC, Path(preview_dir) / f"{name}_preview.svg", px_width=2400)
        res[name] = (classes, sil)
    airfoil_svg(HERE / "sd7037_profile.svg")
    return res


if __name__ == "__main__":
    import sys
    run(sys.argv[1] if len(sys.argv) > 1 else None)
    print("ok")
