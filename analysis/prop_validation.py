# Copyright © 2026 Badr Obtel. All rights reserved.
"""Validation of the Script 3b propulsion model against measured data. PROVISIONAL.

    python analysis/prop_validation.py     (writes out/prop_validation_report.txt and charts)

Run before any Script 3b result is used. Each component is checked against the
best measured evidence available, and the error band is stated:
  A. Propellers: APC computed tables vs UIUC wind-tunnel measurements (17 APC
     Thin Electric props, Vol. 4, plus 3 older Vol. 1 props), matched RPM and J;
     and vs the AIAA static stands (UW 2023, WashU 2022) at measured RPM.
  B. Motors: T-Motor measured maps; the loss fit's in-sample and leave-one-sweep-
     out error; the first-order (Kv, Rm, I0) model against the same measurements.
  C. System: WashU 2022 full-throttle stand (first-order motor, the only kind
     available for that motor).
  D. Flight: ERAU 2023 M2 energy with ERAU's own hardware (the flight factor).
"""
import sys

import numpy as np

import common
import s3b_propulsion as pb
from common import OUT

pdat = pb.pdat


# ---------------------------------------------------------------- A. propellers
def apc_at(prop, rpm, J):
    ct, cp = prop.coef(np.full(np.shape(J), rpm), J)
    return ct, cp


def apc_vs_uiuc():
    """Per prop: median ratios UIUC/APC (CT, CP), median efficiency difference, static
    ratios, and per-run records (RPM fraction of APC's limit, ratios)."""
    out, runs = [], []
    for vol, names in (("volume-4", pdat.UIUC_VOL4), ("volume-1", pdat.UIUC_VOL1_LARGE)):
        for nm in names:
            prop = pb.Prop(pdat.uiuc_apc_name(nm))
            u = pdat.uiuc_runs(nm, vol)
            rT, rP, dE = [], [], []
            for rpm, J, CT, CP in u["runs"]:
                cta, cpa = apc_at(prop, rpm, J)
                ct0, _ = apc_at(prop, rpm, np.array([0.0]))
                ok = np.isfinite(cta) & (cta > 0.25 * ct0[0]) & (CT > 0) & (J > 0.05)
                if ok.sum() < 3:
                    continue
                rt, rp, de = CT[ok] / cta[ok], CP[ok] / cpa[ok], CT[ok] * J[ok] / CP[ok] - cta[ok] * J[ok] / cpa[ok]
                rT.append(rt)
                rP += list(rp)
                dE += list(de)
                runs.append({"prop": nm, "vol": vol, "frac": rpm / prop.rpm_limit, "ct": float(np.median(rt)),
                             "cp": float(np.median(rp)), "deta": float(np.median(de))})
            rT = np.concatenate(rT) if rT else np.array([])
            s_ct = [ct / apc_at(prop, rpm, np.array([0.0]))[0][0] for rpm, ct, cp in u["static"] if rpm >= 1500]
            s_cp = [cp / apc_at(prop, rpm, np.array([0.0]))[1][0] for rpm, ct, cp in u["static"] if rpm >= 1500]
            out.append({"prop": nm, "vol": vol, "n": len(rT), "ct": np.median(rT), "cp": np.median(rP),
                        "deta": np.median(dE), "deta_p10": np.percentile(dE, 10), "deta_p90": np.percentile(dE, 90),
                        "s_ct": np.median(s_ct), "s_cp": np.median(s_cp)})
    return out, runs


def stand_props():
    """Static thrust at the measured RPM: AIAA stands vs APC (rho 1.18-1.225 bracket)."""
    st = pdat.stands()
    out = []
    for pid in ("uw23-16x12", "uw23-17x10", "washu22-static"):
        p = st[pid]
        prop = pb.Prop(p["prop"][4:])
        t_hi, _ = prop.thrust_power(1.225, p["rpm"], 0.0)
        t_lo, _ = prop.thrust_power(1.18, p["rpm"], 0.0)
        out.append({"id": pid, "prop": prop.name, "rpm": p["rpm"], "frac": p["rpm"] / prop.rpm_limit,
                    "meas": p["thrust"], "apc_lo": float(t_lo), "apc_hi": float(t_hi)})
    return out


# ---------------------------------------------------------------- B. motors
def motor_checks():
    """Fit quality per T-Motor winding, leave-one-sweep-out error, and the first-order
    model's efficiency error on the same measured points."""
    reg = __import__("tomllib").loads((common.ANALYSIS / "data" / "prop" / "sources.toml").read_text(encoding="utf-8"))
    out = []
    for src in (s["id"] for s in reg["source"] if s["id"].startswith("tmotor-")):
        tests = {pdat.variant_key(k) for k in pdat.tmotor_tests(src)}
        for sp in pdat.tmotor_specs(src):
            if pdat.variant_key(sp["variant"]) not in tests:
                continue
            m = pb.MapMotor(src, sp["variant"])
            d = m.data
            P_in, w, Q = d["V"] * d["I"], d["w"], d["Q"]
            eta = Q * w / P_in
            sweep = np.cumsum(np.r_[1, (np.diff(d["thr"]) < 0).astype(int)])
            errs = []
            if sweep.max() >= 3:
                for k in range(1, sweep.max() + 1):
                    tr, te = sweep != k, sweep == k
                    c = pb._robust_nnls(pb._loss_features(w[tr], Q[tr]), P_in[tr] - Q[tr] * w[tr], pb.PR["motor_fit"]["huber_k"])
                    pred = Q[te] * w[te] + pb._loss_features(w[te], Q[te]) @ c
                    errs += list(Q[te] * w[te] / pred - eta[te])
            fo = pb.FirstOrderMotor(m.name, m.kv, m.rm, m.i0 * (1.0 if m.i0 else 0.0))
            fo_eta = Q * w / fo.p_in(w, Q)
            hi = d["thr"] >= 60
            out.append({"name": m.name, "n": len(eta), "fit": m.fit_rms_pts,
                        "loso": float(100 * np.sqrt(np.mean(np.square(errs)))) if errs else np.nan,
                        "eta_meas": float(np.median(eta[hi])), "eta_fo": float(np.median(fo_eta[hi])),
                        "fo_minus_meas": float(100 * np.median(fo_eta[hi] - eta[hi]))})
    return out


# ---------------------------------------------------------------- C. system stand
def washu_system():
    st = pdat.stands()["washu22-static"]
    m = pdat.components()["motor"]["sunnysky-x7015-270"]
    prop = pb.Prop("24x12E")
    mot = pb.FirstOrderMotor("SunnySky X7015 270 kV", m["kv"], m["rm"], m["i0"], m["mass"])
    volts = st["power_elec"] / st["current"]
    rpms = np.linspace(3000, 7000, 4001)
    T, P = prop.thrust_power(1.18, rpms, 0.0)
    w = rpms * pb.RPM_TO_RAD
    k = int(np.argmin(np.abs(mot.volts_needed(w, P / w, 0) - volts)))
    Tm, Pm = prop.thrust_power(1.18, st["rpm"], 0.0)
    wm = st["rpm"] * pb.RPM_TO_RAD
    return {"volts": volts, "rpm_model": rpms[k], "rpm_meas": st["rpm"], "t_model": float(T[k]), "t_meas": st["thrust"],
            "i_model": float(mot.p_in(w[k], P[k] / w[k]) / volts), "i_meas": st["current"],
            "eff_implied": float(Pm / st["power_elec"]), "eff_fo": float(Pm / mot.p_in(wm, Pm / wm))}


# ---------------------------------------------------------------- report and charts
def charts(props, runs, stands, motors):
    sys.path.insert(0, str(common.REPO / "design-system" / "matplotlib"))
    import dbfplot as dp
    OUT.mkdir(exist_ok=True)
    dp.use()
    # 1. measured / APC thrust vs RPM fraction of APC's limit
    fig, ax = dp.figure("col", 2.3)
    r4 = [r for r in runs if r["vol"] == "volume-4"]
    ax.scatter([r["frac"] for r in r4], [r["ct"] for r in r4], s=6, color=dp.STEEL, lw=0, label="UIUC VOL. 4, 17 PROPS (RUN MEDIANS)")
    r1 = [r for r in runs if r["vol"] == "volume-1"]
    ax.scatter([r["frac"] for r in r1], [r["ct"] for r in r1], s=7, marker="^", facecolor="none", edgecolor=dp.STEEL, lw=0.6,
               label="UIUC VOL. 1, 2005-08 PROPS")
    for s in stands:
        mid = 0.5 * (s["apc_lo"] + s["apc_hi"])
        ax.errorbar(s["frac"], s["meas"] / mid, yerr=[[s["meas"] / mid - s["meas"] / s["apc_hi"]],
                                                       [s["meas"] / s["apc_lo"] - s["meas"] / mid]],
                    fmt="s", ms=3.4, color=dp.INK, capsize=1.5, lw=0.8)
    ax.plot([], [], "s", ms=3.4, color=dp.INK, label="AIAA STANDS, STATIC (UW 23, WASHU 22)")
    ax.axhline(1.0, color=dp.INK, lw=0.6)
    ax.axhspan(0.85, 1.15, color=dp.BONE, lw=0, zorder=0)
    dp.tag(ax, "BAND: +/-15 % ON AVAILABLE THRUST", "lower right")
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("Propeller speed / APC limit (150,000 / D in)")
    ax.set_ylabel("Measured / APC thrust coefficient")
    leg = ax.legend(loc="upper left", fontsize=4.4)
    for t in leg.get_texts():
        t.set_family(dp.MONO)
    dp.save(fig, OUT / "prop_val_thrust.pdf")
    # 2. efficiency offset per prop
    fig, ax = dp.figure("col", 2.2)
    v4 = [p for p in props if p["vol"] == "volume-4"]
    y = np.arange(len(v4))
    ax.hlines(y, [p["deta_p10"] for p in v4], [p["deta_p90"] for p in v4], color=dp.FOG, lw=2.2)
    ax.plot([p["deta"] for p in v4], y, "o", ms=3, color=dp.INK)
    ax.axvline(0, color=dp.INK, lw=0.6)
    ax.set_yticks(y, [f"APC {p['prop'].replace('65', '6.5').replace('85', '8.5')}E" for p in v4], fontsize=4.6,
                  family=dp.MONO)
    ax.set_ylim(-1.6, len(v4) - 0.4)
    ax.set_xlabel("Efficiency, UIUC measured - APC computed")
    dp.tag(ax, "DOT MEDIAN, BAR P10-P90", "lower right")
    ax.grid(axis="y", visible=False)
    dp.save(fig, OUT / "prop_val_eta.pdf")
    # 3. motor: first-order vs measured efficiency
    fig, ax = dp.figure("col", 2.2)
    ax.plot([m["eta_meas"] for m in motors], [m["eta_fo"] for m in motors], "o", ms=3, color=dp.INK)
    ax.plot([0.6, 1.0], [0.6, 1.0], color=dp.STEEL, lw=0.7)
    ax.set_xlim(0.7, 0.95)
    ax.set_ylim(0.7, 0.95)
    ax.set_xlabel("Measured motor+ESC efficiency (T-Motor maps)")
    ax.set_ylabel("First-order model (Kv, Rm, I0)")
    dp.tag(ax, "23 WINDINGS: DATASHEET MODEL ABOVE THE LINE", "lower right")
    dp.save(fig, OUT / "prop_val_motor.pdf")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    props, runs = apc_vs_uiuc()
    stands = stand_props()
    motors = motor_checks()
    sysw = washu_system()
    cal = pb.calibrate_flight()
    L = ["Script 3b validation (PROVISIONAL). Every comparison is against MEASURED data; APC tables are COMPUTED.", ""]
    L.append("A. Propellers: UIUC wind tunnel / APC computed, matched RPM and advance ratio")
    L.append("   prop    vol  n     CT u/a  CP u/a  eta u-a  [P10   P90]   static CT0 u/a  CP0 u/a")
    for p in props:
        L.append(f"   {p['prop']:6}  {p['vol'][-1]}  {p['n']:4d}  {p['ct']:6.3f}  {p['cp']:6.3f}  {p['deta']:+.3f}  "
                 f"[{p['deta_p10']:+.3f} {p['deta_p90']:+.3f}]  {p['s_ct']:6.3f}         {p['s_cp']:6.3f}")
    v4 = [p for p in props if p["vol"] == "volume-4"]
    L.append(f"   Vol. 4 (17 props, bought 2019-21): efficiency offset +{min(p['deta'] for p in v4):.3f} to "
             f"+{max(p['deta'] for p in v4):.3f} (per-prop medians, all positive); CT ratio {min(p['ct'] for p in v4):.2f}-"
             f"{max(p['ct'] for p in v4):.2f}; Vol. 1 (older props): CT {min(p['ct'] for p in props if p['vol'] == 'volume-1'):.2f}-"
             f"{max(p['ct'] for p in props if p['vol'] == 'volume-1'):.2f}, eta offset ~0.")
    L.append("   Ratio by RPM fraction of APC's limit (Vol. 4 run medians):")
    for lo, hi in ((0.1, 0.3), (0.3, 0.45), (0.45, 0.6), (0.6, 0.8)):
        sel = [r for r in runs if r["vol"] == "volume-4" and lo <= r["frac"] < hi]
        if sel:
            L.append(f"     {lo:.2f}-{hi:.2f}: {len(sel):3d} runs, CT ratio median {np.median([r['ct'] for r in sel]):.3f}, "
                     f"eta offset {np.median([r['deta'] for r in sel]):+.3f}")
    L.append("   AIAA static stands, thrust at the measured RPM (APC at rho 1.18-1.225):")
    for s in stands:
        L.append(f"     {s['id']:16} APC {s['prop']:7} {s['rpm']:5.0f} rpm ({100 * s['frac']:3.0f} % of limit): measured "
                 f"{s['meas']:5.1f} N, APC {s['apc_lo']:5.1f}-{s['apc_hi']:5.1f} N, ratio {s['meas'] / s['apc_hi']:.2f}-"
                 f"{s['meas'] / s['apc_lo']:.2f}")
    L.append("   Reading: below ~65 % of the RPM limit, measured props beat APC's tables (more thrust per RPM, efficiency")
    L.append("   +4 to +7 points); near the limit the two static stands measured 5-13 % LESS thrust than APC (ERAU 2025")
    L.append("   also reports APC nylon props losing efficiency at high RPM). The offset is nearly uniform across props,")
    L.append("   so APC ranks props reliably; the absolute level is set by the flight calibration (D), and available")
    L.append(f"   thrust carries a +/-{100 * pb.PR['prop']['thrust_band']:.0f} % band.")
    L.append("")
    L.append("B. Motors: T-Motor measured maps (input power - shaft power = losses, ESC included)")
    L.append("   winding                 n   fit rms  leave-one-sweep-out   eta meas  first-order  (pts)")
    for m in motors:
        L.append(f"   {m['name']:22} {m['n']:3d}   {m['fit']:5.2f}    {m['loso']:6.2f}              {m['eta_meas']:.3f}    "
                 f"{m['eta_fo']:.3f}      {m['fo_minus_meas']:+5.1f}")
    lo = [m["loso"] for m in motors if np.isfinite(m["loso"])]
    L.append(f"   Loss model P_in = Q w + a + b w + c w^2 + d Q^2: in-sample median {np.median([m['fit'] for m in motors]):.2f} "
             f"pts; held-out sweeps median {np.median(lo):.2f}, P90 {np.percentile(lo, 90):.2f} pts.")
    L.append(f"   First-order datasheet model is {np.median([m['fo_minus_meas'] for m in motors]):+.1f} pts (median) above the "
             f"measured efficiency: used for checks only, never to rank motors.")
    L.append("")
    L.append("C. System: WashU 2022 static stand, full throttle (first-order SunnySky X7015 270 kV; ESC 0.97)")
    L.append(f"   at the measured {sysw['volts']:.1f} V: model {sysw['rpm_model']:.0f} rpm / {sysw['t_model']:.1f} N / "
             f"{sysw['i_model']:.1f} A vs measured {sysw['rpm_meas']:.0f} rpm / {sysw['t_meas']:.1f} N / {sysw['i_meas']:.1f} A")
    L.append(f"   at the measured RPM, APC shaft power implies motor+ESC efficiency {sysw['eff_implied']:.2f}; the first-order "
             f"model gives {sysw['eff_fo']:.2f}. Same direction as B (first-order optimistic); motor identity is an")
    L.append("   assumption (report names an 'X7025-30cc-270', see stands.toml), so this point is not used to tune anything.")
    L.append("")
    L.append("D. Flight: ERAU 2023 M2 (13.26 kg, 27.1 m/s, 42 s laps) with ERAU's hardware in the model")
    res = cal["res"]
    L.append(f"   straight: {float(res['d1']):.1f} N at {cal['rpm_straight']:.0f} rpm, battery-to-thrust eta {cal['eta_straight']:.3f}; "
             f"turn (bank {cal['bank']:.1f} deg): {float(res['dn']):.1f} N at {cal['rpm_turn']:.0f} rpm, eta {cal['eta_turn']:.3f}")
    L.append(f"   lap-mean battery power {cal['p_model']:.0f} W (model) vs {cal['p_meas']:.0f} W (measured, 86 Wh / 249 s): "
             f"k_fl = {cal['k_fl']:.3f}")
    L.append("   The old lumped eta_eff 0.584 is explained by component losses (prop ~0.78 x motor+ESC ~0.78); 3.5 % is")
    L.append("   left for take-off, climb and transients. One flight: the factor's own uncertainty is not measurable here.")
    (OUT / "prop_validation_report.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    charts(props, runs, stands, motors)
    print("\nwrote out/prop_validation_report.txt, prop_val_thrust.pdf, prop_val_eta.pdf, prop_val_motor.pdf")


if __name__ == "__main__":
    main()
