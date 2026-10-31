"""Builders: turn a few design numbers into schema sections, and the reference designs.

    from geometry import build
    g = build.ref_d01()                                  # REF-D01 as a dict
    w, d = build.trapezoid_wing("wing", S=0.9, b=1.82, taper=0.7, airfoil="SD7037",
                                x_le_root=0.33, z=0.10)  # surface dict + derived numbers
    tails = build.tail("conventional", wing_ref=d, Vh=0.5, Vv=0.04, l_h=1.0, l_v=1.0, ...)

Every builder returns plain dicts that pass schema.validate(); the builders do
no I/O. Areas are true planform areas in the surface plane; the tail-volume
arms run from the wing MAC quarter chord to the tail MAC quarter chord.
"""
from __future__ import annotations

import math

from .schema import SCHEMA_ID


# ---------------------------------------------------------------------------
# Trapezoidal panels
# ---------------------------------------------------------------------------
def trap(S, b_semi_total, taper):
    """Root chord, tip chord, MAC and spanwise MAC station for a trapezoid.

    S is the area of the whole surface (both halves if symmetric) and
    b_semi_total the span of the whole surface (2 x semispan if symmetric)."""
    cr = 2 * S / (b_semi_total * (1 + taper))
    ct = taper * cr
    mac = 2 / 3 * cr * (1 + taper + taper ** 2) / (1 + taper)
    y_mac = b_semi_total / 6 * (1 + 2 * taper) / (1 + taper)
    return cr, ct, mac, y_mac


def trapezoid_wing(name, S, b, taper, airfoil, x_le_root, z, sweep_c4_deg=0.0, dihedral_deg=0.0,
                   incidence_deg=0.0, twist_tip_deg=0.0, role="wing", component=None, symmetric=True,
                   y_root=0.0, y_origin=0.0, controls=(), n_break=None, tip_device=None, avl=None):
    """Straight-tapered surface. Returns (surface dict, derived dict).

    symmetric=True: S and b are for the pair (b = tip to tip, the panel runs
    from local y 0 to b/2). symmetric=False: S and b are for one panel (a fin;
    b = its height along the span axis)."""
    half = b / 2 if symmetric else b
    cr, ct, mac, y_mac = trap(S, b if symmetric else 2 * b, taper)
    if not symmetric:                      # one panel of area S: trap() was given the doubled pair
        cr, ct, mac, y_mac = trap(2 * S, 2 * b, taper)
    t4 = math.tan(math.radians(sweep_c4_deg))
    ys = [0.0, half] if not n_break else [half * i / n_break for i in range(n_break + 1)]
    secs = []
    for y in ys:
        c = cr + (ct - cr) * y / half
        x_le = 0.25 * cr + t4 * y - 0.25 * c
        secs.append({"y": round(y, 6), "x_le": round(x_le, 6), "z_le": 0.0, "chord": round(c, 6),
                     "twist_deg": round(twist_tip_deg * y / half, 4), "airfoil": airfoil})
    surf = {"name": name, "role": role, "component": component or name, "symmetric": symmetric,
            "origin": [round(x_le_root, 6), round(y_origin, 6), round(z, 6)], "dihedral_deg": dihedral_deg,
            "incidence_deg": incidence_deg, "sections": secs, "controls": list(controls)}
    if tip_device:
        surf["tip_device"] = tip_device
    if avl:
        surf["avl"] = avl
    x_mac_le = x_le_root + 0.25 * cr + t4 * y_mac - 0.25 * mac
    derived = {"S": S, "b": b, "cr": cr, "ct": ct, "mac": mac, "y_mac": y_mac, "x_mac_le": x_mac_le,
               "x_mac_c4": x_mac_le + 0.25 * mac, "AR": (b * b / S) if symmetric else b * b / S,
               "half": half, "taper": taper}
    return surf, derived


def control(name, function, ctype, y_start, y_end, cf, gain=1.0, sign_dup=1, rng=(-25.0, 25.0), **kw):
    c = {"name": name, "function": function, "type": ctype, "y_start": round(y_start, 6), "y_end": round(y_end, 6),
         "chord_fraction": cf, "gain": gain, "sign_dup": sign_dup, "deflection_range_deg": list(rng)}
    c.update(kw)
    return c


# ---------------------------------------------------------------------------
# Tails
# ---------------------------------------------------------------------------
def tail(kind, wing_ref, Vh, Vv, l_h, l_v, z_h, z_v, AR_h=4.0, taper_h=0.7, AR_v=1.5, taper_v=0.6,
         sweep_v_c4=15.0, airfoil="NACA0009", elevator_cf=0.35, rudder_cf=0.35, boom_y=0.0, vee_dihedral=40.0):
    """Tail surfaces sized by tail volume.

    kind: conventional | T | V | inverted_V | H (twin fins at +-boom_y, one
    stabiliser) | twin_boom (as H, fins on the booms). Vh = Sh l_h / (S c),
    Vv = Sv l_v / (S b); l measured MAC c/4 to MAC c/4. For V tails the
    panels give Sh = S_V cos^2(G) and Sv = S_V sin^2(G) (the effective-area
    rule; the projected areas are S_V cos G and S_V sin G)."""
    S, c, b = wing_ref["S"], wing_ref["mac"], wing_ref["b"]
    x_ac = wing_ref["x_mac_c4"]
    Sh = Vh * S * c / l_h
    Sv = Vv * S * b / l_v
    out, info = [], {"Sh": Sh, "Sv": Sv, "l_h": l_h, "l_v": l_v, "Vh": Vh, "Vv": Vv, "kind": kind}
    elev = lambda half: control("elevator", "elevator", "plain", 0.0, half, elevator_cf, 1.0, 1, (-25, 25))  # noqa: E731
    if kind in ("V", "inverted_V"):
        G = math.radians(vee_dihedral)
        Sv_req = Sh / math.cos(G) ** 2
        Sv_req2 = Sv / math.sin(G) ** 2
        SV = max(Sv_req, Sv_req2)
        bV = math.sqrt(AR_h * SV)
        cr, ct, mac, y_mac = trap(SV, bV, taper_h)
        half = bV / 2
        x_le = x_ac + l_h - 0.25 * cr
        sgn = 1 if kind == "V" else -1
        surf, d = trapezoid_wing("vtail", SV, bV, taper_h, airfoil, x_le, z_h, dihedral_deg=sgn * vee_dihedral,
                                 role="vee_tail", component="vtail", controls=[
                                     control("elevator", "ruddervator_pitch", "plain", 0.0, half, elevator_cf, 1.0, 1),
                                     control("rudder", "ruddervator_yaw", "plain", 0.0, half, elevator_cf, 1.0, -1)])
        out.append(surf)
        info.update(S_vee=SV, b_vee=bV, Sh_eff=SV * math.cos(G) ** 2, Sv_eff=SV * math.sin(G) ** 2,
                    Sh_proj=SV * math.cos(G), Sv_proj=SV * math.sin(G), dihedral=sgn * vee_dihedral)
        return out, info
    # horizontal stabiliser
    bh = math.sqrt(AR_h * Sh)
    crh = trap(Sh, bh, taper_h)[0]
    nfin = 2 if kind in ("H", "twin_boom") else 1
    Sv_each = Sv / nfin
    hv = math.sqrt(AR_v * Sv_each)
    _, dv0 = trapezoid_wing("tmp", Sv_each, hv, taper_v, airfoil, 0.0, 0.0, sweep_c4_deg=sweep_v_c4, symmetric=False)
    x_le_v = x_ac + l_v - (dv0["x_mac_c4"])
    if kind == "T":
        z_h = z_v + hv
    h, dh = trapezoid_wing("htail", Sh, bh, taper_h, airfoil, x_ac + l_h - 0.25 * crh, z_h, role="htail",
                           component="htail", controls=[elev(bh / 2)])
    v, dv = trapezoid_wing("vtail", Sv_each, hv, taper_v, airfoil, x_le_v, z_v, sweep_c4_deg=sweep_v_c4,
                           dihedral_deg=90.0, role="vtail", component="vtail", symmetric=nfin == 2, y_origin=boom_y,
                           controls=[control("rudder", "rudder", "plain", 0.0, hv, rudder_cf, 1.0, 1)])
    out += [h, v]
    info.update(bh=bh, crh=crh, ARh=AR_h, hv=hv, fins=nfin, crv=dv["cr"], ctv=dv["ct"])
    return out, info


# ---------------------------------------------------------------------------
# Bodies
# ---------------------------------------------------------------------------
def station(x, w, h, z=0.0, n=2.0):
    return {"x": round(x, 6), "width": round(w, 6), "height": round(h, 6), "z": round(z, 6), "exponent": n}


def boom(name, x0, x1, d0, d1, y=0.0, z=0.0, symmetric=False, component=None, n_tip=0.004):
    """Round tube with small closed ends (a carbon tail boom)."""
    L = x1 - x0
    st = [station(0.0, n_tip, n_tip, 0.0), station(0.01 * L, d0, d0, 0.0), station(0.99 * L, d1, d1, 0.0),
          station(L, n_tip, n_tip, 0.0)]
    return {"name": name, "role": "boom", "component": component or "fuselage", "symmetric": symmetric,
            "origin": [x0, y, z], "stations": st, "avl": "none"}


def nacelle(name, x0, length, d, y=0.0, z=0.0, symmetric=False, component="nacelle", n=2.0):
    st = [station(0.0, 0.25 * d, 0.25 * d), station(0.08 * length, 0.8 * d, 0.8 * d, 0, n),
          station(0.25 * length, d, d, 0, n), station(0.75 * length, d, d, 0, n),
          station(length, 0.35 * d, 0.35 * d, 0, n)]
    return {"name": name, "role": "nacelle", "component": component, "symmetric": symmetric,
            "origin": [x0, y, z], "stations": st, "avl": "none"}


# ---------------------------------------------------------------------------
# Reference designs (brief section 8)
# ---------------------------------------------------------------------------
SRC = {
    "brief": "DB-02 brief 00_BRIEF.md section 8 reference designs (27 Oct 2026)",
    "sizing": "analysis/inputs/sizing.toml (span 1.82 m; read 27 Oct 2026)",
    "clmax": "analysis/wing_clmax.py / clmax_impact_report.txt: flap from the root over 60 % semispan (read 27 Oct 2026)",
    "mass": "analysis/out/mass_breakdown_report.txt bottom-up budget at S 0.9 m2, medians (16 Oct 2026; read 27 Oct 2026)",
    "prop": "analysis/out/prop_trade_report.txt rank 1: AT7215 KV270 + APC 20x15E + TP3300-8SE55 (read 27 Oct 2026)",
    "cushion": "analysis/out/cushion_report.txt / brief section 5: 100 g container 202 x 202 x 392 mm (read 27 Oct 2026)",
    "cfd": "cfd/cases/rq4_mock/case.toml + geometry_report.txt (24 Oct 2026; read 27 Oct 2026)",
}


def ref_d01(S=0.9, unit_kg=4.0, ref_id="REF-D01"):
    """REF-D01 (0.9 m2) and, with S=1.0 / unit_kg=5.0, REF-D01b.

    Wing, span, taper, airfoil and flap: brief. Everything else: ESTIMATE for a
    common reference (tail by tail volume Vh 0.5 / Vv 0.04 at a 1.0 m arm;
    fuselage pod 1.05 m x 0.22 x 0.22 m; tricycle gear for a 20 in prop)."""
    b, taper = 1.82, 0.7
    x_le_root, z_w = 0.33, 0.10
    semi = b / 2
    ctl = [control("flap", "flap", "plain", 0.0, 0.6 * semi, 0.25, 1.0, 1, (0, 40)),
           control("aileron", "aileron", "plain", 0.6 * semi, 0.95 * semi, 0.25, 1.0, -1, (-20, 20))]
    wing, wd = trapezoid_wing("wing", S, b, taper, "SD7037", x_le_root, z_w, controls=ctl,
                              avl={"nchord": 10, "nspan": 28, "cspace": 1.0, "sspace": 1.0, "component": 1})
    z_boom = 0.02
    tails, ti = tail("conventional", wd, 0.5, 0.04, 1.0, 1.0, z_h=z_boom, z_v=z_boom + 0.010)
    x_end = max(t["origin"][0] + max(s["x_le"] + s["chord"] for s in t["sections"]) for t in tails) + 0.01
    fus = {"name": "fuselage", "role": "fuselage", "component": "fuselage", "symmetric": False, "origin": [0.0, 0.0, 0.0],
           "avl": "body", "stations": [
               station(0.000, 0.000, 0.000, 0.000, 2.0),
               station(0.012, 0.040, 0.040, 0.000, 2.0),
               station(0.040, 0.075, 0.075, 0.000, 2.0),     # spinner / motor (AT7215 can ~0.08 m)
               station(0.080, 0.150, 0.150, 0.000, 2.5),
               station(0.130, 0.220, 0.220, 0.000, 3.0),
               station(0.920, 0.220, 0.220, 0.000, 3.0),
               station(0.990, 0.120, 0.120, 0.010, 2.5),
               station(1.050, 0.045, 0.045, z_boom, 2.0)]}
    bm = boom("tail_boom", 1.00, x_end, 0.032, 0.026, z=z_boom)
    rho_unit = unit_kg
    m_w = round(1.938 * S, 3)          # median wing kg/m2 (mass report)
    m_e = round(0.446 * S, 3)          # median empennage kg per m2 of wing
    x_w = wd["x_mac_le"] + 0.40 * wd["mac"]
    x_tail = ti and (wd["x_mac_c4"] + 1.0 + 0.05)
    slot_l = 0.392
    g = {
        "schema": SCHEMA_ID,
        "meta": {"id": ref_id, "variant": "reference", "revision": "A", "date": "2026-10-27", "author": "S9 geometry toolkit",
                 "status": "reference",
                 "notes": [
                     f"Brief section 8: {S} m2 straight wing, span 1.82 m, taper 0.7, SD7037, plain flap 25 % chord from the root to 60 % semispan; "
                     f"high wing, conventional tail, fixed tricycle, single 8S tractor; unit {unit_kg} kg.",
                     "Everything not in the brief is an ESTIMATE chosen only to make a complete, consistent reference: tail volumes "
                     "Vh 0.5 / Vv 0.04 at a 1.0 m arm (S5 refines), ailerons 60-95 % semispan, wing incidence 0, fuselage pod 1.05 m long "
                     "with a 0.22 x 0.22 m superellipse section and a 32 mm carbon tail boom, gear placed for 0.05 m prop clearance.",
                     "Packaging does not close: two 0.392 m units (cushion report 100 g case) fill the 0.79 m constant section; S8 owns the bay.",
                     "Point masses: medians of the 16-aircraft bottom-up budget (mass report) placed at ESTIMATED stations; S7 replaces them.",
                     "Frame: x aft from the spinner tip, y starboard, z up (fuselage centreline z = 0); metres, kg, deg."],
                 "sources": SRC},
        "reference": {"S_ref": S, "b_ref": b, "c_ref": round(wd["mac"], 6)},
        "airfoils": {"SD7037": {"file": "sd7037.dat", "source": "UIUC coordinates via dbf_airfoil_study/airfoils (SD7037-092-88)"},
                     "NACA0009": {"naca": "0009", "source": "analytic NACA 4-digit"}},
        "surfaces": [wing] + tails,
        "bodies": [fus, bm],
        "propellers": [{"name": "prop", "position": [0.030, 0.0, 0.0], "diameter": 0.508, "pitch": 0.381, "type": "tractor",
                        "symmetric": False, "rotation": "cw", "blades": 2, "spinner_diameter": 0.075,
                        "motor": "T-Motor AT7215 KV270 (prop trade rank 1)", "label": "APC 20x15E"}],
        "gear": {"type": "tricycle", "retractable": False, "faired": True, "wheels": [
            {"name": "nose", "position": [0.10, 0.0, -0.250], "diameter": 0.100, "width": 0.030, "symmetric": False,
             "strut_top": [0.10, 0.0, -0.105], "steerable": True},
            {"name": "main", "position": [0.62, 0.25, -0.245], "diameter": 0.110, "width": 0.035, "symmetric": True,
             "strut_top": [0.56, 0.08, -0.10]}]},
        "payload": {"bay": {"x_start": 0.13, "x_end": 0.92, "width": 0.205, "height": 0.205, "z_center": 0.0, "door": "hinged"},
                    "slots": [
                        {"name": "unit_1", "kind": "sensor_in_container", "dims": [slot_l, 0.202, 0.202],
                         "center": [0.135 + slot_l / 2, 0.0, 0.0], "mass": rho_unit, "missions": ["M2", "GM"]},
                        {"name": "simulator_1", "kind": "simulator", "dims": [slot_l, 0.202, 0.202],
                         "center": [0.135 + 1.5 * slot_l, 0.0, 0.0], "mass": rho_unit, "missions": ["M2"]}]},
        "dr": {"reel": {"center": [0.96, 0.0, 0.010], "diameter": 0.07, "width": 0.05, "mass": 0.32, "axis": "y"},
               "tow_exit": [1.02, 0.0, 0.0], "line_length": 2.73,
               "sensor_stowed_center": [0.80, 0.0, -0.04], "sensor_dims": [0.25, 0.06, 0.06]},
        "masses": [
            {"name": "propulsion (motor, ESC, prop)", "mass": 0.67, "xyz": [0.06, 0.0, 0.0], "group": "propulsion", "grade": "estimate", "source": "mass"},
            {"name": "battery 8S 100 Wh", "mass": 0.70, "xyz": [0.17, 0.0, 0.07], "group": "propulsion", "grade": "estimate",
             "source": "100 Wh / 142 Wh/kg median (sizing.toml method)"},
            {"name": "avionics", "mass": 0.22, "xyz": [0.30, 0.0, 0.08], "group": "avionics", "grade": "estimate", "source": "mass"},
            {"name": "wing", "mass": m_w, "xyz": [round(x_w, 4), 0.0, z_w], "group": "structure", "grade": "estimate",
             "source": "mass: 1.938 kg/m2 median x S, at 40 % MAC"},
            {"name": "fuselage + boom", "mass": 1.57, "xyz": [0.55, 0.0, 0.0], "group": "structure", "grade": "estimate", "source": "mass"},
            {"name": "empennage", "mass": m_e, "xyz": [round(x_tail, 4), 0.0, 0.08], "group": "structure", "grade": "estimate",
             "source": "mass: 0.446 kg per m2 of wing"},
            {"name": "nose gear", "mass": 0.25, "xyz": [0.10, 0.0, -0.18], "group": "gear", "grade": "estimate", "source": "mass (split of 0.72)"},
            {"name": "main gear", "mass": 0.47, "xyz": [0.61, 0.0, -0.17], "group": "gear", "grade": "estimate", "source": "mass (split of 0.72)"},
            {"name": "D&R mechanism", "mass": 0.32, "xyz": [0.96, 0.0, 0.01], "group": "payload_system", "grade": "estimate",
             "source": "sizing.toml [dr] mass_kg"},
            {"name": "unit_1 (sensor in container)", "mass": unit_kg, "xyz": [0.135 + slot_l / 2, 0.0, 0.0], "group": "payload",
             "grade": "estimate", "source": "brief", "missions": ["M2"]},
            {"name": "simulator_1", "mass": unit_kg, "xyz": [0.135 + 1.5 * slot_l, 0.0, 0.0], "group": "payload",
             "grade": "estimate", "source": "brief", "missions": ["M2"]}],
        "extensions": {"x_tail_sizing": {k: (round(v, 5) if isinstance(v, float) else v) for k, v in ti.items()},
                       "x_wing_derived": {k: round(v, 6) for k, v in wd.items()}},
    }
    return g


def ref_d01b():
    return ref_d01(S=1.0, unit_kg=5.0, ref_id="REF-D01b")


def ref_rq4():
    """REF-RQ4: the rq4_mock CFD case, in its own CFD frame (origin = CAD origin,
    nose at x = -0.2388 m) so results line up with cfd/cases/rq4_mock.

    Wing from geometry_report.txt (trapezoid fitted to 13 cuts, scale 3.023):
    S 0.23198 m2, span 1.8198 m, root 0.14323 m, tip 0.11173 m, straight LE at
    x 0.1210 m, chord line z -0.03375 m, incidence 2.48 deg. Body, V-tail and
    nacelle: APPROXIMATED from the case.toml region boxes and the preview
    image (ESTIMATE, +-5 mm). The root glove/strake, the open duct and the
    two-plate mount are simplified (closed nacelle on one pylon)."""
    k = 3.023e-3                                                  # CAD mm -> m
    b = 602.00 * k
    cr, ct = 47.38 * k, 36.96 * k
    S = b * 0.5 * (cr + ct)
    xle = 40.02 * k
    zc = -11.16 * k
    wing = {"name": "wing", "role": "wing", "component": "wing", "symmetric": True, "origin": [round(xle, 6), 0.0, round(zc, 6)],
            "dihedral_deg": 0.0, "incidence_deg": 2.48,
            "sections": [{"y": 0.0, "x_le": 0.0, "z_le": 0.0, "chord": round(cr, 6), "airfoil": "SD7037"},
                         {"y": round(b / 2, 6), "x_le": 0.0, "z_le": 0.0, "chord": round(ct, 6), "airfoil": "SD7037"}],
            "avl": {"nchord": 8, "nspan": 30, "cspace": 1.0, "sspace": 1.0, "component": 1}}
    # V-tail: two near-vertical rectangular panels (front view: root y +-0.045 at z ~0, tips y +-0.117 at z 0.158)
    vt = {"name": "vtail", "role": "vee_tail", "component": "vtail", "symmetric": True, "origin": [0.31, 0.045, -0.005],
          "dihedral_deg": 66.0, "incidence_deg": 0.0,
          "sections": [{"y": 0.0, "x_le": 0.0, "z_le": 0.0, "chord": 0.14, "airfoil": "NACA0008"},
                       {"y": 0.178, "x_le": 0.0, "z_le": 0.0, "chord": 0.14, "airfoil": "NACA0008"}],
          "controls": [control("elevator", "ruddervator_pitch", "plain", 0.0, 0.178, 0.30, 1.0, 1),
                       control("rudder", "ruddervator_yaw", "plain", 0.0, 0.178, 0.30, 1.0, -1)]}
    pylon = {"name": "pylon", "role": "pylon", "component": "nacelle", "symmetric": False, "origin": [0.30, 0.0, 0.035],
             "dihedral_deg": 90.0, "incidence_deg": 0.0,
             "sections": [{"y": 0.0, "x_le": 0.0, "z_le": 0.0, "chord": 0.17, "airfoil": "NACA0012"},
                          {"y": 0.040, "x_le": 0.0, "z_le": 0.0, "chord": 0.17, "airfoil": "NACA0012"}],
             "avl": {"nchord": 4, "nspan": 2}}
    zf = -0.0093
    fus = {"name": "fuselage", "role": "fuselage", "component": "fuselage", "symmetric": False, "origin": [-0.2388, 0.0, 0.0],
           "avl": "body", "stations": [
               station(0.000, 0.020, 0.030, -0.020, 2.0),
               station(0.018, 0.070, 0.100, -0.012, 2.5),
               station(0.070, 0.095, 0.140, 0.008, 3.0),
               station(0.140, 0.099, 0.153, 0.013, 3.0),
               station(0.240, 0.099, 0.135, 0.004, 3.0),
               station(0.300, 0.099, 0.115, -0.007, 3.0),
               station(0.330, 0.099, 0.1085, zf, 3.0),
               station(0.690, 0.099, 0.1085, zf, 3.0),
               station(0.843, 0.099, 0.008, 0.041, 3.0)]}
    nac = {"name": "nacelle", "role": "nacelle", "component": "nacelle", "symmetric": False, "origin": [0.272, 0.0, 0.0985],
           "avl": "none", "stations": [
               station(0.000, 0.072, 0.066, 0.0, 2.2),
               station(0.020, 0.090, 0.087, 0.0, 2.2),
               station(0.230, 0.090, 0.087, 0.0, 2.2),
               station(0.272, 0.050, 0.030, -0.010, 2.2)]}
    return {
        "schema": SCHEMA_ID,
        "meta": {"id": "REF-RQ4", "variant": "reference (CFD mock)", "revision": "A", "date": "2026-10-27",
                 "author": "S9 geometry toolkit", "status": "reference",
                 "notes": ["RQ-4-style mock from Badr Ob's CAD (24 Oct 2026), RQ-4/MQ-4C/MQ-9 reference family (Badr Ob, 10 Oct 2026); "
                           "scaled x3.023 to a 1.82 m span as in cfd/cases/rq4_mock.",
                           "Wing reference geometry is VERIFIED against geometry_report.txt; body, V-tail, pylon and nacelle are "
                           "APPROXIMATIONS (ESTIMATE, about +-5 mm) for AVL, drawings and wetted areas. Use the CAD STL for CFD of this aircraft.",
                           "Airfoil: the CAD section was not identified; SD7037 is a PLACEHOLDER. The nacelle is closed here (open duct in the CAD).",
                           "Frame: the rq4_mock CFD frame (x downstream, y span, z up), origin at the CAD origin; nose at x = -0.2388 m."],
                 "sources": {"cfd": SRC["cfd"]}},
        "reference": {"S_ref": round(S, 6), "b_ref": round(b, 6), "c_ref": 0.12812, "xyz_ref": [0.15301, 0.0, -0.03375]},
        "airfoils": {"SD7037": {"file": "sd7037.dat", "source": "placeholder"}, "NACA0008": {"naca": "0008"}, "NACA0012": {"naca": "0012"}},
        "surfaces": [wing, vt, pylon],
        "bodies": [fus, nac],
        "propellers": [],
        "gear": {"type": "none"},
        "masses": [],
    }


REFS = {"REF-D01": ref_d01, "REF-D01b": ref_d01b, "REF-RQ4": ref_rq4}
