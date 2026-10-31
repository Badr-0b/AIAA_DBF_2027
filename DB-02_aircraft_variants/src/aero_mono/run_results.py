"""Writes out/aero_mono/results.json and figures. Run after run_impacts.py:  PYTHONDONTWRITEBYTECODE=1 python run_results.py"""
import json, math, sys, datetime
from pathlib import Path
import numpy as np
sys.dont_write_bytecode = True
W = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(W / "src"))
from aero_mono import model as M     # noqa: E402
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt     # noqa: E402
OUT = W / "out" / "aero_mono"
imp = json.loads((OUT / "impacts.json").read_text())
T = M.T()
items = {}


def it(i, name, v, rng, unit, grade, src, note="", dist="uniform"):
    items[i] = {"name": name, "value": float(v), "range": [float(min(rng)), float(max(rng))], "dist": dist, "unit": unit,
                "grade": grade, "source": src, "note": note}


FL = {"plain": dict(type="plain", span_frac=0.6, chord_frac=0.25, defl_land_deg=30.0),
      "slotted": dict(type="slotted", span_frac=0.6, chord_frac=0.30, defl_land_deg=30.0),
      "fowler": dict(type="fowler", span_frac=0.6, chord_frac=0.30, defl_land_deg=35.0)}
ref = M.aero({"S": 0.9})
ep = ref["e_parts"]
it("S3-R01", "e_inv_AVL_taper0.7_AR3.68", ep["e_inv"], [0.985, 1.0], "-", "computed", "AVL 3.52 Trefftz plane, wing alone", "inviscid, planar; taper 0.5 / 0.7 / 1.0 gives 0.988 / 0.993 / 0.995 (S 0.9)")
it("S3-R02", "k_fuse", ep["k_fuse"], [0.96, 0.98], "-", "computed", "Kroo 2000 (Annu Rev Fluid Mech) / Raymer fuselage factor 1-2(df/b)^2, df 0.22 m", "AVL BODY gave unphysical CL (1.8 at 4 deg) and was rejected")
it("S3-R03", "K_visc_dCd_dCL2", ep["K_visc"], [0.0045, 0.0075], "-", "computed", "XFoil SD7037 Re 8.5e5, Ncrit 9/5 mean, x1.11 UIUC calibration x1.15 build", "Kroo rule 0.38 CD0 = 0.0061 agrees")
it("S3-R04", "e_oswald_REF-D01", ref["e"], ref["ranges"]["e"], "-", "computed", "1/e = 1/(e_inv k_fuse) + pi AR K_visc", "vs Raymer 0.946 (DB-01) and ERAU 2023 measured 0.842 at AR 5.2")
it("S3-R05", "e_oswald_AR5.2_check", M.aero({"S": 1.82 ** 2 / 5.2})["e"], [0.842, 0.89], "-", "computed", "same method at AR 5.2", "ERAU 2023 measured 0.842 (dbf_aircraft.toml); Raymer 0.89")
for d, n in ((20, "R06"), (30, "R07"), (40, "R08")):
    P = T["plain"]["plain"]["300000"][str(d)]
    it(f"S3-{n}", f"plain_flap_dClmax_2D_{d}deg", P["dclmax"], [P["dclmax"] * 0.9, P["dclmax"] * 1.1], "-", "verified",
       "Williamson 2012 (UIUC LSAT Vol 6), AG40d-02r 25 % flap, Re 3e5", f"dCl(a0) {P['dcl_a0']:.2f}, dCm {P['dcm']:.3f}")
a_s = M.sec_dclmax("slotted", 30, 0.30, "mid")[0]
it("S3-R09", "slotted_flap_dClmax_2D_30deg_cf0.30", a_s, [0.59, 1.02], "-", "estimate", "TR 664 fig. 30 (slotted/plain 1.5); Leng 2022 ICAS Sec. 6.4 measured +1.02 at Re 2.3e5; ESDU 0.59", "range spans ESDU to the quasi-2-D tunnel measurement")
a_f = M.sec_dclmax("fowler", 30, 0.30, "mid")[0]
it("S3-R10", "fowler_flap_dClmax_2D_eff_cf0.30", a_f, [M.sec_dclmax("fowler", 30, 0.30, "lo")[0], M.sec_dclmax("fowler", 30, 0.30, "hi")[0]], "-", "estimate",
   "TR 534 fig. 5 (Re 6.1e5, full-span 0.20/0.30/0.40c: dCLmax 1.16/1.54/1.88 on retracted area) / 0.9; TR 664 fig. 30 Fowler peak 1.45", "area extension is inside the figure (retracted-area basis)")
it("S3-R11", "CLmax_clean_S0.9_taper0.7_SD7037", ref["clmax_clean_untrimmed"], [1.137, 1.235], "-", "computed", "AVL critical section + measured SD7037 sections, calibrated x1.0-1.086 (NACA TN 663)", "DB-01 assumed 1.25")
for k, n in (("plain", "R12"), ("slotted", "R13"), ("fowler", "R14")):
    a = M.aero({"S": 0.9, "flap": FL[k]})
    it(f"S3-{n}", f"clmax_landing_{k}_S0.9_60pct", a["clmax_landing"], a["ranges"]["clmax_landing"], "-", "computed" if k == "plain" else "estimate",
       "area method 0.9 dClmax2D Sf/S x calibration; trimmed, lt 2.5-3.5 cbar", f"untrimmed {a['clmax_landing_untrimmed']:.2f}; cm {a['cm_landing']:.3f}; mass +{a['mass_delta_kg']:.2f} kg")
a = M.aero({"S": 0.9})
it("S3-R15", "CD0_total_REF-D01_buildup", a["cd0"], a["ranges"]["cd0"], "-", "estimate", "XFoil wing + Hoerner body/tail + GT 2026 gear", "DB-01 used 0.0230 (0.0086 + 0.013/S)")
it("S3-R16", "nonwing_drag_area_REF-D01", sum(v for k, v in a["cd0_parts"].items() if k != "wing") * 0.9, a["ranges"]["f_body_m2"], "m2", "estimate",
   "Hoerner body (0.22 x 0.22 x 1.05 m), tails Vh 0.5 / Vv 0.04, gear 12 cm2, other 7 cm2", "DB-01 0.013 (0.006-0.028)")
it("S3-R17", "wing_cd0_intercept", a["cd0_parts"]["wing"], [0.0046, 0.0090], "-", "computed", "XFoil SD7037 Re 8.5e5 x UIUC calibration 1.11 x build 1.0-1.5", "DB-01 0.0086")
it("S3-R18", "xfoil_to_measured_cd_ratio_SD7037_Re3e5", 1.11, [1.07, 1.17], "-", "computed", "UIUC LSAT Vol 1-3 SD7037 clean models vs XFoil Ncrit 9 at cl 0.35 / 0.7 / 1.0", "tripped model x1.7-1.9 (zigzag trip, severe)")
w = {r["h_frac"]: r for r in T["np"]["winglets"] if r["S"] == 0.9 and r["kind"] == "winglet"}
for h, n in ((0.10, "R19"), (0.15, "R20")):
    mm = M.aero({"S": 0.9, "winglet": {"h_frac": h}})
    it(f"S3-{n}", f"winglet_de_h{h:.2f}semispan", w[h]["de"], [w[h]["de"] * 0.5, w[h]["de"] * 3], "-", "computed", "AVL flat wake, toe optimised 0-3 deg, vertical",
       f"h/b {h/2:.3f}; cd0 change {mm['cd0']-a['cd0']:+.4f}; root bending x{w[h]['bend_ratio']:.3f}; upper bracket x3 = literature theory, UNRECONCILED")
t10 = M.aero({"S": 0.9, "flap": dict(FL["plain"], defl_turn_deg=10.0)})
it("S3-R21", "clmax_turn_avail_flap10", t10["clmax_turn_avail"], t10["ranges"]["clmax_turn_avail"], "-", "computed", "plain flap 10 deg, Williamson dClmax 0.22, area method, trimmed",
   f"clean trimmed {a['clmax_clean']:.2f}; e in turns x{t10['e_turn_flap']/t10['e']:.3f} (AVL flap twist)")
mb = [r for r in T["np"]["multi"] if r["config"] == "biplane" and abs(r["gap_over_b"] - 0.15) < 1e-6][0]
it("S3-R22", "biplane_induced_k_ratio_gap0.15", mb["k_ratio"], [0.75, 0.80], "-", "computed", "AVL equal span, equal S, no stagger", "literature value about 0.78 (Prandtl 1924; not re-read here)")
b = M.aero({"S": 0.9, "config": "biplane", "gap_over_b": 0.15})
it("S3-R23", "biplane_e_oswald", b["e"], b["ranges"]["e"], "-", "estimate", "AVL k ratio + Re/2 profile + strut and interference terms", f"CLmax x0.92, mass +0.6 kg, cd0 {b['cd0']:.4f}")
base = imp["REF-D01|baseline"]["central"]["mean"]
it("S3-R24", "adapter_mean_REF-D01_baseline", base, [imp["REF-D01|baseline"]["central"]["p10"], base], "points", "computed", "S12 adapter, 120 DB-01 draws", "DB-01 6.33")
for lv, n in (("ALL_mono", "R25"), ("ALL_slotted", "R26"), ("ALL_fowler", "R27")):
    r = imp[f"REF-D01|{lv}"]["with_ranges"]
    it(f"S3-{n}", f"adapter_mean_REF-D01_{lv}", r["mean"], [r["p10"], r["mean"]], "points", "computed", "S12 adapter, full S3 aero dict with ranges", f"P10 {r['p10']:.2f}; P(M2) {r['p_m2']:.3f}")
fn = {"schema": 1, "stream": "S3", "generated": datetime.datetime.now().astimezone().isoformat(timespec="minutes"), "items": items}
(OUT / "results.json").write_text(json.dumps(fn, indent=1))

# ---------------- figures
plt.rcParams.update({"font.size": 8, "axes.spines.top": False, "axes.spines.right": False})
fig, ax = plt.subplots(1, 2, figsize=(7.5, 3))
Ss = [0.8, 0.9, 1.0, 1.1, 1.2, 1.3]
for k, ls in (("plain", "-"), ("slotted", "--"), ("fowler", ":")):
    for eta, col in ((0.5, "0.6"), (0.7, "k")):
        y = [M.aero({"S": s, "flap": dict(FL[k], span_frac=eta)})["clmax_landing"] for s in Ss]
        ax[0].plot(Ss, y, ls, color=col, label=f"{k} {int(eta*100)} %")
ax[0].set(xlabel="wing area S (m2)", ylabel="trimmed CLmax landing", title="High-lift options, span 1.82 m")
ax[0].legend(fontsize=6, ncol=2)
labs = ["Raymer\n(DB-01)", "S3 e_osw\nAR 3.68", "ERAU 2023\nAR 5.2", "S3 method\nAR 5.2"]
vals = [0.946, ref["e"], 0.842, M.aero({"S": 1.82 ** 2 / 5.2})["e"]]
ax[1].bar(labs, vals, color=["0.75", "0.2", "0.75", "0.4"]); ax[1].set_ylim(0.7, 1.0); ax[1].set(ylabel="Oswald e", title="Oswald e against references")
fig.tight_layout(); fig.savefig(OUT / "fig_highlift_e.png", dpi=200); fig.savefig(OUT / "fig_highlift_e.pdf"); plt.close(fig)

fig, ax = plt.subplots(1, 2, figsize=(7.5, 3))
hs = sorted(h for h in w if h > 0)
ax[0].plot([h / 2 for h in hs], [w[h]["de"] for h in hs], "k-o", label="AVL, toe optimised")
ax[0].plot([h / 2 for h in hs], [3 * w[h]["de"] for h in hs], color="0.5", ls="--", label="x3 theory bracket")
ax[0].set(xlabel="winglet height / span", ylabel="delta e (inviscid)", title="Winglet span-efficiency gain"); ax[0].legend(fontsize=6)
for af, c in (("sd7037", "k"), ("sd7034", "0.4"), ("e387", "0.6"), ("mh114", "0.8")):
    r = [x for x in T["xfoil"] if x["airfoil"] == af and x["re"] == 8e5 and x["ncrit"] == 5.0][0]
    rows = np.array(r["rows"]); ax[1].plot(rows[:, 2] * 1e4, rows[:, 1], color=c, label=af.upper())
ax[1].set(xlim=(40, 300), ylim=(0, 1.5), xlabel="cd (counts)", ylabel="cl", title="XFoil Re 8e5, Ncrit 5"); ax[1].legend(fontsize=6)
fig.tight_layout(); fig.savefig(OUT / "fig_winglet_sections.png", dpi=200); fig.savefig(OUT / "fig_winglet_sections.pdf"); plt.close(fig)

levers = ["e_AVL", "CD0_buildup", "hl_plain", "hl_slotted", "hl_fowler", "turnflap_5", "turnflap_10", "winglet_0.10", "winglet_0.15", "biplane"]
fig, ax = plt.subplots(1, 2, figsize=(7.5, 3.2), sharey=True)
for a_, dn in zip(ax, ("REF-D01", "REF-D01b")):
    b0 = imp[f"{dn}|baseline"]["central"]["mean"]
    d = [imp[f"{dn}|{l}"]["central"]["mean"] - b0 for l in levers]
    a_.barh(levers, d, color="0.3"); a_.axvline(0, color="k", lw=0.6); a_.set(title=f"{dn} (baseline {b0:.2f})", xlabel="change in mean score")
ax[0].invert_yaxis(); fig.tight_layout(); fig.savefig(OUT / "fig_levers.png", dpi=200); fig.savefig(OUT / "fig_levers.pdf"); plt.close(fig)
print("ok", len(items))
