# Copyright © 2026 the members of the AUM AIAA DBF team. All rights reserved.
"""Container foam, size and mass for the Ground Mission drop (evidence gap E05).

    PYTHONIOENCODING=utf-8 python analysis/cushion_study.py

Question: how thick, how big and how heavy must the sensor container be so the sensor
survives the Ground Mission drops (up to 1.524 m, rules Sec. 3.3.4), as a function of how
many g the sensor itself is built to take? Script 6 draws the container mass from
0.4-1.0 kg (ESTIMATE, studies.toml); M2 carries two such containers, so their volume also
sizes the fuselage bay.

Data: MIL-HDBK-304B cushion curves for polyethylene 2.0 pcf (data/cushion_pe2.toml):
minimum peak g per thickness at 36, 42 and 48 in drops, read on the scanned pages.
Method (the handbook's own design approach):
1. Pads under a rigid inner box are sized so the static stress W/A sits at the curve's
   optimum, which gives the minimum peak g for that thickness.
2. For a drop height h and a sensor rating G_allow, the thickness is the smallest t with
   G_min(t, h) <= G_allow (log-log interpolation between the tabulated thicknesses).
3. 60 in (1.524 m) lies beyond the handbook's 48 in: G_min is extrapolated with
   G ~ h^p, p from that thickness's own 36-48 in data ("measured p") or p = 1 (the
   ideal-cushion G = C h / t). Both are reported; containers use the thicker answer.
4. Size and mass: inner box + 2 t on every side; foam only in the pads (six faces); a shell
   of areal density rho_A (ESTIMATE band) over the outer box; an inner box and latch
   allowance (ESTIMATE).
Writes out/cushion_report.txt, cushion_map.csv, cushion_study.pdf.
"""
import csv
import math
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
D = tomllib.loads((HERE / "data" / "cushion_pe2.toml").read_text(encoding="utf-8"))
G0 = 9.80665
IN = 0.0254
PSI = 6894.757293168

# ESTIMATES (sensor envelope from WP-01 K2: body 66 mm, length >= 170 mm; mass from Script 6)
INNER_M = (0.080, 0.080, 0.270)     # rigid inner box around the sensor, m
SHELL_KG_M2 = (0.6, 1.0, 2.0)       # corrugated PP / 1.5 mm ply / 3 mm ply (= 680 kg/m3 x thickness)
INNER_BOX_KG = 0.10                 # inner box, latch, rigging points
SENSOR_KG = [2.0, 3.0, 3.4, 4.0]
G_ALLOW = [50, 75, 100, 150]
HEIGHTS_IN = [36, 42, 48, 60]


def gmin_at(t_idx, h_in, mode):
    """Minimum peak g of tabulated thickness t_idx at drop height h (extrapolated above 48 in)."""
    hs, g = D["heights_in"], D["gmin"][t_idx]
    if h_in in hs:
        return g[hs.index(h_in)]
    p = math.log(g[-1] / g[0]) / math.log(hs[-1] / hs[0]) if mode == "measured p" else 1.0
    return g[-1] * (h_in / hs[-1]) ** p


def thickness_for(g_allow, h_in, mode):
    """Smallest thickness (in) whose minimum peak g at h is within g_allow; None if > 6 in."""
    ts = D["thickness_in"]
    gs = [gmin_at(i, h_in, mode) for i in range(len(ts))]
    if gs[0] <= g_allow:
        return ts[0], gs[0]
    for (t0, g0), (t1, g1) in zip(zip(ts, gs), zip(ts[1:], gs[1:])):
        if g1 <= g_allow <= g0:
            f = math.log(g_allow / g0) / math.log(g1 / g0)          # log-log interpolation
            return math.exp(math.log(t0) + f * (math.log(t1) - math.log(t0))), g_allow
    return None, None


def stress_opt_psi(t_in):
    ts, ss = D["thickness_in"], D["stress_opt_psi"]
    if t_in <= ts[0]:
        return ss[0]
    for t0, t1, s0, s1 in zip(ts, ts[1:], ss, ss[1:]):
        if t0 <= t_in <= t1:
            return s0 + (s1 - s0) * (t_in - t0) / (t1 - t0)
    return ss[-1]


def container(t_in, sensor_kg, shell_kg_m2):
    t = t_in * IN
    a, b, c = INNER_M
    outer = (a + 2 * t, b + 2 * t, c + 2 * t)
    vol_l = outer[0] * outer[1] * outer[2] * 1000
    area = 2 * (outer[0] * outer[1] + outer[0] * outer[2] + outer[1] * outer[2])
    pad_area = (sensor_kg + INNER_BOX_KG) * G0 / (stress_opt_psi(t_in) * PSI)       # m2 per face
    pad_kg = 6 * pad_area * t * D["density_kg_m3"]
    return {"outer_mm": tuple(round(x * 1000) for x in outer), "volume_l": vol_l, "pad_cm2": pad_area * 1e4,
            "foam_kg": pad_kg, "shell_kg": area * shell_kg_m2, "total_kg": pad_kg + area * shell_kg_m2 + INNER_BOX_KG}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(exist_ok=True)
    rows = []
    for h in HEIGHTS_IN:
        for mode in (("data",) if h <= 48 else ("measured p", "p = 1", "safer")):
            for g in G_ALLOW:
                if mode == "safer":
                    ta, tb = thickness_for(g, h, "measured p")[0], thickness_for(g, h, "p = 1")[0]
                    t = None if (ta is None or tb is None) else max(ta, tb)
                else:
                    t, _ = thickness_for(g, h, mode)
                for m in SENSOR_KG:
                    for rho_a in SHELL_KG_M2:
                        c = container(t, m, rho_a) if t else None
                        rows.append({"height_in": h, "height_m": h * IN, "extrapolation": mode, "g_allow": g,
                                     "sensor_kg": m, "shell_kg_m2": rho_a, "thickness_in": t,
                                     "thickness_mm": t * 25.4 if t else None,
                                     **({k: c[k] for k in ("volume_l", "pad_cm2", "foam_kg", "shell_kg", "total_kg")}
                                        if c else {}),
                                     "outer_mm": "x".join(map(str, c["outer_mm"])) if c else ""})
    keys = sorted({k for r in rows for k in r}, key=lambda k: list(rows[0]).index(k) if k in rows[0] else 99)
    with (OUT / "cushion_map.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, keys)
        w.writeheader()
        w.writerows(rows)
    report(rows)
    chart(rows)


def pick(rows, **k):
    return [r for r in rows if all(r.get(a) == b for a, b in k.items())]


def report(rows):
    L = []
    p = L.append
    p("Container foam, size and mass for the Ground Mission drop (cushion_study.py, PROVISIONAL)")
    p("Polyethylene 2.0 pcf, MIL-HDBK-304B Graphs 10.36-10.48 (minimum peak g, read on the scans).")
    p(f"ESTIMATES: inner box {INNER_M[0]*1000:.0f} x {INNER_M[1]*1000:.0f} x {INNER_M[2]*1000:.0f} mm; "
      f"inner box + latch + rigging {INNER_BOX_KG} kg; shell {SHELL_KG_M2[0]}-{SHELL_KG_M2[2]} kg/m2.")
    p("")
    p("Foam thickness for the sensor's g rating (mm; 60 in = 1.524 m extrapolated: measured p / p = 1):")
    p(f"   {'rating':>7}" + "".join(f"{h:>9} in" for h in (36, 42, 48)) + f"{'60 in (meas. p - p = 1)':>26}")
    for g in G_ALLOW:
        cells = []
        for h in (36, 42, 48):
            t, _ = thickness_for(g, h, "data")
            cells.append(f"{t*25.4:>12.0f}" if t else f"{'> 152':>12}")
        tl, _ = thickness_for(g, 60, "measured p")
        th, _ = thickness_for(g, 60, "p = 1")
        f = lambda t: f"{t*25.4:.0f}" if t else ">152"
        p(f"   {g:>5} g" + "".join(cells) + f"{f(tl) + " - " + f(th):>26}")
    p("")
    p("Container at 1.524 m for the reference 3.4 kg sensor (the thicker of the two extrapolations):")
    p(f"   {'rating':>7} {'foam mm':>8} {'outer mm':>16} {'volume L':>9} {'pads cm2':>9} {'foam kg':>8} "
      f"{'mass kg (shell 0.6 / 1.0 / 2.0 kg/m2)':>40}")
    for g in G_ALLOW:
        rs = pick(rows, height_in=60, extrapolation="safer", g_allow=g, sensor_kg=3.4)
        if not rs or rs[0]["thickness_in"] is None:
            p(f"   {g:>5} g  needs more than 6 in")
            continue
        r = rs[0]
        masses = " / ".join(f"{x['total_kg']:.2f}" for x in rs)
        p(f"   {g:>5} g {r['thickness_mm']:>8.0f} {r['outer_mm']:>16} {r['volume_l']:>9.1f} {r['pad_cm2']:>9.0f} "
          f"{r['foam_kg']:>8.2f} {masses:>40}")
    p("")
    p("Reading:")
    c = {g: pick(rows, height_in=60, extrapolation="safer", g_allow=g, sensor_kg=3.4) for g in G_ALLOW}
    lo_hi = lambda g: f"{min(r['total_kg'] for r in c[g]):.2f}-{max(r['total_kg'] for r in c[g]):.2f} kg"
    p(f"- Script 6 draws the container from 0.4-1.0 kg. A sensor rated 100 g needs {c[100][0]['thickness_mm']:.0f} mm of")
    p(f"  foam and a {c[100][0]['volume_l']:.0f} L container of {lo_hi(100)}; rated 150 g, {c[150][0]['thickness_mm']:.0f} mm, "
      f"{c[150][0]['volume_l']:.0f} L, {lo_hi(150)};")
    p(f"  rated 50 g, {c[50][0]['thickness_mm']:.0f} mm, {c[50][0]['volume_l']:.0f} L, {lo_hi(50)}. M2 carries two units.")
    p("- So the sensor's own ruggedness (potted electronics, solid ballast, a tow fitting that does not")
    p("  rely on the body shell) is the main lever on container size, fuselage bay and payload mass.")
    p("- Dropping from less than the rule maximum shrinks the container; the GM score falls in proportion")
    p("  to the declared height (GM = 0.5 + W h / (W h)max), so this is a D5 trade.")
    p("Limits: 1978 foam data (AFPEA); minimum-g reading +/- 3 G; 60 in extrapolated; flat drops on a")
    p("rigid floor only (corner and edge drops are not part of the GM); TC-02 measures our foam and box.")
    (OUT / "cushion_report.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


def chart(rows):
    sys.path.insert(0, str(HERE.parent / "design-system" / "matplotlib"))
    import dbfplot as dp
    dp.use()
    title = dict(fontsize=5.6, family=dp.MONO, color=dp.GRAPHITE, loc="left")
    fig, (a1, a2) = dp.figure("page", 2.5, ncols=2)
    ts = D["thickness_in"]
    for j, (h, col) in enumerate(zip(D["heights_in"], (dp.FOG, dp.STEEL, dp.GRAPHITE))):
        a1.plot([t * 25.4 for t in ts], [D["gmin"][i][j] for i in range(len(ts))], "-o", ms=2.6, lw=0.9,
                color=col, label=f"{h} IN ({h*0.0254:.2f} M), MIL-HDBK-304B")
    for mode, ls in (("measured p", ":"), ("p = 1", "--")):
        a1.plot([t * 25.4 for t in ts], [gmin_at(i, 60, mode) for i in range(len(ts))], ls, color=dp.INK, lw=0.9,
                label=f"60 IN (1.524 M), EXTRAPOLATED ({'MEASURED EXPONENT' if mode == 'measured p' else 'G ~ H'})")
    a1.set_xlabel("Polyethylene 2 pcf thickness (mm)")
    a1.set_ylabel("Minimum peak acceleration (g)")
    a1.set_ylim(0, 220)
    leg = a1.legend(loc="upper right", fontsize=4.2, frameon=False)
    for t in leg.get_texts():
        t.set_family(dp.MONO)
    a1.set_title("CUSHION CURVES, OPTIMUM STATIC STRESS", **title)
    for rho_a, col in zip(SHELL_KG_M2, (dp.FOG, dp.STEEL, dp.INK)):
        pts = [r for r in rows if r["height_in"] == 60 and r["extrapolation"] == "safer" and r["sensor_kg"] == 3.4
               and r["shell_kg_m2"] == rho_a and r.get("total_kg")]
        a2.plot([r["g_allow"] for r in pts], [r["total_kg"] for r in pts], "-o", ms=2.6, lw=0.9, color=col,
                label=f"SHELL {rho_a} KG/M²")
    a2.axhspan(0.4, 1.0, color=dp.MIST, lw=0)
    a2.annotate("SCRIPT 6 RANGE 0.4-1.0 KG", (55, 0.95), fontsize=4.4, family=dp.MONO, va="top")
    a2.set_xlabel("Sensor rating, peak g it survives")
    a2.set_ylabel("Container mass (kg), 1.524 m drop")
    leg = a2.legend(loc="upper right", fontsize=4.4, frameon=False)
    for t in leg.get_texts():
        t.set_family(dp.MONO)
    a2.set_title("CONTAINER MASS FOR A 3.4 KG SENSOR", **title)
    fig.tight_layout()
    dp.save(fig, OUT / "cushion_study.pdf")
    print("wrote out/cushion_study.pdf")


if __name__ == "__main__":
    main()
