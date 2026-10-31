# Copyright © 2026 Badr Obtel. All rights reserved.
"""Wing CLmax, clean and with part-span plain flaps (evidence gap E03, 3-D step).

    PYTHONIOENCODING=utf-8 python analysis/wing_clmax.py      (run clmax_study.py first)

Question: what CLmax does a 0.8-1.0 m2 wing on the 1.82 m span reach with the
measured section data, clean and flapped? sizing.toml carries ESTIMATES of 1.25
(clean, used for the turn limit) and 1.6 (flapped, sets W/S at the stall bound).

Method (critical-section, the standard first-stall criterion):
1. AVL 3.52 (vortex lattice, inviscid, linear) gives each spanwise strip's cl at
   alpha 0 and 10 deg; linearity gives cl(alpha) for every strip. Section lift
   slope is set to the MEASURED SD7037/AG40d slope with AVL's CLAF factor.
2. The flap enters as an equivalent twist of the flapped strips:
   d_alpha = dCl / a0, with dCl the MEASURED lift increment of the AG40d-02r 25 %
   plain flap at alpha -2..2 deg (Williamson 2012, thesis Sec. 6.1 method) and a0
   its measured lift slope. AVL's own flap model is linear thin-airfoil theory,
   which over-predicts a plain flap's lift at 20-40 deg, so it is not used.
3. Each strip stalls at its MEASURED 2-D Cl_max (clean, or clean + measured
   dCl_max of the flapped section; out/clmax_sections.csv). The clean wing reaches
   CLmax at the angle where the first strip does.
4. Flapped wing: clean CLmax + 0.9 dCl_max,2D (S_flapped / S) (the part-span form
   in Raymer, Aircraft Design, ch. 12, after USAF DATCOM; book not re-read on 15 Oct,
   the NACA validation is what supports it). Chosen because it
   reproduced NACA TN 663's measured part-span flap wings best, and never
   over-predicted them, while the strict critical section with flaps stalls at the
   flap-end vortex and misses the measured gain (wing_clmax_validation.py). A
   CALIBRATED value applies that validation's two factors as well.
5. Trim: tail download at CLmax from the wing's pitching moment (camber from AVL,
   flap from the MEASURED moment increment dCm) over an ESTIMATE band of tail arm
   and CG position.
Writes out/wing_clmax_report.txt, wing_clmax.csv, wing_clmax.pdf.
"""
import csv
import math
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "data" / "aero"))
import coords  # noqa: E402
import lsat  # noqa: E402

OUT = HERE / "out"
AVL = HERE / "tools" / "avl352.exe"
CFG = tomllib.load((HERE / "inputs" / "wing_clmax.toml").open("rb"))
COORD = {"SD7037": "coord-sd7037", "SD7062": "coord-sd7062", "SD7034": "coord-sd7034",
         "Clark-Y": "coord-clarky"}


# ---------------------------------------------------------------------------
# Measured section inputs
# ---------------------------------------------------------------------------
def ag40d_flap(re=300e3):
    """Measured AG40d-02r (cf/c 0.25) increments at the tested Re nearest re:
    {delta: (dCl at alpha -2..2, dCm, dCl_max)} and the clean lift slope (per deg)."""
    runs = [r for r in lsat.runs() if r["volume"] == 6 and r["airfoil"].lower().startswith("ag40d")]
    res = sorted({round(r["re"], -5) for r in runs})
    r_use = min(res, key=lambda x: abs(x - re))
    at = {lsat.flap(r)[1]: r for r in runs if round(r["re"], -5) == r_use}
    ref = at[0.0]
    out = {}
    for d, r in at.items():
        if d > 0:
            out[d] = (lsat.increment(r, ref), lsat.increment(r, ref, "cm"), lsat.clmax(r)[0] - lsat.clmax(ref)[0])
    return out, lsat.lift_slope(ref), r_use


def section_clmax():
    """{(section, re, delta): 2-D Cl_max} from clmax_study.py (method b: measured clean +
    measured flap increment; cf/c 0.25), plus the tripped SD7062 clean value."""
    rows = list(csv.DictReader((OUT / "clmax_sections.csv").open(encoding="utf-8")))
    out = {}
    for r in rows:
        if float(r["cf"]) in (0.0, 0.25):
            out[(r["section"], float(r["re"]), float(r["delta"]))] = float(r["b_measured_increment"])
    return out


# ---------------------------------------------------------------------------
# AVL
# ---------------------------------------------------------------------------
def chord(y, half, c_root, taper):
    return c_root * (1 - (1 - taper) * y / half)


def avl_file(path, S, b, taper, eta_f, twist, claf, blend):
    half = b / 2
    c_root = 2 * S / (b * (1 + taper))
    cbar = 2 / 3 * c_root * (1 + taper + taper ** 2) / (1 + taper)
    if twist and eta_f + blend / 2 >= 1.0:          # full-span flap
        ys, incs = [0.0, half], [twist, twist]
    elif twist and eta_f > 0:    # flapped strips carry the equivalent twist; linear blend at the flap end
        ys = [0.0, max(eta_f - blend / 2, 0.0) * half, min(eta_f + blend / 2, 1.0) * half, half]
        incs = [twist, twist, 0.0, 0.0]
    else:
        ys, incs = [0.0, half], [0.0, 0.0]
    # quarter-chord line unswept (Xle = (c_root - c) / 4), moments about it
    L = ["Wing", "0.0", "0 0 0", f"{S:.6f} {cbar:.6f} {b:.6f}", f"{0.25 * c_root:.6f} 0 0", "0.0",
         "SURFACE", "Wing", f"{CFG['avl']['n_chord']} 1.0 {CFG['avl']['n_span']} 1.0", "YDUPLICATE", "0.0"]
    for y, inc in zip(ys, incs):
        c = chord(y, half, c_root, taper)
        L += ["SECTION", f"{0.25 * (c_root - c):.6f} {y:.6f} 0.0 {c:.6f} {inc:.4f}", "AFILE", "af.dat",
              "CLAF", f"{claf:.4f}"]
    path.write_text("\n".join(L) + "\n")
    return cbar


def run_avl(S, b, taper, eta_f, twist, claf, section):
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        coords.selig_file(COORD[section], td / "af.dat")
        cbar = avl_file(td / "w.avl", S, b, taper, eta_f, twist, claf, CFG["wing"]["flap_blend"])
        cmd = ["LOAD w.avl", "OPER"]
        for k, a in enumerate(CFG["avl"]["alpha_runs"]):
            cmd += [f"A A {a:g}", "X", f"FS fs{k}.txt", f"FT ft{k}.txt"]
        cmd += ["", "QUIT"]
        subprocess.run([str(AVL)], input="\n".join(cmd) + "\n", text=True, cwd=td, capture_output=True, timeout=120)
        runs = [(parse_fs(td / f"fs{k}.txt"), parse_ft(td / f"ft{k}.txt")) for k in range(len(CFG["avl"]["alpha_runs"]))]
    return runs, cbar


def parse_fs(path):
    """Right-wing strips: (y, chord, area, cl) from AVL's FS output (first surface only)."""
    strips, on = [], False
    for ln in path.read_text().splitlines():
        if "Surface # 2" in ln:
            break
        if ln.strip().startswith("j ") and "Xle" in ln:
            on = True
            continue
        if on:
            v = ln.split()
            if len(v) >= 10 and v[0].isdigit():
                strips.append((float(v[2]), float(v[4]), float(v[5]), float(v[9])))
    return strips


def parse_ft(path):
    t = path.read_text()
    def get(name):
        i = t.index(name)
        return float(t[i:].split("=")[1].split()[0])
    return {"CL": get("CLtot"), "Cm": get("Cmtot")}


# ---------------------------------------------------------------------------
# Critical section and trim
# ---------------------------------------------------------------------------
def critical(runs, clmax_of, eta_f, half, exclude=0.0):
    """Wing CL at first strip stall, the stall angle and where it starts (eta = y / half)."""
    (s0, f0), (s1, f1) = runs
    a0, a1 = CFG["avl"]["alpha_runs"]
    best = (math.inf, None)
    for (y, c, _, cl0), (_, _, _, cl1) in zip(s0, s1):
        eta = y / half
        if exclude and abs(eta - eta_f) < exclude:
            continue
        slope = (cl1 - cl0) / (a1 - a0)
        a_st = a0 + (clmax_of(eta, c) - cl0) / slope
        if a_st < best[0]:
            best = (a_st, eta)
    a_st, eta = best
    cl = f0["CL"] + (f1["CL"] - f0["CL"]) * (a_st - a0) / (a1 - a0)
    cm = f0["Cm"] + (f1["Cm"] - f0["Cm"]) * (a_st - a0) / (a1 - a0)
    return cl, a_st, eta, cm


def flap_cm_fraction(S, b, taper, eta_f):
    """Fraction of the wing's chord-squared moment area that is flapped: the 2-D dCm
    of the flapped strips scales to the wing by (integral of c^2 over the flap span) / (S cbar)."""
    half = b / 2
    c_root = 2 * S / (b * (1 + taper))
    cbar = 2 / 3 * c_root * (1 + taper + taper ** 2) / (1 + taper)
    n = 400
    num = sum(chord((i + 0.5) / n * eta_f * half, half, c_root, taper) ** 2 for i in range(n)) * eta_f * half / n
    return 2 * num / (S * cbar)


def flapped_area(taper, eta_f):
    """S_flapped / S for a flap from the root over eta_f of the semispan (linear taper)."""
    return (eta_f - (1 - taper) * eta_f ** 2 / 2) / (1 - (1 - taper) / 2)


def trimmed(cl_w, cm_ac):
    """CLmax after the tail load, over the trim band: (low, high)."""
    t = CFG["trim"]
    vals = [cl_w + (cm_ac + cl_w * h) / lt for lt in t["lt_over_cbar"] for h in t["h_minus_hac"]]
    return min(vals), max(vals)


def calibration():
    import json
    path = OUT / "wing_clmax_calibration.json"
    if not path.exists():
        raise SystemExit("run analysis/wing_clmax_validation.py first (NACA TN 663 calibration)")
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    secmax = section_clmax()
    cal = calibration()
    flap, a0_meas, re_flap = ag40d_flap(300e3)
    claf = a0_meas / (2 * math.pi * math.pi / 180)          # measured slope / thin-airfoil 2 pi
    W = CFG["wing"]
    S_ = CFG["stall"]
    half = W["span_m"] / 2
    rows, clean = [], {}

    def re_key(c):
        re = S_["rho"] * S_["v_mps"] * c / S_["mu"]
        return min((3e5, 4e5, 5e5), key=lambda r: abs(r - re))
    for sec in W["sections"]:
        for S in W["areas_m2"]:
            for taper in W["tapers"]:
                for eta_f in W["flap_span"]:
                    for d in W["deltas"]:
                        if d == 0 and eta_f != W["flap_span"][0]:
                            continue                      # the clean wing does not depend on the flap span
                        dcl, dcm, _ = flap.get(d, (0.0, 0.0, 0.0))
                        twist = dcl / a0_meas if d else 0.0
                        runs, cbar = run_avl(S, W["span_m"], taper, eta_f if d else 0.0, twist, claf, sec)

                        def clmax_of(eta, c, d=d, eta_f=eta_f):
                            flapped = d and eta <= eta_f
                            return secmax[(sec, re_key(c), d if flapped else 0.0)]
                        cl_a, a_st, eta_st, cm_avl = critical(runs, clmax_of, eta_f, half)
                        if d == 0:
                            clean[(sec, S, taper)] = (cl_a, a_st, eta_st)
                        cl0, a0_st, eta0 = clean[(sec, S, taper)]
                        # 2-D flap increment at the mean-chord Reynolds number
                        rk = re_key(cbar)
                        dmx = secmax[(sec, rk, d)] - secmax[(sec, rk, 0.0)] if d else 0.0
                        inc = 0.9 * dmx * flapped_area(taper, eta_f) if d else 0.0
                        cons = cl0 + inc                                   # method D, validated conservative
                        best = cal["kappa_clean"] * cl0 + cal["kappa_flap"] * inc   # calibrated on NACA TN 663
                        # AVL's moment is about the quarter-chord line (the a.c. in linear theory):
                        # camber and twist; the flap's own moment is added from the measured dCm
                        cm_ac = cm_avl + (dcm * flap_cm_fraction(S, W["span_m"], taper, eta_f) if d else 0.0)
                        lo, _ = trimmed(cons, cm_ac)
                        _, hi = trimmed(best, cm_ac)
                        rows.append({"section": sec, "S": S, "taper": taper, "AR": W["span_m"] ** 2 / S,
                                     "flap_span": eta_f if d else 0.0, "delta": d, "twist_eq": twist,
                                     "cl_strict": cl_a, "alpha_stall_strict": a_st, "eta_first_stall": eta_st,
                                     "dclmax_2d": dmx, "sf_over_s": flapped_area(taper, eta_f) if d else 0.0,
                                     "cl_conservative": cons, "cl_calibrated": best, "cm_ac": cm_ac,
                                     "cl_trim_lo": lo, "cl_trim_hi": hi, "cbar": cbar,
                                     "eta_first_stall_clean": eta0})
    with (OUT / "wing_clmax.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    report(rows, flap, a0_meas, re_flap, claf, cal)
    chart(rows)


def report(rows, flap, a0, re_flap, claf, cal):
    L = []
    p = L.append
    p("Wing CLmax from measured section data (wing_clmax.py, PROVISIONAL)")
    p(f"AVL 3.52, {CFG['avl']['n_span']} strips per semispan; section slope = measured {a0:.4f}/deg (CLAF {claf:.3f}).")
    p(f"Flap data: AG40d-02r 25 % plain flap, Re {re_flap/1e3:.0f}k (Williamson 2012):")
    for d, (dcl, dcm, dmx) in sorted(flap.items()):
        if d in CFG["wing"]["deltas"]:
            p(f"   {d:.0f} deg: dCl {dcl:+.3f} (equivalent twist {dcl/a0:+.2f} deg); dCm {dcm:+.3f}; dCl_max {dmx:+.3f}")
    p("Method, as validated on NACA TN 663 (out/wing_clmax_validation.txt):")
    p("   clean wing = first strip to reach its measured section Cl_max (critical section, AVL loading);")
    p("   flapped    = clean + 0.9 dCl_max,2D (S_flapped / S)  -> CONSERVATIVE (under-predicted all 12 NACA points)")
    p(f"   calibrated = {cal['kappa_clean']:.3f} x clean + {cal['kappa_flap']:.2f} x the flap increment (NACA TN 663 fit)")
    p("   The strict critical section with flaps (column 'strict') stalls at the flap-end vortex and missed")
    p("   NACA's measured flap gain by up to 0.47; it is kept only for the stall-onset location.")
    p("")
    p("Reference planform 0.9 m2, 1.82 m span (AR 3.68), stall Re from 14 m/s:")
    p(f"   {'section':<7} {'taper':>5} {'flap':>5} {'delta':>5} {'strict':>6} {'1st stall':>9} {'conserv.':>8} "
      f"{'calibr.':>7} {'Cm_ac':>6}  trimmed (cons. low - calibr. high)")
    for r in rows:
        if r["S"] != 0.9:
            continue
        p(f"   {r['section']:<7} {r['taper']:>5.1f} {r['flap_span']:>5.1f} {r['delta']:>5.0f} {r['cl_strict']:>6.3f} "
          f"{r['eta_first_stall_clean'] if r['delta'] == 0 else r['eta_first_stall']:>9.2f} {r['cl_conservative']:>8.3f} "
          f"{r['cl_calibrated']:>7.3f} {r['cm_ac']:>6.3f}  {r['cl_trim_lo']:.3f}-{r['cl_trim_hi']:.3f}")
    p("")
    p("Area effect (SD7037, taper 0.7, flap 0.6 semispan, 30 deg): " + "; ".join(
        f"S {r['S']:.1f}: {r['cl_conservative']:.3f}-{r['cl_calibrated']:.3f}"
        for r in rows if r["section"] == "SD7037" and r["taper"] == 0.7 and r["flap_span"] == 0.6 and r["delta"] == 30))
    p("")
    p("Notes:")
    p("- AVL is inviscid and linear; it gives the span loading only. Stall comes from measured section data.")
    p("- '1st stall' = eta = y / semispan where the first strip stalls (clean rows: the clean wing).")
    p("- Trim band: tail arm 2.5-3.5 cbar and CG -0.05 to +0.10 cbar aft of the wing a.c. (ESTIMATES until the")
    p("  tail is sized). Fuselage lift loss and the propeller slipstream are not modelled.")
    p("- SD7062 uses its smooth-model data; tripped, its clean Cl_max falls 24-27 % (clmax_report.txt).")
    p("- SD7034 has no tunnel data in these volumes: its section values are XFoil corrected by the measured ratio.")
    (OUT / "wing_clmax_report.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


def chart(rows):
    sys.path.insert(0, str(HERE.parent / "design-system" / "matplotlib"))
    import dbfplot as dp
    dp.use()
    title = dict(fontsize=5.6, family=dp.MONO, color=dp.GRAPHITE, loc="left")
    fig, ax = dp.figure("col", 2.5)
    shades = {0.5: dp.FOG, 0.6: dp.STEEL, 0.7: dp.INK}
    for eta_f, col in shades.items():
        pts = [r for r in rows if r["section"] == "SD7037" and r["S"] == 0.9 and r["taper"] == 0.7
               and (r["flap_span"] == eta_f or r["delta"] == 0)]
        pts.sort(key=lambda r: r["delta"])
        x = [r["delta"] for r in pts]
        ax.fill_between(x, [r["cl_conservative"] for r in pts], [r["cl_calibrated"] for r in pts],
                        color=col, alpha=0.25, lw=0)
        ax.plot(x, [r["cl_conservative"] for r in pts], "-o", ms=2.4, lw=0.9, color=col,
                label=f"FLAP SPAN {eta_f:.0%} (BAND: CONSERV.-CALIBR.)")
        ax.plot(x, [r["cl_trim_lo"] for r in pts], ":", lw=0.8, color=col)
    ax.axhline(1.6, color=dp.INK, lw=0.6, ls="--")
    ax.annotate("SIZING.TOML ESTIMATE 1.6", (0.5, 1.6), xytext=(0, 3), textcoords="offset points", fontsize=4.6,
                family=dp.MONO)
    ax.set_xlabel("Plain-flap deflection (deg), cf/c 0.25")
    ax.set_ylabel("Wing $C_{L,max}$: SD7037, 0.9 m², taper 0.7")
    leg = ax.legend(loc="lower right", fontsize=4.4, frameon=False)
    for t in leg.get_texts():
        t.set_family(dp.MONO)
    ax.set_title("WING CLMAX FROM MEASURED SECTIONS; DOTTED: TRIMMED LOW", **title)
    fig.tight_layout()
    dp.save(fig, OUT / "wing_clmax.pdf")
    print("wrote out/wing_clmax.pdf")


if __name__ == "__main__":
    main()

