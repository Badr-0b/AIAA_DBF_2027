# Copyright © 2026 the members of the AUM AIAA DBF team. All rights reserved.
"""Validate wing_clmax.py's 3-D method on measured wings: NACA TN 663 (House, 1938).

    PYTHONIOENCODING=utf-8 python analysis/wing_clmax_validation.py

The test: rectangular and 5:1 tapered Clark Y wings, aspect ratio 6, 20 % chord
plain flaps at 60 deg over 0-100 % of the span from the centre, CLmax measured
(data/aero/naca_tn663.toml, values read from Figs. 7 and 12).
The same chain as wing_clmax.py is run on those wings with MEASURED 2-D inputs:
- Clark Y clean Cl_max vs Re: UIUC LSATs Vol. 3 (Clark-Y (B), Re 1-4e5);
- 20 % plain flap at 60 deg: Williamson's W1011 (11 % thick, close to Clark Y's
  11.7 %), cf/c 0.20, Re 4e5: dCl at alpha -2..2, dCl_max, and the lift slope.
Four stall criteria are compared:
  A  first strip to reach its section Cl_max (strict critical section);
  B  as A, ignoring strips within 3 % of the semispan of the flap end;
  C  as A, ignoring strips within 10 % of the semispan of the flap end;
  D  area ratio: clean wing CLmax by A, plus 0.9 dCl_max (S_flapped / S), the
     part-span increment form in Raymer, Aircraft Design, ch. 12 (after USAF DATCOM;
     the chapter was not re-read on 15 Oct: this validation is the evidence for it).
The criterion with the smallest error on the measured wings is the one
wing_clmax.py's results should be read with. Writes out/wing_clmax_validation.txt.
"""
import math
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "data" / "aero"))
import lsat  # noqa: E402
import wing_clmax as wc  # noqa: E402

T = tomllib.load((HERE / "data" / "aero" / "naca_tn663.toml").open("rb"))
NU = 1.4607e-5            # m2/s, standard sea level (the TN's "standard sea-level conditions")
V = 35.8                  # m/s, "about 80 miles per hour"


def clark_y_clmax():
    """Measured Clark-Y (B) clean Cl_max by Re (untripped), UIUC Vol. 3."""
    pts = sorted((r["re"], lsat.clmax(r)[0]) for r in lsat.runs()
                 if r["airfoil"].startswith("Clark-Y") and "trip" not in r["comment"].lower())
    slope = [lsat.lift_slope(r) for r in lsat.runs()
             if r["airfoil"].startswith("Clark-Y") and "trip" not in r["comment"].lower() and r["re"] > 3.5e5][0]

    def at(re):
        if re <= pts[0][0]:
            return pts[0][1]
        if re >= pts[-1][0]:
            return pts[-1][1]                         # held above the highest tested Re (4e5)
        for (r0, c0), (r1, c1) in zip(pts, pts[1:]):
            if r0 <= re <= r1:
                return c0 + (c1 - c0) * (re - r0) / (r1 - r0)
    return at, pts, slope


def w1011_flap(delta=60.0, re=4e5):
    runs = [r for r in lsat.runs() if r["volume"] == 6 and r["airfoil"].lower().startswith("w1011-20")
            and round(r["re"], -5) == re]
    at = {lsat.flap(r)[1]: r for r in runs}
    ref, fl = at[0.0], at[delta]
    return lsat.increment(fl, ref), lsat.increment(fl, ref, "cm"), lsat.clmax(fl)[0] - lsat.clmax(ref)[0]


flapped_area = wc.flapped_area


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    cmax, pts, slope = clark_y_clmax()
    dcl, dcm, dmx = w1011_flap()
    claf = slope / (2 * math.pi * math.pi / 180)
    twist = dcl / slope
    b = T["test"]["span_m"]
    S = b * b / T["test"]["aspect_ratio"]
    half = b / 2
    L = []
    p = L.append
    p("Validation of the wing CLmax method on NACA TN 663 (wing_clmax_validation.py)")
    p(f"Clark Y clean Cl_max (UIUC Vol. 3): " + ", ".join(f"{r/1e3:.0f}k {c:.3f}" for r, c in pts)
      + f"; lift slope {slope:.4f}/deg (CLAF {claf:.3f})")
    p(f"Flap, W1011 cf/c 0.20 at 60 deg, Re 4e5 (Williamson): dCl {dcl:+.3f} -> twist {twist:+.2f} deg; "
      f"dCl_max {dmx:+.3f}; dCm {dcm:+.3f}")
    p(f"Test Re (derived): {V * 0.254 / NU:.3g} on the rectangular chord; section data held at their 4e5 value above.")
    p("")
    errs = {k: [] for k in "ABCD"}
    k_clean, k_flap = [], []
    for shape in ("rectangular", "tapered"):
        taper = T[shape]["taper"]
        p(f"{shape.capitalize()} wing, AR 6, taper {taper:g}, centre-section flaps:")
        p(f"   {'flap span':>9} {'measured':>8} {'A strict':>8} {'B 3 %':>7} {'C 10 %':>7} {'D area':>7}")
        clean = None
        for eta_f, meas in zip(T[shape]["flap_span"], T[shape]["clmax_centre"]):
            d = eta_f > 0
            runs, cbar = wc.run_avl(S, b, taper, eta_f if d else 0.0, twist if d else 0.0, claf, "Clark-Y")
            c_root = 2 * S / (b * (1 + taper))

            def clmax_of(eta, c, eta_f=eta_f, d=d):
                base = cmax(V * c / NU)
                return base + (dmx if d and eta <= eta_f else 0.0)
            a = wc.critical(runs, clmax_of, eta_f, half)[0]
            bb = wc.critical(runs, clmax_of, eta_f, half, 0.03)[0] if d and eta_f < 1 else a
            cc = wc.critical(runs, clmax_of, eta_f, half, 0.10)[0] if d and eta_f < 1 else a
            if not d:
                clean, meas_clean = a, meas
                k_clean.append(meas / a)
            dd = clean + 0.9 * dmx * flapped_area(taper, eta_f)
            if d and meas - meas_clean >= 0.15:          # increments large enough to read off the figure
                k_flap.append((meas - meas_clean) / (dd - clean))
            for k, v in zip("ABCD", (a, bb, cc, dd)):
                errs[k].append(v - meas)
            p(f"   {eta_f:>9.1f} {meas:>8.2f} {a:>8.3f} {bb:>7.3f} {cc:>7.3f} {dd:>7.3f}")
        p("")
    p("Error, predicted - measured, over both wings and every flap span (12 points):")
    for k, name in zip("ABCD", ("strict critical section", "ignore 3 % at the flap end",
                                "ignore 10 % at the flap end", "area ratio, 0.9 dCl_max S_f/S")):
        e = errs[k]
        rms = math.sqrt(sum(x * x for x in e) / len(e))
        p(f"   {k} {name:<32} mean {sum(e)/len(e):+.3f}, RMS {rms:.3f}, worst {max(e, key=abs):+.3f}")
    kc = sum(k_clean) / len(k_clean)
    kf = sorted(k_flap)[len(k_flap) // 2]
    p("")
    p(f"Calibration (written to out/wing_clmax_calibration.json for wing_clmax.py):")
    p(f"   clean: measured / strict critical section = {', '.join(f'{k:.3f}' for k in k_clean)}; mean {kc:.3f}")
    p(f"   flap increment: measured / area-ratio increment, points with a measured increment >= 0.15:")
    p(f"   {', '.join(f'{k:.2f}' for k in k_flap)}; median {kf:.2f}")
    p("   Reading for our wing: method D unscaled is the CONSERVATIVE value (it under-predicted all 12")
    p("   measured points); D with both factors is the CALIBRATED value. Part of the clean factor is the")
    p("   Re gap below, which our wing (section data at its own Re) does not have, so the truth for our")
    p("   wing is expected between the two.")
    import json
    (wc.OUT / "wing_clmax_calibration.json").write_text(json.dumps(
        {"kappa_clean": kc, "kappa_flap": kf, "k_clean": k_clean, "k_flap": k_flap,
         "source": "wing_clmax_validation.py on NACA TN 663"}, indent=1), encoding="utf-8")
    p("")
    p("Caveats: TN 663 Re 6.2e5 against section data at 4e5 (Clark Y Cl_max is flat from 3e5 to 4e5: 1.354,")
    p("1.351); the W1011 flap stands in for a flapped Clark Y; the TN's flap gaps were sealed; values read")
    p("from the figures carry about +/- 0.02.")
    (wc.OUT / "wing_clmax_validation.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
