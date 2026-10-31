"""AVL studies: winglets / tip plates, flap-twist e, biplane and box wing. Writes out/aero_mono/tables_part_np.json"""
import json, math, sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import avl_tools as A
OUT = A.W / "out" / "aero_mono"
B, TAPER = 1.82, 0.7
A.WORK.mkdir(parents=True, exist_ok=True)

def bending(strips, S, b, q_scale=1.0):
    """root bending coefficient M/(q S b/2): wing strips cl*A*y + winglet strips |cl|*A*z (inward side force, adds)."""
    M = 0.0
    for name, rows in strips.items():
        for z, y, c, area, cl in rows:
            if name.lower().startswith("wing"):
                M += cl * area * abs(y)
            elif name.lower().startswith("wl"):
                M += abs(cl) * area * abs(z)
    return 2 * M / (S * b)

def case(S, h_frac=0.0, below_frac=0.0, tag="w", cl_target=1.0, toes=(0.0, 1.0, 2.0, 3.0)):
    """e and root-bending coefficient; winglet toe is optimised over `toes` (deg, vertical fin, chord 0.5 x wing tip chord:
    the result is insensitive to winglet chord, checked 0.25-1.0). Run at alpha 10 deg (e is CL independent)."""
    half = B / 2
    cr, mac = A.planform(S, B, TAPER)
    ct = A.chord(half, half, cr, TAPER)
    ar = B * B / S
    best = None
    for toe in (toes if h_frac > 0 else (0.0,)):
        surf = A._surface_wing("Wing", S, B, TAPER, nspan=28, nchord=10)
        if h_frac > 0:
            h = h_frac * half; c1 = 0.5 * ct; c2 = 0.7 * c1; xle = 0.25 * (cr - ct) + 0.25 * ct
            hb = below_frac * h
            surf += ["SURFACE", "WL", "10 1.0 12 1.0", "YDUPLICATE", "0.0"]
            for z, c in (([(-hb, c2)] if hb > 0 else []) + [(0.0, c1), (h, c2)]):
                surf += ["SECTION", f"{xle - 0.25 * c:.5f} {half:.5f} {z:.5f} {c:.5f} {toe:.3f}"]
        p = A.WORK / f"{tag}.avl"
        A.write_avl(p, S, B, TAPER, surf)
        r = A.run_case(p, 10.0, tag)
        e = r["CL"] ** 2 / (math.pi * ar * r["CDi"])
        if best is None or e > best[0]:
            best = (e, toe, bending(r["strips"], S, B) * cl_target / r["CL"])
    return {"S": S, "h_frac": h_frac, "below_frac": below_frac, "e": best[0], "bend": best[2], "toe_opt": best[1],
            "h": h_frac * half, "h_over_b": h_frac / 2}

def winglets():
    res = []
    for S in (0.9, 1.1):
        base = case(S, 0.0, 0.0, "b0")
        res.append({**base, "kind": "none", "de": 0.0, "bend_ratio": 1.0})
        for hf in (0.05, 0.10, 0.15, 0.20, 0.30):
            for kind, bf in (("winglet", 0.0), ("tip_plate", 0.5)):
                r = case(S, hf, bf, "w1")
                r.update(kind=kind, de=r["e"] - base["e"], bend_ratio=r["bend"] / base["bend"])
                res.append(r)
    return res

def flap_twist_e():
    """Inviscid e of the wing with the flap as an equivalent twist (as wing_clmax.py): flap span 0.6, blend 0.05."""
    out = []
    S = 0.9; half = B / 2; cr, mac = A.planform(S, B, TAPER)
    for name, tw in (("clean", 0.0), ("turn 10deg plain", 5.74), ("land 30deg plain", 9.09), ("land Fowler/slot (dCl 1.2)", 11.9)):
        L = ["SURFACE", "Wing", "8 1.0 28 1.0", "YDUPLICATE", "0.0"]
        ys = [0.0, 0.575 * half, 0.625 * half, half]; inc = [tw, tw, 0.0, 0.0]
        for y, i in zip(ys, inc):
            c = A.chord(y, half, cr, TAPER)
            L += ["SECTION", f"{0.25*(cr-c):.5f} {y:.5f} 0.0 {c:.5f} {i:.3f}"]
        p = A.WORK / "ft.avl"; A.write_avl(p, S, B, TAPER, L)
        r = A.run_case(p, 4.0, "ft")
        out.append({"case": name, "twist_deg": tw, "e": r["CL"] ** 2 / (math.pi * (B * B / S) * r["CDi"]), "CL": r["CL"]})
    return out

def multi(S=0.9):
    out = []
    ar = B * B / S
    base = case(S, 0.0, 0.0, "m0")
    out.append({"config": "monoplane", "gap_over_b": 0, "e": base["e"]})
    cr, mac = A.planform(S / 2, B, TAPER)
    for g in (0.10, 0.15, 0.20, 0.25):
        for box in (False, True):
            gap = g * B
            surf = A._surface_wing("Wing", S / 2, B, TAPER, z=gap / 2, nspan=24)
            surf += A._surface_wing("Wing2", S / 2, B, TAPER, z=-gap / 2, nspan=24)
            if box:
                half = B / 2; ct = A.chord(half, half, cr, TAPER)
                L = ["SURFACE", "Plate", "6 1.0 6 1.0", "YDUPLICATE", "0.0"]
                for z in (-gap / 2, gap / 2):
                    L += ["SECTION", f"{0.25*(cr-ct):.5f} {half:.5f} {z:.5f} {ct:.5f} 0.0"]
                surf += L
            p = A.WORK / "mb.avl"; A.write_avl(p, S, B, TAPER, surf)
            r1 = A.run_case(p, 3.0, "mba"); r2 = A.run_case(p, 12.0, "mbb")
            e = r2["CL"] ** 2 / (math.pi * ar * r2["CDi"])
            out.append({"config": "box" if box else "biplane", "gap_over_b": g, "e": e, "k_ratio": base["e"] / e,
                        "chord_each": cr})
    return out

if __name__ == "__main__":
    d = {"winglets": winglets(), "flap_twist": flap_twist_e(), "multi": multi()}
    (OUT / "tables_part_np.json").write_text(json.dumps(d, indent=1))
    for r in d["winglets"]: print(r["S"], r["kind"], r["h_frac"], round(r["e"], 4), round(r["de"], 4), round(r["bend_ratio"], 3))
    for r in d["flap_twist"]: print(r)
    for r in d["multi"]: print(r)
