"""S12 adapter: evaluate a DB-02 "design" through the DB-01 pipeline (s4_sizing, s6_studies).

Written by Claude (S12), 27 Oct 2026. Read-only use of REPO/analysis: functions are imported,
no script entry point is called, nothing under REPO/analysis is written.

A design is a wing family + wing area S + payload unit (container + declared max sensor)
plus optional overrides that other streams supply:

    aero        S3/S4 aero(geom) dict: cd0_parts, cd0, e or k, clmax_clean, clmax_landing,
                clmax_turn_avail, mass_delta_kg, optional ranges
    mass        S7 mass(geom) dict: airframe {median, p10, p90} (s4 airframe-fit basis), growth_bias
    propulsion  S6 system() object (p_batt(T, V), pack_kg, wh, layout_penalties, ...) or a
                Script 3b PropulsionModel bundle (see prop_bundle)
    payload     S8 dict: container_kg (scalar or callable of sensor kg), dr {mass_kg, stow_s}
    ops         operating choices: vs_max, n_struct, cl_margin, drop_height_m, n_sim_max,
                t_stow_extra_s, or any s4.Params attribute

With no overrides, evaluate() is s6_studies.evaluate() bit for bit: the DB-01 robust value
0.9 m2 straight / 4 kg unit = 6.3326 mean over s6.draws(120, 2027), expected field
(REPO/analysis/out/s6_report.txt, 1.0/4 -> 6.29, 0.8/4 -> 6.23). tests/test_v_integration.py
checks it.

How overrides reach s4 without editing sizing.toml (in-process only, never on disk):
  1. DParams subclasses s4.Params (copies a draw's state, never re-runs Params.__init__) and
     adds hooks: airframe override, extra empty mass, a per-design family function and a
     per-design stow-time function.
  2. install() rebinds s4.family and s4.stow_time to dispatchers. A dispatcher calls the hook
     the Params object carries; with no hook it calls a registered family (register_family),
     else the original s4 function. So DB-01 calls are unchanged.
  3. s6_studies.ST["design"] keys (drop height, n_sim_max, t_stow_extra_s) are patched only
     inside a context manager and restored on exit.

Uncertainty is kept paired with the DB-01 draws (common random numbers): an override that
replaces a drawn input maps the draw onto the new value by its quantile ("anchored range
map", anchored_map) or keeps the draw's relative factor. Every mapping is documented below.
"""
from __future__ import annotations

import contextlib
import copy
import math
import sys
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path

sys.dont_write_bytecode = True                      # no __pycache__ inside REPO/analysis

W = Path(__file__).resolve().parents[2]             # DB-02_aircraft_variants
REPO = W.parent
ANALYSIS = REPO / "analysis"
if str(ANALYSIS) not in sys.path:
    sys.path.insert(0, str(ANALYSIS))

import numpy as np                                  # noqa: E402

import common                                       # noqa: E402
import s2_scoring as s2                             # noqa: E402
import s3_performance as s3                         # noqa: E402
import s4_sizing as s4                              # noqa: E402
import s6_studies as s6                             # noqa: E402

OUT = W / "out" / "integration"
G0 = common.G0
RULES = common.RULES
SZ = s4.SZ
ST = s6.ST
MC = ST["monte_carlo"]
SPAN_M = SZ["sweep"]["span_m"]
WINDOW_S = RULES["missions"]["window_s"]
TOGW_MAX = RULES["aircraft"]["togw_max_kg"]
USABLE = SZ["battery"]["usable_fraction"]
EPS = 1e-9

# DB-01 robust-map plateau (REPO/analysis/out/s6_report.txt, 120 draws, seed 2027, expected field)
DB01_ROBUST = {(0.9, 4.0): 6.33, (1.0, 4.0): 6.29, (0.8, 4.0): 6.23}


# ---------------------------------------------------------------- Params subclass with hooks
class DParams(s4.Params):
    """s4.Params plus DB-02 hooks. Built from an existing Params (a draw); never re-runs
    Params.__init__ (which re-reads the airframe fit and inserts sys.path entries).

    Hooks (all default to "behave exactly as s4.Params"):
      af_kg      airframe mass (kg) for this design and draw; None = s4 fit x af_factor
      m_extra    extra empty mass (kg): aero mass_delta, gear, door, structure, ...
      family_fn  callable(name, s, P) -> (AR, e, CLmax landing, CLmax turn); None = registry/s4
      stow_fn    callable(m_sensor_array, P) -> stow s (array); None = s4 reel model
    """

    def __init__(self, base):                        # noqa: D401 (no super().__init__ on purpose)
        self.__dict__.update(base.__dict__)
        self.__dict__.setdefault("af_kg", None)
        self.__dict__.setdefault("m_extra", 0.0)
        self.__dict__.setdefault("family_fn", None)
        self.__dict__.setdefault("stow_fn", None)

    def airframe(self, s):
        if self.af_kg is not None:
            return self.af_kg
        return super().airframe(s)

    def empty(self, s):
        return self.airframe(s) + self.m_dr + self.m_prop_delta + self.m_extra


# ---------------------------------------------------------------- family registry + dispatchers
FAMILIES: dict = {}
_ORIG = {}


def register_family(name, fn, clmax_key="straight"):
    """Register a wing family usable by name in s4/s6 calls, without editing sizing.toml.

    fn(s, P) -> (AR, e, CLmax_landing, CLmax_turn) BEFORE the draw's CLmax factor; the
    dispatcher multiplies both CLmax values by P.clmax_factor[clmax_key] (default: the
    straight-wing draw, so a new monoplane family shares the DB-01 CLmax uncertainty).
    """
    FAMILIES[name] = (fn, clmax_key)
    install()


def family_from_aero(aero, span_m=SPAN_M, clmax_key="straight"):
    """A family function from an S3/S4 aero() dict (see module doc for the key meanings)."""
    def fn(s, P=None):
        ar = span_m ** 2 / s
        e = aero["e"] if "e" in aero else 1.0 / (math.pi * ar * aero["k"])
        clf = aero.get("clmax_landing", aero.get("clmax_flapped"))
        clc = aero.get("clmax_turn_avail", aero["clmax_clean"])
        return ar, e, clf, clc
    return fn, clmax_key


def _family_dispatch(name, s, P=None):
    hook = getattr(P, "family_fn", None) if P is not None else None
    if hook is not None:
        fn, key = hook
    elif name in FAMILIES:
        fn, key = FAMILIES[name]
    else:
        return _ORIG["family"](name, s, P)
    ar, e, clf, clc = fn(s, P)
    f = 1.0 if P is None else P.clmax_factor.get(key, 1.0)
    return ar, e, f * clf, f * clc


def _stow_dispatch(m_sensor, P):
    hook = getattr(P, "stow_fn", None)
    if hook is None:
        return _ORIG["stow_time"](m_sensor, P)
    out = np.asarray(hook(np.atleast_1d(np.asarray(m_sensor, dtype=float)), P), dtype=float)
    return float(out.reshape(-1)[0]) if np.ndim(m_sensor) == 0 else out


_family_dispatch._s12 = True
_stow_dispatch._s12 = True


def install():
    """Rebind s4.family and s4.stow_time to the S12 dispatchers (idempotent, in-process only).
    s4.m2_search / m2_fixed / m3_search look `family` up in s4's globals at call time, and
    s6.evaluate calls s4.stow_time by attribute, so both see the dispatchers."""
    if not getattr(s4.family, "_s12", False):
        _ORIG["family"] = s4.family
        s4.family = _family_dispatch
    if not getattr(s4.stow_time, "_s12", False):
        _ORIG["stow_time"] = s4.stow_time
        s4.stow_time = _stow_dispatch


def uninstall():
    """Restore the original s4 functions."""
    if "family" in _ORIG:
        s4.family = _ORIG["family"]
    if "stow_time" in _ORIG:
        s4.stow_time = _ORIG["stow_time"]


install()


# ---------------------------------------------------------------- draws (cached, CRN)
@lru_cache(maxsize=8)
def _draws(n, seed):
    Ps = s6.draws(n, seed)
    pr = common.load("propulsion")["uncertainty"]
    rng = np.random.default_rng(seed + 1)              # exactly prop_trade.robustness()
    pf = rng.uniform(*pr["power_factor"], len(Ps))
    tf = rng.uniform(*pr["thrust_factor"], len(Ps))
    for i, P in enumerate(Ps):
        P.pf_draw, P.tf_draw, P.draw_index = float(pf[i]), float(tf[i]), i
    return tuple(Ps)


def draws(n=MC["draws"], seed=MC["seed"]):
    """The DB-01 paired draws s6.draws(n, seed) (cached), each tagged with the propulsion
    power/thrust factors prop_trade.py pairs with it (rng seed + 1) and its index."""
    return list(_draws(n, seed))


@lru_cache(maxsize=1)
def _base():
    P = s6.base_params()
    P.pf_draw, P.tf_draw, P.draw_index = 1.0, 1.0, -1
    return P


def base_params():
    """Baseline inputs (no uncertainty), as s6.base_params(); cached copy."""
    return copy.copy(_base())


BASE = {"f_body": SZ["aero"]["f_body_m2"], "container_kg": ST["design"]["container_kg"],
        "e_factor": 1.0, "clmax_factor": 1.0, "f_tow": SZ["aero"]["f_tow_m2"]}
RANGE = {"f_body": tuple(MC["f_body_m2"]), "container_kg": tuple(MC["container_kg"]),
         "e_factor": tuple(MC["e_factor"]), "clmax_factor": tuple(MC["clmax_factor_straight"]),
         "f_tow": tuple(MC["f_tow_m2"])}


def anchored_map(x, src, dst):
    """Map a drawn value x from the DB-01 range src = (lo, base, hi) onto dst = (lo', c', hi'),
    piecewise linear so that lo -> lo', base -> c', hi -> hi'. Monotone, so paired draws stay
    paired (common random numbers), and the baseline input maps to the override's central value."""
    lo, b, hi = src
    lo2, c2, hi2 = dst
    if x <= b:
        return c2 - (b - x) / (b - lo) * (c2 - lo2) if b > lo else c2
    return c2 + (x - b) / (hi - b) * (hi2 - c2) if hi > b else c2


def _src(key):
    return (RANGE[key][0], BASE[key], RANGE[key][1])


# ---------------------------------------------------------------- the design object
@dataclass
class Design:
    """One candidate. Units SI. `family` is "straight", "delta" (sizing.toml) or a registered
    family; `aero` overrides the family. `unit` = container + declared max sensor (kg)."""
    id: str
    family: str = "straight"
    s: float = 0.9
    unit: float = 4.0
    aero: dict | None = None
    mass: dict | None = None
    propulsion: object | None = None
    payload: dict | None = None
    ops: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)        # taper, high_lift, winglet, gear, bay, complexity...

    def with_(self, **kw):
        return replace(self, **kw)


ST_KEYS = ("drop_height_m", "n_sim_max", "t_stow_extra_s", "sensor_min_kg")


@contextlib.contextmanager
def st_patch(ops):
    """Temporarily set s6.ST["design"] keys (drop height, n_sim_max, ...) from ops."""
    saved = {k: ST["design"][k] for k in ST_KEYS if k in (ops or {})}
    try:
        for k in saved:
            ST["design"][k] = ops[k]
        yield
    finally:
        ST["design"].update(saved)


# ---------------------------------------------------------------- overrides -> Params
def _apply_aero(Q, d, P):
    a = d.aero
    # drag: wing profile drag per area, and the non-wing drag area (what the DB-01 draw varies)
    if "cd0_parts" in a:
        parts = a["cd0_parts"]
        Q.cd_w = parts["wing"]
        f_nonwing = sum(v for k, v in parts.items() if k != "wing") * d.s
    elif "cd0" in a:
        f_nonwing = (a["cd0"] - Q.cd_w) * d.s
    else:
        f_nonwing = None
    if f_nonwing is not None:
        rng = a.get("ranges", {}).get("f_body_m2")
        if rng:                                       # quantile of the DB-01 draw onto the override range
            Q.f_body = anchored_map(P.f_body, _src("f_body"), (rng[0], f_nonwing, rng[1]))
        else:                                         # keep the DB-01 relative uncertainty
            Q.f_body = f_nonwing * P.f_body / BASE["f_body"]
    if "f_tow_m2" in a:
        Q.f_tow = a["f_tow_m2"] * P.f_tow / BASE["f_tow"]
    rng = a.get("ranges", {}).get("e")
    if rng and "e" in a:                              # map the e draw onto the override's e range
        Q.e_factor = anchored_map(P.e_factor, _src("e_factor"), (rng[0], a["e"], rng[1])) / a["e"]
    fam_fn, key = family_from_aero(a, a.get("span_m", SPAN_M), a.get("clmax_key", "straight"))
    rng = a.get("ranges", {}).get("clmax_factor")
    if rng:
        f = anchored_map(P.clmax_factor.get(key, 1.0), _src("clmax_factor"), (rng[0], 1.0, rng[1]))
        Q.clmax_factor = {**P.clmax_factor, key: f}
    Q.family_fn = (fam_fn, key)
    Q.m_extra += a.get("mass_delta_kg", 0.0)


def _apply_mass(Q, d, P):
    m = d.mass
    sd_fit = _sd_fit()
    af = m.get("airframe")
    growth = m.get("growth_bias", 1.0)
    if af is not None:
        med = af["median"]
        z = math.log(P.af_factor) / sd_fit if sd_fit > 0 else 0.0
        if "p10" in af and "p90" in af and af["p90"] > af["p10"]:
            sd_new = (math.log(af["p90"]) - math.log(af["p10"])) / (2 * 1.2815515655446004)
        else:
            sd_new = sd_fit                           # keep the DB-01 fit scatter
        Q.af_kg = growth * med * math.exp(z * sd_new)
    elif growth != 1.0:
        Q.af_factor = P.af_factor * growth
    Q.m_extra += m.get("extra_kg", 0.0)


@lru_cache(maxsize=1)
def _sd_fit():
    return s4.airframe_fit()[2]


def _apply_prop(Q, prop, P):
    """S6 system() object or prop_bundle(): battery power model, pack, energy, layout."""
    Q.prop = prop.model if hasattr(prop, "model") else prop
    Q.pack_kg = prop.pack_kg
    Q.e_usable = prop.wh * USABLE
    Q.m_prop_delta = getattr(prop, "motor_mass_delta_kg", 0.0)
    lp = getattr(prop, "layout_penalties", None) or {}
    Q.m_prop_delta += lp.get("mass_kg", 0.0)
    Q.f_body = Q.f_body + lp.get("f_m2", 0.0)
    if getattr(prop, "draw_factors", True):
        Q.power_factor = P.pf_draw
        Q._thrust_factor = P.tf_draw
    if getattr(prop, "t_takeoff_s", None) is not None:
        Q.t_to = prop.t_takeoff_s


def _container_for(unit, c, iters=4):
    """Container mass when S8 gives it as a function of the sensor mass: unit = c(sensor) + sensor."""
    if not callable(c):
        return float(c)
    m = 0.6
    for _ in range(iters):
        m = float(c(max(unit - m, 0.0)))
    return m


def _apply_payload(Q, d, P):
    p = d.payload
    if "container_kg" in p:
        c0 = _container_for(d.unit, p["container_kg"])
        rng = p.get("container_range_kg")
        if rng:
            Q.container_kg = anchored_map(P.container_kg, _src("container_kg"), (rng[0], c0, rng[1]))
        else:
            Q.container_kg = c0 * P.container_kg / BASE["container_kg"]
    dr = p.get("dr") or {}
    if "mass_kg" in dr:
        Q.m_dr = dr["mass_kg"]
    if "stow_s" in dr:
        st = dr["stow_s"]
        Q.stow_fn = st if callable(st) else (lambda ms, _P, _v=float(st): np.full(ms.shape, _v))
    Q.m_extra += p.get("extra_kg", 0.0)
    if "f_m2" in p:
        Q.f_body = Q.f_body + p["f_m2"]


def apply(d: Design, P):
    """A DParams for design d under draw P (P is never modified)."""
    Q = DParams(P)
    if d.aero:
        _apply_aero(Q, d, P)
    if d.mass:
        _apply_mass(Q, d, P)
    if d.propulsion is not None:
        _apply_prop(Q, d.propulsion, P)
    if d.payload:
        _apply_payload(Q, d, P)
    for k, v in (d.ops or {}).items():
        if k not in ST_KEYS:
            setattr(Q, k, v)
    return Q


@contextlib.contextmanager
def _thrust(Q):
    """Set the shared PropulsionModel's thrust factor for this draw (prop_trade convention)."""
    model = Q.prop
    tf = getattr(Q, "_thrust_factor", None)
    if model is None or tf is None or not hasattr(model, "thrust_factor"):
        yield
        return
    saved = model.thrust_factor
    model.thrust_factor = tf
    try:
        yield
    finally:
        model.thrust_factor = saved


# ---------------------------------------------------------------- evaluation
def evaluate(d: Design, P=None, field=None, n_sim=None, fine=False):
    """s6.evaluate for design d under draw P (baseline inputs if P is None)."""
    Q = apply(d, P if P is not None else base_params())
    with st_patch(d.ops), _thrust(Q):
        return s6.evaluate(d.family, d.s, d.unit, Q, field=field, n_sim=n_sim, fine=fine)


def evaluate_draws(d: Design, Ps=None, field=None, n_sim=None, fine=False):
    Ps = draws() if Ps is None else Ps
    return [evaluate(d, P, field, n_sim, fine) for P in Ps]


def robust(d: Design, Ps=None, field=None, scenario="expected", fine=False):
    """DB-01 robust-map statistics for one design: mean, P10/P50/P90 of the total, P(M2 feasible)."""
    rs = evaluate_draws(d, Ps, field, fine=fine)
    if any(r is None for r in rs):
        return None
    tot = np.array([r[scenario]["total"] for r in rs])
    return {"id": d.id, "mean": float(tot.mean()), "p10": float(np.percentile(tot, 10)),
            "p50": float(np.median(tot)), "p90": float(np.percentile(tot, 90)),
            "p_m2": float(np.mean([r["m2_feasible"] for r in rs])), "totals": tot, "results": rs}


# ---------------------------------------------------------------- Script 3b propulsion bundles
class PropBundle:
    """A Script 3b System wrapped to the S6 system() contract the adapter reads:
    model (PropulsionModel, has p_batt(T, V) and thrust_factor), pack_kg, wh,
    motor_mass_delta_kg (vs the 0.50 kg class motor inside the airframe fit),
    layout_penalties {mass_kg, f_m2}, static thrust, prop diameter."""

    def __init__(self, name, system, k_fl, v_check, layout=None, rho=None):
        import s3b_propulsion as pb
        PR = common.load("propulsion")
        self.name, self.system = name, system
        self.rho = PR["trade"]["rho"] if rho is None else rho
        self.model = pb.PropulsionModel(system, self.rho, k_fl, v_check=v_check)
        self.pack_kg = system.battery.mass * system.n
        self.wh = system.battery.energy_wh * system.n
        self.motor_mass_delta_kg = system.motor.mass * system.n - PR["mass"]["motor_ref_kg"]
        self.layout_penalties = layout or {"mass_kg": 0.0, "f_m2": 0.0}
        self.i_max = system.i_cap
        self.fuse_a = PR["fuse"]["rating_a"]
        self.prop_diameter_m = system.prop.D
        self.n_systems = system.n
        self.static_thrust_n = float(system.thrust_max(self.rho, 0.0, PR["battery"]["v_oc_start"], iters=30))
        self.draw_factors = True
        self.t_takeoff_s = None

    def p_batt(self, thrust, v):
        return self.model.p_batt(thrust, v)

    def thrust(self, v, v_batt=None):
        return self.model.t_max(v)


@lru_cache(maxsize=None)
def prop_bundle(key="8s"):
    """Script 3b systems from the DB-01 propulsion trade (REPO/analysis/out/prop_trade_report.txt):
      "8s"   Thunder Power TP3300-8SE55 + T-Motor AT7215 KV270 + APC 20x15E (MC mean 6.37)
      "12s"  MaxAmps 2000 mAh 12S + T-Motor AT7215 KV200 + APC 20x15E (6.31)
      "twin" 2 x T-Motor AT4130 KV450 + APC 14x14E on 2 x TP2250-6SR70, +0.15 kg, +20 cm2 (6.21)
    Same flight factor (ERAU 2023) and mid-mission voltage check as prop_trade.robustness()."""
    import s3b_propulsion as pb
    PR = common.load("propulsion")
    v_mid = 0.5 * (PR["battery"]["v_oc_start"] + PR["battery"]["v_oc_end"])
    k_fl = _k_fl()
    if key == "8s":
        sysm = pb.System(pb.Prop("20x15E"), pb.MapMotor("tmotor-at7215", "KV270"),
                         pb.Battery.from_components("tp3300-8se55"))
        return PropBundle("8S TP3300-8SE55 / AT7215 KV270 / APC 20x15E", sysm, k_fl, v_mid)
    if key == "12s":
        sysm = pb.System(pb.Prop("20x15E"), pb.MapMotor("tmotor-at7215", "KV200"),
                         pb.Battery.from_components("maxamps-12s-2000"))
        return PropBundle("12S MaxAmps 2000 / AT7215 KV200 / APC 20x15E", sysm, k_fl, v_mid)
    if key == "twin":
        LY = PR["layout"]
        sysm = pb.System(pb.Prop("14x14E"), pb.MapMotor("tmotor-at4130", "KV450"),
                         pb.Battery.from_components(LY["twin_pack"]), n=2)
        return PropBundle("2x AT4130 KV450 / 2x APC 14x14E / 2x TP2250-6SR70", sysm, k_fl, v_mid,
                          layout={"mass_kg": LY["twin_extra_kg"], "f_m2": LY["twin_extra_cda_m2"]})
    raise KeyError(key)


@lru_cache(maxsize=1)
def _k_fl():
    import s3b_propulsion as pb
    return pb.calibrate_flight()["k_fl"]


# ---------------------------------------------------------------- reference designs (brief Sec. 8)
REF_D01 = Design("REF-D01", "straight", 0.9, 4.0, meta={"taper": 0.7, "high_lift": "plain", "winglet": 0.0,
                                                         "gear": "fixed_tricycle", "bay": "door",
                                                         "prop": "lumped", "config": "monoplane",
                                                         "tail": "conventional", "complexity": "simple"})
REF_D01B = REF_D01.with_(id="REF-D01b", s=1.0, unit=5.0)


def ref_d01_8s():
    """REF-D01 with the DB-01 best 8S system (prop_trade Monte Carlo mean 6.37)."""
    return REF_D01.with_(id="REF-D01-8S", propulsion=prop_bundle("8s"), meta={**REF_D01.meta, "prop": "8s"})
