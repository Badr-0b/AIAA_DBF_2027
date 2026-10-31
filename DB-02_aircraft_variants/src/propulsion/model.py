"""S6 propulsion model for the DB-02 variant study (written 29 Oct 2026).

Builds on REPO/analysis (s3b_propulsion: APC prop tables, T-Motor measured maps, pack model,
ERAU 2023 flight calibration k_fl) and adds: a verified fuse table, a system catalogue with
per-system fuse caps, take-off, margins at heavier gross masses, twin layout effects (engine-out
yaw, slipstream credit), gear height from the prop diameter, and a thermal check.

Import-safe: nothing is run or written on import. Analysis modules are imported lazily and
read-only (no main() is ever called). SI units; grade tags: verified / reseller / estimate /
computed.

API (brief section 8):
    system(name, v_check="mid") -> PropSystem  (adapter contract: model, p_batt(thrust_N, V),
        pack_kg, wh, motor_mass_delta_kg, layout_penalties, i_max, fuse_a, prop_diameter_m,
        draw_factors, t_takeoff_s, static_thrust_n)
    catalogue() -> list of dict
    margins(system, m_gross_kg, S, aero, ...) -> dict
"""
from __future__ import annotations

import math
import sys
from functools import lru_cache
from pathlib import Path

sys.dont_write_bytecode = True

W = Path(__file__).resolve().parents[2]
REPO = W.parent
ANALYSIS = REPO / "analysis"
G0 = 9.80665
SPAN_M = 1.82
RHO = 1.064
TIME_CAL = 1.15          # DB-01 lap/mission time factor (sizing.toml [calibration], 24 measured pairs)


def _d():
    """Lazy, read-only import of the DB-01 analysis modules."""
    if str(ANALYSIS) not in sys.path:
        sys.path.insert(0, str(ANALYSIS))
    import numpy as np
    import common
    import s1_course as s1
    import s3_performance as s3
    import s3b_propulsion as pb
    import s4_sizing as s4

    class NS:
        pass
    ns = NS()
    ns.np, ns.common, ns.s1, ns.s3, ns.pb, ns.s4 = np, common, s1, s3, pb, s4
    ns.PR = common.load("propulsion")
    ns.V_START = ns.PR["battery"]["v_oc_start"]
    ns.V_END = ns.PR["battery"]["v_oc_end"]
    ns.V_MID = 0.5 * (ns.V_START + ns.V_END)
    return ns


@lru_cache(maxsize=1)
def D():
    return _d()


# ---------------------------------------------------------------- fuse truth (S6-R01..R06)
RULE_FUSE_QUOTES = {
    "type": ("The fuse must be a blade style fuse as shown in Figure 5. The fuse must be in a separate fuse harness "
             "between the battery and arming plug.", "rules draft 2 Sep 2026, layout text L754-755"),
    "rating": ("The maximum current rating for the fuse is the maximum continuous discharge current rating of the "
               "battery pack (battery capacity * C-rating or maximum labeled discharge current) up to 100 amps.",
               "rules draft 2 Sep 2026, layout text L776-777"),
    "per_system": ("Each battery/propulsion system is required to have its own fuse and arming plug.",
                   "rules draft 2 Sep 2026, layout text L750"),
    "voltage": ("(none) The rules state no voltage rating for the fuse. Figure 5 shows a '100 Amp Blade Style Fuse' "
                "and a '100 Amp Fuse Holder'.", "searched the layout text for 'volt': only pack-label and Wh lines"),
}

FUSES = [
    dict(id="littelfuse-0299-maxi-32v", maker="Littelfuse", series="MAXI 0299 (ZXNV / TXN / L)", v_dc=32.0,
         amps=[20, 25, 30, 35, 40, 50, 60, 70, 80], interrupt_a=1000.0, grade="verified", date="2026-10-29",
         source="Littelfuse datasheet 'MAXI Blade Fuse Rated 32V' (Voltage Rating 32 VDC; 1000 A @ 32 VDC; ratings 20-80 A), "
                "read as PDF via static.chipdip.ru/lib/649/DOC028649404.pdf and Mouser-hosted copy (static.chipdip.ru/lib/536/DOC011536979.pdf)"),
    dict(id="littelfuse-0max100-smartglow", maker="Littelfuse", series="MAXI Smart Glow 0MAX0xx.X (only 100 A MAXI found)",
         v_dc=32.0, amps=[20, 30, 40, 50, 60, 70, 80, 100], interrupt_a=1000.0, grade="verified", date="2026-10-29",
         source="Littelfuse 'Indicator MAXI Smart Glow fuse, Rated 32 V DC', rev 5/03/2023 (colour table lists 100 A Purple); "
                "Digikey keyword listing: 0MAX100.HXGLO and 0MAX100.XPGLO, 100 A, 32 V DC, series MAXI"),
    dict(id="littelfuse-0899-maxi+-32v", maker="Littelfuse", series="MAXI+ 899", v_dc=32.0, amps=[20, 25, 30, 35, 40, 50, 60],
         interrupt_a=1000.0, grade="reseller", date="2026-10-29",
         source="littelfuse.com series page 899 (search-engine text: 'Voltage Rating 32 VDC', ratings 20-60 A); page itself returned HTTP 403"),
    dict(id="littelfuse-0999-maxi-58v", maker="Littelfuse", series="MAXI 58V 0999 Slo-Blo", v_dc=58.0,
         amps=[20, 25, 30, 35, 40, 50, 60, 80], interrupt_a=1000.0, grade="reseller", date="2026-10-29",
         source="Digikey 0999080-ZXN listing (80 A, 58 V DC, 1 kA breaking capacity, series MAXI, fetched 29 Oct 2026); "
                "Littelfuse series page text via search: ratings 20 A to 80 A, 1 kA at 58 V dc (page HTTP 403). "
                "The prior note 'MAXI 58V reportedly 20-80 A only' is CONFIRMED for Littelfuse"),
    dict(id="eska-343.400-58v", maker="ESKA", series="343.400-58V maxi blade (order 369086 = 100 A, purple)", v_dc=58.0,
         amps=[20, 25, 30, 40, 50, 60, 70, 80, 100], interrupt_a=1000.0, grade="reseller", date="2026-10-29",
         source="ESKA datasheet (Okt-20) as summarised by a web search of soselectronic.com listings: 58 V, 20-100 A, "
                "breaking capacity 1000 A, SAE J1888/J2576, ISO 8820-3, 29 x 8.9 x 21.6 mm; 100 A 'available on request'. "
                "Datasheet PDF itself HTTP 403 - NOT read by us; stock and lead time unknown"),
]
EXCLUDED_FUSES = [
    dict(id="imaxx-mdp100", why="RS Components / Distrelec 100 A 58 V part: Distrelec calls it an M5 bolt-down fuse, "
                                "so it is not a blade fuse (rules Fig. 5)."),
    dict(id="littelfuse-midi-mega", why="MIDI/MEGA fuses are bolt-down, not blade; rules require a blade fuse."),
]


def fuse_options(cells: int, i_cap_a: float):
    """Blade fuses whose DC rating covers a fully charged pack (4.2 V/cell) and whose ampere
    rating is <= the system cap (min of 100 A and the pack's continuous rating, rules L776-777).
    Returns (rated, unrated): rated = voltage-rated parts, with the highest usable ampere rating;
    unrated = best part if the 32 V parts are used above 32 V."""
    v_max = 4.2 * cells
    rated, over = [], []
    for f in FUSES:
        a = max([x for x in f["amps"] if x <= i_cap_a + 1e-9], default=None)
        if a is None:
            continue
        row = dict(id=f["id"], amps=a, v_dc=f["v_dc"], grade=f["grade"], v_pack_max=v_max)
        (rated if f["v_dc"] >= v_max else over).append(row)
    best = lambda L: max(L, key=lambda r: r["amps"], default=None)
    return {"v_pack_max": v_max, "rated_best": best(rated), "over_voltage_best": best(over), "rated": rated, "over": over}


# ---------------------------------------------------------------- catalogue
# Every entry: motor (T-Motor measured map), APC prop, pack id (components.toml) or an explicit
# ESTIMATE pack, n systems, fuse ampere rating chosen per system.
HYP_PACKS = {   # NOT catalogue parts: sensitivity only. Mass from TP2250-6SR70 specific energy (347 g / 49.95 Wh).
    "hyp-8s-1650": dict(name="HYPOTHETICAL 8S 1650 mAh 70C (estimate)", cells=8, cap_ah=1.65, i_max=115.5,
                        mass=0.347 / 49.95 * 8 * 3.7 * 1.65, grade="estimate"),
    "hyp-12s-1100": dict(name="HYPOTHETICAL 12S 1100 mAh 70C (estimate)", cells=12, cap_ah=1.10, i_max=77.0,
                         mass=0.347 / 49.95 * 12 * 3.7 * 1.10, grade="estimate"),
}
TWIN_LAYOUT = dict(mass_kg=0.15, f_m2=0.002, grade="estimate",
                   note="DB-01 propulsion.toml [layout]: second ESC, fuse harness, plug, wiring 0.15 kg; two faired "
                        "nacelles +20 cm2 drag area; sweeps 0.10-0.20 kg and 10-40 cm2")

CAT = {
    "8s": dict(motor=("tmotor-at7215", "KV270"), prop="20x15E", pack="tp3300-8se55", n=1, fuse=100.0,
               note="DB-01 best. 100 A needs a 32 V-rated MAXI used at 33.6 V, or the 58 V ESKA 100 A part"),
    "8s_f80": dict(motor=("tmotor-at7215", "KV270"), prop="20x15E", pack="tp3300-8se55", n=1, fuse=80.0,
                   note="same system with the only Littelfuse 58 V part that exists at >= 80 A (0999080)"),
    "8s_205": dict(motor=("tmotor-at7215", "KV270"), prop="205x14E", pack="tp3300-8se55", n=1, fuse=100.0),
    "8s_21": dict(motor=("tmotor-at7215", "KV270"), prop="21x13E", pack="tp3300-8se55", n=1, fuse=100.0),
    "8s_22": dict(motor=("tmotor-at7215", "KV270"), prop="22x12E", pack="tp3300-8se55", n=1, fuse=100.0),
    "8s_mx": dict(motor=("tmotor-at7215", "KV270"), prop="20x15E", pack="maxamps-8s-3250", n=1, fuse=74.0,
                  note="MaxAmps 3250 8S: 74.75 A continuous, so fuse <= 74 A (rules)"),
    "12s": dict(motor=("tmotor-at7215", "KV200"), prop="20x15E", pack="maxamps-12s-2000", n=1, fuse=54.0,
                note="DB-01 12S; pack is 54 A continuous so the 100 A fuse is not allowed; 54 A part fits 58 V MAXI"),
    "12s_7224": dict(motor=("tmotor-at7224", "KV160"), prop="20x15E", pack="maxamps-12s-2000", n=1, fuse=54.0),
    "13s": dict(motor=("tmotor-at8020", "KV180"), prop="20x15E", pack="maxamps-13s-2000", n=1, fuse=54.0),
    "twin": dict(motor=("tmotor-at4130", "KV450"), prop="14x14E", pack="tp2250-6sr70", n=2, fuse=100.0,
                 layout=TWIN_LAYOUT, note="DB-01 twin (each pack 49.95 Wh, own 100 A fuse)"),
}


class PropSystem:
    """A Script 3b System wrapped to the adapter contract (S12_adapter.md section 3)."""

    def __init__(self, name, spec, v_check="mid", system=None):
        d = D()
        pb = d.pb
        self.name, self.spec, self.v_check_name = name, spec, v_check
        if system is not None:
            mot, pack = system.motor, system.battery
            self.pack_grade = "reseller"
        else:
            mot = pb.MapMotor(*spec["motor"])
        if system is not None:
            pass
        elif "hyp_pack" in spec:
            h = HYP_PACKS[spec["hyp_pack"]]
            pack = pb.Battery(h["name"], h["cells"], h["cap_ah"], h["mass"], h["i_max"])
            self.pack_grade = "estimate"
        else:
            pack = pb.Battery.from_components(spec["pack"])
            self.pack_grade = "reseller"
        self.system = system if system is not None else pb.System(pb.Prop(spec["prop"]), mot, pack, n=spec["n"],
                                                                  fuse_a=spec["fuse"])
        self.rho = RHO
        self.k_fl = k_fl()
        v = {"mid": d.V_MID, "end": d.V_END, "start": d.V_START}[v_check]
        self._v_check = v
        self.n_systems = spec["n"]
        self.pack_kg = pack.mass * spec["n"]
        self.wh = pack.energy_wh * spec["n"]
        self.motor_mass_delta_kg = mot.mass * spec["n"] - d.PR["mass"]["motor_ref_kg"]
        lay = spec.get("layout")
        self.layout_penalties = {"mass_kg": lay["mass_kg"], "f_m2": lay["f_m2"]} if lay else {"mass_kg": 0.0, "f_m2": 0.0}
        self.i_max = self.system.i_cap
        self.fuse_a = spec["fuse"]
        self.prop_diameter_m = self.system.prop.D
        self.draw_factors = True
        self.t_takeoff_s = None
        self._model = None
        self._static = None

    @property
    def model(self):
        if self._model is None:
            self._model = D().pb.PropulsionModel(self.system, self.rho, self.k_fl, v_check=self._v_check)
        return self._model

    @property
    def static_thrust_n(self):
        if self._static is None:
            self._static = float(self.system.thrust_max(self.rho, 0.0, D().V_START, iters=30))
        return self._static

    def p_batt(self, thrust, v):
        return self.model.p_batt(thrust, v)

    def thrust(self, v, v_batt=None):
        return self.model.t_max(v)

    @property
    def cells(self):
        return self.system.battery.cells

    def fuse_info(self):
        return fuse_options(self.cells, min(100.0, self.system.battery.i_max))

    def label(self):
        s = self.system
        return (f"{s.n}x {s.motor.name.replace('T-Motor ', '')} / APC {s.prop.name} / {s.battery.cells}S "
                f"{1000 * s.battery.capacity:.0f} mAh")


@lru_cache(maxsize=1)
def k_fl():
    return D().pb.calibrate_flight()["k_fl"]


@lru_cache(maxsize=None)
def system(name, v_check="mid"):
    if name not in CAT:
        raise KeyError(name)
    return PropSystem(name, CAT[name], v_check)


def from_objects(name, sys3b, fuse=None, layout=None, v_check="mid"):
    """Wrap a prebuilt Script 3b System (used by the searches)."""
    spec = dict(n=sys3b.n, fuse=fuse if fuse is not None else sys3b.i_cap)
    if layout:
        spec["layout"] = layout
    return PropSystem(name, spec, v_check, system=sys3b)


def custom(motor, prop, pack, n=1, fuse=100.0, layout=None, hyp_pack=None, name=None, v_check="mid"):
    spec = dict(motor=motor, prop=prop, pack=pack, n=n, fuse=fuse)
    if layout:
        spec["layout"] = layout
    if hyp_pack:
        spec["hyp_pack"] = hyp_pack
    return PropSystem(name or f"{n}x{motor[1]}/{prop}/{hyp_pack or pack}", spec, v_check)


def catalogue():
    out = []
    for k, spec in CAT.items():
        s = system(k)
        out.append(dict(name=k, label=s.label(), cells=s.cells, n=s.n_systems, wh=round(s.wh, 1), pack_kg=round(s.pack_kg, 3),
                        motor_kg=round(s.system.motor.mass, 3), fuse_a=s.fuse_a, i_cap_a=round(s.i_max, 1),
                        static_thrust_n=round(s.static_thrust_n, 1), prop_d_m=round(s.prop_diameter_m, 4),
                        layout=s.layout_penalties, note=spec.get("note", "")))
    return out


# ---------------------------------------------------------------- aero helper (ledger-accepted)
def accepted_aero(S, flap="slotted", e=0.90):
    """Ledger 05_LEDGER.md (29 Oct): e 0.90; trimmed CLmax plain 1.44 / slotted 1.62 (+0.12 kg) / Fowler 1.92 (+0.30 kg);
    clean CLmax 1.19; central CD0 = DB-01's 0.0086 + 0.013/S."""
    cl, dm = {"plain": (1.44, 0.0), "slotted": (1.62, 0.12), "fowler": (1.92, 0.30)}[flap]
    return {"cd0_parts": {"wing": 0.0086, "body": 0.013 / S, "tail": 0.0, "gear": 0.0, "other": 0.0}, "e": e,
            "clmax_landing": cl, "clmax_clean": 1.19, "clmax_turn_avail": 1.19, "mass_delta_kg": dm, "span_m": SPAN_M}


def _cd0(aero, tow_m2=0.0, S=None):
    if "cd0_parts" in aero:
        c = sum(aero["cd0_parts"].values())
    else:
        c = aero["cd0"]
    return c + (tow_m2 / S if tow_m2 else 0.0)


# ---------------------------------------------------------------- take-off
@lru_cache(maxsize=64)
def _tmax_curve(sysname, v_cell, rho, key=None, _sys=None):
    np = D().np
    s = _sys if _sys is not None else system(sysname)
    v = np.arange(0.0, 41.0, 1.0)
    return v, s.system.thrust_max(rho, v, v_cell, iters=34)


def takeoff(ps: PropSystem, m, S, aero, mu=0.04, v_race=None, rho=RHO, h_clear=3.0, power_credit=1.0, dt=0.02):
    """Take-off from the first throttle advance to race speed (computed).
    Ground roll: full throttle from rest to V_LOF = 1.2 Vs (landing-flap CLmax, no lift credit before
    rotation, rolling mu = 0.04 ESTIMATE from propulsion.toml), thrust from the 3b map at a fresh pack
    (4.15 V/cell). Then climb-out and acceleration to v_race gaining h_clear metres, using the surplus
    power (T - D) V of the same thrust curve. Returns roll time/distance and total clock to race speed."""
    d = D()
    np = d.np
    cd0 = _cd0(aero)
    clf = aero["clmax_landing"]
    ar = aero.get("span_m", SPAN_M) ** 2 / S
    k = 1.0 / (math.pi * aero["e"] * ar)
    v_lof = 1.2 * math.sqrt(2 * m * G0 / (rho * S * clf))
    vv, tt = _tmax_curve(ps.name, d.V_START, rho, None, ps)
    thr = lambda v: float(np.interp(v, vv, tt)) * power_credit
    v, x, t = 0.0, 0.0, 0.0
    while v < v_lof and t < 40:
        a = (thr(v) - 0.5 * rho * v * v * S * cd0 - mu * m * G0) / m
        if a <= 0:
            return {"ok": False, "roll_s": math.inf, "roll_m": math.inf, "to_total_s": math.inf, "v_lof": v_lof}
        v, x, t = v + a * dt, x + v * dt, t + dt
    roll_t, roll_x = t, x
    vr = max(v_race if v_race else 28.0, v_lof)
    e_need = m * G0 * h_clear + 0.5 * m * (vr * vr - v_lof * v_lof)
    e_done, ts = 0.0, 0.0
    while e_done < e_need and ts < 40:
        vc = v_lof + (vr - v_lof) * (e_done / e_need)
        cl = m * G0 / (0.5 * rho * vc * vc * S)
        dr = 0.5 * rho * vc * vc * S * (cd0 + k * cl * cl)
        sur = thr(vc) - dr
        if sur <= 0:
            return {"ok": False, "roll_s": roll_t, "roll_m": roll_x, "to_total_s": math.inf, "v_lof": v_lof}
        e_done += sur * vc * dt
        ts += dt
    return {"ok": True, "roll_s": roll_t, "roll_m": roll_x, "to_total_s": roll_t + ts, "v_lof": v_lof, "climb_s": ts}


# ---------------------------------------------------------------- M2 / M3 margins
def _grid():
    np = D().np
    v = np.arange(14.0, 42.01, 0.25)
    b = np.arange(40.0, 80.01, 1.0)
    return v[:, None], b[None, :]


def _lap_arrays(ps, m, S, aero, tow_m2=0.0, rho=RHO):
    d = D()
    np, s3 = d.np, d.s3
    V, B = _grid()
    ar = aero.get("span_m", SPAN_M) ** 2 / S
    k = 1.0 / (math.pi * aero["e"] * ar)
    cd0 = _cd0(aero, tow_m2, S)
    t_lap, p_mean_sh, n, cl = s3.lap(rho, V, B, S, cd0, k, m, G0)
    r = d.s1.turn_radius(V, B, G0)
    turns = d.s1.TURN_ARC * r
    straight = d.s1.lap_length(r, d.s1.STRAIGHTS_M) - turns
    d1 = s3.drag(rho, V, S, cd0, k, m, 1.0, G0)
    dn = s3.drag(rho, V, S, cd0, k, m, n, G0)
    mod = ps.model
    tf = getattr(mod, "thrust_factor", 1.0)
    p1 = mod.p_batt(d1, V)
    pn = mod.p_batt(dn, V)
    p_mean = (p1 * straight + pn * turns) / (straight + turns)        # k_fl inside p_batt
    return dict(V=V, B=B, t_lap=t_lap * TIME_CAL, t_lap_raw=t_lap, n=n, cl=cl, d1=d1, dn=dn, p1=p1, pn=pn, p_mean=p_mean,
                k=k, cd0=cd0, ar=ar)


def margins(ps: PropSystem, m_gross_kg, S, aero, mission="M2", usable=0.80, vs_max=None, n_struct=4.0,
            cl_margin=0.80, t_to=None, laps=5, n_laps_m3=None, stow_s=20.0, n_stow=2, m3_window_s=300.0,
            tow_m2=0.008, rho=RHO, go_around_climb_s=15.0):
    """Thrust, power and energy margins of propulsion system `ps` at gross mass m_gross_kg (computed).

    M2: fastest feasible (V, bank) for 5 laps, subject to n <= n_struct, turn CL <= cl_margin x
    clmax_turn_avail, turn thrust inside the full-throttle thrust at the pack voltage of `ps` (build
    the system with v_check="end" for the end-of-pack worst case), optional stall bound vs_max, and
    the lap-mean energy inside `usable` x rated Wh (s4 convention: power x (t_to + laps t_lap) x 1.15).
    A go-around reserve is added afterwards: one more lap at the lap-mean power plus go_around_climb_s
    of turn-level power (ESTIMATE of the abort-and-recircuit).
    M3: fewest-energy (V, bank) that fits n_laps_m3 laps + n_stow stow attempts (stow_s each) in the window.
    """
    d = D()
    np = d.np
    A = _lap_arrays(ps, m_gross_kg, S, aero, tow_m2 if mission == "M3" else 0.0, rho)
    clt = aero.get("clmax_turn_avail", aero["clmax_clean"])
    vstall = math.sqrt(2 * m_gross_kg * G0 / (rho * S * aero["clmax_landing"]))
    toff = takeoff(ps, m_gross_kg, S, aero, rho=rho, v_race=24.0)
    t_to_use = t_to if t_to is not None else (toff["to_total_s"] if toff["ok"] else 15.0)
    V, t_lap, p_mean = A["V"], A["t_lap"], A["p_mean"]
    c_n = A["n"] <= n_struct + 1e-9
    c_cl = A["cl"] <= cl_margin * clt + 1e-9
    c_thr = np.isfinite(A["pn"]) & np.isfinite(A["p1"])
    c_st = np.broadcast_to(vstall <= vs_max + 1e-9, c_n.shape) if vs_max else np.ones_like(c_n)
    e_cap = usable * ps.wh
    if mission == "M2":
        clock = t_to_use + laps * t_lap
        e_wh = p_mean * clock / 3600.0
        figure = clock
        c_e = e_wh <= e_cap
    else:
        nl = n_laps_m3
        lap_win = (m3_window_s - t_to_use * TIME_CAL - n_stow * stow_s) / nl
        c_win = t_lap <= lap_win
        e_wh = (p_mean * (t_to_use + nl * A["t_lap_raw"]) * TIME_CAL + n_stow * stow_s * A["p1"]) / 3600.0
        figure = e_wh
        c_e = e_wh <= e_cap
    allc = {"load_factor": c_n, "turn_CL": c_cl, "thrust": c_thr, "stall": c_st, "energy": c_e}
    if mission == "M3":
        allc["window"] = c_win
    ok = np.ones_like(c_n)
    for c in allc.values():
        ok = ok & c
    out = {"mission": mission, "system": ps.name, "m_gross_kg": m_gross_kg, "S": S, "v_stall_ms": vstall,
           "takeoff": toff, "t_to_used_s": t_to_use, "energy_cap_wh": e_cap}
    if not ok.any():
        blockers = []
        for kname in allc:
            others = np.ones_like(c_n)
            for k2, c in allc.items():
                if k2 != kname:
                    others = others & c
            if others.any():
                blockers.append(kname)
        out.update(feasible=False, binding=blockers or ["several"])
        if "energy" in blockers:                          # least-energy point that meets every other limit
            noe = np.ones_like(c_n)
            for k2, c in allc.items():
                if k2 != "energy":
                    noe = noe & c
            ee = np.where(noe, np.broadcast_to(e_wh, noe.shape), np.inf)
            j = np.unravel_index(np.argmin(ee), ee.shape)
            out.update(e_min_wh=float(ee[j]), e_min_frac_rated=float(ee[j]) / ps.wh, v_at_e_min=float(A["V"][j[0], 0]),
                       bank_at_e_min=float(A["B"][0, j[1]]),
                       clock_at_e_min_s=float(np.broadcast_to(figure if mission == "M2" else t_lap, noe.shape)[j]))
        return out
    score = np.where(ok, figure, np.inf)
    i = np.unravel_index(np.argmin(score), score.shape)
    v, bk = float(A["V"][i[0], 0]), float(A["B"][0, i[1]])
    pick = lambda a: float(np.broadcast_to(a, score.shape)[i])
    dn, d1 = pick(A["dn"]), pick(A["d1"])
    # end-of-pack checks on the full-throttle limit of this system's own check voltage and at 3.70 V/cell
    pt_end = ps.system.point(rho, dn, v, d.V_END)
    pt_start = ps.system.point(rho, dn, v, d.V_START)
    tmax_end = float(ps.system.thrust_max(rho, v, d.V_END, iters=34))
    tmax_mid = float(ps.system.thrust_max(rho, v, d.V_MID, iters=34))
    pack = ps.system.battery
    i_t_end = float(pt_end["i"])
    volts_end = float(pt_end["volts"])
    p_avail_end = ps.system.n * volts_end * min(ps.system.i_cap, 1e9) if False else None
    # electrical power at full current cap and end-of-pack voltage (per system, x n)
    v_cap = pack.volts(ps.system.i_cap, d.V_END)
    p_cap_end = ps.system.n * v_cap * ps.system.i_cap
    res = dict(v=v, bank=bk, n=pick(A["n"]), cl_turn=pick(A["cl"]), t_lap_s=pick(A["t_lap"]), d_straight_n=d1, d_turn_n=dn,
               p_straight_w=pick(A["p1"]), p_turn_w=pick(A["pn"]), p_mean_w=pick(A["p_mean"]),
               tmax_end_n=tmax_end, tmax_mid_n=tmax_mid, thrust_margin_end=tmax_end / dn - 1.0,
               thrust_margin_mid=tmax_mid / dn - 1.0, turn_ok_end=bool(pt_end["ok"]), i_turn_end_a=i_t_end,
               i_cap_a=ps.system.i_cap, i_margin_end=1.0 - i_t_end / ps.system.i_cap if i_t_end == i_t_end else float("nan"),
               volts_turn_end_v=volts_end,
               volt_margin_end=(float(pt_end["volts"]) - float(ps.system.motor.volts_needed(
                   float(pt_end["rpm"]) * d.pb.RPM_TO_RAD, float(pt_end["q"]), i_t_end))) / float(pt_end["volts"]),
               p_cap_end_w=p_cap_end, power_margin_end=p_cap_end / pick(A["pn"]) - 1.0,
               static_thrust_n=ps.static_thrust_n, tw_static=ps.static_thrust_n / (m_gross_kg * G0))
    out.update(feasible=True, **res)
    # energy bookkeeping
    if mission == "M2":
        clock = t_to_use + laps * res["t_lap_s"]
        e_m2 = res["p_mean_w"] * clock / 3600.0
        e_res = (res["p_mean_w"] * res["t_lap_s"] + res["p_turn_w"] * go_around_climb_s) / 3600.0
        out.update(m2_clock_s=clock, e_m2_wh=e_m2, e_reserve_wh=e_res, e_total_wh=e_m2 + e_res,
                   frac_of_rated=(e_m2 + e_res) / ps.wh,
                   usable_needed={f"{u:.2f}": (e_m2 + e_res) / ps.wh <= u for u in (0.80, 0.85, 0.90)},
                   e_pass_m2_only={f"{u:.2f}": e_m2 / ps.wh <= u for u in (0.80, 0.85, 0.90)})
    else:
        out.update(laps=n_laps_m3, e_m3_wh=pick(e_wh), frac_of_rated=pick(e_wh) / ps.wh,
                   usable_needed={f"{u:.2f}": pick(e_wh) / ps.wh <= u for u in (0.80, 0.85, 0.90)})
    return out


# ---------------------------------------------------------------- twin effects
def engine_out(m, S, b, y_m, thrust_one_n, v, s_v, l_v, cl_alpha_v=3.0, tau=0.5, dr_max_rad=math.radians(25),
               windmill_cd_a=0.0, rho=RHO):
    """One-engine-out yaw balance (computed, geometry ESTIMATE): yaw moment of the remaining motor at lever arm y plus
    the windmilling drag of the dead prop, against rudder moment q S_v a_v tau dr_max l_v. Returns the ratio
    rudder/needed (>1 = controllable) and the minimum control speed where the ratio crosses 1."""
    import numpy as np
    vv = np.arange(8.0, 40.0, 0.1)
    q = 0.5 * rho * vv ** 2
    n_need = (thrust_one_n + q * windmill_cd_a) * y_m
    n_rud = q * s_v * cl_alpha_v * tau * dr_max_rad * l_v
    ratio = n_rud / n_need
    ok = vv[ratio >= 1.0]
    return {"vmc_ms": float(ok[0]) if len(ok) else math.inf, "yaw_moment_nm": float(thrust_one_n * y_m),
            "ratio_at_20ms": float(np.interp(20.0, vv, ratio))}


def slipstream_clmax_factor(thrust_total_n, v, d_prop_m, n_props, b, fuse_w_m=0.20, rho=RHO, centerline=False):
    """Momentum-theory slipstream credit on the wing CL capacity (computed, UPPER BOUND): the immersed strip carries
    q_s/q times the free-stream lift; q_s/q = 1 + 2 T_i/(rho A V^2) per prop (actuator disc, fully developed
    far-field value). Factor = 1 + f_imm (q_s/q - 1). Ignores contraction, swirl, flap interaction, and
    the tail. For a centreline tractor the strip covered by the fuselage is not counted."""
    A = math.pi * d_prop_m ** 2 / 4.0
    ti = thrust_total_n / n_props
    qr = 1.0 + 2.0 * ti / (rho * A * v * v)
    width = n_props * d_prop_m - (fuse_w_m if centerline else 0.0)
    f_imm = max(0.0, width) / b
    return 1.0 + f_imm * (qr - 1.0), f_imm, qr


# ---------------------------------------------------------------- installation
def gear_height(prop_d_m, l_prop_to_main_m=1.0, c_margin_m=0.05, strut_compress_m=0.03, pitch_down_deg=2.0,
                axis_above_belly_m=0.16):
    """Ground clearance of a nose tractor prop (computed from stated ESTIMATE parameters).
    Worst case is NOT rotation (the nose rises about the mains) but the nose-down roll-out or a nose-strut
    collapse: tip clearance c = margin + strut compression + L tan(pitch-down). Prop axis height
    h_axis = R + c. Strut length under the belly (nose gear, and the main gear for a level stance)
    = h_axis - axis_above_belly. Arming plug: >= 152.4 mm behind the prop plane (rules L681)."""
    R = prop_d_m / 2.0
    c = c_margin_m + strut_compress_m + l_prop_to_main_m * math.tan(math.radians(pitch_down_deg))
    h_axis = R + c
    return dict(prop_d_m=prop_d_m, tip_clearance_m=c, axis_height_m=h_axis, strut_length_m=h_axis - axis_above_belly_m,
                arming_plug_min_offset_m=0.1524)


# ---------------------------------------------------------------- thermal
# T-Motor AT7215 KV220 + APC 19*10 at 100 % throttle, 12S (manufacturer table, tmotor-at7215 page, read 14 Oct 2026):
# 40.12 V, 87.84 A, 3523.62 W in, 7450 rpm, 3.739 N m; "Motor temperature is motor surface temperature at 100 %
# throttle running 3 mins" = 89 C, ambient "/" (not stated). Loss = P_in - Q w (includes the test ESC).
TM_REF = dict(p_in=3523.62, rpm=7450.0, q=3.739, t_surface_c=89.0, t_amb_assumed_c=25.0)
TM_REF["loss_w"] = TM_REF["p_in"] - TM_REF["q"] * TM_REF["rpm"] * math.pi / 30.0


def thermal(ps: PropSystem, thrust_straight, thrust_turn, v, t_s, f_turn, t_amb_c=35.0, rho=RHO,
            c_motor=500.0, c_pack=1000.0):
    """Temperature check (computed). Motor + ESC loss = input - shaft power (the 3b loss map includes the test ESC).
    Motor surface rise is scaled from the manufacturer's 3-minute full-throttle test (TM_REF, ambient not stated, 25 C
    assumed): dT = (89 - 25) K x loss / 607 W per motor; an adiabatic bound (no cooling) is also given.
    Pack heat = I^2 R_pack with the ESTIMATED pack resistance; adiabatic rise with c_pack 1000 J/kg/K (ESTIMATE)."""
    d = D()
    s = ps.system
    pm = pt = 0.0
    for thr, w in ((thrust_straight, 1 - f_turn), (thrust_turn, f_turn)):
        p = s.point(rho, thr, v, d.V_MID)
        pin = float(p["p_batt"]) / s.n
        pm += w * (pin - float(p["p_shaft"]) / s.n)
        pt += w * float(p["i"]) ** 2 * s.battery.r_pack
    k_th = (TM_REF["t_surface_c"] - TM_REF["t_amb_assumed_c"]) / TM_REF["loss_w"]
    return dict(loss_motor_esc_w=pm, loss_pack_w=pt, ref_loss_w=TM_REF["loss_w"],
                dT_motor_scaled_k=k_th * pm, motor_surface_c=t_amb_c + k_th * pm,
                dT_motor_adiabatic_k=pm * t_s / (s.motor.mass * c_motor),
                dT_pack_adiabatic_k=pt * t_s / (s.battery.mass * c_pack), pack_end_c_upper=t_amb_c + pt * t_s / (s.battery.mass * c_pack),
                t_amb_c=t_amb_c)


def impact_prop(key_or_ps, v_check="mid"):
    """Adapter bundle for the impact check."""
    return key_or_ps if isinstance(key_or_ps, PropSystem) else system(key_or_ps, v_check)
