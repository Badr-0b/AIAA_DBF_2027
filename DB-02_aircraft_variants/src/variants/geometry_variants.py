"""DB-02 Variant A and B point designs (orchestrator, 30 Oct 2026): geometry, AVL neutral point and tail sizing,
mass and CG by loading, and the 3-view drawings.  Writes only W/out/variants/ and W/report/figures/.
Run: PYTHONDONTWRITEBYTECODE=1 python src/variants/geometry_variants.py
Coordinates: x aft from the propeller plane, y right, z up, metres.  Every input carries its basis."""
from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
W = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(W / "src"))
from variants import mass_family as MF                 # noqa: E402
REPO = W.parent
OUT = W / "out" / "variants"
OUT.mkdir(parents=True, exist_ok=True)
WORK = OUT / "avl"
WORK.mkdir(exist_ok=True)
AVL = str(REPO / "analysis" / "tools" / "avl352.exe")
AF = W / "src" / "geometry" / "airfoils" / "sd7037.dat"
B = 1.82                      # design span, m (rule <= 1.8288 m)
TAPER = 0.7                   # S3 / DB-01 planform
WASHOUT = 2.0                 # deg tip washout (design choice: tip-stall margin with outboard ailerons)
DIHEDRAL = 2.0                # deg (high wing)
LT_C_MIN = 1.89               # tail arm >= 1.89 mean chords: rev A's 0.9 m2 layout ratio, kept for larger wings (30 Oct)
BOOM_KG_M = 0.10              # extra tail-boom mass per metre of lengthening (carbon tube + wiring; estimate)
FUS_CLEAR = (0.042, 0.052)    # fuselage width / height minus container width / height (rev A: 0.33 x 0.34 on 0.288)

# Shared hardware (S6 propulsion, S8 payload; masses graded in the sources)
SHARED = {
    "prop_d": 0.508,           # APC 20x15E (S6)
    "axis_h": 0.369,           # prop axis above ground for 0.115 m tip clearance (S6 install.json, 20in_Lp1.0)
    "container": (0.298, 0.288, 0.288),   # S8 container built for 6 kg declared, 150 g sensor (m)
    "container_kg": 1.004,     # S8-R04
    "reel_kg": 0.256,          # Savox drum at 6 kg (S8 dr())
    "pack_kg": 0.674,          # TP3300-8SE55 (PR-01 B10)
    "motor_kg": 0.555,         # AT7215 class (T-Motor spec via S6 catalogue; DB-01 motor_ref 0.50 inside fit)
}


def wing_geo(S):
    cr = 2 * S / (B * (1 + TAPER))
    ct = cr * TAPER
    mac = 2 / 3 * cr * (1 + TAPER + TAPER ** 2) / (1 + TAPER)
    y_mac = B / 6 * (1 + 2 * TAPER) / (1 + TAPER)
    return dict(S=S, cr=cr, ct=ct, mac=mac, y_mac=y_mac, AR=B * B / S)


FLAP_NAME = {"fowler": "Fowler", "slotted": "single-slotted", "plain": "plain"}
FLAP_DM = {"fowler": 0.30, "slotted": 0.12, "plain": 0.0}     # S3 flap mechanism deltas (estimate)
SPEC = json.loads((OUT / "selection.json").read_text(encoding="utf-8")) if (OUT / "selection.json").exists() else {}
DEFAULT_SPEC = {"A": {"S": 0.9, "flap": "fowler", "m_hi": 6.0, "container_kg": 1.004},
                "B": {"S": 1.0, "flap": "slotted", "m_hi": 6.0, "container_kg": 1.004}}


def variant(key, S=None, flap=None):
    """key "A"/"B" (selected designs, out/variants/selection.json) or any label with S and flap given."""
    if S is None:
        sp = SPEC.get(key, DEFAULT_SPEC[key])
        S, flap = sp["S"], sp["flap"]
    cf = 0.25 if flap == "plain" else 0.30
    w = wing_geo(S)
    x_le = 0.40                                # wing root LE aft of prop plane (motor, battery, nose bay ahead)
    x_ac = x_le + 0.25 * w["mac"]               # straight quarter-chord line (zero c/4 sweep would move this slightly)
    cw, ch = fuselage_container()               # box fuselage around the largest container either variant carries
    fus_len, fus_w, fus_h = 1.20, round(cw + FUS_CLEAR[0], 3), round(ch + FUS_CLEAR[1], 3)
    return dict(key=key, flap=FLAP_NAME[flap], flap_type=flap, cf=cf, flap_span=0.60, x_le=x_le, x_ac=x_ac, fus_len=fus_len,
                fus_w=fus_w, fus_h=fus_h, z_wing=fus_h / 2, **w)


def fuselage_container():
    """(width, height) of the largest container among the selected variants (one shared fuselage for A and B)."""
    dims = [(0.288, 0.288)]
    try:
        from integration import search as SE
        for sp in (SPEC or DEFAULT_SPEC).values():
            c = SE.payload_for(sp["m_hi"])[2]["container"]
            dims.append((c[1], c[2]))
    except Exception:                          # noqa: BLE001  (payload model unavailable: rev A container)
        pass
    return max(d[0] for d in dims), max(d[1] for d in dims)


def avl_file(v, Sh, Sv, lt, path):
    """Wing + horizontal tail + fin. NACA 0009 tails (AVL built-in). Bref = 1.82 m."""
    cr, ct, half = v["cr"], v["ct"], B / 2
    xr, z = v["x_le"], v["z_wing"]
    ARh, lamh = 4.0, 0.7
    bh = math.sqrt(ARh * Sh); crh = 2 * Sh / (bh * (1 + lamh)); cth = crh * lamh
    ARv, lamv = 1.5, 0.6
    bv = math.sqrt(ARv * Sv); crv = 2 * Sv / (bv * (1 + lamv)); ctv = crv * lamv
    machh = 2 / 3 * crh * (1 + lamh + lamh ** 2) / (1 + lamh)
    x_ach = v["x_ac"] + lt
    xh = x_ach - 0.25 * machh
    zt = 0.06
    ztip = z + half * math.tan(math.radians(DIHEDRAL))
    xtip = xr + 0.25 * (cr - ct)
    L = [f"DB-02 variant {v['key']}", "0.0", "0 0 0.0",
         f"{v['S']:.4f} {v['mac']:.4f} {B:.4f}", f"{v['x_ac']:.4f} 0.0 0.0", "0.030",
         "SURFACE", "Wing", "10 1.0 26 -1.1", "YDUPLICATE", "0.0", "ANGLE", "2.0",
         "SECTION", f"{xr:.4f} 0.0 {z:.4f} {cr:.4f} 0.0", "AFILE", str(AF),
         "SECTION", f"{xtip:.4f} {half:.4f} {ztip:.4f} {ct:.4f} {-WASHOUT:.2f}", "AFILE", str(AF),
         "SURFACE", "Htail", "8 1.0 12 1.0", "YDUPLICATE", "0.0",
         "SECTION", f"{xh:.4f} 0.0 {zt:.4f} {crh:.4f} 0.0", "NACA", "0009",
         "SECTION", f"{xh + 0.25 * (crh - cth):.4f} {bh / 2:.4f} {zt:.4f} {cth:.4f} 0.0", "NACA", "0009",
         "SURFACE", "Fin", "8 1.0 10 1.0",
         "SECTION", f"{x_ach - 0.25 * crv:.4f} 0.0 {zt:.4f} {crv:.4f} 0.0", "NACA", "0009",
         "SECTION", f"{x_ach - 0.25 * crv + 0.35 * (crv - ctv):.4f} 0.0 {zt + bv:.4f} {ctv:.4f} 0.0", "NACA", "0009"]
    Path(path).write_text("\n".join(L) + "\n", encoding="ascii")
    return dict(bh=bh, crh=crh, cth=cth, machh=machh, xh=xh, bv=bv, crv=crv, ctv=ctv, x_ach=x_ach, zt=zt)


def avl_np(path, alpha=4.0):
    cmd = f"LOAD {path}\nOPER\nA A {alpha}\nX\nST\n\n\nQUIT\n"
    p = subprocess.run([AVL], input=cmd, capture_output=True, text=True, cwd=str(WORK), timeout=120)
    t = p.stdout
    m = re.search(r"Xnp\s*=\s*([-\d.Ee+]+)", t)
    cla = re.search(r"CLa\s*=\s*([-\d.Ee+]+)", t)
    cma = re.search(r"Cma\s*=\s*([-\d.Ee+]+)", t)
    cnb = re.search(r"Cnb\s*=\s*([-\d.Ee+]+)", t)
    clb = re.search(r"Clb\s*=\s*([-\d.Ee+]+)", t)
    eff = re.search(r"e\s*=\s*([-\d.Ee+]+)", t)
    if not m:
        raise RuntimeError("AVL: no Xnp\n" + t[-1500:])
    f = lambda r: float(r.group(1)) if r else float("nan")
    return dict(xnp=float(m.group(1)), CLa=f(cla), Cma=f(cma), Cnb=f(cnb), Clb=f(clb), e_inv=f(eff))


def size_tails(v, sm_target=0.16, Vh=0.55, Vv=0.040):
    """Tail areas from volume coefficients (Raymer Table 6.4 class ranges, raised for the low-AR wing's downwash),
    tail arm from the fuselage length; AVL gives the neutral point; CG set at the target static margin."""
    lt0 = 0.70 * v["fus_len"] + 0.05 - v["x_ac"] + 0.40    # tail AC near the fuselage end (+0.40 boom/cone)
    lt = max(lt0, LT_C_MIN * v["mac"])                     # larger wings get a longer boom, not a short-coupled tail
    Sh = Vh * v["S"] * v["mac"] / lt
    Sv = Vv * v["S"] * B / lt
    path = WORK / f"variant_{v['key']}.avl".replace("|", "_")
    tg = avl_file(v, Sh, Sv, lt, path)
    st = avl_np(path)
    x_cg = st["xnp"] - sm_target * v["mac"]
    return dict(lt=lt, boom_extra=lt - lt0, Sh=Sh, Sv=Sv, Vh=Vh, Vv=Vv, x_cg_design=x_cg, sm_target=sm_target, **tg, **st)


def masses(v, tails, decl_kg=6.0):
    """Mass and CG items. Airframe from variants/mass_family.py (30 Oct 2026): the DB-01 fit k S^p (14 aircraft,
    x1.31 scatter; includes a 0.50 kg class motor) anchored at S 0.9 m2 and split by the normalised E02 shares; only
    the wing and tail shares scale with wing area. Flap mechanism from S3 (+0.30 Fowler, +0.12 slotted)."""
    sp = MF.split(v["S"])
    af = sum(sp.values())
    flap_dm = FLAP_DM[v["flap_type"]]
    xcg = tails["x_cg_design"]
    items = [
        ("Wing structure", sp["wing"] + flap_dm, x_le_frac(v, 0.42)),
        ("Fuselage", sp["fuselage"], 0.55),
        ("Motor, mount, ESC, prop", sp["propulsion"] + (SHARED["motor_kg"] - 0.50), 0.05),
        ("Landing gear", sp["gear"], 0.45),
        ("Avionics, Rx, servos", sp["avionics"], 0.30),
        ("Tail and boom", sp["tail"] + BOOM_KG_M * tails["boom_extra"], tails["x_ach"]),
        ("Propulsion pack 8S 97.7 Wh", SHARED["pack_kg"], 0.20),
        ("D&R drum, slip ring, latch", reel_kg(v["key"]), xcg + 0.20),
    ]
    empty = sum(m for _, m, _ in items)
    mom = sum(m * x for _, m, x in items)
    # place the payload bay centre so that the M2 loading sits exactly at the design CG
    sp = SPEC.get(v["key"], DEFAULT_SPEC.get(v["key"], {}))
    decl_kg = sp.get("m_hi", decl_kg)
    m_unit = decl_kg + sp.get("container_kg", SHARED["container_kg"])
    x_bay = ((empty + m_unit) * xcg - mom) / m_unit
    load = {}
    load["M1 / empty, 8S pack"] = (empty, mom / empty)
    load["M2, one unit at declared max"] = (empty + m_unit, (mom + m_unit * x_bay) / (empty + m_unit))
    for ball in (3.0, decl_kg):
        # sensor out of the bay, towed: its weight acts at the exit point (x_bay + 0.05), line ~3 deg from vertical
        load[f"M3, {ball:.1f} kg towed"] = (empty + ball, (mom + ball * x_bay) / (empty + ball))
    xnp = tails["xnp"]
    rows = []
    for k, (m, x) in load.items():
        rows.append(dict(loading=k, mass_kg=m, x_cg=x, sm=(xnp - x) / v["mac"]))
    return dict(items=[dict(name=n, kg=m, x=x) for n, m, x in items], empty=empty, x_bay=x_bay, loadings=rows,
                airframe_fit=af)


def reel_kg(key):
    """Savox drum sized for the variant's declared maximum (S8 payload model dr(); 0.256 kg at 6 kg, 0.30 at 8)."""
    sp = SPEC.get(key, DEFAULT_SPEC.get(key))
    if not sp:
        return SHARED["reel_kg"]
    from payload import model as PM
    return PM.dr(sp["m_hi"], "savox_2290")["mass_kg"]


def x_le_frac(v, frac):
    return v["x_le"] + frac * v["mac"]


def place_wing(key, iters=30, S=None, flap=None):
    """Move the wing (and with it the neutral point) until the EMPTY aircraft's CG sits on the design CG
    (static margin 16 % wing + tail, about 12 % with the fuselage), so the payload bay can sit exactly at the CG and
    no loading moves it."""
    v = variant(key, S, flap)
    for _ in range(iters):
        t = size_tails(v)
        m = masses(v, t)
        x_empty = m["loadings"][0]["x_cg"]
        err = t["x_cg_design"] - x_empty
        if abs(err) < 0.0005:
            break
        v["x_le"] -= 0.8 * err
        v["x_ac"] = v["x_le"] + 0.25 * v["mac"]
    return v, t, m


def trim_geometry(S, flap):
    """Real tail arm and CG of the laid-out aircraft, in mean chords, for the CLmax trim (aero_mono trim_table)."""
    v, t, _ = place_wing(f"S{S:.2f}_{flap}", S=S, flap=flap)
    return {"lt_c": t["lt"] / v["mac"], "h": (t["x_cg_design"] - v["x_ac"]) / v["mac"], "lt": t["lt"], "mac": v["mac"],
            "boom_extra_m": t["boom_extra"], "boom_kg": BOOM_KG_M * t["boom_extra"],
            "x_ac": v["x_ac"], "x_cg": t["x_cg_design"], "xnp": t["xnp"]}


def trim_table_all(areas=(0.8, 0.9, 1.0, 1.1, 1.2, 1.3), flaps=("plain", "slotted", "fowler")):
    tab = {f"{S:.2f}|{f}": trim_geometry(S, f) for S in areas for f in flaps}
    (OUT / "trim_geometry.json").write_text(json.dumps(tab, indent=1), encoding="utf-8")
    for k, d in tab.items():
        print(f"{k:14s} lt/c {d['lt_c']:.2f}  h {d['h']:.3f}  xnp {d['xnp']:.3f}")
    return tab


def run():
    res = {}
    for key in ("A", "B"):
        v, t, m = place_wing(key)
        res[key] = dict(geometry=v, tails=t, mass=m)
        print(key, f"S {v['S']} AR {v['AR']:.2f} cr {v['cr']:.3f} ct {v['ct']:.3f} mac {v['mac']:.3f} | "
                   f"Sh {t['Sh']:.3f} Sv {t['Sv']:.3f} lt {t['lt']:.3f} | Xnp {t['xnp']:.3f} CLa {t['CLa']:.3f} "
                   f"Cma {t['Cma']:.3f} Cnb {t['Cnb']:.4f} Clb {t['Clb']:.4f} | empty {m['empty']:.2f} kg x_bay {m['x_bay']:.3f}")
        for r in m["loadings"]:
            print("   ", f"{r['loading']:32s} {r['mass_kg']:6.2f} kg  x_cg {r['x_cg']:.3f}  SM {r['sm']*100:5.1f} %")
    (OUT / "variants_geometry.json").write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
    return res


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "trim":
        trim_table_all()
    else:
        run()
