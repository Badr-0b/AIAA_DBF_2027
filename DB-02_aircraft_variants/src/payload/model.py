"""S8 payload model: sensor, container, simulators, D&R, bay, tow check, M3 cliffs.

Pure functions, SI units (m, kg, s, N, Pa), no I/O on import. Existing analysis code is imported
read-only (analysis/cushion_study.py data tables and analysis/s5_tow.py physics); nothing is written
outside W. Every constant carries a grade: V verified (primary source read), R reseller (retail
listing), E estimate (reasoned range), C computed.

Public API (brief section 8):
    container(sensor_kg, g_rating, h_m, ...)      -> dict(dims_m, mass_kg, foam_mm, ok_381, notes, ...)
    sensor(mass_kg, g_rating, ...)                -> dict(geometry, ballast, CG, Barrowman CP, CdA ...)
    simulator(sensor_max_kg, container)           -> dict(dims_m, mass_kg, ballast_kg, trim)
    declaration_range(design, ...)                -> mass range one container serves
    dr(sensor_kg, drive="auto")                   -> dict(mass_kg, deploy_s, stow_s, stow_fn, p_fail, ...)
    bay(n_units, unit_dims, sensor_dims, reel)    -> dict(volume_m3, length_m, cg_note, ...)
    payload_for_adapter(sensor_kg_max, g_rating, drive) -> the S12 adapter's "payload" dict
    tow_check(...), line_shape(...), dart_stability(...), m3_lap_table(...), lights_note(), staging_note()
"""
from __future__ import annotations

import math
import sys
import tomllib
from pathlib import Path

sys.dont_write_bytecode = True

W = Path(__file__).resolve().parents[2]
REPO = W.parent
sys.path.insert(0, str(REPO / "analysis"))
sys.path.insert(0, str(W / "src"))

import cushion_study as cs          # noqa: E402  (read-only: MIL-HDBK-304B tables and functions)
import s5_tow as s5                 # noqa: E402  (read-only: pure tow and reel physics)
from rules import model as R        # noqa: E402  (S1: ring-to-bottom geometry and limits)

G0 = 9.80665
IN = 0.0254
OZ = 0.028349523125
DRT = tomllib.loads((REPO / "analysis" / "inputs" / "dr_trade.toml").read_text(encoding="utf-8"))

# ------------------------------------------------------------------------------ data (graded)
# Ballast densities, kg/m3.
BALLAST = {
    # ASTM B777 classes: C1 16.85-17.25, C2 17.15-17.85, C3 17.75-18.35, C4 18.25-18.85 g/cc
    # (GS Alloy datasheet, read via search 29 Oct 2026, grade V). Retail alloy listed at 17.6 g/cc
    # (tungsten.com, 29 Oct 2026, grade R). Class 1 low end used as the design value.
    "tungsten": dict(rho=17000.0, grade="V", usd_per_kg=(1100.0, 1800.0),
                     price_note="tungsten.com 1 lb bags of 17.6 g/cc alloy, US$499.99-799.99 (R, 29 Oct 2026); "
                                "bulk 95WNiFe rod US$58-65/kg, 5 kg MOQ, unverified marketplace listing (E)"),
    # putty: Maximum Velocity lists min density 10 g/cc, 1 oz at US$6.25 (R, 29 Oct 2026)
    "tungsten_putty": dict(rho=10000.0, grade="R", usd_per_kg=(220.0, 390.0),
                           price_note="US$6.25-10.95 per 28 g oz (Maximum Velocity, Pinewood Pro, R, 29 Oct 2026)"),
    # lead 11.34 g/cc: textbook value (CRC), not re-read this session, grade E (+-1 %)
    "lead": dict(rho=11340.0, grade="E", usd_per_kg=(2.0, 2.6),
                 price_note="primary ingot US$0.89-1.17 per lb (Expert Market Research Q2 2026; Argus 12 Jan 2026), "
                            "commodity not retail (R); cast/handling extra; lead is toxic, encapsulate"),
    # steel 7.85 g/cc: textbook value, grade E; price not looked up
    "steel": dict(rho=7850.0, grade="E", usd_per_kg=None, price_note="commodity bar stock; price not sourced"),
}
FOAM_RHO = cs.D["density_kg_m3"]                       # 32.04 kg/m3 (V, cushion_pe2.toml)
LINE_2MM_BREAK_N = 3900.0                              # Liros/Robline SK78 12-strand 2 mm: 399-410 kgf (R, 29 Oct 2026)
LINE_MASS_KG_M = 0.0018                                # same listing: 1.8 g/m (R)

# Cushion curve shape, normalised: peak g / minimum peak g versus static stress / optimum stress.
# Read on MIL-HDBK-304B Graph 10.42 and 10.48, curves 3 and 4 (PE 2 pcf, 3 in and 4 in), by eye,
# +-10 % (grade E for the shape, V for the minima in cushion_pe2.toml).
_CX = [0.15, 0.25, 0.4, 0.6, 1.0, 1.5, 2.0, 3.0, 4.0]
_CF = [1.80, 1.45, 1.15, 1.04, 1.00, 1.05, 1.15, 1.50, 1.90]


def cushion_factor(x: float) -> float:
    """g_peak / g_min at static stress x * sigma_opt (log-x interpolation of the read curve)."""
    if x <= _CX[0]:
        return _CF[0] * (x / _CX[0]) ** -0.6
    if x >= _CX[-1]:
        return _CF[-1] * (x / _CX[-1]) ** 1.5
    for x0, x1, f0, f1 in zip(_CX, _CX[1:], _CF, _CF[1:]):
        if x0 <= x <= x1:
            u = math.log(x / x0) / math.log(x1 / x0)
            return f0 + u * (f1 - f0)
    raise AssertionError


def gmin_thickness(t_m: float, h_m: float) -> float:
    """Minimum peak g of PE 2 pcf of thickness t_m at drop height h_m (conservative of the two
    extrapolations above 48 in; log-log in thickness between the tabulated 1-6 in)."""
    t_in, h_in = t_m / IN, h_m / IN
    ts = cs.D["thickness_in"]
    gs = [max(cs.gmin_at(i, h_in, "measured p"), cs.gmin_at(i, h_in, "p = 1")) for i in range(len(ts))]
    if t_in <= ts[0]:
        return gs[0]
    if t_in >= ts[-1]:
        return gs[-1]
    for (t0, g0), (t1, g1) in zip(zip(ts, gs), zip(ts[1:], gs[1:])):
        if t0 <= t_in <= t1:
            f = math.log(t_in / t0) / math.log(t1 / t0)
            return math.exp(math.log(g0) + f * (math.log(g1) - math.log(g0)))
    raise AssertionError


def foam_thickness(g_rating: float, h_m: float):
    """Smallest PE 2 pcf thickness (m) whose minimum peak g at h_m is within g_rating (the thicker of
    the two extrapolations above 48 in, as cushion_study does); None if above 6 in."""
    h_in = h_m / IN
    ta = cs.thickness_for(g_rating, h_in, "measured p")[0]
    tb = cs.thickness_for(g_rating, h_in, "p = 1")[0]
    if ta is None or tb is None:
        return None
    return max(ta, tb) * IN


def sigma_opt_pa(t_m: float) -> float:
    return cs.stress_opt_psi(t_m / IN) * cs.PSI


# ------------------------------------------------------------------------------ sensor
BASE_KG = 0.35            # E: shell 0.2 + electronics and COTS battery 0.1 + tow eye and fins 0.05 (range 0.25-0.5)
STRUCT_FRAC = 0.05        # E: clamp and structure mass per kg of ballast (range 0.03-0.10)
F_PITCH_MIN_HZ = 0.5       # E: sensor pitch/yaw natural frequency about the CG (aero stiffness only); line pendulum is 0.27 Hz
NOSE_M, TAIL_M = 0.045, 0.045   # E: ogive nose and fin section carry electronics and the aft/fwd LED bands
FILL = 0.75               # E: ballast fraction of the mid-section cylinder volume


def sensor(mass_kg: float, g_rating: float = 100.0, ballast: str = "steel", length_m: float = 0.20,
           fins: str = "cruciform", n_lights_ok: bool = True) -> dict:
    """Geometry of one finned dart of total mass mass_kg (the declared maximum, ballast fully loaded).
    Ballast is a solid cylinder in the mid-section, sized by volume; the body diameter follows from the
    length. fins: 'cruciform' (4 plain fins) or 'ring' (shrouded). Returns SI dict."""
    rho = BALLAST[ballast]["rho"]
    m_ball = max((mass_kg - BASE_KG) / (1.0 + STRUCT_FRAC), 0.0)
    v_ball = m_ball / rho
    L = max(length_m, R.LIMITS["sensor_len_min_m"] + 0.005)
    Lb = L - NOSE_M - TAIL_M
    d = math.sqrt(4.0 * v_ball / (math.pi * FILL * Lb)) if v_ball > 0 else 0.04
    d = max(d, 0.045)                                   # electronics, battery and LED windows need >= 45 mm
    st = dart_stability(dict(d=d, L=L, mass=mass_kg, m_ball=m_ball, Lb=Lb, fins=fins))
    env = d + 2 * st["fin_semi_span"]                   # fins tip to tip (ring: shroud 15 mm proud each side)
    cda = 0.30 * math.pi * d * d / 4.0 + 0.0006 + (0.0003 if fins == "ring" else 0.0)
    return {"mass_kg": mass_kg, "ballast": ballast, "ballast_kg": m_ball, "ballast_vol_l": v_ball * 1000.0,
            "length_m": L, "diameter_m": d, "fins": fins, "envelope_m": (L, env, env),
            "mean_density_kg_m3": mass_kg / (math.pi * d * d / 4.0 * L * 0.85),
            "cg_from_nose_m": st["x_cg"], "x_cp_m": st["x_cp"], "static_margin_cal": st["margin_cal"],
            "fin_span_m": env, "ok_margin": st["ok_margin"], "pitch_hz": st["pitch_hz"], "margin_abs_m": st["margin_abs_m"], "theta_nose_tow_deg": st["theta_nose_tow_deg"], "cda_m2": cda, "g_rating": g_rating,
            "ok_length": L >= R.LIMITS["sensor_len_min_m"],
            "notes": ["length >= 152.4 mm, no diameter rule (L441)",
                      "tow eye above the CG, not at the nose (see dart_stability)",
                      "three LED bands: nose (fwd), mid (centre), fin section (aft)",
                      "ballast slugs clamped on a central rod, removable for M3 (internal, L447-449)"]}


def dart_stability(s: dict, q_pa: float = 374.0) -> dict:
    """Barrowman (1967) subsonic CP of an ogive-nose dart with 4 trapezoid fins, and the two tow
    attachments: (a) eye above the CG (static margin = (x_cp - x_cg)/d), (b) eye at the nose (the dart then
    hangs nose-up at theta_eq, tan(theta) = W x_cg / (q A CNa x_cp), see memo). q 374 Pa = 26.5 m/s at 1.064."""
    d, L, m, mb, Lb = s["d"], s["L"], s["mass"], s["m_ball"], s["Lb"]
    R_ = d / 2.0
    x_ball = NOSE_M + Lb / 2.0
    # remaining mass (base) spread at the middle of the body
    x_cg = (mb * (1 + STRUCT_FRAC) * x_ball + (m - mb * (1 + STRUCT_FRAC)) * (L / 2.0)) / max(m, 1e-9)
    cr = 0.060
    ct = 0.5 * cr
    best = None
    spans = [0.015] if s.get("fins") == "ring" else [0.02, 0.03, 0.04, 0.05, 0.06]   # semi-span beyond the body, m
    for s_f in spans:
        xr = 0.0
        lf = math.hypot(s_f, xr + 0.5 * (ct - cr))
        cna_f = (1 + R_ / (s_f + R_)) * 4 * 4 * (s_f / d) ** 2 / (1 + math.sqrt(1 + (2 * lf / (cr + ct)) ** 2))
        x_f = L - cr
        xf_cp = (xr / 3) * (cr + 2 * ct) / (cr + ct) + (1 / 6) * ((cr + ct) - cr * ct / (cr + ct))
        cna_n, xn = 2.0, 0.466 * NOSE_M
        cna = cna_n + cna_f
        x_cp = (cna_n * xn + cna_f * (x_f + xf_cp)) / cna
        margin = (x_cp - x_cg) / d
        a_ = math.pi * d * d / 4.0
        inertia = m * (L * L / 12.0 + R_ * R_ / 4.0)                    # solid-cylinder transverse inertia about the CG
        k_aero = q_pa * a_ * cna * (x_cp - x_cg)                          # N m/rad
        f_hz = math.sqrt(max(k_aero, 0.0) / inertia) / (2 * math.pi)
        best = dict(s_f=s_f, cna=cna, x_cp=x_cp, margin=margin, f_hz=f_hz)
        if f_hz >= F_PITCH_MIN_HZ:
            break
    a_ref = math.pi * d * d / 4.0
    w = m * G0
    tan_th = w * x_cg / (q_pa * a_ref * best["cna"] * best["x_cp"])
    return {"x_cg": x_cg, "x_cp": best["x_cp"], "margin_cal": best["margin"], "cna": best["cna"],
            "fin_semi_span": best["s_f"], "theta_nose_tow_deg": math.degrees(math.atan(tan_th)),
            "ok_margin": best["f_hz"] >= F_PITCH_MIN_HZ, "pitch_hz": best["f_hz"], "margin_abs_m": best["x_cp"] - x_cg}


# ------------------------------------------------------------------------------ container
WALL_M = 0.003                    # E: shell wall (1.5 mm ply or 3 mm PP) as in S1 sensor_length_max
SHELL_KG_M2 = 1.0                 # E: 1.5 mm ply 0.68 kg/m2 ... 3 mm ply 2.0 (cushion_study range 0.6-2.0, centre 1.0)
HARDWARE_KG = 0.03                # E: six flush hard points, latch, TOP/O/E marking
GAP_M = 0.005                     # E: carrier clearance around the finned sensor
SPREAD = 1.0                      # E: pad bears over (p + SPREAD t)(q + SPREAD t); 0 = no load spreading


def carrier_kg(sensor_kg: float) -> float:
    """E: inner carrier tray with latch and rigging points: 0.10 kg at 3.4 kg (cushion_study), 3 % of the sensor."""
    return max(0.08, 0.03 * sensor_kg)


def _pad_area(p, q, t, spread=SPREAD):
    return (p + spread * t) * (q + spread * t)


def _build_container(sensor_kg, g_rating, h_m, env, sling_deg, g_margin, spread):
    t = foam_thickness(g_rating / g_margin, h_m)
    if t is None:
        return None
    t = math.ceil(t * 1000.0 - 1e-9) / 1000.0
    sig = sigma_opt_pa(t)
    mc = carrier_kg(sensor_kg)
    a_req = (sensor_kg + mc) * G0 / sig
    L, W_, H = (v + 2 * GAP_M for v in env)
    grew = False
    for _ in range(300):                       # grow the smallest faces until every axis has enough pad area
        a_end = _pad_area(W_, H, t, spread)
        a_w = _pad_area(L, H, t, spread)
        a_h = _pad_area(L, W_, t, spread)
        if min(a_end, a_w, a_h) >= a_req - 1e-12:
            break
        if a_end < a_req:
            W_ += 0.002
            H += 0.002
        elif a_w < a_req:
            H += 0.002
            L += 0.002
        else:
            W_ += 0.002
            L += 0.002
        grew = True
    inner = (L, W_, H)
    outer = tuple(v + 2 * t + 2 * WALL_M for v in inner)
    rtb = R.container_ring_to_bottom(outer, sling_deg)
    area = 2 * (outer[0] * outer[1] + outer[0] * outer[2] + outer[1] * outer[2])
    pads = {"L": _pad_area(W_, H, t, spread), "W": _pad_area(L, H, t, spread), "H": _pad_area(L, W_, t, spread)}
    foam_kg = sum(2 * min(a_req, a) * t * FOAM_RHO for a in pads.values())
    shell_kg = area * SHELL_KG_M2
    mass = foam_kg + shell_kg + mc + HARDWARE_KG
    return {"t": t, "inner": inner, "outer": outer, "rtb": rtb, "a_req": a_req, "pads": pads, "foam_kg": foam_kg,
            "shell_kg": shell_kg, "carrier_kg": mc, "mass": mass, "grew": grew, "sigma_opt_pa": sig,
            "ok": rtb["worst"] < R.LIMITS["ring_to_bottom_lt_m"]}


def container(sensor_kg: float, g_rating: float = 100.0, h_m: float = 1.524, sensor_dims=None,
              sling_deg: float = 15.0, g_margin: float = 1.0, ballast: str = "steel",
              fins: str = "cruciform", spread: float = SPREAD, lengths=None) -> dict:
    """Container for a sensor of sensor_kg rated g_rating, dropped from h_m (PE 2 pcf, MIL-HDBK-304B).

    The sensor length is scanned (0.17-0.32 m, body diameter follows from the ballast volume) and the
    lightest container that keeps every ring-to-bottom distance under 381 mm (L538-542) is returned;
    if none does, the one with the smallest worst-axis distance is returned with ok_381 False.
    sensor_dims: fixes the finned sensor envelope (L, W, H) instead. g_margin >= 1 designs the foam for
    g_rating / g_margin so the container keeps slack for a range of declared masses.
    Axes: 'L' = drop on the end faces (long axis vertical), 'W' and 'H' the sides; every axis can be the
    hang axis because the die picks O or E faces (L1002), so all three are checked."""
    cands = []
    if sensor_dims is not None:
        cands.append((None, tuple(sensor_dims)))
    else:
        for L in (lengths or [0.17 + 0.01 * i for i in range(0, 16)]):
            s = sensor(sensor_kg, g_rating, ballast, L, fins)
            cands.append((s, s["envelope_m"]))
    best = None
    for s, env in cands:
        c = _build_container(sensor_kg, g_rating, h_m, env, sling_deg, g_margin, spread)
        if c is None:
            continue
        stab_ok = True if s is None else s["ok_margin"]
        key = (not c["ok"], not stab_ok, c["mass"] if c["ok"] else c["rtb"]["worst"])
        if best is None or key < best[0]:
            best = (key, c, s)
    if best is None:
        return {"dims_m": None, "mass_kg": None, "foam_mm": None, "ok_381": False,
                "notes": [f"no PE 2 pcf thickness up to 152 mm gives {g_rating} g at {h_m / IN:.0f} in"]}
    _, c, s = best
    notes = [f"foam {1000 * c['t']:.0f} mm PE 2 pcf for {g_rating / g_margin:.0f} g at {h_m / IN:.0f} in "
             f"(MIL-HDBK-304B, p-extrapolation above 48 in, conservative)",
             f"worst ring-to-bottom {1000 * c['rtb']['worst']:.0f} mm (L {1000 * c['rtb']['L']:.0f}, "
             f"W {1000 * c['rtb']['W']:.0f}, H {1000 * c['rtb']['H']:.0f}) at a {sling_deg:.0f} deg sling "
             f"to the corners (Figure 1) vs 381 mm",
             f"pad area needed {1e4 * c['a_req']:.0f} cm2 per face at sigma_opt {c['sigma_opt_pa']:.0f} Pa"]
    if c["grew"]:
        notes.append("inner cross-section grown beyond the sensor envelope to give the foam bearing area")
    return {"dims_m": c["outer"], "mass_kg": c["mass"], "foam_mm": 1000.0 * c["t"], "ok_381": c["ok"],
            "ring_to_bottom_m": c["rtb"], "inner_m": c["inner"], "foam_kg": c["foam_kg"],
            "shell_kg": c["shell_kg"], "carrier_kg": c["carrier_kg"], "pad_area_req_m2": c["a_req"],
            "pad_area_avail_m2": c["pads"], "sigma_opt_pa": c["sigma_opt_pa"], "sensor": s,
            "sensor_kg": sensor_kg, "g_rating": g_rating, "g_margin": g_margin, "h_m": h_m, "sling_deg": sling_deg,
            "volume_l": 1000.0 * c["outer"][0] * c["outer"][1] * c["outer"][2], "notes": notes}


G_TOL = 1.02   # interpolation tolerance between the thickness inverse and forward lookups (cushion curve reading is +-3 g anyway)


def serve(design: dict, m_kg: float, recut: bool = False) -> dict:
    """Peak g of an already-built container design carrying a sensor of m_kg (not the one it was sized for).
    recut=True: the foam pads are re-cut at tech to the optimum area for m_kg (allowed: foam is cheap and the
    shell, ring and carrier stay); False: pads as built. Returns {g_peak, ok, x, feasible_area}."""
    t = design["foam_mm"] / 1000.0
    h = design["h_m"]
    mc = carrier_kg(m_kg)
    sig = design["sigma_opt_pa"]
    need = (m_kg + mc) * G0 / sig
    avail = min(design["pad_area_avail_m2"].values())
    gmin = gmin_thickness(t, h)
    if recut:
        if need > avail:
            x = need / avail
            return {"g_peak": gmin * cushion_factor(x), "ok": False, "x": x, "feasible_area": False}
        return {"g_peak": gmin, "ok": gmin <= design["g_rating"] * G_TOL + 1e-9, "x": 1.0, "feasible_area": True}
    built = min(design["pad_area_req_m2"], avail)
    x = (m_kg + mc) * G0 / (built * sig)
    g = gmin * cushion_factor(x)
    return {"g_peak": g, "ok": g <= design["g_rating"] * G_TOL + 1e-9, "x": x, "feasible_area": True}


def recut_mass(design: dict, m_kg: float) -> float:
    """Container mass when the hardware built for design['sensor_kg'] carries a lighter declared sensor m_kg with the
    foam pads re-cut to the optimum area (shell, carrier tray and hard points stay)."""
    t = design["foam_mm"] / 1000.0
    a_req = (m_kg + carrier_kg(m_kg)) * G0 / design["sigma_opt_pa"]
    foam = sum(2 * min(a_req, a) * t * FOAM_RHO for a in design["pad_area_avail_m2"].values())
    return design["shell_kg"] + design["carrier_kg"] + HARDWARE_KG + foam


def declaration_range(design: dict, m_grid=None, recut: bool = False):
    """(m_lo, m_hi, grid rows) of declared sensor masses one built container serves within its g rating."""
    grid = m_grid or [0.25 * i for i in range(4, 61)]
    rows = [(m, serve(design, m, recut)) for m in grid]
    okm = [m for m, r in rows if r["ok"]]
    return (min(okm), max(okm), rows) if okm else (None, None, rows)


def design_for_range(m_lo: float, m_hi: float, g_rating: float = 150.0, h_m: float = 1.524, ballast: str = "tungsten",
                     recut: bool = False, sling_deg: float = 15.0, fins: str = "cruciform") -> dict:
    """ONE physical container for declared sensor masses in [m_lo, m_hi]: built for m_hi. If recut is False the foam pads
    stay as built, so the foam is made thicker (g_margin) until a sensor of m_lo stays within g_rating; if True the pads
    are re-cut at tech to the optimum area for the declared mass, so no slack is needed. Returns the design dict with
    'servable' (sorted masses on a 0.25 kg grid it serves), 'mass_for' (callable m -> container kg) and the sizing."""
    mc_hi = carrier_kg(m_hi)
    g_margin = 1.0
    if not recut:
        x_lo = (m_lo + carrier_kg(m_lo)) / (m_hi + mc_hi)
        g_margin = max(1.0, cushion_factor(x_lo) * 1.001)
    c = container(m_hi, g_rating, h_m, sling_deg=sling_deg, ballast=ballast, fins=fins, g_margin=g_margin)
    grid = [round(m_lo + 0.25 * i, 2) for i in range(int(round((m_hi - m_lo) / 0.25)) + 1)]
    ok = [m for m in grid if serve(c, m, recut)["ok"]]
    c = dict(c)
    c.update({"servable": ok, "recut": recut, "m_lo": m_lo, "m_hi": m_hi, "g_margin": g_margin,
              "mass_for": (lambda m, _c=c, _r=recut: recut_mass(_c, m) if _r else _c["mass_kg"])})
    return c


# ------------------------------------------------------------------------------ simulators
def simulator(sensor_max_kg: float, cont: dict) -> dict:
    """Shipping-container simulator for the declared maximum: the same outer dimensions (+-3.175 mm, L556-557),
    mass container + declared sensor within +-28.35 g (L559-560), TOP marked. Built as a thin ply box of the
    container's size with a ballast tray; ballast trimmed in 5 g steps on a scale good to +-5 g."""
    dims = cont["dims_m"]
    area = 2 * (dims[0] * dims[1] + dims[0] * dims[2] + dims[1] * dims[2])
    shell = area * SHELL_KG_M2
    total = cont["mass_kg"] + sensor_max_kg
    ball = total - shell - HARDWARE_KG
    vol_l = ball / BALLAST["steel"]["rho"] * 1000.0
    cav_l = (dims[0] * dims[1] * dims[2]) * 1000.0 * 0.6
    return {"dims_m": dims, "size_tol_m": R.LIMITS["sim_size_tol_m"], "mass_kg": total,
            "mass_tol_kg": R.LIMITS["sim_mass_tol_kg"], "shell_kg": shell, "ballast_kg": ball,
            "ballast_steel_l": vol_l, "cavity_ok": vol_l < cav_l, "trim_step_kg": 0.005,
            "notes": ["target the container-plus-sensor mass to +-10 g, a third of the +-28.35 g tolerance",
                      "retarget the ballast whenever the declared sensor mass changes at tech",
                      "mass is re-weighed after every container modification"]}


# ------------------------------------------------------------------------------ D&R
Q_REF = 0.5 * 1.064 * 26.5 ** 2          # Pa, M3 race speed at TIMPA design density (dr_trade reference)
CD_LINE = DRT["line"]["cd"]


LEADS_M = 0.0009                                       # E: two 30 AWG PTFE leads laid alongside add ~0.9 mm to the braid diameter


def line_strength_d(sensor_kg: float, n_struct: float = 4.0, sf: float = 3.0) -> float:
    """Strength-member diameter (m): break >= sf x n_struct x m g, strength ~ d^2 from the 2 mm SK78 reference
    (3.9 kN, R, 29 Oct 2026; scaling is E)."""
    need = sf * n_struct * sensor_kg * G0
    return 0.002 * math.sqrt(need / LINE_2MM_BREAK_N)


def line_diameter(sensor_kg: float, n_struct: float = 4.0, sf: float = 3.0) -> float:
    """Overall line diameter (m): strength member plus leads, at least DB-01's 1.5 mm (dr_trade.toml, E)."""
    return max(DRT["line"]["d_m"], line_strength_d(sensor_kg, n_struct, sf) + LEADS_M)


def line_break_n(d_total_m: float) -> float:
    return LINE_2MM_BREAK_N * (max(d_total_m - LEADS_M, 1e-4) / 0.002) ** 2


_DRIVES = {d["id"]: d for d in DRT["drive"]}
# Added drive (Pololu #4756, 131:1 37D, 12 V): 76 rpm, 45 kg-cm stall (extrapolated) listed by Pololu and Core
# Electronics (R, 29 Oct 2026); mass and gearbox limit taken as the 37D family's (E).
_DRIVES["37d_131"] = dict(id="37d_131", tau_stall_nm=4.413, rpm_free=76.0, limit_cont_nm=0.981 * 1.0,
                          limit_inst_nm=2.452, mass_kg=[0.205, 0.235], encoder=True, needs_driver=True,
                          status="RESELLER", kind="gearmotor")
# Two 37D 131:1 geared onto one drum shaft: double torque at the same speed (E: gearbox limits double).
_DRIVES["2x37d_131"] = dict(id="2x37d_131", tau_stall_nm=8.826, rpm_free=76.0, limit_cont_nm=1.962,
                            limit_inst_nm=4.904, mass_kg=[0.41, 0.47], encoder=True, needs_driver=True,
                            status="ESTIMATE", kind="gearmotor")
# REV NEO 550 (0.97 N m stall, 11000 rpm, 0.142 kg motor + 0.113 kg SPARK MAX, V, dr_trade.toml) behind a 15:1 planetary
# at 85 % efficiency: 12.4 N m stall at 733 rpm. Gearbox mass 0.15 kg, 3S pack 0.10-0.15 kg: all E.
_DRIVES["neo550_g15"] = dict(id="neo550_g15", tau_stall_nm=0.97 * 15 * 0.85, rpm_free=11000.0 / 15, limit_cont_nm=float("nan"),
                             limit_inst_nm=float("nan"), mass_kg=[0.355 + 0.15, 0.405 + 0.15], encoder=True,
                             needs_driver=False, status="VERIFIED motor and controller, ESTIMATE gearbox", kind="brushless")
DRIVE_IDS = ["37d_50", "37d_70", "37d_131", "2x37d_131", "savox_2290", "neo550", "neo550_g15"]
RPM = 2.0 * math.pi / 60.0
_PARTS = DRT["parts"]
_A_PARTS = ["drum_frame", "slip_ring", "dock_latch", "fairlead_bead", "wiring", "mcu"]


def _mid(rng, q=0.5):
    return rng[0] + q * (rng[1] - rng[0])


def _wound(span=R.LIMITS["span_max_m"]):
    g = DRT["geometry"]
    deploy = s5.deploy_length(span, R.LIMITS["tow_factor"]) + g["deploy_margin_m"]
    return deploy, deploy + g["stowed_offset_m"]


def _tension(m, n, d_line, cda, q=Q_REF):
    deploy, _ = _wound()
    return s5.tow_tension(m, n, q, cda, d_line, CD_LINE, deploy, G0)


def _size_drum(sensor_kg, drive_id, cda, q=Q_REF):
    d = _DRIVES[drive_id]
    fl, g = DRT["flight"], DRT["geometry"]
    dl = line_diameter(sensor_kg)
    deploy, wound = _wound()
    ts, wf = d["tau_stall_nm"], d["rpm_free"] * RPM
    t1, tn, t2 = (_tension(sensor_kg, n, dl, cda, q) for n in (1.0, fl["n_stow"], fl["n_reverse_check"]))
    best, why = None, "no radius passes"
    r = g["r_core_min_m"]
    while r <= g["r_core_max_m"] + 1e-9:
        r_eff, turns, width = s5.drum_layout(wound, r, dl, g["pitch_factor"], g["dead_wraps"])
        tau1, taun, tau2 = t1 * r_eff, tn * r_eff, t2 * r_eff
        checks = [(tau1 <= fl["duty_max"] * ts, "stow torque above 50 % of stall"),
                  (taun < ts, "stalls at the n = 1.5 stow load"), (tau2 < ts, "back-driven at n = 2")]
        if d.get("limit_cont_nm") is not None and d.get("limit_cont_nm") == d.get("limit_cont_nm"):
            checks += [(tau1 <= d["limit_cont_nm"], "gearbox continuous limit"),
                       (max(taun, tau2) <= d["limit_inst_nm"], "gearbox instantaneous limit")]
        bad = [m for ok, m in checks if not ok]
        if bad:
            why = bad[0]
        else:
            ex = fl["t_door_s"] + fl["t_latch_s"]
            t_stow = s5.stow_time(wound, t1, r_eff, ts, wf, fl["dock_zone_m"], fl["dock_speed_mps"], ex)
            t_dep = s5.run_time(wound, wf * r_eff, ex)
            des = {"drive": drive_id, "r_core_m": r, "r_eff_m": r_eff, "turns": turns, "width_m": width,
                   "line_d_m": dl, "t_stow_s": t_stow, "t_deploy_s": t_dep, "tau1_frac": tau1 / ts,
                   "tau2_frac": tau2 / ts, "t1_n": t1, "t2_n": t2, "wound_m": wound, "deploy_m": deploy}
            if best is None or t_stow < best["t_stow_s"]:
                best = des
        r += g["r_core_step_m"]
    return best if best else why


def dr_mass(sensor_kg: float, drive_id: str, q: float = 0.5) -> float:
    d = _DRIVES[drive_id]
    m = _mid(d["mass_kg"], q) + sum(_mid(_PARTS[n], q) for n in _A_PARTS)
    if d.get("needs_driver"):
        m += _mid(_PARTS["motor_driver"], q)
    if not d.get("encoder"):
        m += _mid(_PARTS["encoder_addon"], q)
    m += 0.02 * max(sensor_kg - 3.4, 0.0)       # E: stronger frame, bearings and latch per kg above the 3.4 kg design
    return m


def dr(sensor_kg: float, drive: str = "auto", cda: float | None = None, q: float = Q_REF) -> dict:
    """Closed-loop drum (DB-01 option A) for a sensor of sensor_kg at the line-tension reference (n 1 stow).
    drive 'auto' picks, among the drives that pass the torque and gearbox checks, the one with the lowest
    stow time plus 4.5 g per second (dr_trade exchange rate). Heavier sensors need more tension in the line:
    drum radius, stow time, line diameter and drive change. p_fail: DB-01 option A rates (benign 1.2 %,
    catastrophic 1.3 %, signal 2.7 %, E) times 1 + 0.15 (m - 3.4) / 3.4 ... see memo (E)."""
    if cda is None:
        cda = DRT["flight"]["sensor_cda_m2"][1]
    ids = DRIVE_IDS if drive == "auto" else [drive]
    best, tried = None, {}
    for did in ids:
        sz = _size_drum(sensor_kg, did, cda, q)
        tried[did] = sz if isinstance(sz, str) else round(sz["t_stow_s"], 2)
        if isinstance(sz, str):
            continue
        mass = dr_mass(sensor_kg, did)
        cost = sz["t_stow_s"] + mass / 0.0045            # 4.5 g = 1 s of stow (dr_trade report)
        if best is None or cost < best[0]:
            best = (cost, did, sz, mass)
    if best is None:
        return {"feasible": False, "mass_kg": None, "deploy_s": None, "stow_s": None, "p_fail": None,
                "tried": tried, "notes": ["no drive passes the torque checks"]}
    _, did, sz, mass = best
    scale = 1.0 + 0.15 * (sensor_kg - 3.4) / 3.4
    p_cat, p_ben, p_sig = 0.013 * max(scale, 0.5), 0.012 * max(scale, 0.5), 0.027
    return {"feasible": True, "mass_kg": mass, "deploy_s": sz["t_deploy_s"], "stow_s": sz["t_stow_s"],
            "p_fail": {"catastrophic": p_cat, "benign": p_ben, "signal": p_sig, "total": p_cat + p_ben + p_sig},
            "drive": did, "drive_status": _DRIVES[did].get("status", ""), "r_core_m": sz["r_core_m"],
            "line_d_m": sz["line_d_m"], "turns": sz["turns"], "width_m": sz["width_m"],
            "t1_n": sz["t1_n"], "wound_m": sz["wound_m"], "tried": tried,
            "joint": "slip ring (Adafruit 1195 class, 12 wires, 2 A, V verified 13 Oct) or a non-rotating spool",
            "notes": ["slip ring carries the lights signal only; the strength member carries the tension "
                      "(UHMWPE braid with two PTFE leads laid alongside)",
                      "non-rotating spool option: fixed inner line end and a level-wind guide; one fewer joint but the "
                      "line twists with the spool, so it needs a swivel at the sensor (Q&A not needed: one tow line)"]}


def stow_fn_factory(sensor_max_kg: float, drive: str = "auto", extra_s: float = 0.0):
    """callable(m_sensor_array, P) -> stow s for the adapter: the drum built for the declared maximum, stowing
    whatever ballast mass is flown (lighter ballast reels in faster)."""
    import numpy as np
    base = dr(sensor_max_kg, drive)
    if not base["feasible"]:
        return lambda ms, P: np.full(np.atleast_1d(ms).shape, np.inf)
    d = _DRIVES[base["drive"]]
    dl, wound = base["line_d_m"], base["wound_m"]
    r_eff = base["r_core_m"] + dl / 2.0
    ts, wf = d["tau_stall_nm"], d["rpm_free"] * RPM
    fl = DRT["flight"]
    cda = fl["sensor_cda_m2"][1]
    deploy, _ = _wound()

    def fn(ms, P):
        q = 0.5 * getattr(P, "rho", 1.064) * 26.5 ** 2
        out = []
        for m in np.atleast_1d(np.asarray(ms, dtype=float)):
            t = s5.tow_tension(m, 1.0, q, cda, dl, CD_LINE, deploy, G0)
            out.append(s5.stow_time(wound, t, r_eff, ts, wf, fl["dock_zone_m"], fl["dock_speed_mps"],
                                    fl["t_door_s"] + fl["t_latch_s"]) + extra_s)
        return np.array(out)
    return fn


# ------------------------------------------------------------------------------ bay
def bay(n_units: int, unit_dims, sensor_dims=None, reel=None, abreast: int = 1, clearance_m: float = 0.01) -> dict:
    """Volume and length of the internal payload bay: n_units containers (TOP up, each unit_dims = (L, W, H)
    with L along the fuselage axis), `abreast` per row, plus the D&R reel next to them. The sensor is inside the
    container in M2; in M3 the sensor sits on the reel's dock (sensor_dims = the finned envelope)."""
    L, Wd, H = unit_dims
    rows = math.ceil(n_units / abreast)
    length = rows * (L + clearance_m) + clearance_m
    width = abreast * (Wd + clearance_m) + clearance_m
    height = H + clearance_m
    if reel is None:
        reel = dict(width_m=0.06, diameter_m=0.10, length_m=0.10)
    reel_len = reel["length_m"]
    if sensor_dims is not None:
        reel_len = max(reel_len, sensor_dims[0] + 0.05)
        width = max(width, sensor_dims[1] + 0.03)
        height = max(height, sensor_dims[2] + 0.03, reel["diameter_m"] + 0.02)
    vol = length * width * height + reel_len * max(width, reel["width_m"]) * max(height, reel["diameter_m"])
    return {"volume_m3": vol, "length_m": length + reel_len, "width_m": width, "height_m": height,
            "unit_mass_total_kg": None, "rows": rows,
            "cg_note": "units sit on the aircraft CG: bay centre at x_cg, M2 balance moves with n_units; "
                       "the dense sensor and its reel add mass forward or aft of the bay centre, so keep the reel and "
                       "dock on the CG too, and use a fore-aft trim ballast tray for the empty-bay M1/M3 case"}


# ------------------------------------------------------------------------------ adapter payload
def container_kg_fn(g_rating: float = 100.0, h_m: float = 1.524, ballast: str = "steel", fins: str = "cruciform",
                    sling_deg: float = 15.0, g_margin: float = 1.0):
    cache = {}

    def f(sensor_kg):
        k = round(float(sensor_kg), 2)
        if k not in cache:
            c = container(max(k, 0.5), g_rating, h_m, ballast=ballast, fins=fins, sling_deg=sling_deg,
                          g_margin=g_margin)
            cache[k] = c["mass_kg"] if c["mass_kg"] else float("nan")
        return cache[k]
    return f


def payload_for_adapter(sensor_kg_max: float, g_rating: float = 100.0, drive: str = "auto",
                        h_m: float = 1.524, ballast: str = "steel", fins: str = "cruciform",
                        sling_deg: float = 15.0, bay_drag_m2: float = 0.0, as_function: bool = True) -> dict:
    """The S12 adapter's `payload` dict for a design that declares sensor_kg_max.
    container_kg: callable(sensor_kg) (or the scalar at sensor_kg_max); container_range_kg: +-25 % band around it
    (the container is built and weighed before tech, so the range only spans design uncertainty, E);
    dr: mass_kg and stow_s (callable of the flown M3 ballast); extra_kg: 0 (bay structure belongs to S7); f_m2."""
    c = container(sensor_kg_max, g_rating, h_m, ballast=ballast, fins=fins, sling_deg=sling_deg)
    d = dr(sensor_kg_max, drive)
    cm = c["mass_kg"]
    return {"container_kg": container_kg_fn(g_rating, h_m, ballast, fins, sling_deg) if as_function else cm,
            "container_range_kg": [0.75 * cm, 1.25 * cm],
            "dr": {"mass_kg": d["mass_kg"], "stow_s": stow_fn_factory(sensor_kg_max, drive)},
            "extra_kg": 0.0, "f_m2": bay_drag_m2,
            "_meta": {"container": c["dims_m"], "ok_381": c["ok_381"], "drive": d.get("drive"),
                      "stow_s_at_max": d.get("stow_s"), "container_kg_at_max": cm}}


# ------------------------------------------------------------------------------ tow check
def line_shape(m_sensor: float, n: float = 1.0, q: float = Q_REF, cda_s: float = 0.003,
               length_m: float | None = None, d_line: float | None = None, nseg: int = 400) -> dict:
    """Quasi-static two-dimensional line shape in the aircraft's vertical (body) plane, flow along +x (aft).
    Integrated from the sensor up to the exit: weight of line and sensor (scaled by load factor n), cross-flow
    drag of the line (cylinder, Cd 1.1, Hoerner, normal component), drag of the sensor q CdA at its end.
    Returns the sensor position relative to the exit (x aft, depth y down), hang angle at the exit from
    vertical, tension at the exit."""
    L = length_m if length_m is not None else _wound()[0]
    dl = d_line if d_line is not None else line_diameter(m_sensor)
    ds = L / nseg
    w_seg = LINE_MASS_KG_M * (dl / 0.002) ** 2 * G0 * n * ds
    tx, ty = -q * cda_s, m_sensor * G0 * n        # tension on the sensor from the line: forward and up
    px, py = 0.0, 0.0
    xs, ys = [0.0], [0.0]
    for _ in range(nseg):
        mag = math.hypot(tx, ty)
        ux, uy = tx / mag, ty / mag                # direction of the line from sensor toward exit
        un = math.sqrt(max(1 - ux * ux, 0.0))      # flow component normal to the line (flow = +x)
        f = q * CD_LINE * dl * ds * un * un        # cross-flow drag on the element, along the flow's normal part
        nx = (1 - ux * ux) / un if un > 1e-9 else 0.0
        ny = (-ux * uy) / un if un > 1e-9 else 0.0
        fxx, fyy = f * nx, f * ny
        tx, ty = tx - fxx, ty - fyy + w_seg
        px, py = px + (-ux) * ds, py + uy * ds     # sensor is aft (+x) and below the exit
        xs.append(px)
        ys.append(py)
    mag = math.hypot(tx, ty)
    return {"aft_m": px, "depth_m": py, "hang_from_vertical_deg": math.degrees(math.atan2(-tx, ty)),
            "t_exit_n": mag, "xs": xs, "ys": ys, "line_d_m": dl, "length_m": L}


def tow_check(sensor_masses=(3.0, 4.4, 6.0, 8.0, 10.0), loads=(1.0, 3.0, 4.0),
              exits=None, tail=None, pusher_prop_dx_m=0.30) -> dict:
    """Tension at n = 1 / 3 / 4 against the sensor mass, hang angle, line shape and clearance to tail and
    prop for candidate exit points. Layout inputs are placeholders until S9/S7 fix the airframe (E):
    exits = {name: horizontal distance (m) from the exit to the tail's leading edge}, tail = (bottom of the
    tail surfaces below the exit axis, m)."""
    exits = exits or {"belly at CG": 0.55, "belly 0.25 m ahead of CG": 0.80, "tail-boom underside": 0.10}
    tail_drop = 0.10 if tail is None else tail
    out = {"tension_n": {}, "hang_deg_from_vertical": {}, "shape": {}, "clearance": {}, "pitch_moment_per_0p1m": {}}
    for m in sensor_masses:
        dl = line_diameter(m)
        cda = sensor(m + 0.0)["cda_m2"]
        for n in loads:
            t = s5.tow_tension(m, n, Q_REF, cda, dl, CD_LINE, _wound()[0], G0)
            out["tension_n"][f"{m}kg_n{n}"] = {"T_n": t, "line_break_margin": line_break_n(dl) / t,
                                                "line_d_mm": dl * 1000}
            out["pitch_moment_per_0p1m"][f"{m}kg_n{n}"] = n * m * G0 * 0.1
        for n in (1.0, 3.24):
            sh = line_shape(m, n, Q_REF, cda)
            out["shape"][f"{m}kg_n{n}"] = {k: sh[k] for k in ("aft_m", "depth_m", "hang_from_vertical_deg", "t_exit_n")}
            for name, dx in exits.items():
                # line x position at tail-bottom depth, interpolated from the shape
                xs, ys = sh["xs"], sh["ys"]
                x_at = next((xs[i] for i in range(len(ys)) if ys[i] >= tail_drop), xs[-1])
                out["clearance"][f"{m}kg_n{n}_{name}"] = {"horizontal_to_tail_m": dx - x_at}
            out["clearance"][f"{m}kg_n{n}_pusher_prop_dx"] = {"line_aft_at_0.25m_depth_m": next(
                (sh['xs'][i] for i in range(len(sh['ys'])) if sh['ys'][i] >= 0.25), sh['xs'][-1])}
    return out


# ------------------------------------------------------------------------------ M3 lap cliff
def m3_lap_table(lap_times=(33.0, 35.0, 37.0, 39.1, 41.0, 43.0, 45.0), stows=(3.0, 6.0, 9.0, 12.0, 15.0, 20.0, 30.0),
                 t_to_s: float = 8.0, window_s: float = 300.0, stow_counts: bool = True) -> dict:
    """Laps in the window = floor((window - t_to - stow) / t_lap) (stow inside the window, the conservative reading
    of L964-972). For each (lap, stow): laps, and the stow-time gain needed to buy one more lap (None if the
    extra lap needs a negative stow)."""
    rows = []
    for tl in lap_times:
        for st in stows:
            n = R.m3_laps(t_to_s, tl, st, window_s, stow_counts)
            crit = window_s - t_to_s - (n + 1) * tl if stow_counts else None   # stow must be below this
            gain = None if (crit is None or crit < 0) else max(0.0, st - crit)
            rows.append({"t_lap_s": tl, "stow_s": st, "laps": n, "gain_for_extra_lap_s": gain,
                         "t_lap_for_extra_lap_s": (window_s - t_to_s - st) / (n + 1)})
    return {"t_to_s": t_to_s, "window_s": window_s, "rows": rows}


# ------------------------------------------------------------------------------ lights and staging
def lights_note() -> dict:
    """Order-of-magnitude light sizing (E): no primary visibility source was read; verify outdoors at 150 m."""
    p_led_w = 3.0
    n_led = 4
    flux_lm = 100.0 * p_led_w * n_led * 0.8          # E: ~100 lm/W class white LEDs, 20 % to the optics
    sr = 2 * math.pi * (2 * math.sin(math.radians(20)))
    intensity = flux_lm / sr
    energy_wh = 3 * (p_led_w * n_led) * (40.0 * 1.0 + 100.0 * 1.0) / 3600.0      # SOLID lap 2, FLASH 50 % ~200 s
    return {"per_light_w": p_led_w * n_led, "flux_lm": flux_lm, "intensity_cd": intensity,
            "flash_hz": 2.0, "energy_wh": energy_wh, "battery_wh_needed": 2 * energy_wh,
            "grade": "E",
            "notes": ["target 200-400 cd per light, 360 deg band; flash 2 Hz at 50 % duty so it is distinct from SOLID",
                      "one small COTS 2S LiPo (7.4 V, 0.5-1 Ah) with a 2x margin covers a full M3 and the GM check",
                      "test outdoors at noon at 150 m (marker distance) before committing to LED count"]}


def staging_note() -> dict:
    """Time estimates (E, to be replaced by drills) inside the 300 s staging box (L833-835)."""
    return {"M2_load_units_s": {"1": 75, "2": 120, "3": 165},
            "M2_fixed_s": 120,
            "M2_total_s": {"1": 195, "2": 240, "3": 285},
            "M3_unpack_attach_s": 90,
            "GM_rig_each_side_s": 50, "GM_total_s": 3 * 50 + 60,
            "grade": "E",
            "notes": ["per unit 45 s in plus 30 s for the secondary restraint; fixed 120 s for pack, checks, switch test",
                      "so 3 units already crowd the 300 s box: another reason to fly one heavy unit rather than 2-3 units",
                      "M3: connector 30 s + attach 40 s + test-box check 20 s; GM: rig change 50 s per side x 3 + unpack 60 s",
                      "every figure is replaced by a stopwatch drill (TC staging card) before the design is signed"]}


LIFTING_SENSOR = ("Fixed wings on the sensor are legal in the text (L451: 'fixed fins, wings or other aero stability "
                  "surfaces ... may not be removed ... or deployed'), but not worth it: a wing that carries 5 kg at "
                  "26 m/s needs about 0.16 m2 (q 374 Pa, CL 0.8), which cannot stow inside the airplane, cannot be "
                  "removed for the container, and breaks the 381 mm envelope; in a 72 deg turn (n 3.2) it would need "
                  "CL 2.5. Keep small fins only.")
