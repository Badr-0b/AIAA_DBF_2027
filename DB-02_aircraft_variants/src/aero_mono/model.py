"""S3 monoplane aerodynamics: aero(geom) -> dict for the S12 adapter. Import-safe, pure, SI.

Tables (out/aero_mono/tables.json) come from build_xfoil.py / build_tables.py / build_nonplanar.py:
XFoil 6.99 sections at the real Re, AVL 3.52 span efficiency and critical-section CLmax, UIUC LSAT flap data.
Every source is listed in sources/S3.toml; method and grades in memos/03_aero.md.
"""
from __future__ import annotations
import json, math
from functools import lru_cache
from pathlib import Path
import numpy as np

W = Path(__file__).resolve().parents[2]
TABLES = W / "out" / "aero_mono" / "tables.json"
RHO, MU = 1.064, 1.86e-5            # TIMPA design density; dry air at 29 C (repo wing_clmax.toml)
V_LAP = 27.0                        # m/s, design lap speed for Reynolds numbers (M2 straight 29.5, turns ~26)
KAPPA_CLEAN = (1.0, 1.0855)         # NACA TN 663 validation (REPO analysis/out/wing_clmax_calibration.json)
KAPPA_FLAP = (1.0, 1.075)
F_CAL_XFOIL = 1.11                  # UIUC LSAT SD7037 measured cd / XFoil cd at Re 3e5 (computed, memo sec. 4)
F_BUILD = (1.0, 1.15, 1.5)          # finish, hinge gaps, tip, control slots: low / central / high (ESTIMATE)
TRIM_BAND = {"lo": (2.5, 0.10), "mid": (3.0, 0.05), "hi": (3.5, -0.05)}   # (lt/cbar, h - h_ac)
EPS_SLOT = {"none": 0.0, "plain": 0.0, "slotted": 0.0004, "fowler": 0.0008}  # retracted-flap hardware, m2 (ESTIMATE)


@lru_cache(maxsize=1)
def T():
    return json.loads(TABLES.read_text(encoding="utf-8"))


def _interp2(tab, taper, S):
    """bilinear in (taper, S) over tab['t|S'][field]; clamps to the grid."""
    tapers = sorted({v["taper"] for v in tab.values()})
    areas = sorted({v["S"] for v in tab.values()})
    return tapers, areas


def _grid(key, field):
    tab = T()[key]
    tapers = sorted({v["taper"] for v in tab.values()})
    areas = sorted({v["S"] for v in tab.values()})
    return tapers, areas, np.array([[tab[f"{t}|{s}"][field] for s in areas] for t in tapers])


def _bilin(key, field, taper, S):
    tp, ar, Z = _grid(key, field)
    taper = min(max(taper, tp[0]), tp[-1]); S = min(max(S, ar[0]), ar[-1])
    zt = [np.interp(S, ar, Z[i]) for i in range(len(tp))]
    return float(np.interp(taper, tp, zt))


# ---------------------------------------------------------------- section data
def sec_dclmax(flap_type, defl, cf, level="mid", re=3e5):
    """2-D flap section increment of Cl_max on the RETRACTED chord/area, and (dCl at alpha 0, dCm about c/4).
    plain  : AG40d-02r 25 % flap, Williamson 2012 (UIUC LSAT Vol 6), measured at Re 3e5; chord scaling cf^0.7 (ESTIMATE, from TR 534 fig. 5)
    slotted: plain x 1.5 (NACA TR 664 fig. 30: slotted 2-h / plain, 1.5 at 20-40 deg); range 0.59 (ESDU) .. 1.02 (Leng 2022 measured) at 30 deg, cf 0.30
    fowler : TR 534 fig. 5 full-span 3-D ,0.9 factor removed: 0.20c 1.29, 0.30c 1.71, 0.40c 2.09; low 1.30 = 0.9 x TR 664 fig. 30 peak 1.45
    level  : 'lo' | 'mid' | 'hi'. Returns (dclmax, dcl_a0, dcm)."""
    if flap_type == "none" or defl <= 0:
        return 0.0, 0.0, 0.0
    P = T()["plain"]["plain"]["300000"]
    ds = sorted(int(k) for k in P if k.isdigit())
    ds_ = [d for d in ds if d > 0]
    cl_ = lambda f: float(np.interp(defl, [0] + ds_, [0.0] + [P[str(d)][f] for d in ds_]))
    p_max, p_a0, p_cm = cl_("dclmax"), cl_("dcl_a0"), cl_("dcm")
    s = (cf / 0.25) ** 0.7
    if flap_type == "plain":
        f = {"lo": 0.9, "mid": 1.0, "hi": 1.1}[level]
        return p_max * s * f, p_a0 * s, p_cm * s
    if flap_type == "slotted":
        d_eff = min(defl, 30.0)                             # slotted lift saturates ~30 deg at low Re (Leng 2022 fig. 13)
        shape = float(np.interp(d_eff, [0] + ds_, [0.0] + [P[str(d)]["dclmax"] for d in ds_])) / P["30"]["dclmax"]
        centre = {"lo": 0.59, "mid": 0.80, "hi": 1.02}[level]          # at cf 0.30, 30 deg
        dmax = centre * shape * (cf / 0.30) ** 0.7
        da0 = p_a0 * 1.25 if defl <= 30 else cl_("dcl_a0") * 1.25
        da0 = float(np.interp(d_eff, [0] + ds_, [0.0] + [P[str(d)]["dcl_a0"] for d in ds_])) * s * 1.25
        return dmax, da0, -0.173 * da0                         # TR 664 p. 29: same dCm per dCl as plain
    if flap_type == "fowler":
        c = np.interp(cf, [0.20, 0.30, 0.40], [1.29, 1.71, 2.09])
        lo = np.interp(cf, [0.20, 0.30, 0.40], [1.29 * 0.9, 1.30, 1.30 * 2.09 / 1.71])
        dmax = {"lo": lo, "mid": (lo + c) / 2, "hi": c}[level]
        shape = float(np.interp(defl, [0, 10, 20, 30, 40], [0.42, 0.60, 0.80, 1.0, 0.85]))   # TR 664 fig. 30 Fowler curve / its 30-deg peak
        da0 = 0.87 * dmax * shape
        return dmax * shape, da0, -0.42 * da0                  # TR 534 tables II-III: dCm/dCl(alpha0) = -0.42
    raise ValueError(flap_type)


def flapped_area_frac(taper, eta_f):
    return (eta_f - (1 - taper) * eta_f ** 2 / 2) / (1 - (1 - taper) / 2)


def flap_cm_fraction(taper, eta_f):
    """share of the wing's c^2 moment area that is flapped (as REPO analysis/wing_clmax.py)."""
    n = 200
    num = sum((1 - (1 - taper) * (i + .5) / n * eta_f) ** 2 for i in range(n)) * eta_f / n
    cbar = 2 / 3 * (1 + taper + taper ** 2) / (1 + taper)
    return 2 * num / (cbar * (1 + taper))


def trim(cl_w, cm_ac, band, table=None):
    lt, h = (table or TRIM_BAND)[band]
    return cl_w + (cm_ac + cl_w * h) / lt


TRIM_DH = 0.03                      # CG tolerance about the design point, fraction of cbar (TC-08 gate: 3 %)


def trim_table(g):
    """Trim bands. Default TRIM_BAND (generic lt 2.5-3.5 cbar). With geom["trim"] = {"lt_c", "h"} from a laid-out
    aircraft (geometry_variants.trim_geometry, 30 Oct 2026): its real tail arm, CG -/+ TRIM_DH for lo/hi."""
    tr = g.get("trim")
    if not tr:
        return TRIM_BAND
    L, H = tr["lt_c"], tr["h"]
    return {"lo": (L, H - TRIM_DH), "mid": (L, H), "hi": (L, H + TRIM_DH)}


# ---------------------------------------------------------------- section drag
@lru_cache(maxsize=256)
def _prof_fit(airfoil, re_b, ncrit):
    rows = [r for r in T()["xfoil"] if r["airfoil"] == airfoil and r["ncrit"] == ncrit]
    if not rows:
        rows = [r for r in T()["xfoil"] if r["airfoil"] == "sd7037" and r["ncrit"] == ncrit]
    fits = []
    for r in rows:
        a = np.array(r["rows"]); cl, cd = a[:, 1], a[:, 2]
        s = (cl >= 0.3) & (cl <= 1.1)
        X = np.vstack([np.ones(s.sum()), cl[s] ** 2]).T
        c = np.linalg.lstsq(X, cd[s], rcond=None)[0]
        fits.append((r["re"], c[0], c[1]))
    fits.sort()
    res = np.array([f[0] for f in fits]); lre = np.log(res)
    lr = math.log(min(max(re_b, res[0]), res[-1]))
    # several entries at the same Re (3e5 table only exists for SD7037): average duplicates
    u = sorted(set(res)); aa = [np.mean([f[1] for f in fits if f[0] == x]) for x in u]; kk = [np.mean([f[2] for f in fits if f[0] == x]) for x in u]
    return float(np.interp(lr, np.log(u), aa)), float(np.interp(lr, np.log(u), kk))


def wing_profile(airfoil, re, level="mid"):
    """(a, kp): wing profile cd = a + kp CL^2 on the real Re, XFoil x UIUC calibration x build factor."""
    af = airfoil.lower()
    a9, k9 = _prof_fit(af, round(re, -4), 9.0)
    a5, k5 = _prof_fit(af, round(re, -4), 5.0)
    if level == "lo":
        a, k, fb = a9, k9, F_BUILD[0]
    elif level == "hi":
        a, k, fb = a5, k5, F_BUILD[2]
    else:
        a, k, fb = 0.5 * (a9 + a5), 0.5 * (k9 + k5), F_BUILD[1]
    return a * F_CAL_XFOIL * fb, k * F_CAL_XFOIL * fb


# ---------------------------------------------------------------- friction build-up
def _cf(re, turb_frac):
    lam = 1.328 / math.sqrt(re)
    tur = 0.455 / math.log10(re) ** 2.58
    return (1 - turb_frac) * lam + turb_frac * tur


def hoerner_body(l, w, h, V=V_LAP, q_build=1.15, f_min=3.0):
    """Drag area (m2) of a streamlined body: Cf (turbulent, prop wash) x S_wet x Hoerner FF x build factor.
    FF = 1 + 1.5 (d/l)^1.5 + 7 (d/l)^3 (Hoerner, Fluid-Dynamic Drag 1965, ch. 6); fineness floored at 3."""
    d = math.sqrt(w * h)
    per = 4 * 0.93 * 0.5 * (w + h)                          # superellipse n = 3 perimeter ~ 0.93 x box perimeter
    swet = per * l * 0.85
    f = max(l / d, f_min)
    ff = 1 + 1.5 * f ** -1.5 + 7 * f ** -3
    cf = _cf(V * l * RHO / MU, 1.0)
    return cf * swet * ff * q_build


def hoerner_tail(area, chord, tc=0.09, V=V_LAP, q_build=1.1, turb=0.5):
    cf = _cf(V * chord * RHO / MU, turb)
    ff = 1 + 2 * tc + 100 * tc ** 4
    return cf * 2.04 * area * ff * q_build


# ---------------------------------------------------------------- geometry normalisation
DEFAULT = dict(S=0.9, span=1.82, taper=0.7, airfoil="SD7037",
               flap=dict(type="plain", span_frac=0.6, chord_frac=0.25, defl_land_deg=30.0, defl_turn_deg=0.0),
               winglet=dict(h_frac=0.0, kind="winglet"), fuselage=dict(l=1.05, w=0.22, h=0.22), nacelle=None,
               gear=dict(type="tricycle", faired=True, retractable=False), config="monoplane", gap_over_b=0.15,
               tail=dict(Sh=None, Sv=None, chord_h=None, chord_v=None, arm=1.0), V=V_LAP, ncrit_level="mid")


def _merge(a, b):
    o = dict(a)
    for k, v in (b or {}).items():
        o[k] = _merge(a[k], v) if isinstance(v, dict) and isinstance(a.get(k), dict) else v
    return o


def _from_s9(g):
    """Reduce an S9 geometry dict (schema s9-geom/1) to the simple form."""
    ref = g["reference"]; S, b = ref["S_ref"], ref["b_ref"]
    simple = dict(S=S, span=b)
    surfs = {s["name"]: s for s in g["surfaces"]}
    wing = next(s for s in g["surfaces"] if s["role"] == "wing")
    sec = wing["sections"]
    simple["taper"] = sec[-1]["chord"] / sec[0]["chord"]
    simple["airfoil"] = sec[0].get("airfoil", "SD7037")
    fl = next((c for c in wing.get("controls", []) if c["function"] == "flap"), None)
    half = b / 2
    if fl:
        rng = fl.get("deflection_range_deg", [0, 40])
        simple["flap"] = dict(type=fl["type"], span_frac=(fl["y_end"] - fl["y_start"]) / half, chord_frac=fl["chord_fraction"],
                              defl_land_deg=min(30.0, rng[1]), defl_turn_deg=0.0)
    else:
        simple["flap"] = dict(type="none")
    td = wing.get("tip_device", {"type": "none"})
    if td["type"] != "none":
        simple["winglet"] = dict(h_frac=td["height"] / half, kind=td["type"])
    fus = next((x for x in g.get("bodies", []) if x["role"] == "fuselage"), None)
    if fus:
        st = fus["stations"]
        simple["fuselage"] = dict(l=max(s["x"] for s in st) - min(s["x"] for s in st), w=max(s["width"] for s in st), h=max(s["height"] for s in st))
    gr = g.get("gear")
    if gr:
        simple["gear"] = dict(type=gr.get("type", "tricycle"), faired=gr.get("faired", True), retractable=gr.get("retractable", False))
    t = {}
    for s in g["surfaces"]:
        if s["role"] in ("htail", "vtail", "vee_tail"):
            ys = [x["y"] for x in s["sections"]]; cs = [x["chord"] for x in s["sections"]]
            area = np.trapezoid(cs, ys) * (2 if s.get("symmetric") else 1)
            key = "h" if s["role"] == "htail" else "v"
            t["S" + key] = t.get("S" + key, 0) + area; t["chord_" + key] = float(np.mean(cs))
    if t:
        simple["tail"] = {k: t.get(k) for k in ("Sh", "Sv", "chord_h", "chord_v")}
    return simple


def _norm(geom):
    geom = dict(geom or {})
    if "surfaces" in geom:
        geom = _from_s9(geom)
    g = _merge(DEFAULT, geom)
    S, b = g["S"], g["span"]
    cr = 2 * S / (b * (1 + g["taper"]))
    cbar = 2 / 3 * cr * (1 + g["taper"] + g["taper"] ** 2) / (1 + g["taper"])
    g["cbar"] = cbar
    t = g["tail"]
    arm = t.get("arm") or 1.0
    if not t.get("Sh"):
        t["Sh"] = 0.5 * S * cbar / arm            # Vh 0.5 as REF-D01 (S9 reference)
    if not t.get("Sv"):
        t["Sv"] = 0.04 * b * S / arm              # Vv 0.04
    t["chord_h"] = t.get("chord_h") or math.sqrt(t["Sh"] / 4.0)
    t["chord_v"] = t.get("chord_v") or math.sqrt(t["Sv"] / 1.8)
    return g


# ---------------------------------------------------------------- the model
def _winglet_de(wl):
    h = wl.get("h_frac", 0.0)
    if h <= 0:
        return 0.0, 1.0
    rows = [r for r in T()["np"]["winglets"] if r["S"] == 0.9 and r["kind"] == wl.get("kind", "winglet") and r["h_frac"] > 0]
    hs = [r["h_frac"] for r in rows]; de = [r["de"] for r in rows]; bm = [r["bend_ratio"] for r in rows]
    return float(np.interp(h, [0] + hs, [0] + de)), float(np.interp(h, [0] + hs, [1] + bm))


def _multi_ratio(gob):
    rows = [r for r in T()["np"]["multi"] if r["config"] == "biplane"]
    return float(np.interp(gob, [r["gap_over_b"] for r in rows], [r["k_ratio"] for r in rows]))


def _eval(g, level):
    """One consistent evaluation at level lo | mid | hi (all ranges move together: lo = pessimistic for performance)."""
    S, b, tp = g["S"], g["span"], g["taper"]
    ar = b * b / S
    config = g["config"]
    biplane = config in ("biplane", "box")
    re = RHO * g["V"] * g["cbar"] / MU * (0.5 if biplane else 1.0)
    # ---- wing profile
    lv = {"lo": "hi", "mid": "mid", "hi": "lo"}[level]       # pessimistic performance = high drag
    a_w, kp = wing_profile(g["airfoil"], re, lv)
    fl = g["flap"]
    a_w += EPS_SLOT.get(fl.get("type", "none"), 0.0) / S
    # ---- span efficiency
    e_avl = _bilin("e", "e_from_CDi", tp, S)
    dfus = math.sqrt(g["fuselage"]["w"] * g["fuselage"]["h"])
    f_fus = 1 - 2 * (dfus / b) ** 2                          # Kroo (2000, ARFM) / Raymer fuselage factor
    de_wl, bend = _winglet_de(g["winglet"])
    f_int = {"lo": 1.05, "mid": 1.0, "hi": 1.0}[level]       # tail download / wing-tail / slipstream interference allowance (ESTIMATE)
    de_wl *= {"lo": 0.5, "mid": 1.0, "hi": 3.0}[level]       # AVL flat-wake value; x3 = literature-theory bracket (Whitcomb/Kroo), UNRECONCILED
    k_ind = 1.0 / (math.pi * ar * (e_avl + de_wl) * f_fus) * f_int
    if biplane:
        k_ind *= _multi_ratio(g["gap_over_b"]) * {"lo": 1.10, "mid": 1.0, "hi": 0.95}[level]
    k = k_ind + kp
    e = 1.0 / (math.pi * ar * k)
    # ---- parasite drag areas (m2)
    wl = g["winglet"]; f_other = 0.0007                      # hatch gaps, servo horns, antennas, wing-body junction (ESTIMATE)
    if wl.get("h_frac", 0) > 0:
        h = wl["h_frac"] * b / 2
        cr = 2 * S / (b * (1 + tp)); ct = tp * cr
        area_w = h * ct * 0.85 * (1.5 if wl.get("kind") == "tip_plate" else 1.0)
        f_other += 2 * hoerner_tail(area_w, ct * 0.85, 0.09, g["V"], 1.25, 0.5)   # both fins, junction allowance 1.25
    if biplane:
        n_strut = 4; gap = g["gap_over_b"] * b
        f_other += n_strut * 0.06 * 0.008 * gap * 1.5        # streamlined strut Cd 0.06 on frontal area x interference 1.5 (ESTIMATE)
    f_body = hoerner_body(g["fuselage"]["l"], g["fuselage"]["w"], g["fuselage"]["h"], g["V"], {"lo": 1.3, "mid": 1.15, "hi": 1.0}[level])
    if g.get("nacelle"):
        n = g["nacelle"]; f_body += hoerner_body(n["l"], n["w"], n["h"], g["V"], 1.15)
    t = g["tail"]
    f_tail = hoerner_tail(t["Sh"], t["chord_h"], 0.09, g["V"], {"lo": 1.25, "mid": 1.1, "hi": 1.0}[level]) \
        + hoerner_tail(t["Sv"], t["chord_v"], 0.09, g["V"], {"lo": 1.25, "mid": 1.1, "hi": 1.0}[level])
    gr = g["gear"]
    if gr.get("type") == "none" or gr.get("retractable"):
        f_gear = 0.0003 if gr.get("retractable") else 0.0
    else:
        f_gear = {"lo": 0.0019, "mid": 0.0012, "hi": 0.00099}[level] * (1.0 if gr.get("faired", True) else 1 / 0.77)   # GT 2026 9.9 cm2 .. Joanneum 19.4 cm2; TR 485 fairing -23 %
    # ---- CLmax
    kc = {"lo": KAPPA_CLEAN[0], "mid": 0.5 * sum(KAPPA_CLEAN), "hi": KAPPA_CLEAN[1]}[level]
    kf = {"lo": KAPPA_FLAP[0], "mid": 0.5 * sum(KAPPA_FLAP), "hi": KAPPA_FLAP[1]}[level]
    cl_strict = _bilin("clean", "cl_strict", tp, S)
    cm_ac = _bilin("clean", "cm_ac", tp, S)
    cl_clean = kc * cl_strict
    ftype = fl.get("type", "none")
    cf = fl.get("chord_frac", 0.25); eta = fl.get("span_frac", 0.6)
    sf = flapped_area_frac(tp, min(eta, 1.0))
    def clmax_flap(defl):
        dmax, da0, dcm = sec_dclmax(ftype, defl, cf, level)
        inc = kf * 0.9 * dmax * sf
        cm = cm_ac + dcm * flap_cm_fraction(tp, min(eta, 1.0))
        return cl_clean + inc, cm, dmax, da0
    cl_land_u, cm_land, dmax_l, _ = clmax_flap(fl.get("defl_land_deg", 30.0)) if ftype != "none" else (cl_clean, cm_ac, 0.0, 0.0)
    cl_turn_u, cm_turn, _, da0_turn = clmax_flap(fl.get("defl_turn_deg", 0.0)) if fl.get("defl_turn_deg", 0) > 0 else (cl_clean, cm_ac, 0.0, 0.0)
    band = {"lo": "lo", "mid": "mid", "hi": "hi"}[level]
    tt = trim_table(g)
    cl_clean_t = trim(cl_clean, cm_ac, band, tt)
    cl_land_t = trim(cl_land_u, cm_land, band, tt)
    cl_turn_t = trim(cl_turn_u, cm_turn, band, tt)
    cm0 = cm_ac
    if biplane:
        kb = {"lo": 0.85, "mid": 0.92, "hi": 1.0}[level]       # biplane interference CLmax/area (ESTIMATE)
        cl_clean_t *= kb; cl_land_t *= kb; cl_turn_t *= kb
    # ---- turn-flap penalty on span efficiency (flap as equivalent twist, AVL; share of induced energy in turns 0.85)
    dt = fl.get("defl_turn_deg", 0.0)
    e_turn = None
    if dt > 0:
        ft = T()["np"]["flap_twist"]
        ratio = np.interp(da0_turn if da0_turn else 0.0, [0.0, 0.58, 0.917, 1.2], [1.0, ft[1]["e"] / ft[0]["e"], ft[2]["e"] / ft[0]["e"], ft[3]["e"] / ft[0]["e"]])
        e_turn = e * ratio
    # ---- mass delta vs the DB-01 plain flap + aileron airframe fit (ESTIMATES, see memo 7)
    dm = {"none": -0.05, "plain": 0.0, "slotted": 0.12, "fowler": 0.30}[ftype]
    if wl.get("h_frac", 0) > 0:
        dm += 0.10 * (wl["h_frac"] / 0.10) * (1.4 if wl.get("kind") == "tip_plate" else 1.0)
    if biplane:
        dm += 0.60
    if gr.get("retractable"):
        dm += 0.18
    return dict(a_w=a_w, e=e, k=k, f_body=f_body, f_tail=f_tail, f_gear=f_gear, f_other=f_other, cl_clean=cl_clean_t,
                cl_land=cl_land_t, cl_turn=cl_turn_t, cl_land_u=cl_land_u, cl_clean_u=cl_clean, dm=dm, cm0=cm0, cm_land=cm_land,
                e_turn=e_turn, e_inv=e_avl + de_wl, dmax=dmax_l, re=re, ar=ar, sf=sf, bend=bend, k_ind=k_ind, kp=kp, f_fus=f_fus, e_avl=e_avl)


def _plain(o):
    if isinstance(o, dict):
        return {k: _plain(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_plain(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        return float(o)
    return o


def aero(geom: dict) -> dict:
    g = _norm(geom)
    S = g["S"]
    mid, lo, hi = _eval(g, "mid"), _eval(g, "lo"), _eval(g, "hi")
    wing = mid["a_w"]
    other = mid["f_other"]
    parts = {"wing": wing, "body": mid["f_body"] / S, "tail": mid["f_tail"] / S, "gear": mid["f_gear"] / S, "other": other / S}
    f_nonwing = lambda d: d["f_body"] + d["f_tail"] + d["f_gear"] + d["f_other"]
    cd0 = sum(parts.values())
    ct = mid["cl_turn"] if g["flap"].get("defl_turn_deg", 0) > 0 else mid["cl_clean"]
    ct_lo = lo["cl_turn"] if g["flap"].get("defl_turn_deg", 0) > 0 else lo["cl_clean"]
    ct_hi = hi["cl_turn"] if g["flap"].get("defl_turn_deg", 0) > 0 else hi["cl_clean"]
    notes = [
        f"Re(cbar {g['cbar']:.3f} m, {g['V']:.0f} m/s) = {mid['re']:.2e}; wing cd = {mid['a_w']:.4f} + {mid['kp']:.4f} CL^2 (XFoil x1.11 UIUC calibration x1.15 build, Ncrit 9/5 mean)",
        f"e = 1/(pi AR (k_ind + kp)): AVL e {mid['e_avl']:.3f}, Kroo fuselage factor {mid['f_fus']:.3f}, k_ind {mid['k_ind']:.4f}, kp {mid['kp']:.4f}",
        ("clmax_* are TRIMMED (tail download, lt 3.0 cbar, CG 0.05 cbar aft of a.c.); untrimmed in clmax_*_untrimmed"
         if not g.get("trim") else
         f"clmax_* are TRIMMED at the laid-out geometry (lt {g['trim']['lt_c']:.2f} cbar, CG {g['trim']['h']:.3f} cbar aft of a.c., "
         f"+/-{TRIM_DH} cbar for lo/hi); untrimmed in clmax_*_untrimmed"),
        "no fuselage lift loss or propeller slipstream credit in CLmax; tow line + sensor drag belong to M3 (S8)"]
    if g["config"] in ("biplane", "box"):
        notes.append("biplane factors from AVL k ratio; CLmax/strut/mass terms are ESTIMATES")
    out = dict(
        cd0_parts=parts, cd0=cd0, e=mid["e"], k=mid["k"], clmax_clean=mid["cl_clean"], clmax_landing=mid["cl_land"],
        clmax_turn_avail=ct, cm0=mid["cm0"], cm_landing=mid["cm_land"], mass_delta_kg=mid["dm"], notes=notes,
        clmax_clean_untrimmed=mid["cl_clean_u"], clmax_landing_untrimmed=mid["cl_land_u"],
        span_m=g["span"], root_bending_ratio=mid["bend"],
        e_parts={"e_inv": mid["e_inv"], "k_fuse": mid["f_fus"], "K_visc": mid["kp"], "e_osw": mid["e"], "1/e_osw": 1 / mid["e"]}, e_turn_flap=mid["e_turn"],
        ranges={"f_body_m2": [f_nonwing(hi), f_nonwing(lo)],
                "e": [lo["e"], hi["e"]],
                "clmax_factor": [min(lo["cl_land"] / mid["cl_land"], 1.0), max(hi["cl_land"] / mid["cl_land"], 1.0)],
                "clmax_landing": [lo["cl_land"], hi["cl_land"]], "clmax_clean": [lo["cl_clean"], hi["cl_clean"]],
                "clmax_turn_avail": [ct_lo, ct_hi], "cd0": [lo["a_w"] + f_nonwing(lo) / S, hi["a_w"] + f_nonwing(hi) / S]})
    return _plain(out)


def polar(geom, CL, V=V_LAP):
    g = _norm(dict(geom, V=V)) if "surfaces" not in geom else _norm(geom)
    d = _eval(g, "mid")
    S = g["S"]
    return d["a_w"] + (d["f_body"] + d["f_tail"] + d["f_gear"] + d["f_other"]) / S + d["k"] * CL ** 2


# reference geometries (brief section 8; REF-RQ4 as a simple dict for the body cross-check)
REF_D01 = dict(S=0.9)
REF_D01B = dict(S=1.0)
