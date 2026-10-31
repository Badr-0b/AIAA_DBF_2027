# Copyright © 2026 Badr Obtel. All rights reserved.
"""Reader for the UIUC Low-Speed Airfoil Tests (LSATs) tabulated data (TOOLING).

The cached zips (analysis/data/raw/aero/uiuc-lsat-v*-data.zip, fetched by
fetch_aero.py) hold the published wind-tunnel polars. Two layouts exist:
  Vols 1-3  one LIFTnn.TXT per volume: runs concatenated, each headed by a
            '::::::::::::::' / file name / '::::::::::::::' banner;
  Vols 4-6  one *_lift.dat per configuration.
Every run block reads (FORMATnn.TXT, "Annotated polar file"):
  Airfoil: / Builder: / Comment:, then per Reynolds number
  "Average Reynolds #:" <Re>, "Number of angles of attack:" <N>, a header
  line, and N rows of alpha (deg) / Cl / (Cm or Cd ...).
Nothing is retyped: values come straight from the published text files.

Vols 1-3 state "Moment data in the file is meaningless" in the lift files, so
only alpha and Cl are read.
"""
import re
import zipfile
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "raw" / "aero"
VOLUMES = {1: "uiuc-lsat-v1-data", 2: "uiuc-lsat-v2-data", 3: "uiuc-lsat-v3-data",
           5: "uiuc-lsat-v5-data", 6: "uiuc-lsat-v6-data"}
NUM = r"[-+]?\d+(?:\.\d+)?"


def _blocks(text):
    """Split a lift file into (file_name, block_text) runs."""
    if "::::::::::::::" in text:
        parts = text.split("::::::::::::::")
        return [(parts[i].strip(), parts[i + 1]) for i in range(1, len(parts) - 1, 2)]
    return [("", text)]


def _runs(block):
    """Every Reynolds-number sweep in one run block: (Re, [(alpha, cl), ...])."""
    out = []
    for m in re.finditer(r"Average Reynolds #:\s*\n\s*(" + NUM + r")\s*\n\s*Number of angles of attack:\s*\n\s*(\d+)\s*\n[^\n]*\n",
                         block):
        re_avg, n = float(m.group(1)), int(m.group(2))
        rows = block[m.end():].splitlines()[:n]
        pts = []
        for r in rows:
            v = r.split()
            if len(v) >= 2:
                pts.append((float(v[0]), float(v[1]), float(v[2]) if len(v) >= 3 else float("nan")))
        if len(pts) != n:
            raise ValueError(f"expected {n} rows after Re {re_avg}, read {len(pts)}")
        out.append((re_avg, pts))
    return out


def _field(block, name):
    m = re.search(name + r":\s*(.*)", block)
    return m.group(1).strip() if m else ""


def runs():
    """All lift runs in the cached volumes, one dict per (configuration, Re)."""
    out = []
    for vol, sid in VOLUMES.items():
        with zipfile.ZipFile(RAW / f"{sid}.zip") as z:
            for name in z.namelist():
                low = name.lower()
                if not (re.search(r"/lift\d\d\.txt$", low) or low.endswith("_lift.dat")):
                    continue
                text = z.read(name).decode("latin-1")
                for fname, block in _blocks(text):
                    airfoil = _field(block, "Airfoil")
                    comment = _field(block, "Comment")
                    for re_avg, pts in _runs(block):
                        out.append({"volume": vol, "source": sid, "member": name.split("/")[-1],
                                    "file": fname or name.split("/")[-1], "airfoil": airfoil,
                                    "builder": _field(block, "Builder"), "comment": comment,
                                    "re": re_avg, "alpha": [p[0] for p in pts], "cl": [p[1] for p in pts],
                                    # third column: Cm in the lift files of Vols 4-6; Vols 1-3 state
                                    # "Moment data in the file is meaningless"
                                    "cm": [p[2] for p in pts] if vol >= 4 else None})
    return out


def upsweep(run):
    """The increasing-alpha part of a sweep (the tunnel runs go up, then back down)."""
    a = run["alpha"]
    k = next((i for i in range(1, len(a)) if a[i] < a[i - 1] - 0.5), len(a))
    return k


def at_alpha(run, alpha, field="cl"):
    """Linear interpolation of cl (or cm) at alpha on the up-sweep; None outside the range."""
    k = upsweep(run)
    a, v = run["alpha"][:k], run[field][:k]
    pts = sorted(zip(a, v))
    for (a0, v0), (a1, v1) in zip(pts, pts[1:]):
        if a0 <= alpha <= a1 and a1 > a0:
            return v0 + (v1 - v0) * (alpha - a0) / (a1 - a0)
    return None


def increment(run, ref, field="cl", alphas=(-2.0, -1.0, 0.0, 1.0, 2.0)):
    """Mean of field(run) - field(ref) at the given angles: Williamson's lift and
    moment increment (thesis Sec. 6.1, five angles -2 to +2 deg)."""
    d = []
    for a in alphas:
        x, y = at_alpha(run, a, field), at_alpha(ref, a, field)
        if x is None or y is None:
            return None
        d.append(x - y)
    return sum(d) / len(d)


def lift_slope(run, a0=-2.0, a1=4.0):
    """Least-squares dCl/dalpha (per deg) on the up-sweep between a0 and a1."""
    k = upsweep(run)
    pts = [(a, c) for a, c in zip(run["alpha"][:k], run["cl"][:k]) if a0 <= a <= a1]
    n = len(pts)
    ma = sum(p[0] for p in pts) / n
    mc = sum(p[1] for p in pts) / n
    return sum((a - ma) * (c - mc) for a, c in pts) / sum((a - ma) ** 2 for a, _ in pts)


def flap(run):
    """Flap chord ratio and deflection (deg) of a Vol 6 / Vol 5 flapped run, else (None, 0).

    Vol 6 comments read 'Cf/C = 30%, Flap = 40 deg'; the AG40d-02r (25 % chord) and
    AG455ct-02r (30 %) runs give the deflection only (thesis Table 6.1 gives cf/c).
    """
    c = run["comment"]
    m = re.search(r"Flap\s*=\s*(" + NUM + ")", c)
    if not m:
        return None, 0.0
    d = float(m.group(1))
    k = re.search(r"Cf/C\s*=\s*(\d+)\s*%", c)
    if k:
        return int(k.group(1)) / 100.0, d
    a = run["airfoil"].lower()
    if a.startswith("ag40d"):
        return 0.25, d
    if a.startswith("ag455ct"):
        return 0.30, d
    return None, d


def clmax(run):
    """Maximum lift coefficient of the sweep (up and down branches) and its angle."""
    i = max(range(len(run["cl"])), key=lambda j: run["cl"][j])
    return run["cl"][i], run["alpha"][i]
