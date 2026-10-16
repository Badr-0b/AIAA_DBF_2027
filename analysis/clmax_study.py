# Copyright © 2026 the members of the AUM AIAA DBF team. All rights reserved.
"""Section maximum lift, clean and with a plain flap: measured data, XFoil check,
and the 2-D values for our candidate sections (evidence gap E03).

    PYTHONIOENCODING=utf-8 python analysis/clmax_study.py   (about 5 min the first time)

Question: what Cl_max can the wing's sections reach at the stall Reynolds number
(about 3-5e5 for a 0.9 m2 wing on a 1.82 m span at 14 m/s), with and without a
plain trailing-edge flap? sizing.toml carries ESTIMATES (wing CLmax 1.25 clean,
1.6 flapped); this script replaces guesswork with measurements where they exist.

Evidence (analysis/data/aero/, every value read from the published files):
- UIUC LSATs Vols 1-3, 5: clean Cl_max of SD7037 (four wind-tunnel models),
  SD7062, Clark Y, E387, FX 63-137 at Re 0.6-4.6e5.
- Williamson (UIUC MS thesis, 2012; LSATs Vol 6): plain flaps on W1011 (11 %),
  W1015 (15 %), cf/c 0.20 and 0.30, hinged on the chord line, 0-65 deg, Re 1-4e5;
  AG40d-02r (8 %, cambered, cf/c 0.25, lower-surface hinge).
Method:
1. XFoil 6.99 (240 panels, Ncrit 9) is run on the same sections at the same Re
   and flap settings; its error against the measurement is reported, clean and
   flapped (Cl_max and the flap increment dCl_max separately).
2. For our candidates (SD7037, SD7034, SD7062, MH 114) the 2-D flapped Cl_max is
   built two independent ways and both are reported:
   (a) measured clean Cl_max (XFoil x measured/XFoil ratio where no tunnel data
       exist) + XFoil dCl_max x its measured/XFoil ratio;
   (b) measured clean Cl_max + the MEASURED dCl_max of the nearest Williamson
       configuration (thickness and flap chord), no XFoil at all.
The 3-D wing value (span loading, flap span, trim) is wing_clmax.py's job.
Writes out/clmax_report.txt, clmax_measured.csv, clmax_xfoil.csv (run cache),
clmax_validation.csv, clmax_sections.csv, clmax_study.pdf.
"""
import csv
import math
import statistics as st
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "data" / "aero"))
import coords  # noqa: E402
import lsat  # noqa: E402
import xfoil_tools as xt  # noqa: E402

OUT = HERE / "out"
WORK = OUT / "xfoil_work"
CACHE = OUT / "clmax_xfoil.csv"
WORKERS = 12

# Measured sections: LSAT airfoil-name prefix -> coordinate source id.
SECTIONS = {"SD7037": "coord-sd7037", "SD7062": "coord-sd7062", "Clark-Y": "coord-clarky",
            "E387": "coord-e387", "FX 63-137": "coord-fx63137", "W1011": "coord-w1011",
            "W1015": "coord-w1015"}
CANDIDATES = {"SD7037": "coord-sd7037", "SD7034": "coord-sd7034", "SD7062": "coord-sd7062",
              "MH 114": "coord-mh114"}
FLAPS_VAL = {0.20: 0.80, 0.30: 0.70}          # cf/c -> hinge x/c (Williamson, chord-line hinge)
DELTAS = [10.0, 20.0, 30.0, 40.0]
RE_PRED = [300e3, 400e3, 500e3]
FLAPS_PRED = {0.25: 0.75, 0.30: 0.70}


# ---------------------------------------------------------------------------
# 1. Measured data
# ---------------------------------------------------------------------------
def section_of(airfoil):
    a = airfoil.upper().replace(" ", "")
    for k in SECTIONS:
        if a.startswith(k.upper().replace(" ", "")):
            return k
    return None


def measured():
    """Clean and flapped Cl_max rows from the LSAT files."""
    rows = []
    for r in lsat.runs():
        sec = section_of(r["airfoil"])
        cf, d = lsat.flap(r)
        if r["airfoil"].upper().startswith("AG40D"):
            sec = "AG40d-02r"
        if sec is None:
            continue
        c = r["comment"].lower()
        tripped = any(k in c for k in ("trip", "u.s.t.", "vortex", "covering"))
        if r["volume"] in (1, 2, 3) and "flap" in c:       # Vol 3 sailplane camber flaps
            continue
        cm, a = lsat.clmax(r)
        rows.append({"section": sec, "model": r["airfoil"], "volume": r["volume"], "file": r["file"],
                     "cf": cf if cf else 0.0, "delta": d, "re": r["re"], "clmax": cm, "alpha": a,
                     "tripped": tripped, "comment": r["comment"]})
    return rows


def nearest(rows, re, tol=0.12):
    """Rows within tol (relative) of re."""
    return [r for r in rows if abs(r["re"] / re - 1) <= tol]


# ---------------------------------------------------------------------------
# 2. XFoil runs (cached)
# ---------------------------------------------------------------------------
def key(sid, re, cf, hinge_x, yt, d):
    return f"{sid}|{re:.0f}|{cf:.2f}|{hinge_x:.2f}|{yt:.2f}|{d:.1f}"


def load_cache():
    if not CACHE.exists():
        return {}
    return {r["key"]: r for r in csv.DictReader(CACHE.open(encoding="utf-8"))}


def run_case(job):
    sid, re, cf, hx, yt, d = job
    WORK.mkdir(parents=True, exist_ok=True)
    dat = coords.selig_file(sid, WORK / f"{sid}.dat")
    rows, restarts = xt.sweep_up(dat, re, flap=(hx, yt, d) if d else None)
    cm, a, cap = xt.clmax(rows)
    return {"key": key(*job), "sid": sid, "re": re, "cf": cf, "hinge_x": hx, "hinge_yt": yt, "delta": d,
            "clmax": cm, "alpha": a, "stall_captured": cap, "points": len(rows),
            "restarts": " ".join(f"{s:g}" for s in restarts)}


def xfoil_all(jobs):
    cache = load_cache()
    todo = [j for j in dict.fromkeys(jobs) if key(*j) not in cache]
    if todo:
        print(f"XFoil: {len(todo)} sweeps on {WORKERS} workers ...", flush=True)
        with ThreadPoolExecutor(WORKERS) as ex:
            for i, res in enumerate(ex.map(run_case, todo), 1):
                cache[res["key"]] = res
                if i % 20 == 0:
                    print(f"  {i}/{len(todo)}", flush=True)
        fields = ["key", "sid", "re", "cf", "hinge_x", "hinge_yt", "delta", "clmax", "alpha",
                  "stall_captured", "points", "restarts"]
        with CACHE.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fields)
            w.writeheader()
            for k in sorted(cache):
                w.writerow({c: cache[k][c] for c in fields})
    out = {}
    for k, r in cache.items():
        out[k] = {**r, "re": float(r["re"]), "cf": float(r["cf"]), "delta": float(r["delta"]),
                  "clmax": float(r["clmax"]), "alpha": float(r["alpha"]),
                  "stall_captured": str(r["stall_captured"]) == "True"}
    return out


def xf(X, sid, re, cf=0.0, hx=0.0, yt=0.5, d=0.0):
    return X[key(sid, re, cf, hx, yt, d)]


# ---------------------------------------------------------------------------
# 3. Validation and prediction
# ---------------------------------------------------------------------------
def validation_jobs(meas):
    jobs = []
    for m in meas:
        if m["tripped"] or m["section"] not in SECTIONS or m["re"] < 90e3:
            continue
        re = round(m["re"], -4)
        sid = SECTIONS[m["section"]]
        if m["delta"] == 0:
            jobs.append((sid, re, 0.0, 0.0, 0.5, 0.0))
        elif m["section"] in ("W1011", "W1015") and m["delta"] in DELTAS and m["cf"] in FLAPS_VAL:
            jobs.append((sid, re, m["cf"], FLAPS_VAL[m["cf"]], 0.5, m["delta"]))
            jobs.append((sid, re, 0.0, 0.0, 0.5, 0.0))
    return jobs


def prediction_jobs():
    jobs = []
    for sid in CANDIDATES.values():
        for re in RE_PRED:
            jobs.append((sid, re, 0.0, 0.0, 0.5, 0.0))
            for cf, hx in FLAPS_PRED.items():
                for d in DELTAS:
                    jobs.append((sid, re, cf, hx, 0.5, d))
    return jobs


def compare(meas, X):
    """Measured vs XFoil, clean and flapped, at the measured Re (rounded to 10k)."""
    out = []
    base = {}
    for m in meas:
        if m["tripped"] or m["section"] not in SECTIONS or m["re"] < 90e3:
            continue
        re = round(m["re"], -4)
        sid = SECTIONS[m["section"]]
        x0 = xf(X, sid, re)
        if m["delta"] == 0:
            base[(m["section"], m["model"], m["cf"], re)] = (m["clmax"], x0["clmax"])
            out.append({**m, "re_run": re, "xfoil": x0["clmax"], "captured": x0["stall_captured"],
                        "kind": "clean", "d_meas": float("nan"), "d_xfoil": float("nan")})
    for m in meas:
        if m["tripped"] or m["section"] not in ("W1011", "W1015") or m["delta"] not in DELTAS:
            continue
        if m["cf"] not in FLAPS_VAL:
            continue
        re = round(m["re"], -4)
        sid = SECTIONS[m["section"]]
        xd = xf(X, sid, re, m["cf"], FLAPS_VAL[m["cf"]], 0.5, m["delta"])
        ref = [v for k, v in base.items() if k[0] == m["section"] and k[2] == m["cf"] and k[3] == re]
        if not ref:
            continue
        m0, x0 = ref[0]
        out.append({**m, "re_run": re, "xfoil": xd["clmax"], "captured": xd["stall_captured"], "kind": "flap",
                    "d_meas": m["clmax"] - m0, "d_xfoil": xd["clmax"] - x0})
    return out


def ratio_stats(vals):
    vals = [v for v in vals if math.isfinite(v)]
    if not vals:
        return {"n": 0}
    return {"n": len(vals), "median": st.median(vals), "min": min(vals), "max": max(vals),
            "mean": st.mean(vals), "sd": st.stdev(vals) if len(vals) > 1 else 0.0}


def measured_clean(meas, section, re):
    """Mean measured clean Cl_max of a section at re (all untripped models within 12 %), with the spread."""
    v = [m["clmax"] for m in nearest(meas, re) if m["section"] == section and m["delta"] == 0
         and not m["tripped"]]
    return (st.mean(v), min(v), max(v), len(v)) if v else None


def williamson_increment(meas, tc, cf, d, re):
    """Measured dCl_max of the Williamson/AG40d configuration nearest in t/c and cf/c at the
    nearest tested Re (interpolated in thickness between W1011 and W1015 where both exist)."""
    def dcl(section, cf_):
        rows = [m for m in meas if m["section"] == section and abs(m["cf"] - cf_) < 1e-6 and not m["tripped"]]
        res = sorted({round(m["re"], -5) for m in rows})
        if not res:
            return None
        r_use = min(res, key=lambda r: abs(r - re))
        at = {m["delta"]: m["clmax"] for m in rows if round(m["re"], -5) == r_use}
        if 0.0 not in at or d not in at:
            return None
        return at[d] - at[0.0]
    cf_use = 0.30 if cf >= 0.275 else 0.20
    w11, w15 = dcl("W1011", cf_use), dcl("W1015", cf_use)
    if w11 is None or w15 is None:
        return None
    t = min(max((tc - 0.11) / 0.04, 0.0), 1.0)          # interpolate on thickness, clamp outside 11-15 %
    w = w11 + t * (w15 - w11)
    if abs(cf - cf_use) > 1e-6:                          # 0.25: halfway between the two flap sizes
        o = 0.20 if cf_use == 0.30 else 0.30
        a11, a15 = dcl("W1011", o), dcl("W1015", o)
        if a11 is not None and a15 is not None:
            w = 0.5 * (w + a11 + t * (a15 - a11))
    return w


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(exist_ok=True)
    meas = measured()
    with (OUT / "clmax_measured.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, ["section", "model", "volume", "file", "cf", "delta", "re", "clmax", "alpha",
                               "tripped", "comment"])
        w.writeheader()
        for m in sorted(meas, key=lambda m: (m["section"], m["cf"], m["delta"], m["re"])):
            w.writerow(m)

    X = xfoil_all(validation_jobs(meas) + prediction_jobs())
    val = compare(meas, X)
    with (OUT / "clmax_validation.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, ["kind", "section", "model", "cf", "delta", "re", "re_run", "clmax", "xfoil",
                               "captured", "d_meas", "d_xfoil"])
        w.writeheader()
        for v in val:
            w.writerow({k: v[k] for k in w.fieldnames})

    clean = [v for v in val if v["kind"] == "clean" and v["captured"]]
    flp = [v for v in val if v["kind"] == "flap" and v["captured"]]
    r_clean = ratio_stats([v["clmax"] / v["xfoil"] for v in clean])
    r_clean_re = ratio_stats([v["clmax"] / v["xfoil"] for v in clean if v["re"] >= 190e3])
    r_flap = ratio_stats([v["clmax"] / v["xfoil"] for v in flp])
    r_inc = ratio_stats([v["d_meas"] / v["d_xfoil"] for v in flp if v["d_xfoil"] > 0.05])

    # Candidate sections: method (a) bias-corrected XFoil, method (b) measured increments.
    sec_rows = []
    for name, sid in CANDIDATES.items():
        _, pts = coords.read(sid)
        tc = coords.max_thickness(pts)
        for re in RE_PRED:
            x0 = xf(X, sid, re)
            mc = measured_clean(meas, name, re) if name in SECTIONS else None
            if mc is None and name in SECTIONS:
                mc = measured_clean(meas, name, 300e3)       # SD7037 tested to 3e5 only
            clean_val = mc[0] if mc else x0["clmax"] * r_clean_re["median"]
            clean_src = (f"measured ({mc[3]} runs, {mc[1]:.2f}-{mc[2]:.2f})" if mc
                         else f"XFoil x {r_clean_re['median']:.3f}")
            sec_rows.append({"section": name, "tc": tc, "re": re, "cf": 0.0, "delta": 0.0,
                             "xfoil": x0["clmax"], "xfoil_captured": x0["stall_captured"],
                             "clean_used": clean_val, "clean_basis": clean_src,
                             "a_xfoil_corrected": clean_val, "b_measured_increment": clean_val})
            for cf, hx in FLAPS_PRED.items():
                for d in DELTAS:
                    xd = xf(X, sid, re, cf, hx, 0.5, d)
                    inc_x = (xd["clmax"] - x0["clmax"]) * r_inc["median"]
                    inc_w = williamson_increment(meas, tc, cf, d, re)
                    sec_rows.append({"section": name, "tc": tc, "re": re, "cf": cf, "delta": d,
                                     "xfoil": xd["clmax"], "xfoil_captured": xd["stall_captured"],
                                     "clean_used": clean_val, "clean_basis": clean_src,
                                     "a_xfoil_corrected": clean_val + inc_x,
                                     "b_measured_increment": clean_val + inc_w if inc_w is not None else float("nan")})
    with (OUT / "clmax_sections.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, list(sec_rows[0]))
        w.writeheader()
        w.writerows(sec_rows)

    report(meas, val, r_clean, r_clean_re, r_flap, r_inc, sec_rows)
    chart(val, sec_rows)


def fmt_stats(s):
    if not s.get("n"):
        return "no data"
    return f"median {s['median']:.3f}, range {s['min']:.3f}-{s['max']:.3f}, n {s['n']}"


def report(meas, val, r_clean, r_clean_re, r_flap, r_inc, sec_rows):
    L = []
    p = L.append
    p("Section Cl_max: measured data, XFoil check, candidate sections (clmax_study.py, PROVISIONAL)")
    p("Sources: UIUC LSATs Vols 1-3, 5, 6 (data/aero/sources.toml); XFoil 6.99, 240 panels, Ncrit 9.")
    p("")
    p("1. Measured clean Cl_max (untripped models; Re within 12 % of the column):")
    p(f"   {'section':<10}" + "".join(f"{r/1e3:>13.0f}k" for r in (100e3, 200e3, 300e3, 400e3)))
    for sec in ["SD7037", "SD7062", "Clark-Y", "E387", "FX 63-137", "W1011", "W1015"]:
        cells = []
        for re in (100e3, 200e3, 300e3, 400e3):
            v = [m["clmax"] for m in nearest(meas, re) if m["section"] == sec and m["delta"] == 0 and not m["tripped"]]
            cells.append(f"{min(v):.2f}-{max(v):.2f}" if len(v) > 1 else (f"{v[0]:.2f}" if v else "-"))
        p(f"   {sec:<10}" + "".join(f"{c:>14}" for c in cells))
    p("   Rough leading edge (zig-zag trip at 2 % upper / 5 % lower, h = 0.58 mm on the test models):")
    for sec in ["SD7037", "SD7062", "Clark-Y"]:
        for re in (200e3, 300e3, 400e3):
            t = [m["clmax"] for m in nearest(meas, re) if m["section"] == sec and m["tripped"] and "trip" in m["comment"].lower()]
            c = [m["clmax"] for m in nearest(meas, re) if m["section"] == sec and m["delta"] == 0 and not m["tripped"]]
            if t and c:
                p(f"   {sec:<10} Re {re/1e3:.0f}k: clean {st.mean(c):.2f} -> tripped {st.mean(t):.2f} ({st.mean(t)/st.mean(c)-1:+.0%})")
    p("")
    p("2. Measured plain-flap increment dCl_max = Cl_max(delta) - Cl_max(0), same model and Re:")
    for sec, cf in [("AG40d-02r", 0.25), ("W1011", 0.20), ("W1011", 0.30), ("W1015", 0.20), ("W1015", 0.30)]:
        for re in (200e3, 300e3, 400e3):
            at = {m["delta"]: m["clmax"] for m in meas if m["section"] == sec and abs(m["cf"] - cf) < 1e-6
                  and round(m["re"], -5) == re and not m["tripped"]}
            if 0.0 in at and any(d in at for d in DELTAS):
                p(f"   {sec:<10} cf/c {cf:.2f} Re {re/1e3:.0f}k: clean {at[0.0]:.2f}; " +
                  ", ".join(f"{d:.0f} deg {at[d]:.2f} ({at[d]-at[0.0]:+.2f})" for d in DELTAS if d in at))
    p("")
    p("3. XFoil against the measurements (stall captured in XFoil):")
    p(f"   clean Cl_max, measured / XFoil, all Re >= 1e5: {fmt_stats(r_clean)}")
    p(f"   clean Cl_max, measured / XFoil, Re >= 2e5:    {fmt_stats(r_clean_re)}")
    p(f"   flapped Cl_max (W1011, W1015), measured / XFoil: {fmt_stats(r_flap)}")
    p(f"   flap increment dCl_max, measured / XFoil:     {fmt_stats(r_inc)}")
    p("   by section (clean, Re >= 2e5): " + "; ".join(
        f"{s} {st.median([v['clmax']/v['xfoil'] for v in val if v['kind']=='clean' and v['section']==s and v['captured'] and v['re']>=190e3]):.3f}"
        for s in SECTIONS if [v for v in val if v['kind']=='clean' and v['section']==s and v['captured'] and v['re']>=190e3]))
    nc = [v for v in val if not v["captured"]]
    p(f"   sweeps where XFoil did not capture stall (excluded): {len(nc)}")
    p("")
    p("4. Candidate sections, 2-D Cl_max (a: XFoil corrected by the ratios above; b: measured clean +")
    p("   measured Williamson increment interpolated on t/c and cf/c). Flap hinge on the chord line.")
    for sec in CANDIDATES:
        for re in RE_PRED:
            rows = [r for r in sec_rows if r["section"] == sec and r["re"] == re]
            c = rows[0]
            p(f"   {sec:<7} t/c {c['tc']:.3f} Re {re/1e3:.0f}k  clean {c['clean_used']:.2f} [{c['clean_basis']}], XFoil {c['xfoil']:.2f}")
            for cf in FLAPS_PRED:
                s = ", ".join(f"{r['delta']:.0f}: {r['a_xfoil_corrected']:.2f}/{r['b_measured_increment']:.2f}"
                              for r in rows if r["cf"] == cf)
                p(f"           cf/c {cf:.2f} (a/b) {s}")
    p("")
    p("Notes:")
    p("- Measured values are 2-D section data from the UIUC tunnel (turbulence about 0.1 %); Cl_max is the")
    p("  highest Cl of the sweep. Williamson states lift uncertainty 1.5 % and angle 0.08 deg (thesis Sec. 3.7).")
    p("- SD7037 was tested only up to Re 3e5; its 4-5e5 values reuse the 3e5 measurement (Cl_max rises")
    p("  slowly with Re for this section: +0.02-0.06 from 1e5 to 3e5).")
    p("- No wind-tunnel data exist in these volumes for SD7034 or MH 114; their clean values are XFoil")
    p("  corrected by the measured/XFoil ratio of the tested sections (method a), a weaker basis.")
    p("- These are 2-D section values. The wing's CLmax is lower (span loading, flap span, tail trim):")
    p("  wing_clmax.py.")
    (OUT / "clmax_report.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


def chart(val, sec_rows):
    sys.path.insert(0, str(HERE.parent / "design-system" / "matplotlib"))
    import dbfplot as dp
    dp.use()
    title = dict(fontsize=5.6, family=dp.MONO, color=dp.GRAPHITE, loc="left")
    fig, (a1, a2) = dp.figure("page", 2.6, ncols=2)
    cl = [v for v in val if v["kind"] == "clean" and v["captured"]]
    fl = [v for v in val if v["kind"] == "flap" and v["captured"]]
    lim = [0.8, 2.3]
    a1.plot(lim, lim, "-", color=dp.FOG, lw=0.8)
    a1.plot([v["xfoil"] for v in cl], [v["clmax"] for v in cl], "o", ms=3.2, mfc="white", mec=dp.INK, mew=0.8,
            label="CLEAN, 7 SECTIONS")
    a1.plot([v["xfoil"] for v in fl], [v["clmax"] for v in fl], "s", ms=2.8, color=dp.STEEL, mew=0,
            label="PLAIN FLAP 10-40°, W1011/W1015")
    a1.set_xlim(lim)
    a1.set_ylim(lim)
    a1.set_xlabel("XFoil $C_{l,max}$")
    a1.set_ylabel("Measured $C_{l,max}$, UIUC tunnel")
    leg = a1.legend(loc="upper left", fontsize=4.6, frameon=False)
    for t in leg.get_texts():
        t.set_family(dp.MONO)
    a1.set_title("XFOIL AGAINST THE WIND TUNNEL, RE 1-4.6E5", **title)
    shades = {"SD7037": dp.INK, "SD7034": dp.GRAPHITE, "SD7062": dp.STEEL, "MH 114": dp.FOG}
    for sec, col in shades.items():
        rows = [r for r in sec_rows if r["section"] == sec and r["re"] == 400e3 and r["cf"] in (0.0, 0.30)]
        rows.sort(key=lambda r: r["delta"])
        a2.plot([r["delta"] for r in rows], [r["b_measured_increment"] if r["cf"] else r["clean_used"] for r in rows],
                "-o", ms=2.6, lw=1.0, color=col, label=sec.upper())
        a2.plot([r["delta"] for r in rows], [r["a_xfoil_corrected"] for r in rows], ":", color=col, lw=0.8)
    a2.set_xlabel("Flap deflection (deg), cf/c 0.30")
    a2.set_ylabel("Section $C_{l,max}$, Re 4E5")
    leg = a2.legend(loc="lower right", fontsize=4.6, frameon=False)
    for t in leg.get_texts():
        t.set_family(dp.MONO)
    a2.set_title("CANDIDATES: MEASURED INCREMENT (SOLID), CORRECTED XFOIL (DOTTED)", **title)
    fig.tight_layout()
    dp.save(fig, OUT / "clmax_study.pdf")
    print("wrote out/clmax_study.pdf")


if __name__ == "__main__":
    main()
