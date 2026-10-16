# Copyright © 2026 the members of the AUM AIAA DBF team. All rights reserved.
"""Airfoil coordinate files from the UIUC database, in either published layout (TOOLING).

Selig:     name line, then x y from the trailing edge over the upper surface to
           the leading edge and back along the lower surface.
Lednicer:  name line, a line with the upper and lower point counts, then the
           upper surface and the lower surface, each from the leading edge.
selig_file() writes the Selig layout that XFoil and AVL read.
"""
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "raw" / "aero"


def read(sid):
    """(name, [(x, y), ...]) in Selig order for registry id sid (e.g. 'coord-clarky')."""
    lines = (RAW / f"{sid}.dat").read_text(encoding="latin-1").splitlines()
    name = lines[0].strip()
    rows = [tuple(float(v) for v in l.split()) for l in lines[1:] if l.strip()]
    if rows[0][0] > 1.5:                                  # Lednicer
        nu, nl = int(rows[0][0]), int(rows[0][1])
        up, lo = rows[1:1 + nu], rows[1 + nu:1 + nu + nl]
        if len(up) != nu or len(lo) != nl:
            raise ValueError(f"{sid}: expected {nu} + {nl} points")
        pts = list(reversed(up)) + lo[1:]                 # TE -> LE -> TE, LE point once
    else:
        pts = rows
    return name, pts


def thickness(pts, x):
    """Local thickness at chord station x (linear interpolation on each surface)."""
    ile = min(range(len(pts)), key=lambda i: pts[i][0])
    up = sorted(pts[:ile + 1])
    lo = sorted(pts[ile:])

    def at(s):
        for (x0, y0), (x1, y1) in zip(s, s[1:]):
            if x0 <= x <= x1 and x1 > x0:
                return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
        raise ValueError(f"x = {x} outside the surface")
    return at(up) - at(lo)


def max_thickness(pts, n=400):
    return max(thickness(pts, 0.002 + 0.996 * i / n) for i in range(n + 1))


def selig_file(sid, dest):
    name, pts = read(sid)
    Path(dest).write_text(name + "\n" + "\n".join(f"{x:.6f} {y:.6f}" for x, y in pts) + "\n")
    return Path(dest)
