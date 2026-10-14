# Copyright © 2026 the members of the AUM AIAA DBF team. All rights reserved.
"""Script 3b: propulsion component model (prop + motor/ESC + battery + fuse). PROVISIONAL.

Written by Claude (14 Oct 2026); the team reviews and owns the numbers (rules
Sec. 1.3). Replaces Script 3's single lumped efficiency (eta_eff 0.58) with
components whose data are measured or published, each checked before use:

  Prop     APC Thin Electric tables (COMPUTED by APC), interpolated in RPM and
           advance ratio J; APC's RPM limit 150,000 / D(in) enforced.
           Checked against UIUC wind-tunnel data and AIAA stand data.
  Motor    T-Motor AT series: losses fitted to the manufacturer's MEASURED test
           table (input power - shaft power, ESC included):
               P_in = Q w + a + b w + c w^2 + d Q^2
           (fixed electronics loss, friction, iron loss, copper loss), robust
           non-negative least squares. Full-throttle speed line
               V_batt >= w / Kv + R_eff I_batt   (R_eff from the 100 % rows).
           Other motors: first-order model (Kv, Rm, I0, ESC efficiency); the
           validation shows it is optimistic, so it is used for checks only.
  Battery  V = cells (v_oc - I r_cell), r_cell = k_ir / capacity (ESTIMATE
           calibrated on WashU 2022), current capped by min(fuse 100 A, pack
           rating, motor peak).
  Flight   k_fl: measured / modelled mean battery power on ERAU 2023's M2 flight,
           modelled with ERAU's own hardware (calibrate_flight).

Units SI: N, m/s, rad/s (w), N*m (Q), W, A, V, kg/m^3. rpm where named rpm.
All operating-point functions accept numpy arrays.
"""
import math
import re
import sys

import numpy as np
from scipy.optimize import nnls

import common
import s1_course as s1
import s3_performance as s3
from common import G0

sys.path.insert(0, str(common.ANALYSIS / "data" / "prop"))
import propdata as pdat                                   # noqa: E402

PR = common.load("propulsion")
RPM_LIMIT_E = pdat.components()["statement"][PR["prop"]["rpm_limit_statement"]]["rpm_limit_e"]  # rpm * in
IN_M = pdat.IN_M
RPM_TO_RAD = math.pi / 30.0


# ---------------------------------------------------------------- propeller
class Prop:
    """APC propeller from its PER3 table. k_ct, k_cp scale the coefficients (sensitivity only)."""

    def __init__(self, name, k_ct=1.0, k_cp=1.0):
        t = pdat.apc_table(name)
        self.name, self.D = name, t["D"]
        self.rpm_limit = RPM_LIMIT_E / (self.D / IN_M)
        self.rpms = t["rpm"]
        self.runs = [(r[1], r[2] * k_ct, r[3] * k_cp) for r in t["runs"]]
        self.version = t["version"]

    def coef(self, rpm, J):
        """(Ct, Cp) at (rpm, J): linear in J on each APC RPM table, then linear in RPM.
        nan beyond a table's last J (no data there) and above the highest table RPM."""
        rpm, J = np.broadcast_arrays(np.asarray(rpm, dtype=float), np.asarray(J, dtype=float))
        ct = np.array([np.interp(J, j, c, right=np.nan) for j, c, _ in self.runs])
        cp = np.array([np.interp(J, j, p, right=np.nan) for j, _, p in self.runs])
        r = np.clip(rpm, self.rpms[0], self.rpms[-1])
        i = np.clip(np.searchsorted(self.rpms, r) - 1, 0, len(self.rpms) - 2)
        f = (r - self.rpms[i]) / (self.rpms[i + 1] - self.rpms[i])
        take = lambda a, k: np.take_along_axis(a, k[None], axis=0)[0]
        out = [(1 - f) * take(a, i) + f * take(a, i + 1) for a in (ct, cp)]
        bad = rpm > self.rpms[-1]
        return [np.where(bad, np.nan, o) for o in out]

    def thrust_power(self, rho, rpm, v):
        """Thrust (N) and shaft power (W) at rpm and airspeed v."""
        n = np.asarray(rpm, dtype=float) / 60.0
        with np.errstate(divide="ignore", invalid="ignore"):
            J = np.where(n > 0, v / (n * self.D), np.inf)
        ct, cp = self.coef(rpm, J)
        return ct * rho * n ** 2 * self.D ** 4, cp * rho * n ** 3 * self.D ** 5

    def rpm_for_thrust(self, rho, thrust, v, iters=48):
        """Lowest rpm (on APC's tables) giving `thrust` at airspeed v; nan if out of reach."""
        thrust, v = np.broadcast_arrays(np.asarray(thrust, dtype=float), np.asarray(v, dtype=float))
        lo = np.full(thrust.shape, 100.0)
        hi = np.full(thrust.shape, float(self.rpms[-1]))
        t_hi, _ = self.thrust_power(rho, hi, v)
        reach = np.nan_to_num(t_hi, nan=-1.0) >= thrust
        for _ in range(iters):
            mid = 0.5 * (lo + hi)
            t, _ = self.thrust_power(rho, mid, v)
            up = np.nan_to_num(t, nan=-1.0) < thrust
            lo, hi = np.where(up, mid, lo), np.where(up, hi, mid)
        return np.where(reach, hi, np.nan)


# ---------------------------------------------------------------- motors
def _robust_nnls(A, y, k):
    """Non-negative least squares with Huber weights (scaled columns)."""
    sc = np.abs(A).max(axis=0)
    sc[sc == 0] = 1.0
    w = np.ones(len(y))
    for _ in range(10):
        x, _ = nnls((A / sc) * w[:, None], y * w, maxiter=5000)
        r = y - (A / sc) @ x
        s = 1.4826 * np.median(np.abs(r - np.median(r))) + 1e-9
        u = np.abs(r) / (k * s)
        w = np.where(u <= 1.0, 1.0, 1.0 / u)
    return x / sc


def _loss_features(w, q):
    return np.column_stack([np.ones_like(w), w, w * w, q * q])


class MapMotor:
    """Motor + ESC from a manufacturer's measured test table (T-Motor AT series)."""

    kind = "measured map"

    def __init__(self, source, variant, k_huber=PR["motor_fit"]["huber_k"]):
        key = pdat.variant_key(variant)
        spec = next(s for s in pdat.tmotor_specs(source) if pdat.variant_key(s["variant"]) == key)
        rows = next(v for k, v in pdat.tmotor_tests(source).items() if pdat.variant_key(k) == key)
        a = np.array([r[1:] for r in rows])
        thr, V, I, _, rpm, Q, _ = a.T
        w = rpm * RPM_TO_RAD
        self.name = f"T-Motor {source.split('-')[1].upper()} {key}"
        self.source, self.key = source, key
        self.kv, self.rm, self.i0, self.mass = spec["kv"], spec["rm"], spec["i0"], spec["mass"]
        self.i_peak = spec["i_peak"]
        self.kv_rad = self.kv * RPM_TO_RAD
        rated = next((v for k, v in spec["raw"].items() if k.startswith("Rated Voltage")), "")
        cells = [int(x) for x in re.findall(r"\d+", rated.split("/")[0])]
        self.cells_rated = (min(cells), max(cells)) if cells else (1, 99)   # e.g. "6-12S" -> (6, 12)
        self.coef = _robust_nnls(_loss_features(w, Q), V * I - Q * w, k_huber)
        full = thr == 100
        self.r_eff = float(np.median((V[full] - w[full] / self.kv_rad) / I[full])) if full.any() else self.rm
        # fit quality on the measured points (efficiency points)
        eta_m = Q * w / (V * I)
        eta_f = Q * w / self.p_in(w, Q)
        self.fit_rms_pts = float(100 * np.sqrt(np.mean((eta_f - eta_m) ** 2)))
        self.data = {"V": V, "I": I, "w": w, "Q": Q, "thr": thr, "props": [r[0] for r in rows]}

    def p_in(self, w, q):
        """Electrical input power (ESC input), W, for shaft speed w and torque q."""
        a, b, c, d = self.coef
        return q * w + a + b * w + c * w * w + d * q * q

    def volts_needed(self, w, q, i_batt):
        """Battery voltage needed to reach w at full throttle."""
        return w / self.kv_rad + self.r_eff * i_batt


class FirstOrderMotor:
    """First-order DC motor (Kv, Rm, I0) behind an ESC of constant efficiency (Drela,
    'First-Order DC Electric Motor Model', MIT 2007). Used for checks only (optimistic)."""

    kind = "first-order"

    def __init__(self, name, kv, rm, i0, mass=float("nan"), i_peak=float("inf"),
                 eta_esc=PR["esc"]["eta_first_order"]):
        self.name, self.kv, self.rm, self.i0, self.mass, self.i_peak = name, kv, rm, i0, mass, i_peak
        self.kv_rad, self.eta_esc = kv * RPM_TO_RAD, eta_esc

    def current(self, q):
        return q * self.kv_rad + self.i0          # I = Q / Kt + I0, Kt = 1 / Kv (SI)

    def p_in(self, w, q):
        i = self.current(q)
        return (w / self.kv_rad + i * self.rm) * i / self.eta_esc

    def volts_needed(self, w, q, i_batt):
        return (w / self.kv_rad + self.current(q) * self.rm) / self.eta_esc


# ---------------------------------------------------------------- battery
class Battery:
    """LiPo pack: cells, capacity (Ah), mass (kg), max continuous current (A)."""

    def __init__(self, name, cells, capacity_ah, mass=float("nan"), i_max=float("inf"),
                 k_ir=PR["battery"]["k_ir_mohm_ah"] * 1e-3):
        self.name, self.cells, self.capacity, self.mass, self.i_max = name, cells, capacity_ah, mass, i_max
        self.r_pack = cells * k_ir / capacity_ah
        self.energy_wh = cells * PR["battery"]["cell_v_rated"] * capacity_ah

    @classmethod
    def from_components(cls, bid, **kw):
        b = pdat.components()["battery"][bid]
        i_max = b["i_cont"] if "i_cont" in b else b["c_cont"] * b["capacity"]
        return cls(b["name"], int(b["cells"]), b["capacity"], b["mass"], i_max, **kw)

    def current(self, p, v_oc_cell):
        """Pack current (A) delivering terminal power p (W); nan if the pack cannot."""
        v0 = self.cells * v_oc_cell
        disc = v0 * v0 - 4.0 * self.r_pack * np.asarray(p, dtype=float)
        with np.errstate(invalid="ignore"):
            return np.where(disc >= 0, (v0 - np.sqrt(np.maximum(disc, 0))) / (2.0 * self.r_pack), np.nan)

    def volts(self, i, v_oc_cell):
        return self.cells * v_oc_cell - self.r_pack * i


# ---------------------------------------------------------------- system
class System:
    """n identical propulsion systems (each: one pack, fuse, ESC, motor, prop; rules
    Sec. 3.2.3.1). Thrust and power are totals; the battery is one system's pack."""

    def __init__(self, prop, motor, battery, n=1, fuse_a=PR["fuse"]["rating_a"]):
        self.prop, self.motor, self.battery, self.n = prop, motor, battery, n
        self.i_cap = min(fuse_a, battery.i_max, motor.i_peak)

    @property
    def name(self):
        return f"{self.n}x {self.motor.name} / APC {self.prop.name} / {self.battery.name}"

    def point(self, rho, thrust, v, v_oc_cell):
        """Steady operating point for total thrust at airspeed v. Returns a dict of arrays:
        rpm, q (N*m), p_shaft, p_batt (total W), i (A per pack), volts, eta (T v / P),
        and ok (all limits met: APC rpm limit, full-throttle voltage, current cap)."""
        t1 = np.asarray(thrust, dtype=float) / self.n
        v = np.asarray(v, dtype=float)
        rpm = self.prop.rpm_for_thrust(rho, t1, v)
        _, p_sh = self.prop.thrust_power(rho, rpm, v)
        w = rpm * RPM_TO_RAD
        with np.errstate(invalid="ignore", divide="ignore"):
            q = p_sh / w
            p_in = self.motor.p_in(w, q)
            i = self.battery.current(p_in, v_oc_cell)
            volts = self.battery.volts(i, v_oc_cell)
            ok = ((rpm <= self.prop.rpm_limit) & (self.motor.volts_needed(w, q, i) <= volts)
                  & (i <= self.i_cap))
            eta = np.where(p_in > 0, t1 * v / p_in, np.nan)
        return {"rpm": rpm, "q": q, "p_shaft": self.n * p_sh, "p_batt": self.n * p_in, "i": i,
                "volts": volts, "eta": eta, "ok": np.nan_to_num(ok, nan=0).astype(bool) & np.isfinite(p_in)}

    def thrust_max(self, rho, v, v_oc_cell, t_hi=400.0, iters=40):
        """Largest total thrust meeting every limit at airspeed v (bisection)."""
        v = np.asarray(v, dtype=float)
        lo, hi = np.zeros(v.shape), np.full(v.shape, t_hi)
        for _ in range(iters):
            mid = 0.5 * (lo + hi)
            ok = self.point(rho, mid, v, v_oc_cell)["ok"]
            lo, hi = np.where(ok, mid, lo), np.where(ok, hi, mid)
        return lo


# ---------------------------------------------------------------- lap and flight calibration
def lap_battery_power(system, rho, v, bank_deg, s, cd0, k, mass, v_oc_cell, g=G0):
    """Distance-weighted mean battery power over one constant-speed lap (straights at
    n = 1, turns at n = 1/cos(bank)), plus the turn point (for the thrust check)."""
    r = s1.turn_radius(v, bank_deg, g)
    n = s1.load_factor(bank_deg)
    turns = s1.TURN_ARC * r
    straight = s1.lap_length(r, s1.STRAIGHTS_M) - turns
    d1 = s3.drag(rho, v, s, cd0, k, mass, 1.0, g)
    dn = s3.drag(rho, v, s, cd0, k, mass, n, g)
    p1 = system.point(rho, d1, v, v_oc_cell)
    pn = system.point(rho, dn, v, v_oc_cell)
    mean = (p1["p_batt"] * straight + pn["p_batt"] * turns) / (straight + turns)
    return {"p_mean": mean, "straight": p1, "turn": pn, "d1": d1, "dn": dn, "n": n}


def erau_2023_system():
    c = PR["calibration"]
    prop = Prop(c["erau_prop"])
    motor = MapMotor(*c["erau_motor"])
    battery = Battery("12S 2250 mAh (ERAU 2023)", c["erau_cells"], c["erau_capacity_ah"])
    return System(prop, motor, battery)


def calibrate_flight(system=None, v_oc_cell=None):
    """k_fl = measured mean battery power / modelled lap-mean battery power, ERAU 2023 M2.

    Flight data (stands.toml erau23-m2-flight, AIAA 2023 Table 8-3): 89 ft/s, 42 s lap,
    29.24 lb, 1,243 W; airframe as s4_sizing.calibration_eta (CD0 0.0583, e 0.842,
    S 6.05 ft^2, AR 5.2, rho 1.225). The bank follows from the lap geometry."""
    st = pdat.stands()["erau23-m2-flight"]
    system = system or erau_2023_system()
    v_oc = PR["battery"]["v_oc_start"] if v_oc_cell is None else v_oc_cell
    ft2 = 0.09290304
    s, k = 6.05 * ft2, s3.induced_factor(5.2, 0.842)
    v, lap = st["v_air"], st["lap_time"]
    r = (v * lap - s1.STRAIGHTS_M) / s1.TURN_ARC
    bank = math.degrees(math.atan(v * v / (G0 * r)))
    res = lap_battery_power(system, 1.225, v, bank, s, 0.0583, k, st["mass"], v_oc)
    p_model = float(res["p_mean"])
    return {"k_fl": st["power_avg"] / p_model, "p_model": p_model, "p_meas": st["power_avg"], "bank": bank,
            "v": v, "eta_straight": float(res["straight"]["eta"]), "eta_turn": float(res["turn"]["eta"]),
            "rpm_straight": float(res["straight"]["rpm"]), "rpm_turn": float(res["turn"]["rpm"]),
            "ok_turn": bool(res["turn"]["ok"]), "res": res}


# ---------------------------------------------------------------- fast model for Scripts 4/6
class PropulsionModel:
    """A System on a (thrust, airspeed) grid, for vectorised use in Scripts 4/6.

    p_batt(T, v): k_fl x component battery power (nan where a limit is broken)
    t_max(v):     full-throttle thrust at v_check (default: end-of-mission voltage, the worst case)
    """

    def __init__(self, system, rho, k_fl, v_grid=(8.0, 50.0, 0.5), t_step=1.0, v_check=None):
        self.system, self.rho, self.k_fl = system, rho, k_fl
        self.v = np.arange(v_grid[0], v_grid[1] + 1e-9, v_grid[2])
        v_end = PR["battery"]["v_oc_end"]
        v_mid = 0.5 * (PR["battery"]["v_oc_start"] + v_end)
        self.v_check = v_end if v_check is None else v_check     # cell voltage of the turn-thrust check
        self.thrust_factor = 1.0                                   # Monte Carlo scale on available thrust
        self.tmax = system.thrust_max(rho, self.v, self.v_check)
        self.t = np.arange(0.0, 1.2 * float(self.tmax.max()) + t_step, t_step)   # room for thrust_factor > 1
        T, V = np.meshgrid(self.t, self.v, indexing="ij")
        pt = system.point(rho, T, V, v_mid)
        self.p = np.where(np.isfinite(pt["p_batt"]), pt["p_batt"], np.nan)

    def t_max(self, v):
        return np.interp(v, self.v, self.tmax, left=np.nan, right=np.nan)

    def p_batt(self, thrust, v):
        """Battery power (W) for thrust (N) at airspeed v, x k_fl; nan above t_max(v)."""
        thrust, v = np.broadcast_arrays(np.asarray(thrust, dtype=float), np.asarray(v, dtype=float))
        ti = np.clip((thrust - self.t[0]) / (self.t[1] - self.t[0]), 0, len(self.t) - 1.000001)
        vi = np.clip((v - self.v[0]) / (self.v[1] - self.v[0]), 0, len(self.v) - 1.000001)
        i0, j0 = ti.astype(int), vi.astype(int)
        fi, fj = ti - i0, vi - j0
        P = self.p
        out = ((1 - fi) * (1 - fj) * P[i0, j0] + fi * (1 - fj) * P[i0 + 1, j0]
               + (1 - fi) * fj * P[i0, j0 + 1] + fi * fj * P[i0 + 1, j0 + 1])
        return np.where(thrust <= self.thrust_factor * self.t_max(v), self.k_fl * out, np.nan)
