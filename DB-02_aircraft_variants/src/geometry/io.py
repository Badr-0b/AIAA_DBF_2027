"""Load, save and resolve S9 geometry documents.

    from geometry import io
    g = io.load("early/REF-D01.json")      # validated dict (raises GeometryError)
    r = io.resolve(g)                      # global section / station geometry for the exporters
    io.save(g, "out/my_variant.json")

resolve() is the single place where the local surface frames, tip devices,
control-surface boundaries, mirrored bodies and airfoil coordinates are turned
into global numbers. to_avl, to_stl, three_view and wetted all consume it, so
they cannot disagree about the shape.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import numpy as np

from . import schema

PKG = Path(__file__).resolve().parent
AIRFOIL_DIR = PKG / "airfoils"
N_AIRFOIL = 61          # x stations per side after resampling (cosine spacing), LE and TE included


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------
def load(path, strict=True):
    """Read a JSON geometry, validate it and return the dict.

    The document's folder is remembered under geom["_dir"] (not saved) so that
    relative airfoil paths resolve. strict=False returns invalid documents too
    (the errors are in geom["_errors"])."""
    path = Path(path)
    g = json.loads(path.read_text(encoding="utf-8"))
    err, warn = schema.validate(g)
    if err and strict:
        raise schema.GeometryError(err, warn)
    g["_dir"] = str(path.resolve().parent)
    g["_warnings"] = warn
    if err:
        g["_errors"] = err
    return g


def save(geom, path):
    """Validate and write the document (keys starting with '_' are dropped)."""
    clean = {k: v for k, v in geom.items() if not k.startswith("_")}
    schema.check(clean)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean, indent=1, default=_np_default) + "\n", encoding="utf-8", newline="\n")
    return path


def _np_default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


# ---------------------------------------------------------------------------
# Airfoils
# ---------------------------------------------------------------------------
def naca4(code, n=N_AIRFOIL):
    """NACA 4-digit section, closed trailing edge; returns Selig-ordered (x, z)."""
    m, p, t = int(code[0]) / 100, int(code[1]) / 10, int(code[2:4]) / 100
    beta = np.linspace(0, np.pi, n)
    x = 0.5 * (1 - np.cos(beta))
    yt = 5 * t * (0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - 0.1036 * x ** 4)
    if m > 0 and p > 0:
        yc = np.where(x < p, m / p ** 2 * (2 * p * x - x ** 2), m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * x - x ** 2))
        dy = np.where(x < p, 2 * m / p ** 2 * (p - x), 2 * m / (1 - p) ** 2 * (p - x))
    else:
        yc, dy = np.zeros_like(x), np.zeros_like(x)
    th = np.arctan(dy)
    xu, zu = x - yt * np.sin(th), yc + yt * np.cos(th)
    xl, zl = x + yt * np.sin(th), yc - yt * np.cos(th)
    X = np.concatenate([xu[::-1], xl[1:]])
    Z = np.concatenate([zu[::-1], zl[1:]])
    return X, Z


def read_dat(path):
    """Selig or Lednicer coordinate file -> Selig-ordered (x, z), unit chord."""
    rows = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        p = line.replace(",", " ").split()
        try:
            rows.append((float(p[0]), float(p[1])))
        except (ValueError, IndexError):
            continue
    a = np.array(rows)
    if len(a) and a[0, 0] > 1.5:                     # Lednicer: first row = point counts
        nu, nl = int(a[0, 0]), int(a[0, 1])
        up, lo = a[1:1 + nu], a[1 + nu:1 + nu + nl]
        a = np.concatenate([up[::-1], lo[1:]])
    x0, x1 = a[:, 0].min(), a[:, 0].max()
    a[:, 0] = (a[:, 0] - x0) / (x1 - x0)
    a[:, 1] /= (x1 - x0)
    return a[:, 0], a[:, 1]


def airfoil_xz(name, geom=None):
    """Raw coordinates for an airfoil name used in a document."""
    lib = (geom or {}).get("airfoils", {})
    ent = lib.get(name)
    if ent is None:
        if str(name).upper().startswith("NACA"):
            return naca4(str(name)[4:].strip())
        ent = {"file": name}
    if "naca" in ent:
        return naca4(ent["naca"])
    f = Path(ent["file"])
    cands = [f] if f.is_absolute() else [Path((geom or {}).get("_dir", ".")) / f, AIRFOIL_DIR / f, AIRFOIL_DIR / f.name]
    for c in cands:
        if c.exists():
            return read_dat(c)
    raise FileNotFoundError(f"airfoil '{name}': none of {[str(c) for c in cands]} exists")


def resample(x, z, n=N_AIRFOIL):
    """(xs, z_upper, z_lower) at n cosine-spaced stations from TE (x=1) to LE (x=0)."""
    i0 = int(np.argmin(x))
    xu, zu = x[:i0 + 1][::-1], z[:i0 + 1][::-1]        # LE -> TE
    xl, zl = x[i0:], z[i0:]
    xs = 0.5 * (1 + np.cos(np.linspace(0, np.pi, n)))  # 1 -> 0
    ou, ol = np.argsort(xu), np.argsort(xl)
    zU = np.interp(xs, xu[ou], zu[ou])
    zL = np.interp(xs, xl[ol], zl[ol])
    zle = 0.5 * (zU[-1] + zL[-1])
    zU[-1] = zL[-1] = zle
    return xs, zU, zL


def airfoil_table(name, geom=None, n=N_AIRFOIL):
    xs, zu, zl = resample(*airfoil_xz(name, geom), n=n)
    return {"name": name, "x": xs, "zu": zu, "zl": zl, "tc": float((zu - zl).max())}


# ---------------------------------------------------------------------------
# Resolve: local definitions -> global geometry
# ---------------------------------------------------------------------------
def _rotx(v, gam):
    """Rotate (y, z) of local vectors about +x by gam (rad)."""
    c, s = math.cos(gam), math.sin(gam)
    v = np.asarray(v, float)
    out = v.copy()
    out[..., 1] = c * v[..., 1] - s * v[..., 2]
    out[..., 2] = s * v[..., 1] + c * v[..., 2]
    return out


def _interp_section(a, b, y):
    t = (y - a["y"]) / (b["y"] - a["y"])
    out = {k: a.get(k, 0.0) + t * (b.get(k, 0.0) - a.get(k, 0.0)) for k in ("x_le", "z_le", "chord", "twist_deg")}
    out["y"] = y
    out["airfoil"] = a.get("airfoil")
    out["_blend"] = (a.get("airfoil"), b.get("airfoil"), t)
    return out


def _expand_surface(s, geom):
    """Return (local sections incl. control breaks and winglet, extra surfaces)."""
    secs = [dict(c) for c in s["sections"]]
    extra = []
    td = s.get("tip_device") or {"type": "none"}
    if td["type"] == "winglet":
        t = secs[-1]
        h, cant = td["height"], math.radians(td.get("cant_deg", 0.0))
        secs.append({"y": t["y"] + h * math.sin(cant), "z_le": t.get("z_le", 0.0) + h * math.cos(cant),
                     "x_le": t["x_le"] + h * math.tan(math.radians(td.get("sweep_le_deg", 30.0))),
                     "chord": td.get("tip_chord", 0.5 * t["chord"]), "twist_deg": -td.get("toe_deg", 0.0),
                     "airfoil": td.get("airfoil", t.get("airfoil")), "_winglet": True})
    elif td["type"] == "tip_plate":
        t = secs[-1]
        gam = math.radians(s.get("dihedral_deg", 0.0))
        tip = np.array(s["origin"], float) + _rotx([t["x_le"], t["y"], t.get("z_le", 0.0)], gam)
        h, fb = td["height"], td.get("fraction_below", 0.4)
        c = td.get("root_chord", 1.1 * t["chord"])
        x0 = tip[0] - 0.5 * (c - t["chord"])
        af = td.get("airfoil", "NACA0006")
        extra.append({"name": f"{s['name']}_tip_plate", "role": "tip_plate", "component": s.get("component", s["name"]),
                      "symmetric": s["symmetric"], "origin": [x0, float(tip[1]), float(tip[2]) - fb * h],
                      "dihedral_deg": 90.0, "incidence_deg": 0.0,
                      "sections": [{"y": 0.0, "x_le": 0.0, "z_le": 0.0, "chord": c, "airfoil": af},
                                   {"y": h, "x_le": 0.0, "z_le": 0.0, "chord": c, "airfoil": af}],
                      "avl": {"nchord": 6, "nspan": 6}})
    # control boundaries become sections (AVL needs them; the loft does not care)
    wing_part = [c for c in secs if not c.get("_winglet")]
    for ctl in s.get("controls", []):
        for yb in (ctl["y_start"], ctl["y_end"]):
            if any(abs(c["y"] - yb) < 1e-6 for c in wing_part):
                continue
            for a, b in zip(wing_part, wing_part[1:]):
                if a["y"] < yb < b["y"]:
                    n = _interp_section(a, b, yb)
                    wing_part.insert(wing_part.index(b), n)
                    break
    secs = wing_part + [c for c in secs if c.get("_winglet")]
    return secs, extra


def _section_frames(P, joined_root):
    """Per-section span direction s, thickness direction n and mitre factor k.

    P (m, 3) global leading-edge points. Panel directions are taken in the y-z
    plane (the section planes contain the x axis, as in AVL)."""
    m = len(P)
    d = np.diff(P, axis=0)
    d[:, 0] = 0.0
    nrm = np.linalg.norm(d, axis=1)
    nrm[nrm < 1e-12] = 1.0
    d = d / nrm[:, None]
    S, K = np.zeros((m, 3)), np.ones(m)
    for i in range(m):
        a = d[i - 1] if i > 0 else None
        b = d[i] if i < m - 1 else None
        if i == 0 and joined_root:
            a = b * np.array([1.0, 1.0, -1.0])         # mirror image of the first panel, traversed inward
        if a is None:
            s = b
        elif b is None:
            s = a
        else:
            s = a + b
            s = s / max(np.linalg.norm(s), 1e-12)
            cosh = np.clip(np.dot(s, b), 1e-3, 1.0)
            K[i] = 1.0 / cosh
        S[i] = s
    N = np.cross(np.array([1.0, 0.0, 0.0]), S)
    return S, N, K


def resolve(geom):
    """Global geometry used by every exporter.

    Returns {"surfaces": [...], "bodies": [...], "geom": geom}. Each surface has
    numpy arrays for the defined half (as written; mirrored copies are made by
    the consumers): le (m,3), chord (m), twist_deg (m, incidence included),
    span_dir S, thickness dir N, mitre K, airfoil tables, local y, controls."""
    out = {"surfaces": [], "bodies": [], "geom": geom}
    tables = {}

    def table(name):
        if name not in tables:
            tables[name] = airfoil_table(name, geom)
        return tables[name]

    queue = [copy.deepcopy(s) for s in geom["surfaces"]]
    while queue:
        s = queue.pop(0)
        secs, extra = _expand_surface(s, geom)
        queue.extend(extra)
        gam = math.radians(s.get("dihedral_deg", 0.0))
        org = np.array(s["origin"], float)
        loc = np.array([[c["x_le"], c["y"], c.get("z_le", 0.0)] for c in secs])
        le = org + _rotx(loc, gam)
        joined = bool(s["symmetric"]) and abs(le[0, 1]) < 1e-9
        S, N, K = _section_frames(le, joined)
        afs = []
        for c in secs:
            bl = c.get("_blend")
            if bl and bl[0] != bl[1] and bl[0] and bl[1]:
                ta, tb = table(bl[0]), table(bl[1])
                t = bl[2]
                afs.append({"name": f"{bl[0]}~{bl[1]}@{t:.2f}", "x": ta["x"], "zu": (1 - t) * ta["zu"] + t * tb["zu"],
                            "zl": (1 - t) * ta["zl"] + t * tb["zl"], "tc": None})
            else:
                afs.append(table(c.get("airfoil") or "NACA0012"))
        out["surfaces"].append({
            "name": s["name"], "role": s["role"], "component": s.get("component", s["name"]),
            "symmetric": bool(s["symmetric"]), "joined_root": joined, "dihedral_deg": s.get("dihedral_deg", 0.0),
            "le": le, "chord": np.array([c["chord"] for c in secs], float),
            "twist_deg": np.array([c.get("twist_deg", 0.0) for c in secs], float) + s.get("incidence_deg", 0.0),
            "y_local": np.array([c["y"] for c in secs], float), "S": S, "N": N, "K": K,
            "airfoils": afs, "winglet": np.array([bool(c.get("_winglet")) for c in secs]),
            "controls": s.get("controls", []), "avl": s.get("avl", {}), "src": s,
        })
    for b in geom.get("bodies", []):
        st = b["stations"]
        org = np.array(b["origin"], float)
        ex = [st_.get("exponent", 2.0) for st_ in st]
        rb = {"name": b["name"], "role": b["role"], "component": b.get("component", b["name"]),
              "x": org[0] + np.array([q["x"] for q in st], float), "y": org[1],
              "zc": org[2] + np.array([q.get("z", 0.0) for q in st], float),
              "w": np.array([q["width"] for q in st], float), "h": np.array([q["height"] for q in st], float),
              "n_top": np.array([e[0] if isinstance(e, list) else e for e in ex], float),
              "n_bot": np.array([e[1] if isinstance(e, list) else e for e in ex], float),
              "avl": b.get("avl", "body" if b["role"] == "fuselage" else "none"), "src": b}
        out["bodies"].append(rb)
        if b.get("symmetric") and abs(org[1]) > 1e-9:
            mb = dict(rb, name=b["name"] + "_L", y=-org[1])
            rb["name"] = b["name"] + ("_R" if org[1] > 0 else "_L")
            mb["name"] = b["name"] + ("_L" if org[1] > 0 else "_R")
            out["bodies"].append(mb)
    return out


def section_points(rs, i, te_thickness=0.0, n_chord=None):
    """3-D points of section i of a resolved surface: (upper (n,3), lower (n,3)),
    TE first, LE last. te_thickness (m) opens the trailing edge (XFoil-style
    linear thickening, 0 = sharp)."""
    af = rs["airfoils"][i]
    xs, zu, zl = af["x"], af["zu"], af["zl"]
    if n_chord and n_chord != len(xs):
        xn = 0.5 * (1 + np.cos(np.linspace(0, np.pi, n_chord)))
        zu, zl = np.interp(xn, xs[::-1], zu[::-1]), np.interp(xn, xs[::-1], zl[::-1])
        xs = xn
    c, th = rs["chord"][i], math.radians(rs["twist_deg"][i])
    n, k = rs["N"][i], rs["K"][i]
    ex = np.array([1.0, 0.0, 0.0])
    cdir = math.cos(th) * ex - math.sin(th) * n
    ndir = math.sin(th) * ex + math.cos(th) * n
    dt = 0.5 * te_thickness / c * xs if te_thickness > 0 else 0.0 * xs
    le = rs["le"][i]
    U = le + c * (xs[:, None] * cdir + (k * (zu + dt))[:, None] * ndir)
    L = le + c * (xs[:, None] * cdir + (k * (zl - dt))[:, None] * ndir)
    return U, L


def mirror_y(P):
    Q = np.array(P, float).copy()
    Q[..., 1] *= -1
    return Q
