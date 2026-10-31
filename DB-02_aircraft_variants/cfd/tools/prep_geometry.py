# Copyright © 2026 Badr Obtel. All rights reserved.
"""CAD STL -> snappyHexMesh-ready surface, reference geometry and case parameters.

    PYTHONIOENCODING=utf-8 python cfd/tools/prep_geometry.py cfd/cases/<case>

Reads <case>/case.toml and writes:
    constant/geometry/<case>.obj   outer skin in the CFD frame (m), one group per patch
    constant/geometry/reference    span, S, MAC, CofR, domain and mesh sizes (OpenFOAM dict)
    system/caseParameters          flow conditions (OpenFOAM dict)
    geometry_report.txt, geometry_preview.png

Why the skin step: SolidWorks exports shelled parts and multi-body assemblies as
overlapping closed surfaces (an inner skin ~1 mm under the outer one, wing and
pylon roots buried inside the fuselage and nacelle). snappyHexMesh can mesh around
that, but snapping pulls points to the NEAREST surface, which can be an inner skin
or a buried root. So the outside air is found by a voxel flood fill from the domain
corner, and a face is kept if ANY point of it, nudged along its outward normal,
lands in outside air. Faces that only touch cavities or other bodies are dropped;
faces that straddle a body junction are kept whole, so the wetted surface stays
closed (any open edges left are buried inside a solid, not leak paths).
"""
import struct
import sys
import time
import tomllib
from pathlib import Path

import numpy as np
from scipy import ndimage

REPO = Path(__file__).resolve().parents[3]   # DB-02 local copy: W/cfd/tools -> repo root
AXES = {"+x": (0, 1), "-x": (0, -1), "+y": (1, 1), "-y": (1, -1), "+z": (2, 1), "-z": (2, -1)}


# ---------------------------------------------------------------------------
# STL in, topology
# ---------------------------------------------------------------------------
def read_stl(path):
    raw = path.read_bytes()
    n = struct.unpack("<I", raw[80:84])[0]
    if len(raw) != 84 + 50 * n:
        sys.exit(f"{path}: not a binary STL (size {len(raw)} != 84 + 50*{n})")
    dt = np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    return np.frombuffer(raw, dtype=dt, count=n, offset=84)["v"].astype(np.float64)


def weld(V):
    """Shared-vertex form: points P (m,3) and faces F (n,3)."""
    tol = 1e-6 * np.linalg.norm(np.ptp(V.reshape(-1, 3), 0))
    uq, inv = np.unique(np.round(V.reshape(-1, 3) / tol).astype(np.int64), axis=0, return_inverse=True)
    return uq * tol, inv.reshape(-1, 3)


def edges(F):
    E = np.sort(np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), axis=1)
    return np.unique(E, axis=0, return_counts=True)


def bodies(F, npts):
    """Connected components over shared edges; returns per-face body index, 0 = most faces."""
    ue, _ = edges(F)
    parent = np.arange(npts)

    def find(x):
        r = x
        while parent[r] != r:
            r = parent[r]
        while parent[x] != r:
            parent[x], x = r, parent[x]
        return r
    for a, b in ue:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    root = np.array([find(i) for i in range(npts)])[F[:, 0]]
    ids, inv, cnt = np.unique(root, return_inverse=True, return_counts=True)
    rank = np.empty(len(ids), int)
    rank[np.argsort(-cnt)] = np.arange(len(ids))
    return rank[inv]


def subdivide(T, s, parent):
    """Bisect the longest edge until every edge <= s; yields (sub-triangles, parent face index)."""
    while len(T):
        e = np.stack([np.linalg.norm(T[:, 1] - T[:, 0], axis=1),
                      np.linalg.norm(T[:, 2] - T[:, 1], axis=1),
                      np.linalg.norm(T[:, 0] - T[:, 2], axis=1)], 1)
        done = e.max(1) <= s
        if done.any():
            yield T[done], parent[done]
        T, e, parent = T[~done], e[~done], parent[~done]
        if not len(T):
            return
        k = e.argmax(1)
        r = np.arange(len(T))
        a, b, c = T[r, k], T[r, (k + 1) % 3], T[r, (k + 2) % 3]
        m = 0.5 * (a + b)
        T = np.concatenate([np.stack([a, m, c], 1), np.stack([m, b, c], 1)])
        parent = np.concatenate([parent, parent])


# ---------------------------------------------------------------------------
# Outer skin
# ---------------------------------------------------------------------------
def outer_faces(V, h, offs):
    """Faces touching outside air (see module docstring). h, offs in file units.
    Several offsets because a voxel crossed by a slanted face reaches up to
    sqrt(3) h from it, so the nearest test point can sit in the face's own wall."""
    lo, hi = V.reshape(-1, 3).min(0), V.reshape(-1, 3).max(0)
    pad = 4
    org = lo - pad * h
    dims = np.ceil((hi - lo) / h).astype(int) + 2 * pad + 1
    wall = np.zeros(dims, dtype=bool)
    idx = np.arange(len(V))
    for i0 in range(0, len(V), 4000):
        for D, _ in subdivide(V[i0:i0 + 4000], 0.5 * h, idx[i0:i0 + 4000]):
            pts = np.concatenate([D.reshape(-1, 3), D.mean(1), 0.5 * (D[:, 0] + D[:, 1]),
                                  0.5 * (D[:, 1] + D[:, 2]), 0.5 * (D[:, 2] + D[:, 0])])
            ijk = np.floor((pts - org) / h).astype(int)
            wall[ijk[:, 0], ijk[:, 1], ijk[:, 2]] = True
    lab, nlab = ndimage.label(~wall)                  # 6-connected air regions
    outside = lab == lab[0, 0, 0]
    pocket = (lab > 0) & ~outside                     # sealed cavities
    del lab
    cr = np.cross(V[:, 1] - V[:, 0], V[:, 2] - V[:, 0])
    nrm = cr / np.maximum(np.linalg.norm(cr, axis=1, keepdims=True), 1e-30)
    keep = np.zeros(len(V), bool)
    n_sub = np.zeros(len(V))
    n_pocket = np.zeros(len(V))
    for i0 in range(0, len(V), 4000):
        for D, par in subdivide(V[i0:i0 + 4000], h, idx[i0:i0 + 4000]):
            for j, off in enumerate(offs):
                q = np.floor((D.mean(1) + off * nrm[par] - org) / h).astype(int)
                q = np.clip(q, 0, dims - 1)
                keep[par[outside[q[:, 0], q[:, 1], q[:, 2]]]] = True
                if j == 0:
                    np.add.at(n_sub, par, 1)
                    np.add.at(n_pocket, par, pocket[q[:, 0], q[:, 1], q[:, 2]])
    mostly_pocket = keep & (n_pocket > 0.5 * n_sub)
    return keep, dict(grid=dims.tolist(), air_regions=int(nlab), wall_voxels=int(wall.sum()),
                      kept_facing_pockets=int(mostly_pocket.sum()), pocket_faces=np.where(mostly_pocket)[0])


# ---------------------------------------------------------------------------
# Regions and wing reference geometry
# ---------------------------------------------------------------------------
def regions(cfg, cen, body):
    names = []
    for r in cfg["region"]:
        if r["name"] not in names:
            names.append(r["name"])
    names.append("fuselage")
    reg = np.full(len(cen), names.index("fuselage"))
    free = np.ones(len(cen), bool)
    for r in cfg["region"]:
        m = free.copy()
        if "body" in r:
            m &= body == r["body"]
        for ax, key in ((0, "x"), (1, "y"), (2, "z")):
            if key in r:
                m &= (cen[:, ax] >= r[key][0]) & (cen[:, ax] <= r[key][1])
        if "abs_x" in r:
            ax_ = np.abs(cen[:, 0])
            m &= (ax_ >= r["abs_x"][0]) & (ax_ <= r["abs_x"][1])
        reg[m] = names.index(r["name"])
        free &= ~m
    return names, reg


def section(V, x0):
    """Cut faces with the plane x = x0 (CAD frame): segment end points (k,3)."""
    d = V[:, :, 0] - (x0 + 1e-4)          # nudge off tessellation seams (vertices exactly on x0)
    m = (d.min(1) < 0) & (d.max(1) > 0)
    pts = []
    for tri, dd in zip(V[m], d[m]):
        for i, j in ((0, 1), (1, 2), (2, 0)):
            if dd[i] * dd[j] < 0:
                t = dd[i] / (dd[i] - dd[j])
                pts.append(tri[i] + t * (tri[j] - tri[i]))
    return np.array(pts)


def wing_reference(Vw, fit):
    """Trapezoidal reference wing from section cuts of the right wing (CAD frame, file units)."""
    st = np.linspace(fit[0], fit[1], 13)
    rows = []
    for x0 in st:
        p = section(Vw, x0)
        le, te = p[np.argmin(p[:, 1])], p[np.argmax(p[:, 1])]
        rows.append((x0, le[1], le[2], te[1], te[2], np.linalg.norm(te[1:] - le[1:]),
                     np.degrees(np.arctan2(le[2] - te[2], te[1] - le[1]))))
    rows = np.array(rows)
    tip = Vw[:, :, 0].max()
    cfit = np.polyfit(rows[:, 0], rows[:, 5], 1)
    lefit = np.polyfit(rows[:, 0], rows[:, 1], 1)
    zfit = np.polyfit(rows[:, 0], 0.5 * (rows[:, 2] + rows[:, 4]), 1)
    cr, ct = np.polyval(cfit, 0.0), np.polyval(cfit, tip)
    lam = ct / cr
    b = 2 * tip
    S = b * 0.5 * (cr + ct)
    mac = 2 / 3 * cr * (1 + lam + lam ** 2) / (1 + lam)
    x_mac = b / 6 * (1 + 2 * lam) / (1 + lam)
    resid = rows[:, 5] - np.polyval(cfit, rows[:, 0])
    return dict(b=b, S=S, cr=cr, ct=ct, lam=lam, mac=mac, AR=b * b / S, x_mac=x_mac,
                le_mac=np.polyval(lefit, x_mac), z_mac=np.polyval(zfit, x_mac),
                incidence=rows[:, 6].mean(), chord_fit_resid=np.abs(resid).max(), stations=rows)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def frame_matrix(fr):
    R = np.zeros((3, 3))
    for row, key in enumerate(("x", "y", "z")):
        col, sgn = AXES[fr[key]]
        R[row, col] = sgn
    if round(np.linalg.det(R)) != 1:
        sys.exit("[frame] must be a right-handed rotation")
    return R


def foam_dict(path, obj, body, note):
    head = ("FoamFile\n{\n    format      ascii;\n    class       dictionary;\n"
            f"    object      {obj};\n}}\n// Written by cfd/tools/prep_geometry.py from case.toml. {note}\n\n")
    path.write_text(head + body, encoding="utf-8")


def fmt(v):
    return "(" + " ".join(f"{x:.6g}" for x in v) + ")"


def main(case):
    cfg = tomllib.load((case / "case.toml").open("rb"))
    t0 = time.time()
    src = REPO / cfg["source"]["stl"]
    V = read_stl(src)
    mm = 1e-3 / cfg["source"]["units_m"]                   # file units per mm
    P, F = weld(V)
    ue, cnt = edges(F)
    body = bodies(F, len(P))
    keep, vox = outer_faces(V, cfg["skin"]["voxel_mm"] * mm, [o * mm for o in cfg["skin"]["offset_mm"]])
    Fk = F[keep]
    ue_k, cnt_k = edges(Fk)
    cen = V.mean(1) / mm                                    # CAD frame, mm
    names, reg = regions(cfg, cen, body)
    area = 0.5 * np.linalg.norm(np.cross(V[:, 1] - V[:, 0], V[:, 2] - V[:, 0]), axis=1) / mm ** 2
    wmask = keep & (reg == names.index("wing")) & (cen[:, 0] > 0)
    w = wing_reference(V[wmask] / mm, cfg["wing"]["fit_abs_x"])

    # CAD (file units) -> CFD frame (m), scaled
    R = frame_matrix(cfg["frame"])
    k = cfg["source"]["units_m"] * cfg["frame"]["scale"]
    to_cfd = lambda X: (np.asarray(X, float) @ R.T) * k     # noqa: E731
    used = np.unique(Fk)
    remap = np.full(len(P), -1)
    remap[used] = np.arange(len(used))
    Pc = to_cfd(P[used])
    km = k * mm                                             # metres per CAD mm
    b, S, mac = w["b"] * km, w["S"] * km ** 2, w["mac"] * km
    cg = cfg["moment"]["cg_mm"]
    cg_cad = np.array([0.0, w["le_mac"] + 0.25 * w["mac"], w["z_mac"]]) if cg == "mac_quarter" else np.array(cg, float)
    CofR = to_cfd(cg_cad * mm)
    lo, hi = Pc.min(0), Pc.max(0)

    # Flow and first layer
    fl, me = cfg["flow"], cfg["mesh"]
    Re = fl["U"] * mac / fl["nu"]
    utau = fl["U"] * np.sqrt(fl["cf_sizing"] / 2)
    y1 = fl["yplus"] * fl["nu"] / utau
    base = b / me["base_per_span"]
    cell = base / 2 ** me["surface_level"][0]
    tot = y1 * (me["expansion"] ** me["n_layers"] - 1) / (me["expansion"] - 1)
    up, down, lat, vert = me["domain_span"]
    x0 = np.floor((lo[0] - up * b) / base) * base
    x1 = np.ceil((hi[0] + down * b) / base) * base
    y1d = np.ceil(lat * b / base) * base
    zc = 0.5 * (lo[2] + hi[2])
    z0 = np.floor((zc - vert * b) / base) * base
    z1 = np.ceil((zc + vert * b) / base) * base
    ncell = [round((x1 - x0) / base), round(y1d / base), round((z1 - z0) / base)]
    near_lo, near_hi = lo - 0.1 * b, hi + 0.1 * b
    near_lo[1] = -0.01 * b
    zw = to_cfd(np.array([0.0, 0.0, w["z_mac"]]) * mm)[2]
    xle = to_cfd(np.array([0.0, w["le_mac"], 0.0]) * mm)[0]
    wake_lo = np.array([xle, -0.01 * b, zw - 0.1 * b])
    wake_hi = np.array([hi[0] + 0.5 * b, 0.55 * b, zw + 0.1 * b])
    dist = " ".join(f"({d * mac:.4g} {lvl})" for d, lvl in me["distance_mac"])
    loc = np.array([x0 + 0.37 * base, 0.73 * y1d, z1 - 0.41 * base])

    geo = case / "constant" / "geometry"
    geo.mkdir(parents=True, exist_ok=True)
    obj = geo / f"{case.name}.obj"
    with obj.open("w", encoding="ascii", newline="\n") as f:
        f.write(f"# {src.name} outer skin, CFD frame, metres (prep_geometry.py)\n")
        f.writelines(f"v {x:.7g} {y:.7g} {z:.7g}\n" for x, y, z in Pc)
        rk = reg[keep]
        for ri, nm in enumerate(names):
            f.write(f"g {nm}\n")
            f.writelines(f"f {a + 1} {b_ + 1} {c + 1}\n" for a, b_, c in remap[Fk[rk == ri]])

    foam_dict(geo / "reference", "reference", (
        f"span        {b:.6g};      // m, full span\n"
        f"Sref        {S:.6g};      // m2, trapezoidal reference wing to the centreline\n"
        f"refArea     {S / 2:.6g};  // m2, half model: coefficients use S/2 with half-model forces\n"
        f"refLength   {mac:.6g};    // m, mean aerodynamic chord\n"
        f"refCofR     {fmt(CofR)};  // m, moment reference ({'MAC quarter chord, PARAMETER until the CG is given' if cg == 'mac_quarter' else 'CG from case.toml'})\n"
        f"macY        {w['x_mac'] * km:.6g};      // m, spanwise station of the MAC (half model, +y)\n"
        f"macLE       {fmt([xle, w['x_mac'] * km, zw])};  // m, MAC leading edge on the chord line\n"
        f"bodyMin    {fmt(lo)};\nbodyMax     {fmt(hi)};\n"
        f"xMin {x0:.6g}; xMax {x1:.6g}; yMax {y1d:.6g}; zMin {z0:.6g}; zMax {z1:.6g};\n"
        f"nx {ncell[0]}; ny {ncell[1]}; nz {ncell[2]};\n"
        f"nearMin {fmt(near_lo)}; nearMax {fmt(near_hi)};\n"
        f"wakeMin {fmt(wake_lo)}; wakeMax {fmt(wake_hi)};\n"
        f"locationInMesh {fmt(loc)};\n"
        f"surfaceLevel ({me['surface_level'][0]} {me['surface_level'][1]}); featureLevel {me['feature_level']};\n"
        f"nacelleLevel ({me['nacelle_level'][0]} {me['nacelle_level'][1]});\n"
        f"nearLevel {me['near_level']}; wakeLevel {me['wake_level']};\n"
        f"distLevels ({dist});\n"
        f"nLayers {me['n_layers']}; expansionRatio {me['expansion']}; firstLayerThickness {y1:.4g};\n"
        f"minLayerThickness {0.1 * tot:.4g};\n"
        f"patchNames ({' '.join(names)});\n"), f"Scale {cfg['frame']['scale']}.")

    alphas = fl["alpha_deg"]
    k_in = 1.5 * (fl["Tu"] * fl["U"]) ** 2
    om_in = k_in / (fl["nut_ratio"] * fl["nu"])
    tu = 100 * fl["Tu"]
    re_theta = 1173.51 - 589.428 * tu + 0.2196 / tu ** 2 if tu <= 1.3 else 331.5 * (tu - 0.5658) ** -0.671
    foam_dict(case / "system" / "caseParameters", "caseParameters", (
        f"UMag        {fl['U']:.6g};     // m/s\n"
        f"nuAir       {fl['nu']:.6g};    // m2/s\n"
        f"rhoDesign   {fl['rho']:.6g};   // kg/m3 (forces are reported with it; the solver is incompressible)\n"
        f"alphas      ({' '.join(f'{a:g}' for a in alphas)});   // deg, body axis\n"
        f"kInf        {k_in:.6g};        // 1.5 (Tu U)^2, Tu = {fl['Tu']}\n"
        f"omegaInf    {om_in:.6g};       // k / (nu_t/nu * nu), nu_t/nu = {fl['nut_ratio']}\n"
        f"ReThetatInf {re_theta:.6g};    // Langtry-Menter correlation at Tu = {tu:.2f} %\n"
        f"gammaIntInf 1;\n"
        f"nIter       {fl['iterations']};   // SIMPLE iterations per angle\n"), "")

    # Report
    nm_k = int((cnt_k > 2).sum())
    A = {nm: area[keep & (reg == i)].sum() for i, nm in enumerate(names)}
    L = [f"Geometry preparation: {case.name}  ({time.strftime('%Y-%m-%d %H:%M')}, {time.time() - t0:.0f} s)",
         f"Source {cfg['source']['stl']}: {len(V)} triangles, {len(P)} vertices, header '{Path(src).read_bytes()[:80].rstrip(bytes([0, 32])).decode('latin1', 'replace')[:40]}'",
         f"  edges: open {(cnt == 1).sum()}, non-manifold {(cnt > 2).sum()}; closed bodies {body.max() + 1}",
         f"  bounding box (mm, CAD frame): {np.round(V.reshape(-1, 3).min(0) / mm, 2)} to {np.round(V.reshape(-1, 3).max(0) / mm, 2)}",
         f"Outer skin (voxel {cfg['skin']['voxel_mm']} mm, grid {vox['grid']}, {vox['air_regions']} sealed air pockets incl. outside):",
         f"  kept {keep.sum()} of {len(V)} faces; area kept {area[keep].sum():.0f} mm2, dropped {area[~keep].sum():.0f} mm2 (inner skins, buried roots)",
         f"  kept surface: open edges {(cnt_k == 1).sum()} (buried flaps of straddling faces), non-manifold {nm_k}",
         f"  straddling faces (touch outside air but mostly face a sealed pocket; kept whole): {vox['kept_facing_pockets']}",
         "  wetted area by patch (CAD mm2, scale 1): " + ", ".join(f"{nm} {a:.0f}" for nm, a in A.items()),
         f"Wing reference (CAD mm, scale 1; stations |x| {cfg['wing']['fit_abs_x']}):",
         f"  span {w['b']:.2f}, root chord (centreline) {w['cr']:.2f}, tip chord {w['ct']:.2f}, taper {w['lam']:.3f}",
         f"  S {w['S']:.0f} mm2, AR {w['AR']:.2f}, MAC {w['mac']:.2f} at |x| {w['x_mac']:.1f}, MAC LE y {w['le_mac']:.2f}, chord-line z {w['z_mac']:.2f}",
         f"  incidence to the fuselage datum {w['incidence']:.2f} deg (LE-TE line); chord fit residual max {w['chord_fit_resid']:.3f} mm",
         "  stations |x|, LE y, LE z, TE y, TE z, chord, incidence:"]
    L += ["   " + " ".join(f"{v:8.2f}" for v in r) for r in w["stations"]]
    L += [f"CFD frame (m) at scale {cfg['frame']['scale']}: span {b:.4f}, Sref {S:.5g}, MAC {mac:.5g}, CofR {np.round(CofR, 5)}",
          f"  body box {np.round(lo, 4)} to {np.round(hi, 4)}",
          f"Flow: U {fl['U']} m/s, nu {fl['nu']} -> Re(MAC) {Re:,.0f}; alphas {alphas}",
          f"Mesh: base {base * 1e3:.1f} mm, domain x [{x0:.3f}, {x1:.3f}] y [0, {y1d:.3f}] z [{z0:.3f}, {z1:.3f}], {ncell} background cells",
          f"  skin cells {cell * 1e3:.3f} mm (level {me['surface_level'][0]}), features {base / 2 ** me['feature_level'] * 1e3:.3f} mm;"
          f" walls ~{1.0 * cfg['frame']['scale']:.1f} mm thick",
          f"  layers {me['n_layers']} x {me['expansion']}: first {y1 * 1e6:.1f} um (y+ {fl['yplus']} at Cf {fl['cf_sizing']}), "
          f"stack {tot * 1e3:.2f} mm = {tot / cell:.2f} skin cells, last layer {y1 * me['expansion'] ** (me['n_layers'] - 1) / cell:.2f} cell"]
    rep = "\n".join(L) + "\n"
    (case / "geometry_report.txt").write_text(rep, encoding="utf-8")
    print(rep)
    preview(case / "geometry_preview.png", Pc, remap[Fk], reg[keep], names, CofR)


def preview(png, Pc, Fk, rk, names, CofR):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    cols = {"wing": "#4C78A8", "fuselage": "#9D9D9D", "vtail": "#E45756", "nacelle": "#F2B134"}
    T = Pc[Fk]
    cr = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    nn = cr / np.maximum(np.linalg.norm(cr, axis=1, keepdims=True), 1e-30)
    light = np.array([-0.3, 0.4, 0.86]) / np.linalg.norm([-0.3, 0.4, 0.86])
    fig, axs = plt.subplots(3, 1, figsize=(11, 12), gridspec_kw=dict(height_ratios=[2.2, 1, 1]))
    for ax, (i, j, k, s, title) in zip(axs, [(0, 1, 2, 1, "top (x downstream, y span)"),
                                            (0, 2, 1, -1, "side (from +y)"), (1, 2, 0, -1, "front (from upstream)")]):
        o = np.argsort(s * T[:, :, k].mean(1))
        base = np.array([matplotlib.colors.to_rgb(cols.get(names[r], "#777777")) for r in rk[o]])
        shade = (0.45 + 0.55 * np.abs(nn[o] @ light))[:, None]
        ax.add_collection(PolyCollection(T[o][:, :, [i, j]], facecolors=base * shade, edgecolors="none"))
        ax.plot(CofR[i], CofR[j], "k+", ms=12, mew=2)
        ax.autoscale()
        ax.set_aspect("equal")
        ax.set_title(title, loc="left")
        ax.grid(alpha=0.3)
    handles = [plt.Line2D([], [], color=cols.get(n, "#777"), lw=8, label=n) for n in names]
    handles.append(plt.Line2D([], [], color="k", marker="+", ls="", ms=10, label="moment ref."))
    axs[0].legend(handles=handles, loc="upper right", ncol=5, fontsize=9)
    fig.tight_layout()
    fig.savefig(png, dpi=110)


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
