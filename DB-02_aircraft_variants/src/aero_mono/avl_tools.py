"""Small AVL 3.52 driver for span-efficiency studies (own code; the repo AVL file writer is not used).
All runs execute in W/out/aero_mono/work/avl (never elsewhere). SI, degrees.  Import-safe."""
from __future__ import annotations
import math, os, re, subprocess
from pathlib import Path

W = Path(__file__).resolve().parents[2]
REPO = W.parent
AVL_EXE = str(REPO / "analysis" / "tools" / "avl352.exe")
WORK = W / "out" / "aero_mono" / "work" / "avl"


def chord(y, half, cr, taper):
    return cr * (1 - (1 - taper) * y / half)


def planform(S, b, taper):
    cr = 2 * S / (b * (1 + taper))
    mac = 2 / 3 * cr * (1 + taper + taper ** 2) / (1 + taper)
    return cr, mac


def _surface_wing(name, S, b, taper, z=0.0, xle0=0.0, nspan=24, nchord=8, ydup=True):
    cr, mac = planform(S, b, taper)
    half = b / 2
    L = ["SURFACE", name, f"{nchord} 1.0 {nspan} 1.0"]
    if ydup:
        L += ["YDUPLICATE", "0.0"]
    L += ["TRANSLATE", f"{xle0:.5f} 0.0 {z:.5f}"]
    for y in (0.0, half):
        c = chord(y, half, cr, taper)
        L += ["SECTION", f"{0.25 * (cr - c):.5f} {y:.5f} 0.0 {c:.5f} 0.0"]
    return L


def _surface_winglet(name, y, xle_tip, c_tip, h, below=0.0, c_top_ratio=0.7, nspan=6, nchord=6):
    """Vertical fin at the tip station y: from z = -below to z = h (quarter-chord straight)."""
    ct = c_tip
    c_top = ct * c_top_ratio
    L = ["SURFACE", name, f"{nchord} 1.0 {nspan} 1.0", "YDUPLICATE", "0.0"]
    pts = []
    if below > 0:
        pts.append((-below, ct * c_top_ratio))
    pts.append((0.0, ct))
    pts.append((h, c_top))
    for z, c in pts:
        xle = xle_tip + 0.25 * ct - 0.25 * c
        L += ["SECTION", f"{xle:.5f} {y:.5f} {z:.5f} {c:.5f} 0.0"]
    return L


def _body(name, length, diam, x0=0.0, z0=0.0, nose=0.12, tail=0.2, n=14):
    """Slender-body fuselage (circular equivalent diameter) for an AVL BODY: ogive nose, cylinder, cone tail."""
    xs, rs = [], []
    for i in range(n + 1):
        t = i / n
        x = t * length
        if t < nose:
            r = diam / 2 * math.sqrt(1 - (1 - t / nose) ** 2)
        elif t > 1 - tail:
            r = diam / 2 * (1 - t) / tail
        else:
            r = diam / 2
        xs.append(x); rs.append(max(r, 1e-4))
    fn = f"{name}.dat"
    (WORK / fn).write_text("\n".join(f"{x:.5f} {r:.5f}" for x, r in zip(xs, rs)) + "\n")
    return ["BODY", name, "16 1.0", "BFILE", fn, "TRANSLATE", f"{x0:.5f} 0.0 {z0:.5f}"]


def write_avl(path, S, b, taper, surfaces_extra=(), body=None, title="w"):
    cr, mac = planform(S, b, taper)
    L = [title, "0.0", "0 0 0", f"{S:.6f} {mac:.6f} {b:.6f}", f"{0.25 * cr:.5f} 0 0", "0.0"]
    L += list(surfaces_extra)
    if body:
        L += body
    path.write_text("\n".join(L) + "\n")


def parse_st(text):
    def g(key):
        m = re.search(re.escape(key) + r"\s*=\s*(-?\d+\.\d+|-?\d+\.?\d*E[+-]\d+|-?\d+)", text)
        return float(m.group(1)) if m else float("nan")
    return {"CL": g("CLtot"), "CD": g("CDtot"), "CDi": g("CDind"), "e": g("e"), "Cm": g("Cmtot")}


def parse_fs(text):
    """strips per surface: {surface name: [(Zle, Yle, chord, area, cl)]} from an AVL FS dump."""
    out, cur, on = {}, None, False
    for ln in text.splitlines():
        m = re.match(r"\s*Surface #\s*\d+\s+(\S+)", ln)
        if m:
            cur = m.group(1); out[cur] = []; on = False; continue
        if ln.strip().startswith("j ") and "Xle" in ln:
            on = True; continue
        if on and cur:
            v = ln.split()
            if len(v) >= 10 and v[0].isdigit():
                out[cur].append((float(v[3]), float(v[2]), float(v[4]), float(v[5]), float(v[9])))
    return out


def run_case(avl_path, alpha=4.0, tag="c", flap=None):
    WORK.mkdir(parents=True, exist_ok=True)
    st, fs = f"{tag}_st.txt", f"{tag}_fs.txt"
    for f in (st, fs):
        p = WORK / f
        if p.exists():
            p.unlink()
    cmd = [f"LOAD {avl_path.name}", "OPER", f"A A {alpha:g}", "X", f"ST {st}", f"FS {fs}", "", "QUIT"]
    subprocess.run([AVL_EXE], input="\n".join(cmd) + "\n", text=True, cwd=WORK, capture_output=True, timeout=180)
    res = parse_st((WORK / st).read_text())
    res["strips"] = parse_fs((WORK / fs).read_text())
    return res
