"""Builds the lookup tables the fast model reads: out/aero_mono/tables.json. Not imported by model.py.
Heavy parts: AVL strip runs (clean CLmax, e), run with  PYTHONDONTWRITEBYTECODE=1 python build_tables.py [part]
Everything writes inside W/out/aero_mono/. Existing repo modules are imported read-only (functions only, no main())."""
import json, math, sys, tempfile
from pathlib import Path
import numpy as np
W = Path(__file__).resolve().parents[2]
REPO = W.parent
OUT = W / "out" / "aero_mono"
WORK = OUT / "work" / "tmp"
WORK.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(WORK)
sys.dont_write_bytecode = True
sys.path.insert(0, str(REPO / "analysis")); sys.path.insert(0, str(REPO / "analysis" / "data" / "aero"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import wing_clmax as wc            # noqa: E402   (read-only import; no main())
import lsat                        # noqa: E402
import avl_tools as A              # noqa: E402

TAPERS = (0.5, 0.7, 1.0)
AREAS = (0.8, 0.9, 1.0, 1.1, 1.2, 1.3)
B = 1.82


def clean_table():
    secmax = wc.section_clmax()
    flap, a0, _ = wc.ag40d_flap(300e3)
    claf = a0 / (2 * math.pi * math.pi / 180)
    half = B / 2
    out = {}
    for t in TAPERS:
        for S in AREAS:
            runs, cbar = wc.run_avl(S, B, t, 0.0, 0.0, claf, "SD7037")
            def re_key(c):
                re = 1.064 * 14.0 * c / 1.86e-5
                return min((3e5, 4e5, 5e5), key=lambda r: abs(r - re))
            def clmax_of(eta, c):
                return secmax[("SD7037", re_key(c), 0.0)]
            cl, a_st, eta, cm = wc.critical(runs, clmax_of, 0.0, half)
            out[f"{t}|{S}"] = {"taper": t, "S": S, "cl_strict": cl, "alpha_stall": a_st, "eta_first_stall": eta,
                               "cm_ac": cm, "cbar": cbar}
    return out


def e_table():
    out = {}
    for t in TAPERS:
        for S in AREAS:
            p = A.WORK / "e.avl"
            A.write_avl(p, S, B, t, A._surface_wing("Wing", S, B, t, nspan=28, nchord=8))
            r = A.run_case(p, 4.0, "e")
            ar = B * B / S
            e_cd = r["CL"] ** 2 / (math.pi * ar * r["CDi"])
            out[f"{t}|{S}"] = {"taper": t, "S": S, "AR": ar, "e_trefftz": r["e"], "e_from_CDi": e_cd, "CL": r["CL"]}
    return out


def plain_flap_table():
    """AG40d-02r 25 % plain flap, Williamson 2012 / UIUC LSAT Vol 6, at Re 3e5 and 4e5 (read from the cached zips)."""
    runs = [r for r in lsat.runs() if r["volume"] == 6 and r["airfoil"].lower().startswith("ag40d")]
    tab = {}
    for rr in (3e5, 4e5):
        at = {lsat.flap(r)[1]: r for r in runs if round(r["re"], -5) == rr}
        ref = at[0.0]
        tab[str(int(rr))] = {str(int(d)): {"dcl_a0": lsat.increment(r, ref), "dcm": lsat.increment(r, ref, "cm"),
                                           "dclmax": lsat.clmax(r)[0] - lsat.clmax(ref)[0]}
                             for d, r in sorted(at.items()) if d >= 0}
        tab[str(int(rr))]["clmax_clean"] = lsat.clmax(ref)[0]
    return tab


def flap_drag_table():
    """Profile-drag increment of the AG40d-02r plain flap at fixed section CL (UIUC LSAT Vol 6 drag files, Re ~3e5)."""
    import re as _re, zipfile
    z = zipfile.ZipFile(REPO / "analysis" / "data" / "raw" / "aero" / "uiuc-lsat-v6-data.zip")
    res = {}
    for d in (0, 5, 10, 15, 20, 25):
        name = f"volume06/ag40d_f{'p' + str(d) if d else '0'}_drag.dat"
        t = z.read(name).decode("latin-1")
        for m in _re.finditer(r"Average Reynolds #:\s*\n\s*(\d+(?:\.\d+)?)\s*\n\s*Number of angles of attack:\s*\n\s*(\d+)\s*\n[^\n]*\n", t):
            re_, n = float(m.group(1)), int(m.group(2))
            if abs(re_ - 3e5) > 0.4e5:
                continue
            rows = [l.split() for l in t[m.end():].splitlines()[:n]]
            cl = np.array([float(r[1]) for r in rows]); cd = np.array([float(r[2]) for r in rows])
            o = np.argsort(cl)
            res[str(d)] = {"re": re_, "cd": {str(c): float(np.interp(c, cl[o], cd[o])) for c in (0.8, 1.0, 1.2)},
                           "cl_range": [float(cl.min()), float(cl.max())]}
    return res


if __name__ == "__main__":
    part = sys.argv[1] if len(sys.argv) > 1 else "all"
    p = OUT / f"tables_part_{part}.json"
    if part == "clean":
        d = clean_table()
    elif part == "e":
        d = e_table()
    elif part == "plain":
        d = {"plain": plain_flap_table(), "flap_drag": flap_drag_table()}
    json.dump(d, open(p, "w"), indent=1)
    print("wrote", p)
