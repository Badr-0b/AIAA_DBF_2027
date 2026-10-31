"""S1 rules model: hard limits of the 2026-27 DBF rules and a compliance checker.

Source: REPO/rules/2027_DBF_Rules_Draft.pdf (DRAFT dated 2 Sep 2026, SHA-256
d94773fb17ee3bdac88191bf4cbce96c8d0b2166b9b089ed670052bf9ca3bae1), quoted from
REPO/analysis/data/raw/aiaa-dbf-2027-rules-draft.layout.txt. "L<n>" below are
line numbers in that layout text. Checked on aiaa.org for a newer version on
27 Oct 2026 (see memos/01_rules_strategy.md, item A).

Public API (pure functions, SI units, no I/O on import):
    check(geom, ops, verbose=False) -> list[dict]
        Each dict: {"id", "clause", "lines", "status", "message", "value", "limit"}.
        status is one of
          "FAIL"          a definite violation under the rule text;
          "RISK"          compliant only under one reading of an ambiguous clause
                          (a Q&A item), or a "should" clause is not met;
          "WARN"          compliant, but inside a small margin;
          "UNVERIFIABLE"  an input needed for the check is missing.
        verbose=True also returns the "PASS" rows.
    Helpers: deploy_length_min, container_ring_to_bottom, sensor_length_max,
    pack_wh, pack_i_cont, fuse_limit_a, togw_display_limit_kg, m3_laps,
    mission_time, RULES (the clause registry), LIMITS.

Geometry schema: PROVISIONAL until W/early/S9_schema.md appears. Every lookup
goes through _get() with aliases, and a missing key yields UNVERIFIABLE, never an
exception. Keys (all SI; x positive aft from the nose datum):

geom = {
  "id": "REF-D01",
  "span_m": 1.82,                     # projected tip-to-tip wing span
  "max_width_m": 1.82,                # overall lateral extent of the whole airplane
  "wing": {"config": "monoplane|biplane|box|tandem|flying_wing|bwb|joined",
           "tip_device": "none|winglet|tip_plate", "tip_device_cant_deg": 0.0},
  "tail": {"type": "conventional|T|V|inverted_V|H|twin_boom|cruciform|Y|none"},
  "gear": {"type": "tricycle|taildragger|...", "retractable": False},
  "propulsion": {"layout": "tractor|pusher|push_pull|twin_tractor|edf",
                 "n_systems": 1, "n_motors": 1,
                 "motor_cots_unmodified": True, "prop_commercial": True,
                 "packs": [{"mfr": "...", "part": "...", "chem": "LiPo", "cells": 8,
                            "v_nom": 29.6, "capacity_ah": 3.3, "c_rating": 55,
                            "i_cont_a": None, "wh": None}],      # one per system
                 "fuse_a": [100.0],                               # one per system
                 "prop_planes": [{"x_m": 0.0, "kind": "tractor"}]},
  "arming_plugs": [{"system": 0, "x_m": 0.35, "surface": "top",
                    "behind_panel": False}],
  "rc_switch": {"external": True, "under_hatch": False},
  "controls": {"elevator": True, "rudder": True, "aileron": True, "flaps": True,
               "ruddervator": False, "elevon": False, "flaperon": False},
  "failsafe": {"throttle": "closed", "elevator": "full_up", "rudder": "full_right",
               "aileron": "full_right", "flaps": "full_down"},
  "flight_control": {"autopilot": False, "flight_controller": False, "gps": False,
                     "camera": False, "fpv": False, "gyro": False,
                     "telemetry": "rc_link|standalone|none"},
  "hatches": [{"name": "bay", "latch": "spring|screw|pin|tape|velcro|magnet"}],
  "variable_geometry": [{"name": "flap", "rc_controlled": True, "swapped": False}],
  "dr": {"internal": True, "permanent": True, "deploy_length_m": 2.80,
         "door": True, "opening_covered_m1m2": True},
  "sensor": {"length_m": 0.20, "mass_max_kg": 3.4, "ballast_internal": True,
             "fins_fixed": True, "n_lights": 3, "battery_internal": True,
             "rx_in_sensor": False, "carried_internal": True},
  "container": {"dims_m": [L, W, H], "mass_kg": 0.6, "rect_prism": True,
                "sling_angle_deg": 30.0, "ring_allow_m": 0.01905,
                "ring_to_bottom_m": None,      # or the measured worst case
                "ring_id_m": 0.0127, "ring_section_m": 0.003,
                "attach_flush": True, "marked_top": True, "marked_oe": True},
  "simulator": {"dims_m": [L, W, H], "mass_kg": 4.0, "adjustable_ballast": True,
                "marked_top": True},
  "structure": {"tip_test_mass_ok_kg": 16.0},   # mass the wing passes the tip test at
  "cg_marked": True,
}
ops = {
  "declared": {"sensor_max_kg": 3.4, "n_sim_max": 1, "tip_test_mass_kg": 15.0},
  "m1_waived": True,
  "attempts": [{"mission": "M2", "togw_kg": 14.4, "n_sim": 1, "t_takeoff_s": 8,
                "t_lap_s": 39.8},
               {"mission": "M3", "togw_kg": 9.8, "sensor_kg": 3.4, "laps": 7,
                "t_takeoff_s": 8, "t_lap_s": 39.1, "stow_s": 12, "deploy_s": 7.5}],
  "gm": {"height_in": 60},
  "staging": {"opens_hatch_in_box": False, "t_est_s": 180},
}
"""
from __future__ import annotations

import math

# ----------------------------------------------------------------- exact units
IN = 0.0254
FT = 0.3048
LB = 0.45359237
OZ = 0.028349523125

# ----------------------------------------------------------------- hard limits
LIMITS = {
    "span_max_m": 6 * FT,                    # L418 "Maximum allowable wingspan is 6 feet."
    "togw_lt_kg": 55 * LB,                   # L627 "must be less than 55-lb" (strict)
    "energy_total_max_wh": 100.0,            # L771
    "energy_pack_max_wh": 100.0,             # L772-774
    "fuse_max_a": 100.0,                     # L776-777
    "arming_min_m": 6 * IN,                  # L681 "No part ... closer than 6 inches"
    "sensor_len_min_m": 6 * IN,              # L441 "minimum overall length of six inches"
    "tow_factor": 1.5,                       # L502-504
    "ring_id_min_m": 0.5 * IN,               # L533-534
    "ring_section_max_m": IN / 8,            # L533-534
    "pin_d_m": 0.25 * IN,                    # L535
    "ring_to_bottom_lt_m": 15 * IN,          # L538-542 ("should be less than 15 inches")
    "drop_max_m": 60 * IN,                   # L1002
    "drop_step_m": IN,                       # L1002 "whole inches"
    "sim_size_tol_m": IN / 8,                # L556-557
    "sim_mass_tol_kg": OZ,                   # L559-560
    "window_s": 300.0,                       # L915, L938, L967
    "staging_s": 300.0,                      # L833
    "gm_s": 300.0,                           # L983
    "m1_laps": 3,                            # L913
    "m2_laps": 5,                            # L937
    "m3_min_laps": 3,                        # derived from L958-963 (FLASHING after lap 2)
    "qr_start_height_m": 4 * FT,             # L1044-1045 "approximately four feet"
    "tip_test_g": 2.5,                       # L1266 '"roughly" equivalent to a 2.5g load case'
    "qa_round1_questions": 5,                # L204
    "qa_later_questions": 3,                 # L205
}
RING_OD_M = LIMITS["ring_id_min_m"] + 2 * LIMITS["ring_section_max_m"]   # 19.05 mm, smallest legal ring
EPS = 1e-9


# ----------------------------------------------------------------- tolerant lookup
_MISSING = object()


def _get(d, *paths, default=_MISSING):
    """First present value among dotted paths (aliases) in nested dict d."""
    for p in paths:
        cur = d
        ok = True
        for k in p.split("."):
            if isinstance(cur, dict) and k in cur and cur[k] is not None:
                cur = cur[k]
            else:
                ok = False
                break
        if ok:
            return cur
    return None if default is _MISSING else default


def _num(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _as_list(x):
    if x is None:
        return []
    return list(x) if isinstance(x, (list, tuple)) else [x]


# ----------------------------------------------------------------- physics/rule helpers
def deploy_length_min(span_m):
    """Minimum deploy distance, exit point to the sensor's forward tip (L502-504)."""
    return LIMITS["tow_factor"] * span_m


def line_length_min(span_m, attach_aft_of_nose_m=0.0, sag_allow_m=0.0):
    """Tow-line length needed so the exit-to-nose distance meets 1.5 b when the line
    attaches attach_aft_of_nose_m behind the sensor nose (nose then sits ahead of the
    attachment). sag_allow_m: extra line for catenary sag if measured in flight."""
    return deploy_length_min(span_m) + attach_aft_of_nose_m + sag_allow_m


def sling_height(face_a_m, face_b_m, sling_angle_deg, ring_allow_m=RING_OD_M):
    """Height from the hanging (top) face to the top of the ring for a four-leg sling to
    the face corners (rules Figure 1), legs at sling_angle_deg above horizontal."""
    half_diag = 0.5 * math.hypot(face_a_m, face_b_m)
    return half_diag * math.tan(math.radians(sling_angle_deg)) + ring_allow_m


def container_ring_to_bottom(dims_m, sling_angle_deg=30.0, ring_allow_m=RING_OD_M):
    """Ring-to-bottom distance for each of the three drop axes (L538-542): the container
    dimension along the axis plus the sling over the opposite face. Returns
    {"L": .., "W": .., "H": .., "worst": ..} in m; dims_m = (L, W, H)."""
    L, W, H = (float(v) for v in dims_m)
    out = {"L": L + sling_height(W, H, sling_angle_deg, ring_allow_m),
           "W": W + sling_height(L, H, sling_angle_deg, ring_allow_m),
           "H": H + sling_height(L, W, sling_angle_deg, ring_allow_m)}
    out["worst"] = max(out.values())
    return out


def sensor_length_max(foam_m, inner_cross_m, wall_m=0.003, sling_angle_deg=30.0,
                      ring_allow_m=RING_OD_M, limit_m=None):
    """Longest sensor (plus inner box) whose container keeps every ring-to-bottom
    distance below 381 mm. inner_cross_m: the inner box's square cross-section side."""
    limit = LIMITS["ring_to_bottom_lt_m"] if limit_m is None else limit_m
    w = inner_cross_m + 2 * foam_m + 2 * wall_m
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        L = mid + 2 * foam_m + 2 * wall_m
        if container_ring_to_bottom((L, w, w), sling_angle_deg, ring_allow_m)["worst"] < limit:
            lo = mid
        else:
            hi = mid
    return lo


def pack_wh(pack):
    """Rated energy = rated capacity x rated voltage (L772-774)."""
    wh = _num(_get(pack, "wh"))
    if wh is not None:
        return wh
    cap, v = _num(_get(pack, "capacity_ah")), _num(_get(pack, "v_nom", "voltage_v"))
    if cap is None or v is None:
        mah = _num(_get(pack, "capacity_mah"))
        cells = _num(_get(pack, "cells"))
        cap = mah / 1000.0 if mah is not None else cap
        if v is None and cells is not None:
            v = 3.7 * cells          # LiPo nominal per cell; label value governs at tech
    return cap * v if (cap is not None and v is not None) else None


def pack_i_cont(pack):
    """Maximum continuous discharge current: capacity x C-rating or the labelled maximum (L776-777)."""
    i = _num(_get(pack, "i_cont_a", "i_max_a"))
    if i is not None:
        return i
    cap, c = _num(_get(pack, "capacity_ah")), _num(_get(pack, "c_rating"))
    if cap is None:
        mah = _num(_get(pack, "capacity_mah"))
        cap = mah / 1000.0 if mah is not None else None
    return cap * c if (cap is not None and c is not None) else None


def fuse_limit_a(pack):
    """Largest legal blade fuse for this pack: min(continuous rating, 100 A)."""
    i = pack_i_cont(pack)
    return None if i is None else min(i, LIMITS["fuse_max_a"])


def togw_display_limit_kg():
    """Largest true mass that still displays below 55.00 lb after Sec. 6.2 rounding to
    0.01 lb (54.99 lb shown): < 54.995 lb."""
    return 54.995 * LB


def mission_time(t_takeoff_s, t_lap_s, laps):
    """Window time used: take-off roll and climb plus `laps` laps (L917, L942)."""
    return t_takeoff_s + laps * t_lap_s


def m3_laps(t_takeoff_s, t_lap_s, stow_s=0.0, window_s=None, stow_counts=True):
    """Whole M3 laps inside the window. stow_counts=True charges the stow inside the
    window (the conservative reading of L964-972); False lets the stow run after it."""
    w = LIMITS["window_s"] if window_s is None else window_s
    budget = w - (stow_s if stow_counts else 0.0) - t_takeoff_s
    return max(0, int(math.floor(budget / t_lap_s + EPS))) if t_lap_s > 0 else 0


def drop_inches(h_m):
    """Declared GM height in whole inches, never above h_m and never above 60 in (L1002)."""
    return int(min(60, math.floor(h_m / IN + EPS)))


# ----------------------------------------------------------------- clause registry
# id, section, lines, verbatim quote (trimmed with "..." only), requirement, verification
RULES = [
    ("C01", "3.1", "418", "Maximum allowable wingspan is 6 feet.",
     "Projected tip-to-tip span <= 1.8288 m; wingspan is not defined (Q&A); keep overall width <= 1.8288 m as fallback", "inspection (tape)"),
    ("C02", "3.2.1", "627", "The airplane TOGW (take-off gross weight with payload) must be less than 55-lb.",
     "Every attempt TOGW < 24.948 kg; displayed to 0.01 lb so true mass < 24.945 kg", "inspection (scale)"),
    ("C03", "3.2.1", "578-580", "During Tech Inspection, the airplane must pass the wing tip load test in the flight configuration with the maximum designed takeoff weight, to include the heaviest weight payload declared and heaviest battery pack(s) to be flown.",
     "Wing and carry-through pass a two-tip lift at the declared MGTOW (~2.5 g)", "test (tip test)"),
    ("C04", "3.2.1", "584", "The maximum load demonstrated will be recorded and may not be increased after completing Tech Inspection.",
     "Tip-test mass becomes the permanent TOGW cap; size the spar for the highest mass ever to be declared", "test + analysis"),
    ("C05", "3.2.1", "582", "The loaded and empty CG locations must be marked on the exterior of the airplane.",
     "Exterior CG marks, empty and loaded", "inspection"),
    ("C06", "3.2.1", "585-587", "No structure nor components may be dropped from the airplane during flight unless required by a mission specific objective.",
     "Retain everything incl. tow line and sensor; a line break is a dropped part", "test (line proof load) + analysis"),
    ("C07", "3.2.1", "589-590", "All structure, components, and payloads must be mechanically fastened and not rely on friction to be the primary retention method.",
     "Mechanical restraint of payload units, packs, sensor", "inspection"),
    ("C08", "3.2.1", "592-593", "No form of externally assisted take-off is allowed. All energy for take-off must come from the on-board propulsion battery pack(s).",
     "Ground-roll take-off on own power", "inspection"),
    ("C09", "3.2.1", "595-596", "The airplane must be propeller driven and electric powered with an unmodified, over-the-counter model, brushed or brushless electric motor.",
     "COTS unmodified motor(s); propeller or commercial ducted fan (L615)", "inspection"),
    ("C10", "3.2.1", "598-600", "No autopilots/flight controllers are allowed under any circumstances, even in manual mode. No onboard GPS systems are allowed. Flight stabilization subsystems and rate gyros are allowed.",
     "No FC/autopilot/GPS; a stand-alone gyro stabiliser is allowed", "inspection"),
    ("C11", "3.2.1", "602-603", "The radio-control Transmitter/Receiver must be a commercially available controller with fail-safe capability and operating on a legal US frequency (72MHz, 900MHz, 2.4GHz).",
     "COTS Tx/Rx with per-output fail-safe (ELRS 2.4 GHz PWM Rx)", "inspection + test"),
    ("C12", "3.2.1", "605-607", "Telemetry systems using stand-alone transmitters and receivers or ground stations are not allowed.",
     "Telemetry only over the RC link; non-RF loggers allowed", "inspection"),
    ("C13", "3.2.1", "609", "Cameras on or in the airplane are not allowed during the competition under any circumstances.",
     "No camera aboard (incl. sensor)", "inspection"),
    ("C14", "3.2.1", "617-620", "each airplane will use a commercially produced propeller/blades. ... The propeller blades may be modified to reduce the propeller diameter by clipping the tips. ... No other modifications to the propeller are allowed.",
     "Commercial props; only tip clipping, paint balance, reamed bore", "inspection"),
    ("C15", "3.2.1", "622", "The propeller (diameter/pitch) may be changed for each flight attempt.",
     "Permission: prop is a per-attempt choice", "n/a"),
    ("C16", "3.2.1", "629-630", "The exact airplane being presented at Tech Inspection must have been flown prior to the contest date. Proof of flight must be presented upon entering Tech Inspection.",
     "Fly the contest airframe before travel; video of straight and level flight", "test (video)"),
    ("C17", "3.2.1", "638-642", "The airplane must remain substantially the same as documented in the report ... The configuration drawing ... will be used to verify the airplane configuration during Tech Inspection.",
     "Freeze configuration items at the 19 Feb report", "inspection vs drawing"),
    ("C18", "3.2.1", "647-649", "The airplane must have an externally accessible SWITCH to turn on the radio control system. It may not be internal or under a panel or hatch. An arming plug is NOT considered an acceptable switch.",
     "External Rx switch separate from fuse/arming", "inspection"),
    ("C19", "3.2.1", "651-654", "all permanent fasteners shall be tight with a secondary retention method ... Clevises on flight controls ... must have an appropriate mechanical locking device",
     "Thread-locker/Nyloc/safety wire; clevis keepers", "inspection"),
    ("C20", "3.2.1", "656-658", "Commercially available control horns MUST be installed per manufacturer's instructions. NOTE: Control horns may not be adhered to film surfaces as sole attachment method.",
     "Horns through-bolted or bonded to structure, not to film", "inspection"),
    ("C21", "3.2.1", "660-661", "All control surfaces, wing-surfaces, and fuselage components supporting aerodynamic surfaces must have adequate stiffness to resist flutter & aero-elastic effects.",
     "Flutter margin at the highest dive speed (fail-safe case)", "analysis + inspection"),
    ("C22", "3.2.1", "663-664", "All motors and propellers must be secured to airplane with sufficient strength and integrity to withstand all expected flight loads",
     "Motor mount sized for thrust, torque, manoeuvre and landing", "inspection + analysis"),
    ("C23", "3.2.1", "666-667", "All electrical connections shall be fully insulated with no visible wires or exposed surfaces which may conduct electricity.",
     "Insulated connectors throughout", "inspection"),
    ("C24", "3.2.2", "671-672", "The airplane must have an external motor arming plug for each propulsion system separate from the onboard radio receiver (Rx) switch.",
     "One external arming plug per propulsion system", "inspection"),
    ("C25", "3.2.2", "680", "The arming plug wire must be the same gauge or larger diameter than the propulsion battery wire.",
     "Plug wire gauge >= pack lead gauge", "inspection"),
    ("C26", "3.2.2", "681-683", "No part of the arming plug may be closer than 6 inches from the plane of any propeller ... the propeller plane extends beyond the physical dimensions of the airplane.",
     "Every plug >= 152.4 mm from every prop plane (planes extend across the whole airplane)", "inspection (rule)"),
    ("C27", "3.2.2", "690-692", "accessible by a crew member standing ahead of the propeller(s) for pusher airplanes and standing behind the propeller(s) for tractor airplanes (i.e. the crew member must not reach across the propeller plane to access the arming plug).",
     "Tractor: plug aft of all prop planes; pusher: ahead; push-pull: no reach over either (FAQ L1712-1714)", "inspection"),
    ("C28", "3.2.2", "695-696, 701", "The arming plug MUST be mounted on the outside of the airplane (it may NOT be behind an access panel or door) ... MUST be mounted on the top or upper surface of the airplane",
     "Plug on the top surface, exposed", "inspection"),
    ("C29", "3.2.2", "704-706", "The arming plug shall be integrated into the electrical circuit on the positive (+ Red) wire between the fuse and the electronic speed controller (ESC)",
     "Battery -> fuse harness -> plug (+) -> ESC", "inspection"),
    ("C30", "3.2.3", "710-715", "All battery packs must be un-altered and commercially procured as Commercial-Off-The-Shelf (COTS) battery packs. Custom battery packs are not allowed. ... The Original Manufacturer's Label must be clearly visible on ALL battery packs.",
     "COTS labelled packs (propulsion, Rx, sensor)", "inspection"),
    ("C31", "3.2.3", "717, 720", "A separate battery is required for the Rx/Servos on the airplane. ... If the ESC has a Battery Eliminator Circuit (BEC), it must be disabled.",
     "Separate Rx pack; BEC red wire removed", "inspection + test"),
    ("C32", "3.2.3", "723-727", "All batteries must be stored and charged in a commercially-available, unaltered and manufacturer-labeled battery charging sack ... the only time batteries may be out of the sack is for tech inspection or while in the airplane.",
     "Charging sack logistics; sensor battery while packed is a Q&A item", "inspection"),
    ("C33", "3.2.3.1", "734-736", "There shall be a maximum of one battery pack connected to a propulsion system.",
     "One pack per system", "inspection"),
    ("C34", "3.2.3.1", "740-741", "All propulsion battery packs must be identical (same manufacturer, part number, size, voltage, power, rating, etc).",
     "Multi-system: identical packs at the same time", "inspection"),
    ("C35", "3.2.3.1", "743-744", "Each battery pack must be independently connected to its own propulsion system. Batteries may not be connected in series or parallel.",
     "No series/parallel packs", "inspection"),
    ("C36", "3.2.3.1", "750, 754-755", "Each battery/propulsion system is required to have its own fuse and arming plug. ... The fuse must be a blade style fuse ... in a separate fuse harness between the battery and arming plug.",
     "Per system: blade fuse harness + arming plug", "inspection"),
    ("C37", "3.2.3.2", "771", "Total Propulsion Energy stored on airplane (sum of all propulsion batteries) shall not exceed 100 Watt-hours.",
     "Sum of rated Wh <= 100", "inspection (label)"),
    ("C38", "3.2.3.2", "772-774", "Individual battery packs may not exceed ... 100 Watt-hours (rated capacity * rated voltage) per battery pack",
     "Each pack <= 100 Wh rated", "inspection (label)"),
    ("C39", "3.2.3.2", "776-777", "The maximum current rating for the fuse is the maximum continuous discharge current rating of the battery pack (battery capacity * C-rating or maximum labeled discharge current) up to 100 amps.",
     "Fuse <= min(pack continuous, 100 A), per system", "inspection"),
    ("C40", "3.1.1", "438-439", "Teams may have only one sensor. Once Tech Inspection is completed with that sensor, any damage to the sensor during a mission must be repaired and reapproved by Tech Inspection.",
     "One sensor; GM damage needs re-tech", "inspection"),
    ("C41", "3.1.1", "441", "The sensor must have a minimum overall length of six inches.",
     "Sensor length >= 152.4 mm", "inspection (sensor length at tech, L1315)"),
    ("C42", "3.1.1", "443-445", "The sensor must be aerodynamically stable during deployment, operation and recovery ... remaining in a fixed orientation in the horizontal plane (not spinning or rotating) with no effect on the stability of the aircraft",
     "Stable towed body; no roll/spin; no aircraft upset", "test (tow test) + Flight Director"),
    ("C43", "3.1.1", "447-449", "The sensor weight may be changed for any Mission 3 attempt; the weight may not exceed the maximum declared weight in Tech Inspection. Weight that is added ... must be internal to the sensor",
     "Internal ballast bay; M3 mass <= declared max", "inspection"),
    ("C44", "3.1.1", "451-453", "The sensor may have fixed fins ... These may not be removed for installation in the sensor shipping container or deployed during the deployment process.",
     "Fixed external geometry; container must fit the finned sensor", "inspection"),
    ("C45", "3.1.1", "455-456", "The sensor must connect to the deployment and recovery device using a tow line. The tow line must have a mechanical and electrical connection to the sensor.",
     "Conductive tow line + slip ring", "inspection + test"),
    ("C46", "3.1.1", "459-478", "three separate lights, a forward light, a center light and an aft light ... three modes ... The Rx for the payload signal must be in the airplane ... The control electronics ... must be in the sensor.",
     "3 lights, OFF/SOLID/FLASHING, Rx in airplane, electronics in sensor", "test (test box)"),
    ("C47", "3.1.1", "480-482", "The sensor must contain its own battery ... compliant with the battery requirements in section 3.2.3 ... internal to the sensor",
     "COTS labelled sensor battery inside the sensor", "inspection"),
    ("C48", "3.1.1", "484-486", "No part of the sensor may be outside of the airplane external surfaces or features until commanded to deploy. If the opening for the sensor is not covered by a door or hatch for Mission 3, it may NOT be covered for Mission 1 and 2.",
     "Internal stowage; open slot stays open in all missions", "inspection"),
    ("C49", "3.1.1", "488-489", "Prior to deployment and after recovery, the sensor must be securely restrained by the deployment and recovery mechanism for take-off, flight and landing.",
     "Docking latch on the D&R", "inspection + test"),
    ("C50", "3.1.1", "491-493", "Teams must have a sensor test box ... The test box must connect to the sensor tow line electrical connection.",
     "Sensor test box", "test"),
    ("C51", "3.1.2", "497-500", "The deployment and recovery mechanism ... must be internal to the airplane ... must be permanently installed in the Mission 3 location for all missions.",
     "D&R mass flies in M1/M2", "inspection"),
    ("C52", "3.1.2", "502-504", "must deploy the sensor with a tow line to a distance equal to or greater than 1.5 times the airplane wingspan when measured from the exit location of the airplane to the forward tip of the sensor.",
     "Exit-to-nose >= 1.5 b (2.743 m at 1.8288 m)", "inspection (L1327) + test"),
    ("C53", "3.1.3", "508-511", "The sensor shipping container must fully enclose the sensor and protect it from drop shock events ... must be a rectangular prism.",
     "Closed rectangular prism", "inspection"),
    ("C54", "3.1.3", "515-522", "The top surface ... must be marked with \"TOP\" ... Each pair of opposing sides ... marked with the letters \"O\" or \"E\"",
     "TOP and O/E markings", "inspection"),
    ("C55", "3.1.3", "524-525", "For mission 2, the sensor shipping container with the maximum weight sensor declared in Tech Inspection must be loaded and secured in the airplane with the surface marked \"TOP\" facing up.",
     "M2 bay accepts units TOP-up", "inspection"),
    ("C56", "3.1.3", "533-535", "single metal lifting ring with a minimum inside diameter of 1/2 inch and maximum cross-section of 1/8 inch diameter ... suspended by a 1/4 inch diameter brass pin",
     "Ring ID >= 12.7 mm, wire <= 3.175 mm", "inspection"),
    ("C57", "3.1.3", "538-542", "The total distance from the rigging ring to the bottom surface of any container side should be less than 15 inches ... will only guarantee that a maximum drop height of 60 inches may be achieved with a maximum rigging plus container length of 15 inches.",
     "Every axis: container dim + sling < 381 mm", "analysis + measurement"),
    ("C58", "3.1.3", "543-545", "The feature(s) where the rigging attaches to the sensor shipping container must be flush or below the surface when the rigging is not attached",
     "Recessed hard points", "inspection"),
    ("C59", "3.1.3", "556-557", "The shipping container simulators must be the same shape and size as the sensor shipping container within +/- 1/8 inch.",
     "Simulator dims within +/-3.175 mm", "inspection"),
    ("C60", "3.1.3", "559-560", "The shipping container simulator must be the same weight as the sensor shipping container plus the maximum weight sensor declared in Tech Inspection within +/- 1 ounce.",
     "Simulator mass within +/-28.35 g of container + declared sensor", "inspection (scale)"),
    ("C61", "3.1", "428-430", "All sensor shipping containers ... must be secured sufficiently to assure safe flight without possible shift of aircraft CG outside of design limits",
     "Positive restraint of every unit", "inspection"),
    ("C62", "3.2.1", "574", "The airplane may be of any configuration except rotary wing or lighter-than-air.",
     "No rotary wing/LTA", "inspection"),
    ("C63", "3.3.2", "798-802", "The airplane must be in the desired configuration to start the assembly. Once a team enters the staging area, no adjustments are allowed to the airplane configuration such as opening hatches or any other work necessary for the installation of batteries and payloads.",
     "Enter with hatches already open (reading A) or hatch-free loading (reading B); Q&A", "test (staging drill)"),
    ("C64", "3.3.2", "803-805", "All payload restraints must be in the airplane prior to entering the staging area. ... Ballast may be used in the airplane but it must be installed prior to entering the staging area and may not be moved or adjusted",
     "Restraints and aircraft ballast fixed before staging", "test (staging drill)"),
    ("C65", "3.3.2", "825-828", "The ground crew member is the only person who may touch the airplane while inside the staging box",
     "One-person loading in < 300 s", "test (staging drill)"),
    ("C66", "3.3.2", "833-835", "There will be a 5-minute time limit in the staging box ... Any and all work required to install the propulsion battery pack(s) and payloads, check flight controls and prepare the airplane for flight must be completed within the 5-minute time limit.",
     "Staging work <= 300 s incl. M3 unpack + attach", "test (staging drill)"),
    ("C67", "3.3.3", "877, 884", "The Flight Missions must be flown in order. ... A new mission may not be flown until the team has obtained a successful score for the preceding mission.",
     "Sequential missions", "n/a"),
    ("C68", "3.3.3", "879-882", "Teams may elect to waive a Mission 1 attempt and proceed directly to Mission 2 ... If a team waives Mission 1 and then fails to complete Mission 2, the team may not then attempt a Mission 1.",
     "Waiver option (strategy)", "n/a"),
    ("C69", "3.3.3", "885-887", "After successfully completing all three flight missions, teams will be allowed one additional attempt for both Mission 2 and Mission 3 to improve their score.",
     "Extra attempts (strategy)", "n/a"),
    ("C70", "3.3.3", "889", "The airplane must be flown in the same configuration for all three missions unless specifically cited herein.",
     "No hardware changes between missions except batteries/payloads (FAQ L1672-1673)", "inspection"),
    ("C71", "3.3.3", "891", "The airplane will use ground rolling takeoff and landing. There is no limit on take-off distance this year.",
     "Wheeled gear; no TO distance limit", "n/a"),
    ("C72", "3.3.3", "892-895", "The airplane must be \"straight and level\" when passing the turn marker before initiating a turn.",
     "Marker overshoot in the lap model", "n/a"),
    ("C73", "3.3.3", "897-902", "A successful landing is defined as landing on the paved portion of the runway. ... may not \"bounce\" off the runway. ... \"significant\" damage during landing will not receive a score",
     "Landing gear and approach speed for paved touchdown", "test"),
    ("C74", "3.3.3.1", "913-915", "Teams must complete 3 laps within the flight window. ... There will be a 5-minute flight window for this mission.",
     "M1: t_TO + 3 laps <= 300 s", "analysis"),
    ("C75", "3.3.3.2", "928-932", "the minimum payload must include the sensor in shipping container ... may not exceed the maximum number declared at Tech Inspection.",
     "M2: sensor unit + n_sim <= declared", "n/a"),
    ("C76", "3.3.3.2", "937-938", "Teams must complete 5 laps within the flight window. ... There will be a 5-minute window for this mission.",
     "M2: t_TO + 5 laps <= 300 s", "analysis"),
    ("C77", "3.3.3.3", "955-957", "the sensor must be deployed by remote command and must be fully deployed prior to the first downwind 180 degree turn. The sensor lights must be in the \"OFF\" mode when deployed.",
     "Deploy time < take-off-to-downwind-marker time", "test"),
    ("C78", "3.3.3.3", "958-963", "After crossing the start/finish line to complete the first lap, the sensor lights must be commanded to the \"SOLID ON\" mode prior to the next upwind turn. ... \"FLASHING ON\" ...",
     "M3 >= 3 laps (derived)", "n/a"),
    ("C79", "3.3.3.3", "964-966", "After completion of the final lap, the sensor will be commanded to the lights \"OFF\" mode and stowed by remote command; the sensor must be fully stowed inside the aircraft prior to landing.",
     "Stow before landing; window charge of stow is ambiguous (Q&A)", "test"),
    ("C80", "3.3.4", "1002-1003", "The assembly crew member will declare the drop height in whole inches up to a maximum of 60 inches.",
     "GM height integer inches <= 60", "n/a"),
    ("C81", "3.3.4", "1069-1087", "If any drop damages the rigging or damages the container such that the rigging cannot be removed ... Any physical or structural damage is a mission failure. ... Altered or missing function of the sensor lights is a mission failure.",
     "Sensor survives 6 drops at the declared height, lights work", "test (TC-02 drop)"),
    ("C82", "3.3.4", "1010-1041", "The five minute mission time limit will be for attaching and changing the rigging, then loading into the quick release mechanism and then removing the sensor from the shipping container after all drops are completed.",
     "GM handling <= 300 s", "test (GM drill)"),
    ("C83", "4", "1100", "Each team may only submit one airplane (airframe) to technical inspection for the fly-off.",
     "One airframe; repair, no spare (FAQ L1668-1669)", "n/a"),
    ("C84", "4.1", "1144-1147", "Team members will declare the maximum number of Mission 2 shipping container simulators. ... The sensor must be at its maximum weight ... This will be the maximum weight of the sensor for any mission attempt.",
     "Tech declarations: n_sim_max, sensor max", "n/a"),
    ("C85", "4.1", "1149-1153", "All propulsion batteries and battery packs that teams intend to use over the full duration of the competition, including back-up batteries, must be brought to Tech Inspection",
     "Bring every pack and fuse harness to tech", "n/a"),
    ("C86", "4.2.1", "1198-1201", "Verify each hatch or access panel has a positive, mechanical latching method ... Magnets are not an acceptable latching method. Velcro may be an acceptable method depending on the implementation",
     "Spring/pin/screw latches; no magnets", "inspection"),
    ("C87", "4.2.3", "1243-1247", "Verify all propulsion batteries are the same chemistry ... Verify each propulsion battery does not exceed 100 W-hrs ... Verify there is only one battery per propulsion system.",
     "Same chemistry for all packs", "inspection"),
    ("C88", "4.2.4", "1265-1268", "The airplane will be lifted with one lift point at each wing tip with the airplane configured with the maximum weight of payloads and batteries (MGTOW) ... (this is \"roughly\" equivalent to a 2.5g load case) ... Verify the MGTOW does not exceed 55 lbs.",
     "Tip lift points; MGTOW <= 55 lb", "test"),
    ("C89", "4.2.5", "1282-1286", "Verify the propulsion system(s) does not operate with arming plug removed. ... Verify the airplane does not respond to commands with receiver switch OFF and arming plug installed. ... Verify airplane controls respond to commands with",
     "Safing logic", "test"),
    ("C90", "4.2.5", "1288-1302", "Verify fail-safe mode ... Throttle closed ... Full up elevator ... Full right rudder ... Full right aileron ... Full Flaps down ... For airplanes not equipped with a particular control, then the tech inspector must be satisfied that the intended function of the fail-safe system will be carried out.",
     "Per-output fail-safe; structure survives the resulting spiral", "test"),
    ("C91", "4.2.5", "1272-1274", "Teams must put the RC controller in the Range Check (low power) mode while conducting this test.",
     "Range check mode (ELRS has none: Q&A)", "test"),
    ("C92", "6", "1609-1611", "the contest committee reserves the right to ration and/or schedule flights.",
     "Plan for 2-3 attempts", "n/a"),
    ("C93", "6.2", "1631-1641", "times or physical measurements will be rounded to the number of decimal places shown below.",
     "Scoring rounding", "n/a"),
    ("C94", "FAQ A.1", "1668-1669", "If the airplane is damaged on a flight can we use another copy of the airplane which has the same design? Answer: No, you must repair the original airplane.",
     "Repair kit, not a second airframe", "n/a"),
    ("C95", "FAQ A.1", "1670-1673", "You may not change the hardware configuration of the airplane for the different missions unless specifically allowed by the rules for each year (i.e., batteries, payloads, payload support, etc).",
     "Packs and payload support may change between missions", "n/a"),
    ("C96", "FAQ A.2", "1693-1704", "Examples of major configuration changes that will not be allowed ... Tricycle ... tail dragger ... (Conventional tail, T-Tail, V-Tail) ... (Conventional wing, flying wing, blended wing body) ... (Tractor propulsion, pusher propulsion, number of propulsion motors)",
     "Frozen at 19 Feb: gear type, tail type, wing type, tractor/pusher, motor count", "inspection vs drawing"),
    ("C97", "FAQ A.2", "1707-1709", "Variable geometry is allowed provided it is controlled remotely through the RC control system. You may not \"swap out\" parts for different missions.",
     "RC-actuated variable geometry only", "inspection"),
    ("C98", "FAQ A.2", "1710-1714", "You may use a push-pull configuration but must locate the arming plug(s) such that they may be accessed by the crew member without having to reach over or around either propeller or being in the propeller disk plane of either propeller.",
     "Push-pull arming access", "inspection"),
    ("C99", "1.2", "140-142", "The team pilot must be an AMA (Academy of Model Aeronautics) member.",
     "Pilot AMA membership before the fly-off", "n/a"),
]
RULE_BY_ID = {r[0]: r for r in RULES}


# ----------------------------------------------------------------- check()
def _row(cid, status, message, value=None, limit=None):
    r = RULE_BY_ID[cid]
    return {"id": cid, "clause": "Sec. " + r[1], "lines": r[2], "status": status,
            "message": message, "value": value, "limit": limit}


def _bool_check(rows, cid, val, bad_when, msg_bad, msg_missing):
    if val is None:
        rows.append(_row(cid, "UNVERIFIABLE", msg_missing))
    elif bool(val) == bad_when:
        rows.append(_row(cid, "FAIL", msg_bad))
    else:
        rows.append(_row(cid, "PASS", "ok"))


def _check_span(geom, rows):
    lim = LIMITS["span_max_m"]
    b = _num(_get(geom, "span_m", "wing.span_m", "b_m"))
    if b is None:
        rows.append(_row("C01", "UNVERIFIABLE", "span_m missing"))
        return
    if b > lim + EPS:
        rows.append(_row("C01", "FAIL", f"span {b:.4f} m > {lim:.4f} m", b, lim))
        return
    width = _num(_get(geom, "max_width_m", "overall_width_m"))
    tip = str(_get(geom, "wing.tip_device", "tip_device", default="none")).lower()
    cfg = str(_get(geom, "wing.config", "wing_config", default="monoplane")).lower()
    if width is not None and width > lim + EPS:
        rows.append(_row("C01", "RISK", f"projected wing span {b:.4f} m is legal but overall width {width:.4f} m "
                         f"exceeds {lim:.4f} m; 'wingspan' is undefined (Q&A). Fallback: keep all parts inside "
                         f"{lim:.4f} m", width, lim))
    elif tip not in ("none", "", "false") and width is None:
        rows.append(_row("C01", "RISK", f"tip device '{tip}' with no max_width_m: confirm canted winglet or "
                         f"tip-plate lateral extent stays inside {lim:.4f} m (wingspan undefined; Q&A)", b, lim))
    elif lim - b < 0.005:
        rows.append(_row("C01", "WARN", f"span {b:.4f} m within 5 mm of the {lim:.4f} m limit; "
                         f"build tolerance and tape measurement", b, lim))
    else:
        rows.append(_row("C01", "PASS", f"span {b:.4f} m", b, lim))
    if cfg in ("biplane", "box", "joined", "tandem"):
        rows.append(_row("C88", "RISK", f"{cfg}: 'one lift point at each wing tip' (L1265) is undefined for "
                         f"stacked or joined wings; provide hard points at the outboard tip of the main lifting "
                         f"surface and ask Q&A which tip"))


def _attempt_masses(ops):
    return [(a, _num(_get(a, "togw_kg", "mass_kg"))) for a in _as_list(_get(ops, "attempts"))]


def _check_mass(geom, ops, rows):
    lim, disp = LIMITS["togw_lt_kg"], togw_display_limit_kg()
    att = _attempt_masses(ops)
    if not att or all(m is None for _, m in att):
        rows.append(_row("C02", "UNVERIFIABLE", "no attempt TOGW in ops.attempts"))
    for a, m in att:
        if m is None:
            continue
        tag = _get(a, "mission", default="?")
        if m >= lim - EPS:
            rows.append(_row("C02", "FAIL", f"{tag} TOGW {m:.3f} kg is not < {lim:.5f} kg (55 lb)", m, lim))
        elif m >= disp:
            rows.append(_row("C02", "FAIL", f"{tag} TOGW {m:.4f} kg rounds to 55.00 lb (Sec. 6.2)", m, disp))
        elif m > lim - 0.25:
            rows.append(_row("C02", "WARN", f"{tag} TOGW {m:.3f} kg within 0.25 kg of 55 lb", m, lim))
        else:
            rows.append(_row("C02", "PASS", f"{tag} TOGW {m:.3f} kg", m, lim))
    # tip test: declared MGTOW must cover every attempt and the heaviest payload + pack
    tip = _num(_get(ops, "declared.tip_test_mass_kg", "declared.mgtow_kg"))
    if tip is None:
        rows.append(_row("C04", "UNVERIFIABLE", "declared.tip_test_mass_kg missing"))
    else:
        heavy = [m for _, m in att if m is not None]
        if heavy and max(heavy) > tip + EPS:
            rows.append(_row("C04", "FAIL", f"attempt TOGW {max(heavy):.3f} kg exceeds the demonstrated tip-test "
                             f"mass {tip:.3f} kg, which cannot be raised after tech (L584)", max(heavy), tip))
        else:
            rows.append(_row("C04", "PASS", f"tip-test mass {tip:.3f} kg covers all attempts", tip, None))
        if tip >= lim - EPS:
            rows.append(_row("C88", "FAIL", f"tip-test MGTOW {tip:.3f} kg exceeds 55 lb", tip, lim))
        ok_mass = _num(_get(geom, "structure.tip_test_mass_ok_kg", "structure.mgtow_ok_kg"))
        if ok_mass is None:
            rows.append(_row("C03", "UNVERIFIABLE", "structure.tip_test_mass_ok_kg missing (S7)"))
        elif ok_mass + EPS < tip:
            rows.append(_row("C03", "FAIL", f"wing passes the tip test only to {ok_mass:.2f} kg < declared {tip:.2f} kg",
                             ok_mass, tip))
        else:
            rows.append(_row("C03", "PASS", f"structure good to {ok_mass:.2f} kg", ok_mass, tip))
        # the declared tip-test mass must include heaviest payload and heaviest pack (L578-580)
        empty = _num(_get(geom, "mass.empty_kg", "empty_kg"))
        pack = _num(_get(geom, "mass.pack_kg", "propulsion.pack_mass_kg"))
        smax = _num(_get(ops, "declared.sensor_max_kg"))
        cont = _num(_get(geom, "container.mass_kg"))
        nsim = _num(_get(ops, "declared.n_sim_max"))
        if None not in (empty, pack, smax, cont, nsim):
            need = empty + pack + max((1 + nsim) * (cont + smax), smax)
            if need > tip + 1e-3:
                rows.append(_row("C03", "FAIL", f"tip-test mass {tip:.2f} kg < empty + pack + heaviest declared "
                                 f"payload {need:.2f} kg (L578-580)", tip, need))


def _packs(geom):
    packs = _as_list(_get(geom, "propulsion.packs", "packs"))
    if not packs:
        p = _get(geom, "propulsion.pack", "pack")
        n = int(_num(_get(geom, "propulsion.n_systems", default=1)) or 1)
        packs = [p] * n if p else []
    return packs


def _check_power(geom, rows):
    packs = _packs(geom)
    nsys = _num(_get(geom, "propulsion.n_systems", "n_systems"))
    if not packs:
        for cid in ("C37", "C38", "C39", "C34"):
            rows.append(_row(cid, "UNVERIFIABLE", "propulsion.packs missing"))
        return
    nsys = int(nsys) if nsys is not None else len(packs)
    if len(packs) != nsys:
        rows.append(_row("C33", "FAIL", f"{len(packs)} packs listed for {nsys} propulsion systems "
                         f"(one pack per system, L734)", len(packs), nsys))
    else:
        rows.append(_row("C33", "PASS", f"{nsys} system(s), one pack each"))
    whs = [pack_wh(p) for p in packs]
    if any(w is None for w in whs):
        rows.append(_row("C38", "UNVERIFIABLE", "pack rated Wh not derivable (capacity x voltage)"))
    else:
        for i, w in enumerate(whs):
            lim = LIMITS["energy_pack_max_wh"]
            rows.append(_row("C38", "FAIL" if w > lim + EPS else "PASS", f"pack {i}: {w:.2f} Wh", w, lim))
        tot = sum(whs)
        lim = LIMITS["energy_total_max_wh"]
        st = "FAIL" if tot > lim + EPS else ("WARN" if tot > 0.995 * lim else "PASS")
        rows.append(_row("C37", st, f"total rated propulsion energy {tot:.2f} Wh", tot, lim))
    if nsys > 1:
        keys = ("mfr", "part", "chem", "cells", "v_nom", "capacity_ah", "capacity_mah", "c_rating")
        sigs = {tuple(_get(p, k) for k in keys) for p in packs}
        rows.append(_row("C34", "FAIL" if len(sigs) > 1 else "PASS",
                         "packs differ (must be identical, L740-741)" if len(sigs) > 1 else "packs identical"))
    chems = {str(_get(p, "chem", default="")).lower() for p in packs}
    if len(chems) > 1:
        rows.append(_row("C87", "FAIL", f"mixed chemistries {sorted(chems)}"))
    fuses = _as_list(_get(geom, "propulsion.fuse_a", "fuse_a"))
    if not fuses:
        rows.append(_row("C39", "UNVERIFIABLE", "propulsion.fuse_a missing"))
    else:
        if len(fuses) == 1 and nsys > 1:
            fuses = fuses * nsys
        if len(fuses) != nsys:
            rows.append(_row("C36", "FAIL", f"{len(fuses)} fuses for {nsys} systems", len(fuses), nsys))
        for i, (f, p) in enumerate(zip(fuses, packs)):
            lim = fuse_limit_a(p)
            f = _num(f)
            if lim is None or f is None:
                rows.append(_row("C39", "UNVERIFIABLE", f"system {i}: pack continuous rating or fuse unknown"))
            else:
                rows.append(_row("C39", "FAIL" if f > lim + EPS else "PASS",
                                 f"system {i}: fuse {f:.0f} A vs limit {lim:.1f} A", f, lim))


def _prop_planes(geom):
    return [p for p in _as_list(_get(geom, "propulsion.prop_planes", "prop_planes")) if isinstance(p, dict)]


def _check_arming(geom, rows):
    plugs = [p for p in _as_list(_get(geom, "arming_plugs", "propulsion.arming_plugs")) if isinstance(p, dict)]
    nsys = int(_num(_get(geom, "propulsion.n_systems", "n_systems", default=len(plugs) or 1)) or 1)
    if not plugs:
        rows.append(_row("C24", "UNVERIFIABLE", "arming_plugs missing"))
        return
    rows.append(_row("C24", "FAIL" if len(plugs) < nsys else "PASS",
                     f"{len(plugs)} plug(s) for {nsys} system(s)", len(plugs), nsys))
    planes = _prop_planes(geom)
    layout = str(_get(geom, "propulsion.layout", default="")).lower()
    for i, p in enumerate(plugs):
        surf = str(_get(p, "surface", default="")).lower()
        if not surf:
            rows.append(_row("C28", "UNVERIFIABLE", f"plug {i}: surface missing"))
        elif surf not in ("top", "upper"):
            rows.append(_row("C28", "FAIL", f"plug {i} on '{surf}' surface; must be top/upper (L701, L1235)"))
        elif _get(p, "behind_panel", default=False):
            rows.append(_row("C28", "FAIL", f"plug {i} behind a panel or door (L695)"))
        else:
            rows.append(_row("C28", "PASS", f"plug {i} on top, exposed"))
        x = _num(_get(p, "x_m"))
        if x is None or not planes:
            rows.append(_row("C26", "UNVERIFIABLE", f"plug {i}: x_m or prop_planes missing"))
            continue
        dmin = min(abs(x - _num(pl.get("x_m", float("nan"))) if _num(pl.get("x_m")) is not None else float("inf"))
                   for pl in planes)
        half = _num(_get(p, "half_length_m", default=0.0)) or 0.0      # plug body extent along x
        dmin -= half
        lim = LIMITS["arming_min_m"]
        st = "FAIL" if dmin < lim - EPS else ("WARN" if dmin < lim + 0.02 else "PASS")
        rows.append(_row("C26", st, f"plug {i}: {1000 * dmin:.0f} mm from the nearest prop plane "
                         f"(planes extend beyond the airframe, L683)", dmin, lim))
        tractors = [_num(pl.get("x_m")) for pl in planes
                    if str(pl.get("kind", "")).lower() == "tractor" and _num(pl.get("x_m")) is not None]
        pushers = [_num(pl.get("x_m")) for pl in planes
                   if str(pl.get("kind", "")).lower() == "pusher" and _num(pl.get("x_m")) is not None]
        if tractors and pushers:
            between = max(tractors) < x < min(pushers)
            rows.append(_row("C98", "RISK" if between else "FAIL",
                             f"push-pull: plug {i} {'between the prop planes' if between else 'outside the planes'}; "
                             f"crew must not reach over/around either prop nor stand in either disk plane "
                             f"(FAQ L1712-1714); 4.2.2 also bars access 'from the side' (L1231). Q&A or "
                             f"tech-inspector call"))
        elif tractors and x < max(tractors):
            rows.append(_row("C27", "FAIL", f"tractor: plug {i} ahead of a prop plane; must be reachable from behind"))
        elif pushers and x > min(pushers):
            rows.append(_row("C27", "FAIL", f"pusher: plug {i} behind a prop plane; must be reachable from the front"))
        else:
            rows.append(_row("C27", "PASS", f"plug {i} access side ok ({layout or 'layout n/a'})"))


def _check_controls(geom, rows):
    fc = _get(geom, "flight_control", default={}) or {}
    for key, msg in (("autopilot", "autopilot"), ("flight_controller", "flight controller (even in manual mode)"),
                     ("gps", "onboard GPS")):
        if fc.get(key):
            rows.append(_row("C10", "FAIL", f"{msg} aboard (L598-600)"))
    if fc and not any(fc.get(k) for k in ("autopilot", "flight_controller", "gps")):
        if fc.get("gyro"):
            rows.append(_row("C10", "RISK", "gyro stabiliser allowed (L600) only if it is not a flight-controller "
                             "class device; use a stand-alone RC gyro, keep a photo of the part for tech"))
        else:
            rows.append(_row("C10", "PASS", "no FC/autopilot/GPS"))
    elif not fc:
        rows.append(_row("C10", "UNVERIFIABLE", "flight_control block missing"))
    if fc.get("camera") or fc.get("fpv"):
        rows.append(_row("C13", "FAIL", "camera/FPV aboard (L609, FAQ L1733-1734)"))
    tel = str(fc.get("telemetry", "")).lower()
    if tel in ("standalone", "ground_station"):
        rows.append(_row("C12", "FAIL", "stand-alone telemetry link (L605-607)"))
    sw = _get(geom, "rc_switch")
    if sw is None:
        rows.append(_row("C18", "UNVERIFIABLE", "rc_switch missing"))
    elif not sw.get("external", False) or sw.get("under_hatch", False):
        rows.append(_row("C18", "FAIL", "Rx switch must be external, not under a panel or hatch (L647-649)"))
    else:
        rows.append(_row("C18", "PASS", "external Rx switch"))
    _bool_check(rows, "C09", _get(geom, "propulsion.motor_cots_unmodified"), False,
                "motor modified or not COTS (L595-596)", "propulsion.motor_cots_unmodified missing")
    _bool_check(rows, "C14", _get(geom, "propulsion.prop_commercial"), False,
                "non-commercial propeller/fan blades (L617-620)", "propulsion.prop_commercial missing")
    for h in _as_list(_get(geom, "hatches")):
        latch = str(_get(h, "latch", default="")).lower()
        name = _get(h, "name", default="hatch")
        if not latch:
            rows.append(_row("C86", "UNVERIFIABLE", f"{name}: latch type missing"))
        elif "magnet" in latch:
            rows.append(_row("C86", "FAIL", f"{name}: magnets are not an acceptable latch (L1199-1200)"))
        elif "velcro" in latch:
            rows.append(_row("C86", "RISK", f"{name}: Velcro is at the inspector's discretion (L1200-1201); add a pin"))
        else:
            rows.append(_row("C86", "PASS", f"{name}: {latch} latch"))
    for v in _as_list(_get(geom, "variable_geometry")):
        name = _get(v, "name", default="item")
        if not _get(v, "rc_controlled", default=False):
            rows.append(_row("C97", "FAIL", f"{name}: variable geometry must be RC-controlled (FAQ L1708)"))
        elif _get(v, "swapped", default=False):
            rows.append(_row("C97", "FAIL", f"{name}: parts may not be swapped between missions (FAQ L1709)"))
        else:
            rows.append(_row("C97", "PASS", f"{name}: RC-controlled"))
    cfg = str(_get(geom, "wing.config", "wing_config", default="")).lower()
    if cfg in ("rotary", "rotorcraft", "lta", "airship"):
        rows.append(_row("C62", "FAIL", f"{cfg} configurations are excluded (L574)"))


def _check_failsafe(geom, rows):
    ctl = _get(geom, "controls", default={}) or {}
    fs = _get(geom, "failsafe", default=None)
    tail = str(_get(geom, "tail.type", "tail_type", default="")).lower()
    if ctl.get("ruddervator") or tail in ("v", "inverted_v", "y"):
        rows.append(_row("C90", "RISK", "V-tail ruddervators cannot give full up elevator and full right rudder at "
                         "once; L1301-1302 lets the inspector accept the 'intended function'. Set full up with the "
                         "remaining travel to right yaw and ask Q&A; a conventional/T/H tail removes the issue"))
    if ctl.get("elevon"):
        rows.append(_row("C90", "RISK", "elevons cannot give full up and full right aileron at once; same Q&A path"))
    if ctl.get("flaperon"):
        rows.append(_row("C90", "RISK", "flaperons cannot give full flaps down and full right aileron at once"))
    if fs is None:
        rows.append(_row("C90", "UNVERIFIABLE", "failsafe block missing (set per output on the ER8/ER6)"))
        return
    need = {"throttle": "closed", "elevator": "full_up", "rudder": "full_right", "aileron": "full_right",
            "flaps": "full_down"}
    bad = [k for k, v in need.items() if (ctl.get(k, k == "throttle") and str(fs.get(k, "")).lower() != v)]
    if bad:
        rows.append(_row("C90", "FAIL", f"fail-safe outputs wrong for {bad} (L1291-1299)"))
    else:
        rows.append(_row("C90", "PASS", "fail-safe states as L1291-1299"))
    vne = _num(_get(geom, "structure.failsafe_case_ok"))
    if vne is None:
        rows.append(_row("C21", "UNVERIFIABLE", "structure.failsafe_case_ok missing: the fail-safe spiral "
                         "(full up, full flaps, full right roll/yaw, throttle closed) from M2 top speed must not "
                         "exceed flap placard or flutter speed (S5/S7)"))
    elif not vne:
        rows.append(_row("C21", "FAIL", "structure not cleared for the fail-safe load case"))


def _check_payload(geom, ops, rows):
    span = _num(_get(geom, "span_m", "wing.span_m"))
    dr = _get(geom, "dr", default=None)
    if dr is None:
        rows.append(_row("C52", "UNVERIFIABLE", "dr block missing"))
    else:
        if dr.get("internal") is False:
            rows.append(_row("C51", "FAIL", "D&R mechanism must be internal (L497)"))
        if dr.get("permanent") is False:
            rows.append(_row("C51", "FAIL", "D&R must be permanently installed for all missions (L499-500)"))
        dl = _num(dr.get("deploy_length_m"))
        if dl is None or span is None:
            rows.append(_row("C52", "UNVERIFIABLE", "dr.deploy_length_m or span missing"))
        else:
            need = deploy_length_min(span)
            st = "FAIL" if dl < need - EPS else ("WARN" if dl < need + 0.05 else "PASS")
            rows.append(_row("C52", st, f"exit-to-nose {dl:.3f} m vs 1.5 b = {need:.3f} m", dl, need))
        if dr.get("door") is False and dr.get("opening_covered_m1m2"):
            rows.append(_row("C48", "FAIL", "no M3 door, so the opening may not be covered in M1/M2 (L485-486)"))
    sen = _get(geom, "sensor", default=None)
    if sen is None:
        rows.append(_row("C41", "UNVERIFIABLE", "sensor block missing"))
    else:
        ln = _num(sen.get("length_m"))
        lim = LIMITS["sensor_len_min_m"]
        if ln is None:
            rows.append(_row("C41", "UNVERIFIABLE", "sensor.length_m missing"))
        else:
            st = "FAIL" if ln < lim - EPS else ("WARN" if ln < lim + 0.003 else "PASS")
            rows.append(_row("C41", st, f"sensor length {1000 * ln:.1f} mm", ln, lim))
        for k, cid, bad, msg in (("ballast_internal", "C43", False, "ballast must be internal (L448-449)"),
                                 ("fins_fixed", "C44", False, "fins must be fixed, not deployable (L451-453)"),
                                 ("battery_internal", "C47", False, "sensor battery must be internal (L482)"),
                                 ("rx_in_sensor", "C46", True, "the payload Rx may not be in the sensor (L474)"),
                                 ("carried_internal", "C48", False, "sensor must be carried internally (L484)")):
            if k in sen and bool(sen[k]) == bad:
                rows.append(_row(cid, "FAIL", msg))
        nl = _num(sen.get("n_lights"))
        if nl is not None and nl < 3:
            rows.append(_row("C46", "FAIL", f"{int(nl)} lights; three separate lights required (L459)"))
    c = _get(geom, "container", default=None)
    hdecl = _num(_get(ops, "gm.height_in"))
    if hdecl is None and _num(_get(ops, "gm.height_m")) is not None:
        hdecl = _num(_get(ops, "gm.height_m")) / IN
    if c is None:
        rows.append(_row("C57", "UNVERIFIABLE", "container block missing"))
    else:
        if c.get("rect_prism") is False:
            rows.append(_row("C53", "FAIL", "container must be a rectangular prism (L511)"))
        rid, rs = _num(c.get("ring_id_m")), _num(c.get("ring_section_m"))
        if rid is not None and rid < LIMITS["ring_id_min_m"] - EPS:
            rows.append(_row("C56", "FAIL", f"ring ID {1000 * rid:.2f} mm < 12.70 mm", rid, LIMITS["ring_id_min_m"]))
        if rs is not None and rs > LIMITS["ring_section_max_m"] + EPS:
            rows.append(_row("C56", "FAIL", f"ring section {1000 * rs:.3f} mm > 3.175 mm (a 3.2 mm metric ring fails)",
                             rs, LIMITS["ring_section_max_m"]))
        rtb = _num(c.get("ring_to_bottom_m"))
        dims = c.get("dims_m")
        if rtb is None and dims:
            rtb = container_ring_to_bottom(dims, _num(c.get("sling_angle_deg")) or 30.0,
                                           _num(c.get("ring_allow_m")) or RING_OD_M)["worst"]
        lim = LIMITS["ring_to_bottom_lt_m"]
        if rtb is None:
            rows.append(_row("C57", "UNVERIFIABLE", "container dims_m or ring_to_bottom_m missing"))
        elif rtb >= lim - EPS:
            hcap = LIMITS["drop_max_m"] - (rtb - lim)
            st = "RISK" if (hdecl is None or hdecl * IN > hcap + EPS) else "WARN"
            rows.append(_row("C57", st, f"worst ring-to-bottom {1000 * rtb:.0f} mm >= 381 mm: the fixture guarantees "
                             f"60 in only below 381 mm (L538-542); guaranteed height falls to "
                             f"{math.floor(hcap / IN + EPS)} in if the fixture has no spare travel", rtb, lim))
        else:
            rows.append(_row("C57", "PASS", f"worst ring-to-bottom {1000 * rtb:.0f} mm", rtb, lim))
    # simulators
    sim = _get(geom, "simulator", default=None)
    smax = _num(_get(ops, "declared.sensor_max_kg"))
    if sim is not None and c is not None:
        sd, cd = sim.get("dims_m"), c.get("dims_m")
        if sd and cd:
            dev = max(abs(float(a) - float(b)) for a, b in zip(sorted(sd), sorted(cd)))
            rows.append(_row("C59", "FAIL" if dev > LIMITS["sim_size_tol_m"] + EPS else "PASS",
                             f"simulator size deviation {1000 * dev:.2f} mm", dev, LIMITS["sim_size_tol_m"]))
        sm, cm = _num(sim.get("mass_kg")), _num(c.get("mass_kg"))
        if None not in (sm, cm, smax):
            dev = sm - (cm + smax)
            tol = LIMITS["sim_mass_tol_kg"]
            st = "FAIL" if abs(dev) > tol + EPS else ("WARN" if abs(dev) > 0.9 * tol else "PASS")
            rows.append(_row("C60", st, f"simulator {sm:.4f} kg vs unit {cm + smax:.4f} kg ({1000 * dev:+.1f} g)",
                             dev, tol))
        if sim.get("adjustable_ballast") is False:
            rows.append(_row("C60", "WARN", "simulators without adjustable ballast cannot follow a declared "
                             "sensor mass chosen at tech"))
    elif sim is None:
        rows.append(_row("C60", "UNVERIFIABLE", "simulator block missing"))


def _check_ops(geom, ops, rows):
    smax = _num(_get(ops, "declared.sensor_max_kg"))
    nsim_max = _num(_get(ops, "declared.n_sim_max"))
    for a in _as_list(_get(ops, "attempts")):
        mis = str(_get(a, "mission", default="")).upper()
        tto, tl = _num(_get(a, "t_takeoff_s")), _num(_get(a, "t_lap_s"))
        if mis == "M2":
            n = _num(_get(a, "n_sim"))
            if n is not None and nsim_max is not None and n > nsim_max + EPS:
                rows.append(_row("C75", "FAIL", f"M2 flies {int(n)} simulators > declared {int(nsim_max)}", n, nsim_max))
            if tto is not None and tl is not None:
                t = mission_time(tto, tl, LIMITS["m2_laps"])
                st = "FAIL" if t > LIMITS["window_s"] else ("WARN" if t > 0.9 * LIMITS["window_s"] else "PASS")
                rows.append(_row("C76", st, f"M2 {t:.1f} s for 5 laps", t, LIMITS["window_s"]))
        elif mis == "M1":
            if tto is not None and tl is not None:
                t = mission_time(tto, tl, LIMITS["m1_laps"])
                rows.append(_row("C74", "FAIL" if t > LIMITS["window_s"] else "PASS", f"M1 {t:.1f} s", t, 300.0))
        elif mis == "M3":
            ms = _num(_get(a, "sensor_kg"))
            if ms is not None and smax is not None and ms > smax + EPS:
                rows.append(_row("C43", "FAIL", f"M3 sensor {ms:.3f} kg > declared max {smax:.3f} kg", ms, smax))
            laps = _num(_get(a, "laps"))
            if laps is not None and laps < LIMITS["m3_min_laps"]:
                rows.append(_row("C78", "FAIL", f"{int(laps)} M3 laps; the light sequence needs >= 3", laps, 3))
            stow = _num(_get(a, "stow_s", default=0.0)) or 0.0
            if None not in (tto, tl, laps):
                t_noshow = mission_time(tto, tl, laps)
                t_stow = t_noshow + stow
                w = LIMITS["window_s"]
                if t_noshow > w + EPS:
                    rows.append(_row("C79", "FAIL", f"{int(laps)} laps end at {t_noshow:.1f} s > 300 s", t_noshow, w))
                elif t_stow > w + EPS:
                    rows.append(_row("C79", "RISK", f"{int(laps)} laps fit only if the {stow:.1f} s stow may run after "
                                     f"300 s ({t_stow:.1f} s with stow); Q&A", t_stow, w))
                else:
                    rows.append(_row("C79", "PASS", f"{int(laps)} laps + stow end at {t_stow:.1f} s", t_stow, w))
            dep = _num(_get(a, "deploy_s"))
            t_dw = _num(_get(a, "t_to_downwind_marker_s"))
            if dep is not None and t_dw is not None:
                rows.append(_row("C77", "FAIL" if dep > t_dw else "PASS",
                                 f"deploy {dep:.1f} s vs {t_dw:.1f} s available before the first downwind 180",
                                 dep, t_dw))
    hin = _num(_get(ops, "gm.height_in"))
    if hin is not None:
        if abs(hin - round(hin)) > 1e-9 or hin > 60 or hin <= 0:
            rows.append(_row("C80", "FAIL", f"GM height {hin} in is not a whole number of inches in 1-60", hin, 60))
        else:
            rows.append(_row("C80", "PASS", f"GM height {int(hin)} in", hin, 60))
    stg = _get(ops, "staging", default=None)
    if stg is not None:
        if stg.get("opens_hatch_in_box"):
            rows.append(_row("C63", "RISK", "plan opens a hatch inside the staging box; L800-802 says 'no "
                             "adjustments ... such as opening hatches'. Enter with hatches open (reading A) or "
                             "ask Q&A"))
        t = _num(stg.get("t_est_s"))
        if t is not None:
            st = "FAIL" if t > LIMITS["staging_s"] else ("WARN" if t > 0.8 * LIMITS["staging_s"] else "PASS")
            rows.append(_row("C66", st, f"staging estimate {t:.0f} s", t, LIMITS["staging_s"]))
    if _get(geom, "cg_marked") is False:
        rows.append(_row("C05", "FAIL", "loaded and empty CG must be marked on the exterior (L582)"))


def check(geom, ops=None, verbose=False):
    """Compliance of one aircraft (geom) and its operating plan (ops) with the 2027 draft.

    Never raises on missing or malformed keys: those come back as UNVERIFIABLE rows.
    Returns the non-PASS rows (all rows with verbose=True)."""
    geom = geom if isinstance(geom, dict) else {}
    ops = ops if isinstance(ops, dict) else {}
    rows = []
    for fn, args in ((_check_span, (geom, rows)), (_check_mass, (geom, ops, rows)), (_check_power, (geom, rows)),
                     (_check_arming, (geom, rows)), (_check_controls, (geom, rows)),
                     (_check_failsafe, (geom, rows)), (_check_payload, (geom, ops, rows)),
                     (_check_ops, (geom, ops, rows))):
        try:
            fn(*args)
        except Exception as exc:              # tolerant by contract: report, do not crash
            rows.append({"id": "C00", "clause": "-", "lines": "-", "status": "UNVERIFIABLE",
                         "message": f"{fn.__name__} could not run: {type(exc).__name__}: {exc}",
                         "value": None, "limit": None})
    return rows if verbose else [r for r in rows if r["status"] != "PASS"]


def summary(rows):
    """Counts by status."""
    out = {}
    for r in rows:
        out[r["status"]] = out.get(r["status"], 0) + 1
    return out
