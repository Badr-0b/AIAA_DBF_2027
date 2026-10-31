# Copyright © 2026 Badr Obtel. All rights reserved.
"""Propulsion trade (DB-01 D9; PR-01 B07-B10). PROVISIONAL.

    python analysis/prop_trade.py        (about 5 min; writes out/prop_trade_report.txt, .csv, charts)

Question: which motor, propeller and pack fly the Script 6 reference design
(straight wing 0.9 m2, 4 kg payload unit) for the most mission points, inside
the rules (one pack per system <= 100 Wh, fuse <= 100 A and <= the pack's
rating) and inside each part's limits (APC RPM limit, motor rated cell range
and peak current, full-throttle voltage)?

Stage 1 (screen): every T-Motor winding with a measured map x every APC Thin
Electric prop 14-22 in x every verified pack, at the reference operating points
(M2 at W 8 kg and M3 towing 3.4 kg, Script 4's lumped-model speed and bank).
Stage 2: the best systems through the full Script 4/6 mission evaluation with
the Script 3b model (speed and bank re-optimised for each system), scored on
the expected-field total. Motor mass enters as the difference from the class
mass inside the airframe fit (propulsion.toml [mass]).
Nothing here is a decision: the team picks D9 and the parts.
"""
import csv
import re
import sys
import time

import numpy as np

import common
import s1_course as s1
import s3_performance as s3
import s3b_propulsion as pb
import s4_sizing as s4
import s6_studies as s6
from common import G0, OUT

PR = common.load("propulsion")
TR = PR["trade"]
RHO = TR["rho"]
V_END, V_START = PR["battery"]["v_oc_end"], PR["battery"]["v_oc_start"]
V_MID = 0.5 * (V_START + V_END)
S_REF, UNIT_REF = 0.9, 4.0          # Script 6 robust reference (s6_report.txt, 14 Oct)


def candidates():
    reg = __import__("tomllib").loads((common.ANALYSIS / "data" / "prop" / "sources.toml").read_text(encoding="utf-8"))
    motors = []
    for src in (s["id"] for s in reg["source"] if s["id"].startswith("tmotor-")):
        tests = {pb.pdat.variant_key(k) for k in pb.pdat.tmotor_tests(src)}
        for sp in pb.pdat.tmotor_specs(src):
            if pb.pdat.variant_key(sp["variant"]) in tests:
                motors.append(pb.MapMotor(src, sp["variant"]))
    props = [pb.Prop(n) for n in pb.pdat.apc_names() if re.fullmatch(TR["props"], n)]
    comp = pb.pdat.components()["battery"]
    packs = [pb.Battery.from_components(b) for b, d in comp.items() if not d.get("twin_only")]
    return motors, props, packs


def reference_points():
    """Speed, bank and drag of the reference design's M2 (W 8 kg) and M3 (3.4 kg sensor)
    laps under Script 4's lumped model: where Stage 1 compares the systems."""
    P = s4.Params()
    ar, e, clf, clc = s4.family("straight", S_REF, P)
    k = s3.induced_factor(ar, e)
    _, v, bank = s4.grids(True)
    V, B = np.meshgrid(v, bank, indexing="ij")
    out = {}
    for name, extra, pay, f_tow in (("M2", 0.0, 8.0, 0.0), ("M3", 0.0, UNIT_REF - 0.6, P.f_tow)):
        cd0 = P.cd_w + (P.f_body + f_tow) / S_REF
        m = P.empty(S_REF) + P.battery() + pay
        t_lap, p_mean, n, cl = s3.lap(P.rho, V, B, S_REF, cd0, k, m, G0)
        ok = (s3.stall_speed(P.rho, S_REF, m, clf, G0) <= P.vs_max) & (cl <= P.cl_margin * clc) & (n <= P.n_struct)
        e = p_mean / P.eta * (s3.lap(P.rho, V, B, S_REF, cd0, k, m, G0)[0] * 5 + P.t_to) / 3600 * P.time_cal
        if name == "M2":
            t = np.where(ok & (e <= P.e_usable), t_lap, np.inf)
        else:
            t = np.where(ok & (p_mean / P.eta * 300 / 3600 <= P.e_usable), t_lap, np.inf)
        i = np.unravel_index(np.argmin(t), t.shape)
        vv, bb = float(V[i]), float(B[i])
        r = s1.turn_radius(vv, bb, G0)
        turns = s1.TURN_ARC * r
        straight = s1.lap_length(r, s1.STRAIGHTS_M) - turns
        nn = float(s1.load_factor(bb))
        out[name] = {"v": vv, "bank": bb, "n": nn, "mass": m,
                     "d1": float(s3.drag(P.rho, vv, S_REF, cd0, k, m, 1.0, G0)),
                     "dn": float(s3.drag(P.rho, vv, S_REF, cd0, k, m, nn, G0)),
                     "fs": straight / (straight + turns), "ft": turns / (straight + turns)}
    return out


def screen(motors, props, packs, ref):
    """Stage 1: lap-mean battery power at the reference points. Turn limits checked at the
    mid-mission voltage (ok) and at the end-of-mission voltage (ok_end, with margins)."""
    rows = []
    for prop in props:
        ops = {}
        for mis in ("M2", "M3"):
            r = ref[mis]
            for seg, thrust in (("s", r["d1"]), ("t", r["dn"])):
                rpm = float(prop.rpm_for_thrust(RHO, thrust, r["v"]))
                _, p_sh = prop.thrust_power(RHO, rpm, r["v"])
                w = rpm * pb.RPM_TO_RAD
                ops[mis + seg] = (rpm, w, float(p_sh) / w if rpm == rpm else np.nan)
        if any(not np.isfinite(o[0]) for o in ops.values()):
            continue
        for mot in motors:
            p_in = {key: float(mot.p_in(o[1], o[2])) for key, o in ops.items()}
            for pack in packs:
                if not mot.cells_rated[0] <= pack.cells <= mot.cells_rated[1]:
                    continue
                cap = min(PR["fuse"]["rating_a"], pack.i_max, mot.i_peak)

                def turn_ok(v_cell):
                    good, v_marg, i_marg = True, np.inf, np.inf
                    for key in ("M2t", "M3t"):
                        rpm, w, q = ops[key]
                        i = float(pack.current(p_in[key], v_cell))
                        avail, need = pack.volts(i, v_cell), mot.volts_needed(w, q, i)
                        good &= (rpm <= prop.rpm_limit) and (i <= cap) and (need <= avail)
                        v_marg, i_marg = min(v_marg, (avail - need) / avail), min(i_marg, (cap - i) / cap)
                    return bool(good), v_marg, i_marg
                ok_mid, _, _ = turn_ok(V_MID)
                ok_end, vm_end, im_end = turn_ok(V_END)
                m2 = ref["M2"]["fs"] * p_in["M2s"] + ref["M2"]["ft"] * p_in["M2t"]
                m3 = ref["M3"]["fs"] * p_in["M3s"] + ref["M3"]["ft"] * p_in["M3t"]
                rows.append({"motor": mot, "prop": prop, "pack": pack, "ok": ok_mid, "ok_end": ok_end,
                             "v_margin_end": vm_end, "i_margin_end": im_end, "m2_w": m2, "m3_w": m3,
                             "i_turn": float(pack.current(p_in["M2t"], V_END)), "cap": cap,
                             "rpm_turn": ops["M2t"][0], "rpm_frac": ops["M2t"][0] / prop.rpm_limit,
                             "eta_m2": ref["M2"]["v"] * (ref["M2"]["fs"] * ref["M2"]["d1"]
                                                         + ref["M2"]["ft"] * ref["M2"]["dn"]) / m2})
    return rows


def evaluate(system, k_fl, v_check, factor=1.0):
    """Stage 2: the reference design flown with this system (expected field), the turn
    thrust checked at cell voltage v_check."""
    model = pb.PropulsionModel(system, RHO, k_fl, v_check=v_check)
    P = s6.base_params()
    s4.with_propulsion(P, model, system.battery, system.motor.mass * system.n - PR["mass"]["motor_ref_kg"])
    P.power_factor = factor
    r = s6.evaluate("straight", S_REF, UNIT_REF, P, fine=True)
    e = r["expected"]
    return {"total": e["total"], "M2": e["M2"], "M3": e["M3"], "GM": e["GM"], "t2": e["t2"], "w": e["w"],
            "n_sim": e["n_sim"], "laps": r["laps"], "m3_mass": r["m3_mass"], "m2_ok": r["m2_feasible"],
            "tmax30": float(model.t_max(30.0)), "model": model, "P": P}


def robustness(systems, k_fl, grid=((S_REF, UNIT_REF),), extras=None):
    """Monte Carlo: Script 6's paired draws (airframe mass, drag, CLmax, lap-time factor, air
    density, container, ...) plus the propulsion bands of propulsion.toml [uncertainty], the
    same draws for every system. Returns {label: {(S, unit): totals array}} and P(M2)."""
    U = PR["uncertainty"]
    Ps = s6.draws(U["draws"], s6.ST["monte_carlo"]["seed"])
    rng = np.random.default_rng(s6.ST["monte_carlo"]["seed"] + 1)
    pf = rng.uniform(*U["power_factor"], len(Ps))
    tf = rng.uniform(*U["thrust_factor"], len(Ps))
    out = {}
    for label, sysm in systems.items():
        model = pb.PropulsionModel(sysm, RHO, k_fl, v_check=V_MID)
        dcda, dm = (extras or {}).get(label, (0.0, 0.0))      # layout drag area (m2) and mass (kg)
        delta = sysm.motor.mass * sysm.n - PR["mass"]["motor_ref_kg"] + dm
        out[label] = {}
        for s, unit in grid:
            tot, ok = [], []
            for P, f_p, f_t in zip(Ps, pf, tf):
                P2 = s6.copy.copy(P)
                s4.with_propulsion(P2, model, sysm.battery, delta)
                P2.power_factor = f_p
                P2.f_body = P.f_body + dcda
                model.thrust_factor = f_t
                r = s6.evaluate("straight", s, unit, P2)
                tot.append(r["expected"]["total"])
                ok.append(r["m2_feasible"])
            model.thrust_factor = 1.0
            out[label][(s, unit)] = (np.array(tot), np.array(ok))
    return out


def charts(mc_rows, diam):
    """mc_rows: [(label, totals)] in display order; diam: [(cells, D in, row, eval)]."""
    sys.path.insert(0, str(common.REPO / "design-system" / "matplotlib"))
    import dbfplot as dp
    OUT.mkdir(exist_ok=True)
    dp.use()
    fig, ax = dp.figure("page", 2.6)
    labels = [l for l, _ in mc_rows]
    ax.boxplot([t for _, t in mc_rows], vert=False, widths=0.5, showfliers=False, whis=(10, 90),
               medianprops={"color": dp.INK}, boxprops={"color": dp.INK}, whiskerprops={"color": dp.INK},
               capprops={"color": dp.INK})
    ax.plot([t.mean() for _, t in mc_rows], range(1, len(mc_rows) + 1), "D", ms=3, color=dp.INK)
    ax.set_yticks(range(1, len(labels) + 1), [l.upper() for l in labels], fontsize=4.6, family=dp.MONO)
    ax.set_xlabel("Total mission score at the reference design, expected field (120 paired draws)")
    ax.set_title("BOX P25-P75, WHISKERS P10-P90, DIAMOND MEAN", fontsize=5.6, family=dp.MONO, color=dp.GRAPHITE, loc="left")
    ax.grid(axis="y", visible=False)
    dp.save(fig, OUT / "prop_trade_mc.pdf")
    fig, ax = dp.figure("col", 2.2)
    for cells, ls in ((8, "-"), (12, "--"), (13, ":")):
        pts = sorted((d, ev["total"]) for c, d, r, ev in diam if c == cells)
        if pts:
            ax.plot([p[0] for p in pts], [p[1] for p in pts], color=dp.INK, ls=ls, marker="o", ms=2.6, lw=1.0,
                    label=f"{cells}S")
    ax.set_xlabel("Propeller diameter (in, APC Thin Electric)")
    ax.set_ylabel("Total mission score (deterministic)")
    leg = ax.legend(loc="lower left", fontsize=5)
    for t in leg.get_texts():
        t.set_family(dp.MONO)
    dp.save(fig, OUT / "prop_trade_diameter.pdf")


def takeoff_roll(system, mass, s, cd0, clf, mu, rho=RHO, dt=0.02):
    """Ground roll (s, m) at full throttle from rest to 1.2 x stall (flaps), friction mu on
    weight, drag q S CD0 (no lift credit: conservative). Report only."""
    v_lof = 1.2 * float(s3.stall_speed(rho, s, mass, clf, G0))
    v, x, t = 0.0, 0.0, 0.0
    while v < v_lof and t < 60:
        thrust = float(system.thrust_max(rho, v, V_START, iters=24))
        a = (thrust - 0.5 * rho * v * v * s * cd0 - mu * mass * G0) / mass
        if a <= 0:
            return np.inf, np.inf
        v, x, t = v + a * dt, x + v * dt, t + dt
    return t, x


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    t0 = time.time()
    cal = pb.calibrate_flight()
    k_fl = cal["k_fl"]
    motors, props, packs = candidates()
    ref = reference_points()
    lines = ["Propulsion trade (PROVISIONAL), Script 3b component model. Reference design: straight wing "
             f"{S_REF} m2, {UNIT_REF:.0f} kg payload unit (Script 6).",
             f"Flight factor k_fl = {k_fl:.3f} (ERAU 2023 M2: model {cal['p_model']:.0f} W, measured {cal['p_meas']:.0f} W, "
             f"with ERAU's own APC 20x13E, AT7215 KV220 and 12S).",
             f"Candidates: {len(motors)} T-Motor windings with measured maps, {len(props)} APC Thin Electric props "
             f"14-22 in, {len(packs)} packs.", ""]
    for mis, r in ref.items():
        lines.append(f"  reference {mis}: {r['mass']:.2f} kg at {r['v']:.2f} m/s, bank {r['bank']:.0f} deg (n {r['n']:.2f}): "
                     f"drag {r['d1']:.1f} N straight, {r['dn']:.1f} N turn; turns {100 * r['ft']:.0f} % of the lap")
    rows = screen(motors, props, packs, ref)
    feas = [r for r in rows if r["ok"]]
    n_end = sum(r["ok_end"] for r in rows)
    lines += ["", f"Stage 1: {len(rows)} combinations inside the motors' rated cell ranges. Turn limits (APC RPM limit, "
              f"current cap, full-throttle voltage) met by {len(feas)} at the mid-mission voltage ({V_MID:.3f} V/cell) and "
              f"by {n_end} at the end-of-mission voltage ({V_END} V/cell, measured resting value after a full M2)."]
    by_pack = {}
    for r in feas:
        by_pack.setdefault(r["pack"].name, []).append(r)
    lines.append("  best per pack (lowest M2 + M3 lap-mean battery power; end-of-mission margins: voltage, current):")
    keep = []
    for name, rs in sorted(by_pack.items(), key=lambda kv: min(x["m2_w"] + x["m3_w"] for x in kv[1])):
        rs.sort(key=lambda x: x["m2_w"] + x["m3_w"])
        b = rs[0]
        lines.append(f"    {name:42} {b['motor'].name:24} APC {b['prop'].name:7} M2 {b['m2_w']:5.0f} W M3 {b['m3_w']:5.0f} W"
                     f"  eta(M2) {b['eta_m2']:.3f}  end: V {100 * b['v_margin_end']:+5.1f} %, I {100 * b['i_margin_end']:+5.1f} %")
        keep += rs[:4]
    missing = sorted({p.name for p in packs} - set(by_pack))
    for name in missing:
        lines.append(f"    {name:42} no motor in the measured-map set meets the turn limits (rated cells, Kv, current)")
    feas.sort(key=lambda x: x["m2_w"] + x["m3_w"])
    for r in feas:
        if len(keep) >= TR["stage2_keep"]:
            break
        if r not in keep:
            keep.append(r)
    lines += ["", f"Stage 2: {len(keep)} systems through the Script 4/6 mission evaluation at the reference design (speed and "
              "bank re-optimised per system; expected field; motor and pack mass charged). 'total' checks the M2/M3 turn "
              "thrust at the mid-mission voltage; 'end' at the end-of-mission voltage (worst case)."]
    legacy = s6.evaluate("straight", S_REF, UNIT_REF, s6.base_params(), fine=True)["expected"]
    lines.append(f"  lumped-eta reference (eta 0.58, 100 Wh at 142 Wh/kg): total {legacy['total']:.2f} (M2 {legacy['M2']:.2f}, "
                 f"M3 {legacy['M3']:.2f}, GM {legacy['GM']:.2f}; M2 {legacy['t2']:.1f} s)")
    res = []
    for r in keep:
        sysm = pb.System(r["prop"], r["motor"], r["pack"])
        ev = evaluate(sysm, k_fl, V_MID)
        ev_end = evaluate(sysm, k_fl, V_END)
        ev["total_end"], ev["t2_end"] = ev_end["total"], ev_end["t2"]
        ev["t0"] = float(sysm.thrust_max(RHO, 0.0, V_START))
        ev["mass_delta"] = sysm.motor.mass - PR["mass"]["motor_ref_kg"] + sysm.battery.mass - 100.0 / ev["P"].wh_per_kg
        res.append((r, sysm, ev))
    res.sort(key=lambda x: (-x[2]["total"], -x[2]["total_end"]))
    lines.append("   rank  motor                    prop      pack                                       total  end    M2    M3"
                 "   M2 s  laps  static N  T@30 N  dmass kg")
    for i, (r, sysm, ev) in enumerate(res, 1):
        lines.append(f"   {i:4d}  {r['motor'].name:24} {r['prop'].name:8}  {r['pack'].name:42} {ev['total']:5.2f}  "
                     f"{ev['total_end']:5.2f}  {ev['M2']:4.2f}  {ev['M3']:4.2f}  {ev['t2']:5.1f}  {ev['laps']:4d}  "
                     f"{ev['t0']:7.1f}  {ev['tmax30']:6.1f}  {ev['mass_delta']:+.3f}")
    # ---- Monte Carlo: best system per pack, plus the lumped-eta model on the same draws
    best = {}
    for r, sysm, ev in res:
        best.setdefault(r["pack"].name, (r, sysm, ev))
    systems = {f"{r['pack'].name} | {r['motor'].name} | APC {r['prop'].name}": sysm for r, sysm, ev in best.values()}
    mc = robustness(systems, k_fl)
    Ps = s6.draws(PR["uncertainty"]["draws"], s6.ST["monte_carlo"]["seed"])
    leg = np.array([s6.evaluate("straight", S_REF, UNIT_REF, P)["expected"]["total"] for P in Ps])
    lines += ["", f"Monte Carlo at the reference ({PR['uncertainty']['draws']} paired draws: Script 6 draws + battery power "
              f"x U{tuple(PR['uncertainty']['power_factor'])} + available thrust x U{tuple(PR['uncertainty']['thrust_factor'])}):",
              "  system                                                                           mean   P10   P50   P90  P(M2)"]
    lines.append(f"  {'lumped eta (Script 6 draws, eta 0.45-0.65)':80} {leg.mean():5.2f} {np.percentile(leg, 10):5.2f} "
                 f"{np.median(leg):5.2f} {np.percentile(leg, 90):5.2f}")
    ranked = sorted(mc.items(), key=lambda kv: -kv[1][(S_REF, UNIT_REF)][0].mean())
    top_tot = ranked[0][1][(S_REF, UNIT_REF)][0]
    for label, d in ranked:
        tot, ok = d[(S_REF, UNIT_REF)]
        cmp = "" if tot is top_tot else (f"   best beats it in {100 * np.mean(top_tot > tot + 1e-9):3.0f} % of draws, "
                                         f"mean gain {np.mean(top_tot - tot):+.3f}")
        lines.append(f"  {label:80} {tot.mean():5.2f} {np.percentile(tot, 10):5.2f} {np.median(tot):5.2f} "
                     f"{np.percentile(tot, 90):5.2f}  {100 * ok.mean():3.0f} %{cmp}")
    # ---- does the reference design still hold with real propulsion? (wing area x unit neighbourhood)
    grid = [(s, u) for s in (0.8, 0.9, 1.0) for u in (3.0, 4.0, 5.0)]
    picks = {}
    for label, sysm in systems.items():
        cells = sysm.battery.cells
        key = "8S" if cells == 8 else f"{cells}S"
        if key not in picks or mc[label][(S_REF, UNIT_REF)][0].mean() > mc[picks[key][0]][(S_REF, UNIT_REF)][0].mean():
            picks[key] = (label, sysm)
    chosen = dict(sorted(picks.values(), key=lambda x: -mc[x[0]][(S_REF, UNIT_REF)][0].mean())[:2])
    nb = robustness(chosen, k_fl, grid)
    lines += ["", "Reference check with real propulsion: mean total (P(M2 feasible)) over the same draws, wing area x unit:"]
    for label, d in nb.items():
        lines.append(f"  {label}")
        lines.append("     S m2 \\ unit kg      3.0             4.0             5.0")
        for s in (0.8, 0.9, 1.0):
            lines.append(f"     {s:4.1f}        " + "  ".join(f"{d[(s, u)][0].mean():5.2f} ({100 * d[(s, u)][1].mean():3.0f} %)"
                                                         for u in (3.0, 4.0, 5.0)))
        bs = max(d, key=lambda k: d[k][0].mean())
        lines.append(f"     best cell: S {bs[0]} m2, unit {bs[1]} kg")
    # ---- propeller diameter: best feasible system per diameter (ground clearance sets the gear height)
    lines += ["", "Propeller diameter (ground clearance drives tricycle-gear height): best Stage-1 system per diameter, "
              "evaluated as Stage 2 (deterministic, mid-voltage check):",
              "  D in   cells  motor                    prop      total   M2 s   tip clearance radius mm"]
    diam = []
    for cells in sorted({r["pack"].cells for r in feas}):
        for d_in in sorted({round(r["prop"].D / pb.IN_M, 1) for r in feas if r["pack"].cells == cells}):
            cand = [r for r in feas if r["pack"].cells == cells and abs(r["prop"].D / pb.IN_M - d_in) < 0.05]
            if not cand:
                continue
            r = min(cand, key=lambda x: x["m2_w"] + x["m3_w"])
            ev = evaluate(pb.System(r["prop"], r["motor"], r["pack"]), k_fl, V_MID)
            diam.append((cells, d_in, r, ev))
            lines.append(f"  {d_in:4.1f}   {cells:4d}S  {r['motor'].name:24} {r['prop'].name:8}  {ev['total']:5.2f}  {ev['t2']:5.1f}   "
                         f"{1000 * r['prop'].D / 2:5.0f}")
    # ---- take-off roll (report only)
    lines += ["", f"Take-off roll at M2 weight, full throttle from rest to 1.2 x flapped stall (friction {TR['mu_roll']}, no lift "
              "credit), fresh pack:"]
    P0 = s4.Params()
    ar, e, clf, clc = s4.family("straight", S_REF, P0)
    cd0 = P0.cd_w + P0.f_body / S_REF
    for label, sysm in systems.items():
        m = s4.Params().empty(S_REF) + sysm.motor.mass - PR["mass"]["motor_ref_kg"] + sysm.battery.mass + 8.0
        tr, xr = takeoff_roll(sysm, m, S_REF, cd0, clf, TR["mu_roll"])
        lines.append(f"  {label:80} {m:5.2f} kg: {tr:4.1f} s, {xr:5.1f} m")
    # ---- layout: twin tractor (two systems, two identical 50 Wh packs) vs the best single, same draws
    LY = PR["layout"]
    twin_pack = pb.Battery.from_components(LY["twin_pack"])
    tw = []
    for mot in (m for m in motors if m.cells_rated[0] <= twin_pack.cells <= m.cells_rated[1]):
        for prop in (p for p in props if p.D <= 18.0 * pb.IN_M):
            sysm = pb.System(prop, mot, twin_pack, n=2)
            pw, ok = 0.0, True
            for mis in ("M2", "M3"):
                r = ref[mis]
                pt = sysm.point(RHO, np.array([r["d1"], r["dn"]]), r["v"], V_MID)
                ok &= bool(pt["ok"][1]) and bool(np.isfinite(pt["p_batt"]).all())
                pw += r["fs"] * pt["p_batt"][0] + r["ft"] * pt["p_batt"][1]
            if ok:
                tw.append((pw, sysm))
    tw.sort(key=lambda x: x[0])
    lines += ["", f"Layout: twin tractor, two systems on {twin_pack.name} (2 x {twin_pack.energy_wh:.1f} Wh, 2 x 100 A fuses), "
              f"+{LY['twin_extra_kg']} kg and +{1e4 * LY['twin_extra_cda_m2']:.0f} cm2 drag area (ESTIMATES) vs a single nose motor:",
              f"  {len(tw)} twin motor-prop pairs meet the turn limits at the mid-mission voltage (6S-rated windings, props <= 18 in)."]
    if tw:
        twins = {f"TWIN 2x {s.motor.name} | 2x APC {s.prop.name} | 2x 6S 2250": s for _, s in tw[:3]}
        ext = {k: (LY["twin_extra_cda_m2"], LY["twin_extra_kg"]) for k in twins}
        mt = robustness(twins, k_fl, extras=ext)
        for label, d in mt.items():
            tot, ok = d[(S_REF, UNIT_REF)]
            lines.append(f"  {label:80} mean {tot.mean():5.2f}  P10 {np.percentile(tot, 10):5.2f}  P(M2) {100 * ok.mean():3.0f} %"
                         f"   best single beats it in {100 * np.mean(top_tot > tot + 1e-9):3.0f} % of draws, "
                         f"mean gain {np.mean(top_tot - tot):+.3f}")
        mt0 = robustness(twins, k_fl, extras={k: (0.0, 0.0) for k in twins})
        for label, d in mt0.items():
            tot = d[(S_REF, UNIT_REF)][0]
            lines.append(f"  with NO layout penalty, {label.split(' | ')[0]} {label.split(' | ')[1]}: mean {tot.mean():5.2f}; "
                         f"best single still ahead in {100 * np.mean(top_tot > tot + 1e-9):3.0f} % of draws")
        mc.update(mt)
    OUT.mkdir(exist_ok=True)
    with (OUT / "prop_trade_mc.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["system", "S_m2", "unit_kg", "mean", "p10", "p50", "p90", "p_m2"])
        for src in (mc, nb):
            for label, d in src.items():
                for (s, u), (tot, ok) in d.items():
                    w.writerow([label, s, u, f"{tot.mean():.4f}", f"{np.percentile(tot, 10):.4f}", f"{np.median(tot):.4f}",
                                f"{np.percentile(tot, 90):.4f}", f"{ok.mean():.3f}"])
    with (OUT / "prop_trade_stage2.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["motor", "prop", "pack", "cells", "total_mid", "total_end", "M2", "M3", "GM", "t2_s", "laps",
                    "static_N", "tmax30_N", "mass_delta_kg", "m2_w_screen", "m3_w_screen", "v_margin_end", "i_margin_end"])
        for r, sysm, ev in res:
            w.writerow([r["motor"].name, r["prop"].name, r["pack"].name, r["pack"].cells, f"{ev['total']:.4f}",
                        f"{ev['total_end']:.4f}", f"{ev['M2']:.4f}", f"{ev['M3']:.4f}", f"{ev['GM']:.4f}", f"{ev['t2']:.2f}",
                        ev["laps"], f"{ev['t0']:.2f}", f"{ev['tmax30']:.2f}", f"{ev['mass_delta']:.4f}", f"{r['m2_w']:.1f}",
                        f"{r['m3_w']:.1f}", f"{r['v_margin_end']:.4f}", f"{r['i_margin_end']:.4f}"])
    allsys = {**systems, **(twins if tw else {})}

    def short(label):
        s_ = allsys[label]
        brand = "TP" if "Thunder" in s_.battery.name else "MaxAmps"
        c = re.search(r"(\d+)C\)", s_.battery.name)
        return (f"{'2x ' if s_.n == 2 else ''}{s_.motor.name.replace('T-Motor ', '')} / APC {s_.prop.name} / "
                f"{s_.battery.cells}S {1000 * s_.battery.capacity:.0f} {brand}{' ' + c.group(1) + 'C' if c else ''}")
    rows_mc = sorted(((short(k), d[(S_REF, UNIT_REF)][0]) for k, d in mc.items()), key=lambda x: x[1].mean())
    charts([("lumped eta 0.58 (Script 6)", leg)] + rows_mc, diam)
    lines.append("\nwrote out/prop_trade_report.txt, prop_trade_stage2.csv, prop_trade_mc.csv, prop_trade_mc.pdf, "
                 "prop_trade_diameter.pdf")
    lines.append(f"\n({time.time() - t0:.0f} s)")
    (OUT / "prop_trade_report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return res, rows, ref, cal


if __name__ == "__main__":
    main()
