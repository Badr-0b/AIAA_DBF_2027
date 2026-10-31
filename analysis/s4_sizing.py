# Copyright © 2026 Badr Obtel. All rights reserved.
"""Script 4: sizing and the 01-vs-02 trade (R&D Sec. 4, Script 4). PROVISIONAL.

    python analysis/s4_sizing.py

Written 13 Oct 2026 after Pair mode was lifted; the team reviews and owns
the numbers (rules Sec. 1.3). Inputs: inputs/sizing.toml (every value sourced
or marked ESTIMATE), data/dbf_airframes.csv (verified AIAA report data),
proposal/data/numbers.tex (rho).

Mass build-up: airframe(S) from the fit to 14 top-3 aircraft (no battery, no
payload) + the D&R mechanism (sizing.toml [dr], flown in every mission, rules
Sec. 3.1.2) + battery (100 Wh at the median same-pack specific energy) + payload.
M3 stow time comes from the reel drive's speed-torque line at the sensor's 1 g tow
tension (stow_time; Table 06 option A), so heavier sensors stow slower.
Drag: CD0 = wing profile drag per area + non-wing drag area / S.
For each wing area and wing family the script searches payload x speed x bank
for the fastest feasible five-lap M2 and keeps the payload that maximises the
M2 score rate W/t. Feasible means: TOGW below the rule, 1 g stall speed (flaps)
below the field-anchored bound, turn CL inside the buffet margin, load factor
inside the structural limit, peak battery power inside fuse x pack voltage,
mission energy inside the usable energy. M3: laps of the 5-min window towing a
sensor of mass m_s, energy for the whole window.

The model flies every turn at constant speed. Flight data show turns cost speed
and laps run slow of prediction (calibration_time.pdf: median x1.15 over 24 lap
and mission pairs). That factor (sizing.toml [calibration]) is applied inside the
model to every lap time, the M2 clock and the M2 energy, so M2 rates, M3 laps and
energy checks are all on the flown, not the predicted, time base.
"""
import csv
import math
import sys

import numpy as np

import common
import s3_performance as s3
from common import G0, OUT, RULES

SZ = common.load("sizing")
AIR = RULES["aircraft"]
DATA = common.ANALYSIS / "data"
M3_MASSES = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0)
TIME_CAL = SZ["calibration"]["time_factor"]    # measured / predicted time (sizing.toml [calibration])
EPS = 1e-9


# ---------------------------------------------------------------- evidence
def airframe_fit():
    """(k, p, sd): airframe kg = k S^p, log residual sd; fitted to dbf_airframes.csv."""
    sys.path.insert(0, str(DATA))
    from aircraft_model import fit_power
    rows = [r for r in csv.DictReader((DATA / "dbf_airframes.csv").open(encoding="utf-8"))
            if r["airframe_kg"] and r["wing_area_m2"]]
    k, p, _, sd = fit_power([float(r["wing_area_m2"]) for r in rows], [float(r["airframe_kg"]) for r in rows])
    return k, p, sd, len(rows)


def pack_specific_energy():
    vals = sorted(float(r["pack_wh_per_kg"]) for r in csv.DictReader((DATA / "dbf_airframes.csv").open(encoding="utf-8"))
                  if r["pack_wh_per_kg"])
    return float(np.median(vals)), len(vals)


def calibration_eta():
    """Effective efficiency from ERAU 2023's measured M2 flight (dbf_aircraft, Table 8-3)."""
    ft, ft2, lb = 0.3048, 0.09290304, 0.45359237
    k = s3.induced_factor(5.2, 0.842)
    return s3.calibrate_eta(1.225, 89 * ft, 42.0, 6.05 * ft2, 0.0583, k, 29.24 * lb, 1243.0, G0)


# ---------------------------------------------------------------- model
class Params:
    """One set of model inputs (baseline from sizing.toml, or a Monte Carlo draw)."""
    def __init__(self, **over):
        a, b, pr = SZ["aero"], SZ["battery"], SZ["propulsion"]
        k, p, sd, _ = airframe_fit()
        self.rho = common.number("nRho")
        self.k_af, self.p_af, self.af_factor = k, p, 1.0
        self.wh_per_kg = pack_specific_energy()[0]
        self.e_usable = b["energy_wh"] * b["usable_fraction"]
        self.p_max = b["fuse_a"] * b["pack_v_loaded"]
        self.eta = pr["eta_eff"]
        self.t_to = pr["t_takeoff_s"]
        self.cd_w = a["cd_wing_per_area"]
        self.f_body = a["f_body_m2"]
        self.f_tow = a["f_tow_m2"]
        self.cl_margin = a["cl_turn_margin"]
        self.n_struct = a["n_struct"]
        self.vs_max = a["v_stall_max"]
        self.e_factor = 1.0
        self.time_cal = TIME_CAL
        self.clmax_factor = {}
        self.m_dr = SZ["dr"]["mass_kg"]
        self.prop = None            # Script 3b PropulsionModel; None = the lumped eta model
        self.pack_kg = None         # propulsion pack mass when a specific pack is chosen
        self.m_prop_delta = 0.0     # motor mass minus the class mass inside the airframe fit
        self.power_factor = 1.0     # uncertainty multiplier on Script 3b battery power
        self.__dict__.update(over)

    def airframe(self, s):
        return self.af_factor * self.k_af * s ** self.p_af

    def empty(self, s):
        """Airframe plus the D&R mechanism, which flies in every mission (Sec. 3.1.2)."""
        return self.airframe(s) + self.m_dr + self.m_prop_delta

    def battery(self):
        return self.pack_kg if self.pack_kg is not None else SZ["battery"]["energy_wh"] / self.wh_per_kg


def with_propulsion(P, model, battery, motor_mass_delta=0.0):
    """Params P switched to a Script 3b propulsion model: component battery power, the
    chosen pack's mass and usable energy (usable fraction x its rated Wh)."""
    P.prop, P.pack_kg, P.m_prop_delta = model, battery.mass * model.system.n, motor_mass_delta
    P.e_usable = battery.energy_wh * model.system.n * SZ["battery"]["usable_fraction"]
    return P


def battery_power(P, V, B, s, cd0, k, m):
    """Lap-mean battery power (W), turn power (W) and the power check, for every (mass,
    speed, bank). Lumped model (P.prop None): mean shaft power / eta and the turn's
    shaft power / eta <= fuse x pack voltage (exactly Script 3's s3.mission). Script 3b
    model: component battery power x k_fl on the straights (n = 1) and the turns, and
    the turn thrust within full-throttle thrust at the end-of-mission voltage."""
    if P.prop is None:
        _, p_mean, n, _ = s3.lap(P.rho, V, B, s, cd0, k, m, G0)
        p_peak = s3.power_required(P.rho, V, s, cd0, k, m, n, G0) / P.eta
        return p_mean / P.eta, p_peak, p_peak <= P.p_max
    import s1_course as s1
    r = s1.turn_radius(V, B, G0)
    n = s1.load_factor(B)
    turns = s1.TURN_ARC * r
    straight = s1.lap_length(r, s1.STRAIGHTS_M) - turns
    p1 = P.prop.p_batt(s3.drag(P.rho, V, s, cd0, k, m, 1.0, G0), V)
    pn = P.prop.p_batt(s3.drag(P.rho, V, s, cd0, k, m, n, G0), V)
    mean = P.power_factor * (p1 * straight + pn * turns) / (straight + turns)
    ok = np.isfinite(mean)
    return np.where(ok, mean, np.inf), np.where(ok, P.power_factor * pn, np.inf), ok


def family(name, s, P=None):
    """AR, Oswald e, CLmax with flaps, clean CLmax for a wing family at area s (span fixed).
    A draw may scale both CLmax values (P.clmax_factor[name])."""
    c = SZ["config"][name]
    ar = SZ["sweep"]["span_m"] ** 2 / s
    e = s3.oswald_straight(ar) if c["oswald"] == "raymer_straight" else s3.oswald_swept(ar, c["sweep_le_deg"])
    f = 1.0 if P is None else P.clmax_factor.get(name, 1.0)
    return ar, e, f * c["clmax_flapped"], f * c["clmax_clean"]


def grids(fine=True):
    sw = SZ["sweep"]
    dp, dv, db = (0.25, 0.25, 1.0) if fine else (0.5, 0.5, 2.0)
    return (np.arange(sw["payload_kg"][0], sw["payload_kg"][1] + EPS, dp),
            np.arange(sw["v_mps"][0], sw["v_mps"][1] + EPS, dv),
            np.arange(sw["bank_deg"][0], sw["bank_deg"][1] + EPS, db))


def m2_search(name, s, P, fine=True):
    """Best five-lap M2 at wing area s: dict, plus the rate-vs-payload curve."""
    pay, v, bank = grids(fine)
    ar, e, clf, clc = family(name, s, P)
    k = s3.induced_factor(ar, e * P.e_factor)
    cd0 = P.cd_w + P.f_body / s
    m = (P.empty(s) + P.battery() + pay)[:, None, None]
    V, B = v[None, :, None], bank[None, None, :]
    res = s3.mission(P.rho, V, B, s, cd0, k, m, RULES["missions"]["m2_laps"], P.eta, P.t_to, G0)
    p_mean, p_peak, ok_p = battery_power(P, V, B, s, cd0, k, m)
    t_cal, e_cal = res["t"] * P.time_cal, p_mean * res["t"] / 3600.0 * P.time_cal   # flown time base
    ok = ((m < AIR["togw_max_kg"]) & (s3.stall_speed(P.rho, s, m, clf, G0) <= P.vs_max)
          & (res["cl_turn"] <= P.cl_margin * clc) & (res["n"] <= P.n_struct)
          & ok_p & (e_cal <= P.e_usable))
    t = np.where(ok, t_cal, np.inf)
    flat = t.reshape(len(pay), -1)
    t_best = flat.min(axis=1)
    rate = np.where(np.isfinite(t_best), pay / t_best, 0.0)
    i = int(np.argmax(rate))
    j = int(np.argmin(flat[i]))
    jv, jb = divmod(j, len(bank))
    pick = lambda arr: float(np.broadcast_to(arr, t.shape)[i, jv, jb])
    best = {"payload": float(pay[i]), "rate": float(rate[i]), "t": float(t_best[i]), "v": float(v[jv]),
            "bank": float(bank[jb]), "n": pick(res["n"]), "e_wh": pick(e_cal),
            "p_peak": pick(p_peak), "cl_turn": pick(res["cl_turn"]), "t_lap": pick(res["t_lap"]) * P.time_cal,
            "mass": float(m[i, 0, 0]), "ar": ar, "e": e, "cd0": cd0,
            "v_stall": float(s3.stall_speed(P.rho, s, m[i, 0, 0], clf, G0))}
    best["binding"] = binding(best, P, clc)
    return best, (pay, rate)


def binding(b, P, clc):
    """Constraints within 3 % of their limit at the optimum."""
    out = []
    if b["e_wh"] >= 0.97 * P.e_usable: out.append("energy")
    if P.prop is None and b["p_peak"] >= 0.97 * P.p_max: out.append("peak power")
    if b["v_stall"] >= 0.97 * P.vs_max: out.append("stall speed")
    if b["cl_turn"] >= 0.97 * P.cl_margin * clc: out.append("turn CL")
    if b["n"] >= 0.97 * P.n_struct: out.append("load factor")
    if b["mass"] >= 0.97 * AIR["togw_max_kg"]: out.append("TOGW")
    return out or ["none (interior optimum)"]


def stow_time(m_sensor, P):
    """Stow time (s) for each sensor mass: the Table 06 option-A reel (sizing.toml [dr],
    drive and drum geometry from dr_trade.toml) reeling in against the 1 g tow tension,
    with the trade's docking slow-down, latch and door times. inf if the drive stalls."""
    import s5_tow as s5
    dr, D = SZ["dr"], common.load("dr_trade")
    drive = next(d for d in D["drive"] if d["id"] == dr["drive"])
    g, ln, fl = D["geometry"], D["line"], D["flight"]
    deploy = s5.deploy_length(RULES["aircraft"]["span_max_m"], RULES["sensor"]["tow_factor"]) + g["deploy_margin_m"]
    wound = deploy + g["stowed_offset_m"]
    q = 0.5 * P.rho * dr["v_ref_mps"] ** 2
    r_eff = dr["r_core_m"] + ln["d_m"] / 2.0
    ws = drive["rpm_free"] * 2.0 * math.pi / 60.0
    ms = np.atleast_1d(np.asarray(m_sensor, dtype=float))
    out = np.array([s5.stow_time(wound, s5.tow_tension(m, 1.0, q, fl["sensor_cda_m2"][1], ln["d_m"], ln["cd"],
                                                       deploy, G0),
                                 r_eff, drive["tau_stall_nm"], ws, fl["dock_zone_m"], fl["dock_speed_mps"],
                                 fl["t_door_s"] + fl["t_latch_s"]) for m in ms])
    return float(out[0]) if np.ndim(m_sensor) == 0 else out


def m3_search(name, s, m_sensor, P, stow_s=None, fine=True):
    """Most whole laps in the M3 window towing m_sensor (energy for the whole window).
    m_sensor may be an array: one lap count per mass. stow_s: seconds to stow after the
    last lap (scalar or one per mass); None uses the reel model (stow_time)."""
    _, v, bank = grids(fine)
    ar, e, clf, clc = family(name, s, P)
    k = s3.induced_factor(ar, e * P.e_factor)
    cd0 = P.cd_w + (P.f_body + P.f_tow) / s
    ms = np.atleast_1d(np.asarray(m_sensor, dtype=float))
    m = (P.empty(s) + P.battery() + ms)[:, None, None]   # the line carries the sensor's weight
    V, B = v[None, :, None], bank[None, None, :]
    t_lap, p_mean, n, cl = s3.lap(P.rho, V, B, s, cd0, k, m, G0)
    t_lap = t_lap * P.time_cal                           # flown time base
    window = RULES["missions"]["window_s"]
    stow = stow_time(ms, P) if stow_s is None else np.broadcast_to(np.asarray(stow_s, dtype=float), ms.shape)
    limit = (window - stow)[:, None, None]
    t_first = P.t_to + t_lap
    laps = np.where(t_first > limit + EPS, 0, 1 + np.floor((limit - t_first) / t_lap + EPS))
    p_batt, _, ok_p = battery_power(P, V, B, s, cd0, k, m)
    e_wh = p_batt * window / 3600.0
    ok = ((s3.stall_speed(P.rho, s, m, clf, G0) <= P.vs_max) & (cl <= P.cl_margin * clc) & (n <= P.n_struct)
          & ok_p & (e_wh <= P.e_usable))
    best = np.where(ok, laps, 0).reshape(len(ms), -1).max(axis=1).astype(int)
    return int(best[0]) if np.ndim(m_sensor) == 0 else best


def m2_fixed(name, s, payload, P, fine=True):
    """Fastest feasible five-lap M2 clock (flown time base, s) carrying exactly `payload` kg;
    inf when infeasible. payload may be an array: one time per payload."""
    _, v, bank = grids(fine)
    ar, e, clf, clc = family(name, s, P)
    k = s3.induced_factor(ar, e * P.e_factor)
    cd0 = P.cd_w + P.f_body / s
    pay = np.atleast_1d(np.asarray(payload, dtype=float))
    m = (P.empty(s) + P.battery() + pay)[:, None, None]
    V, B = v[None, :, None], bank[None, None, :]
    res = s3.mission(P.rho, V, B, s, cd0, k, m, RULES["missions"]["m2_laps"], P.eta, P.t_to, G0)
    p_mean, _, ok_p = battery_power(P, V, B, s, cd0, k, m)
    ok = ((m < AIR["togw_max_kg"]) & (s3.stall_speed(P.rho, s, m, clf, G0) <= P.vs_max)
          & (res["cl_turn"] <= P.cl_margin * clc) & (res["n"] <= P.n_struct)
          & ok_p & (p_mean * res["t"] / 3600.0 * P.time_cal <= P.e_usable))
    t = np.where(ok, res["t"] * P.time_cal, np.inf).reshape(len(pay), -1).min(axis=1)
    return float(t[0]) if np.ndim(payload) == 0 else t


def strategy(name, s, vs, unit_kg, n_sim, m3_sensor_kg, h_m, container_kg):
    """Every mission for one complete choice. Unit = container + declared max sensor
    (rules: each simulator matches it within 1 oz), so W = (1 + n_sim) x unit."""
    import s2_scoring as s2
    P = Params(vs_max=vs)
    w = (1 + n_sim) * unit_kg
    t2 = m2_fixed(name, s, w, P)
    laps = m3_search(name, s, m3_sensor_kg, P)
    sensor_max = unit_kg - container_kg
    h = s2.declared_drop_height(h_m)
    out = {}
    for sc in ("expected", "aggressive"):
        f = common.field_maxima(sc)
        done2 = math.isfinite(t2) and t2 <= RULES["missions"]["window_s"]
        m2 = s2.m2(w, t2 if done2 else 1.0, f["m2"], completed=done2)
        done3 = done2 and laps >= RULES["missions"]["m3_min_laps"] and m3_sensor_kg <= sensor_max + EPS
        m3 = s2.m3(laps, m3_sensor_kg, f["m3"], completed=done3)       # missions fly in order (Sec. 3.3.3)
        gm = s2.gm(sensor_max, h, f["gm"])
        out[sc] = (m2, m3, gm, s2.total_mission(1.0, m2, m3, gm))
    return w, t2, laps, sensor_max, out


# ---------------------------------------------------------------- outputs
def design_points():
    a = common.load("aircraft")
    return {"a01": ("straight", a["a01"]["wing_area_m2"]), "a02": ("delta", a["a02"]["wing_area_m2"])}


MC_RANGES = ("f_body 0.006-0.028 m2, eta 0.45-0.65, airframe x lognormal(sd of the fit), take-off 4-15 s, "
             "pack 27-42 V, rho 1.05-1.10, e x0.9-1.1, CLmax straight x0.9-1.06 (1.44-1.70), delta x0.85-1.30")


def monte_carlo(designs, vs_max, n_draws=300, seed=13):
    """Best M2 rate for each design {label: (family, S)} over the UNCERTAIN inputs only.
    Decisions (S, accepted stall speed, load-factor limit) stay fixed. Paired draws."""
    rng = np.random.default_rng(seed)
    _, _, sd, _ = airframe_fit()
    out = {key: [] for key in designs}
    for _ in range(n_draws):
        P = Params(f_body=rng.uniform(0.006, 0.028), eta=rng.uniform(*SZ["propulsion"]["eta_sweep"]),
                   af_factor=math.exp(rng.normal(0.0, sd)), t_to=rng.uniform(4.0, 15.0),
                   p_max=SZ["battery"]["fuse_a"] * rng.uniform(27.0, 42.0),
                   rho=rng.uniform(*SZ["air"]["rho_sweep"]), e_factor=rng.uniform(0.9, 1.1),
                   clmax_factor={"straight": rng.uniform(0.90, 1.0625), "delta": rng.uniform(0.85, 1.30)},
                   vs_max=vs_max)
        for key, (fam, s) in designs.items():
            out[key].append(m2_search(fam, s, P, fine=False)[0]["rate"])
    return {key: np.array(v) for key, v in out.items()}


def decision_table(vs_list=(12.0, 14.0, 16.0, 18.0)):
    """Best M2 by accepted stall speed and wing: the payload-vs-risk decision."""
    designs = [("a01", "straight", 0.414), ("S 0.60", "straight", 0.60), ("S 0.80", "straight", 0.80),
               ("a02", "delta", 0.83)]
    f_exp = common.field_maxima("expected")["m2"]
    rows = []
    for label, fam, s in designs:
        for vs in vs_list:
            b = m2_search(fam, s, Params(vs_max=vs))[0]
            rows.append((label, fam, s, vs, b, 1 + min(1.0, b["rate"] / f_exp)))
    return rows


def charts(P, sweep, curves, m3, table):
    sys.path.insert(0, str(common.REPO / "design-system" / "matplotlib"))
    import dbfplot as dp
    OUT.mkdir(exist_ok=True)
    dp.use()
    # 1. best M2 rate vs wing area, both families, with field maxima
    fig, ax = dp.figure("col", 2.3)
    for fam, ls in (("straight", "-"), ("delta", "--")):
        ss = [x[0] for x in sweep[fam]]
        ax.plot(ss, [1000 * x[1]["rate"] for x in sweep[fam]], color=dp.INK, ls=ls, lw=1.1,
                label=SZ["config"][fam]["name"].upper())
    for sc, ls in (("aggressive", ":"), ("expected", "-.")):
        f = common.field_maxima(sc)["m2"]
        ax.axhline(1000 * f, color=dp.STEEL, lw=0.7, ls=ls)
        ax.text(1.09, 1000 * f, f"FIELD MAX {sc[:4].upper()}.", ha="right", va="bottom", fontsize=4.6,
                family=dp.MONO, color=dp.STEEL)
    for key, (fam, s) in design_points().items():
        b = m2_search(fam, s, P)[0]
        ax.plot(s, 1000 * b["rate"], "o", ms=3.4, color=dp.INK, zorder=3)
        ax.annotate(key.upper(), (s, 1000 * b["rate"]), xytext=(4, -8), textcoords="offset points",
                    fontsize=5.0, family=dp.MONO)
    ax.set_xlim(0.3, 1.1)
    ax.set_ylim(0, None)
    ax.set_xlabel("Wing area S (m²), span 1.82 m")
    ax.set_ylabel("Best M2 rate W/t (g/s), flown time base")
    dp.tag(ax, "ACCEPTED STALL <= 14 M/S, BASELINE INPUTS", "upper left")
    leg = ax.legend(loc="lower right", fontsize=4.8)
    for t in leg.get_texts():
        t.set_family(dp.MONO)
    dp.save(fig, OUT / "m2_rate_vs_area.pdf")
    # 2. rate vs payload at the design points
    fig, ax = dp.figure("col", 2.1)
    for (key, (pay, rate)), ls in zip(curves.items(), ("-", "--")):
        ax.plot(pay, 1000 * rate, color=dp.INK, ls=ls, lw=1.1, label=key.upper())
    ax.set_xlabel("M2 payload (kg)")
    ax.set_ylabel("Best M2 rate W/t (g/s), flown time base")
    ax.set_xlim(0, SZ["sweep"]["payload_kg"][1])
    ax.set_ylim(0, None)
    leg = ax.legend(loc="upper left", fontsize=5.0)
    for t in leg.get_texts():
        t.set_family(dp.MONO)
    dp.save(fig, OUT / "m2_rate_vs_payload.pdf")
    # 3. M3 laps and laps x sensor mass
    fig, ax = dp.figure("col", 2.1)
    for (key, rows), ls in zip(m3.items(), ("-", ":", "-.")):
        ax.plot([r[0] for r in rows], [r[1] * r[0] for r in rows], color=dp.INK, ls=ls, lw=1.1, marker="o", ms=2.4,
                label=key.upper().replace("A0", "0"))
    for sc, ls in (("aggressive", ":"), ("expected", "-.")):
        ax.axhline(common.field_maxima(sc)["m3"], color=dp.STEEL, lw=0.7, ls=ls)
    ax.set_xlabel("M3 sensor mass towed (kg)")
    ax.set_ylabel("Laps x sensor mass (kg·laps), model")
    leg = ax.legend(loc="upper left", fontsize=5.0)
    for t in leg.get_texts():
        t.set_family(dp.MONO)
    dp.save(fig, OUT / "m3_laps_x_mass.pdf")
    # 4. M2 score vs accepted stall speed (the risk decision)
    fig, ax = dp.figure("col", 2.2)
    for (label, ls) in (("a01", "-"), ("S 0.60", (0, (5, 2))), ("S 0.80", "-."), ("a02", ":")):
        pts = [(vs, sc) for lb, fam, s, vs, b, sc in table if lb == label]
        ax.plot([x[0] for x in pts], [x[1] for x in pts], color=dp.INK, ls=ls, lw=1.1, marker="o", ms=2.4,
                label=label.upper().replace("A0", "0").replace("S 0", "STRAIGHT 0") + (" DELTA" if label == "a02" else ""))
    ax.axvspan(9.4, 14.4, color=dp.BONE, lw=0, zorder=0)
    ax.text(12.9, 1.04, "TOP-3 DESIGN STALL SPEEDS", ha="center", fontsize=4.6, family=dp.MONO, color=dp.STEEL)
    ax.set_xlim(11, 19)
    ax.set_ylim(1.0, 2.0)
    ax.set_xlabel("Accepted 1 g stall speed at M2 weight, flaps (m/s)")
    ax.set_ylabel("M2 score vs expected field (x1.15 times)")
    leg = ax.legend(loc="upper left", fontsize=4.8)
    for t in leg.get_texts():
        t.set_family(dp.MONO)
    dp.save(fig, OUT / "m2_score_vs_stall.pdf")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    P = Params()
    k, p, sd, n_af = airframe_fit()
    whkg, n_pk = pack_specific_energy()
    eta_cal, bank_cal = calibration_eta()
    print("Script 4 (PROVISIONAL)  inputs/sizing.toml + data/dbf_airframes.csv + nRho")
    print(f"  rho {P.rho} kg/m3; airframe {k:.2f} S^{p:.2f} kg (n={n_af}, x{math.exp(sd):.2f} 1-sd); "
          f"battery {P.battery():.3f} kg (100 Wh at {whkg:.0f} Wh/kg, n={n_pk})")
    print(f"  eta_eff {P.eta} (ERAU 2023 M2 calibration gives {eta_cal:.3f} at a {bank_cal:.1f} deg bank); "
          f"usable {P.e_usable:.0f} Wh; peak {P.p_max:.0f} W; take-off {P.t_to:.0f} s")
    pts = design_points()
    curves, m3 = {}, {}
    print("\nBest M2 (five laps) at the design points, baseline inputs:")
    for key, (fam, s) in pts.items():
        b, curve = m2_search(fam, s, P)
        curves[key] = curve
        fm = {sc: common.field_maxima(sc)["m2"] for sc in ("expected", "aggressive")}
        print(f"  {key} {SZ['config'][fam]['name']}: S {s} m2, AR {b['ar']:.2f}, e {b['e']:.3f}, CD0 {b['cd0']:.4f}")
        print(f"     payload {b['payload']:.2f} kg, TOGW {b['mass']:.2f} kg, V {b['v']:.2f} m/s, bank {b['bank']:.0f} deg "
              f"(n {b['n']:.2f}, turn CL {b['cl_turn']:.2f}), stall {b['v_stall']:.1f} m/s")
        print(f"     lap {b['t_lap']:.1f} s, M2 {b['t']:.1f} s (model x{TIME_CAL}), "
              f"energy {b['e_wh']:.1f} Wh, peak {b['p_peak']:.0f} W; binding: {', '.join(b['binding'])}")
        for sc, f in fm.items():
            print(f"     M2 score vs {sc:10} field: {1 + min(1, b['rate'] / f):.2f}")
        m3[key] = [(ms, m3_search(fam, s, ms, P)) for ms in M3_MASSES]
        print("     M3 laps by towed sensor mass: " + ", ".join(f"{ms:g} kg {n}" for ms, n in m3[key]))
    m3["straight 0.80"] = [(ms, m3_search("straight", 0.80, ms, P)) for ms in M3_MASSES]
    print("  straight 0.80 m2, M3 laps by towed sensor mass: "
          + ", ".join(f"{ms:g} kg {n}" for ms, n in m3["straight 0.80"]))
    print("\nWing-area sweep (best M2 rate, g/s):")
    sweep = {}
    for fam in ("straight", "delta"):
        sweep[fam] = [(float(s), m2_search(fam, float(s), P, fine=False)[0])
                      for s in np.round(np.arange(0.30, 1.10 + EPS, 0.05), 2)]
        best = max(sweep[fam], key=lambda x: x[1]["rate"])
        print(f"  {fam:8}: " + " ".join(f"{s:.2f}:{1000 * b['rate']:.0f}" for s, b in sweep[fam])
              + f"   peak at S {best[0]:.2f} ({1000 * best[1]['rate']:.0f} g/s, payload {best[1]['payload']:.1f} kg)")
    print(f"\nDecision table: best M2 by accepted stall speed (M2 score vs expected field, times x{TIME_CAL}):")
    print("  design   family    S m2  Vs<=  payload kg  TOGW kg     M2 s  W/t g/s  M2 score  binding")
    table = decision_table()
    for label, fam, s, vs, b, score in table:
        print(f"  {label:7}  {fam:8}  {s:4.2f}  {vs:4.0f}  {b['payload']:10.2f}  {b['mass']:7.2f}  "
              f"{b['t']:8.1f}  {1000 * b['rate']:7.1f}  {score:8.2f}  {', '.join(b['binding'])}")
    container = 0.6                 # ESTIMATE until TC-02 sizes the foam (kg)
    print(f"\nStrategy table (complete choices; container {container} kg ESTIMATE; M1 waived and credited by M2;"
          " drop 1.524 m; times x1.15):")
    print("  wing            Vs  unit kg  N_sim  W kg  M2 s   M3 sensor  laps  | expected: M2   M3   GM  total"
          " | aggressive: M2   M3   GM  total")
    for fam, s, vs, unit, nsim, m3s in (("straight", 0.414, 14, 3.5, 0, 2.0), ("straight", 0.414, 14, 1.75, 1, 1.15),
                                        ("straight", 0.80, 14, 8.0, 0, 5.0), ("straight", 0.80, 14, 4.0, 1, 3.4),
                                        ("straight", 0.80, 14, 6.0, 0, 5.0), ("straight", 0.80, 16, 11.5, 0, 6.0),
                                        ("delta", 0.83, 14, 3.0, 0, 2.0)):
        w, t2, laps, smax, sc = strategy(fam, s, vs, unit, nsim, m3s, 1.524, container)
        e, a = sc["expected"], sc["aggressive"]
        print(f"  {fam:8} {s:5.3f}  {vs:3.0f}  {unit:7.2f}  {nsim:5d}  {w:5.2f}  {t2:5.1f}  {m3s:9.2f}  {laps:4d}"
              f"  |          {e[0]:4.2f} {e[1]:4.2f} {e[2]:4.2f}  {e[3]:4.2f}"
              f" |            {a[0]:4.2f} {a[1]:4.2f} {a[2]:4.2f}  {a[3]:4.2f}")
    print(f"\nMonte Carlo, 300 paired draws over the uncertain inputs ({MC_RANGES}), accepted stall 14 m/s:")
    designs = {"a01 straight 0.414": ("straight", 0.414), "straight 0.83": ("straight", 0.83),
               "a02 delta 0.83": ("delta", 0.83)}
    mc = monte_carlo(designs, 14.0)
    for key, r in mc.items():
        print(f"  {key:20}: best M2 rate P10 {1000 * np.percentile(r, 10):.0f} / P50 {1000 * np.percentile(r, 50):.0f} "
              f"/ P90 {1000 * np.percentile(r, 90):.0f} g/s")
    print(f"  straight 0.83 beats delta 0.83 (same area, planform only) in "
          f"{100 * np.mean(mc['straight 0.83'] > mc['a02 delta 0.83']):.0f} % of draws")
    print(f"  delta 0.83 beats the 01 placeholder (0.414) in "
          f"{100 * np.mean(mc['a02 delta 0.83'] > mc['a01 straight 0.414']):.0f} % of draws")
    charts(P, sweep, curves, m3, table)
    print("\nwrote out/m2_rate_vs_area.pdf, m2_rate_vs_payload.pdf, m3_laps_x_mass.pdf, m2_score_vs_stall.pdf")


if __name__ == "__main__":
    main()
