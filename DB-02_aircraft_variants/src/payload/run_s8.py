"""Build W/out/payload/results.json (S8-Rnn) and tables.json. Run: python src/payload/run_s8.py. Writes only to W/out/payload."""
from __future__ import annotations

import glob
import json
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
W = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(W / "src"))
from payload import model as M                  # noqa: E402
from rules import model as R                    # noqa: E402

OUT = W / "out" / "payload"


def build():
    items = {}
    n = [0]

    def add(name, value, rng, unit, grade, source, note):
        n[0] += 1
        items[f"S8-R{n[0]:02d}"] = {"name": name, "value": value, "range": rng, "dist": "uniform" if rng else "point",
                                    "unit": unit, "grade": grade, "source": source, "note": note}

    tables = {}
    db01 = (0.392, 0.202, 0.202)
    r15 = R.container_ring_to_bottom(db01, 15.0)
    r0 = R.container_ring_to_bottom(db01, 0.0, 0.0)
    r30 = R.container_ring_to_bottom(db01, 30.0)
    add("db01_100g_container_worst_ring_to_bottom", round(r15["worst"], 4), [round(r0["worst"], 4), round(r30["worst"], 4)], "m", "computed",
        "S1 rules.model.container_ring_to_bottom on cushion_report.txt 202x202x392 mm; L538-542",
        "392 mm long even with no sling; 15 deg sling gives 0.449 m (0.494 m at 30 deg); limit 0.381 m")
    rows = []
    for g in (100.0, 150.0):
        for m in (3.0, 4.4, 6.0, 8.0, 10.0):
            for sl in (15.0, 10.0):
                c = M.container(m, g, 1.524, ballast="tungsten", sling_deg=sl)
                s = c["sensor"]
                rows.append({"g_rating": g, "sensor_kg": m, "sling_deg": sl, "dims_mm": [round(x * 1000) for x in c["dims_m"]],
                             "mass_kg": round(c["mass_kg"], 3), "foam_mm": round(c["foam_mm"]),
                             "worst_rtb_mm": round(c["ring_to_bottom_m"]["worst"] * 1000), "ok_381": c["ok_381"],
                             "sensor_len_mm": round(s["length_m"] * 1000), "sensor_dia_mm": round(s["diameter_m"] * 1000),
                             "sensor_env_mm": round(s["envelope_m"][1] * 1000), "volume_l": round(c["volume_l"], 1)})
    tables["containers"] = rows
    for m in (3.0, 4.4, 6.0, 8.0, 10.0):
        r = next(x for x in rows if x["g_rating"] == 150.0 and x["sensor_kg"] == m and x["sling_deg"] == 15.0)
        add(f"container_mass_{m}kg_150g", r["mass_kg"], [round(r["mass_kg"] * 0.75, 3), round(r["mass_kg"] * 1.25, 3)], "kg", "estimate",
            "model.container (MIL-HDBK-304B minima verified; curve shape, bearing area, shell mass estimated)",
            f"{r['dims_mm']} mm, foam {r['foam_mm']} mm, worst ring-to-bottom {r['worst_rtb_mm']} mm, ok_381 {r['ok_381']}")
    c100 = [x for x in rows if x["g_rating"] == 100.0 and x["sling_deg"] == 15.0]
    add("g100_container_worst_rtb_range_3_to_10kg", min(x["worst_rtb_mm"] for x in c100),
        [min(x["worst_rtb_mm"] for x in c100), max(x["worst_rtb_mm"] for x in c100)], "mm", "computed",
        "model.container, 15 deg sling, tungsten", "a 100 g-rated sensor never meets 381 mm for 3-10 kg (foam 62 mm); build for 150 g")
    decl = {}
    for lo, hi, sl in ((3.0, 6.0, 15.0), (3.0, 8.0, 15.0), (4.4, 10.0, 10.0)):
        for rc in (True, False):
            c = M.design_for_range(lo, hi, recut=rc, sling_deg=sl)
            decl[f"{lo}-{hi}|{'recut' if rc else 'built'}"] = {
                "dims_mm": [round(x * 1000) for x in c["dims_m"]], "mass_kg": round(c["mass_kg"], 3), "foam_mm": round(c["foam_mm"]),
                "g_margin": round(c["g_margin"], 3), "ok_381": c["ok_381"], "worst_rtb_mm": round(c["ring_to_bottom_m"]["worst"] * 1000),
                "serves": [c["servable"][0], c["servable"][-1]], "mass_at_lo": round(c["mass_for"](lo), 3),
                "mass_at_hi": round(c["mass_for"](hi), 3), "sling_deg": sl}
    tables["declaration"] = decl
    d = decl["3.0-8.0|recut"]
    add("one_container_declared_range_recut", d["serves"], [3.0, 8.0], "kg", "estimate", "model.design_for_range(3, 8, recut=True)",
        f"150 g sensor, {d['foam_mm']} mm PE foam, {d['dims_mm']} mm, {d['mass_kg']} kg, ok_381 {d['ok_381']}; pads re-cut at tech")
    d = decl["3.0-8.0|built"]
    add("one_container_declared_range_as_built_pads", d["serves"], [3.0, 8.0], "kg", "estimate", "model.design_for_range(3, 8, recut=False)",
        f"foam thickened to {d['foam_mm']} mm (g margin {d['g_margin']}): {d['dims_mm']} mm, worst rtb {d['worst_rtb_mm']} mm, ok_381 {d['ok_381']}")
    d = decl["4.4-10.0|recut"]
    add("heavy_range_4p4_10_container_recut_10deg_sling", d["mass_kg"], None, "kg", "estimate", "model.design_for_range(4.4, 10, recut, 10 deg sling)",
        f"{d['dims_mm']} mm, worst rtb {d['worst_rtb_mm']} mm, ok_381 {d['ok_381']}")
    for b in ("tungsten", "lead", "steel"):
        s = M.sensor(6.0, 150.0, b, 0.20)
        add(f"sensor_6kg_{b}_diameter", round(s["diameter_m"] * 1000, 1), None, "mm", "estimate",
            f"model.sensor, {b} {M.BALLAST[b]['rho']:.0f} kg/m3 (grade {M.BALLAST[b]['grade']})",
            f"L 200 mm, ballast {s['ballast_kg']:.2f} kg = {s['ballast_vol_l']:.2f} L; {M.BALLAST[b]['price_note']}")
    s = M.sensor(6.0, 150.0, "tungsten", 0.20)
    add("sensor_6kg_static_margin_cal", round(s["static_margin_cal"], 3), None, "cal", "computed", "Barrowman 1967, 4 trapezoid fins; model.dart_stability",
        f"CP {s['x_cp_m'] * 1000:.0f} mm, CG {s['cg_from_nose_m'] * 1000:.0f} mm from the nose; pitch frequency {s['pitch_hz']:.2f} Hz (aero stiffness only)")
    add("nose_tow_equilibrium_angle_6kg", round(s["theta_nose_tow_deg"], 1), [50.0, 82.0], "deg nose-up", "computed",
        "tan(theta) = W x_cg / (q A CNa x_cp), q 374 Pa", "a nose tow hangs the dart nose-up; put the tow eye above the CG")
    drt = {}
    for m in (3.4, 4.4, 6.0, 8.0, 10.0):
        row = {}
        for drv in ("37d_70", "2x37d_131", "savox_2290", "neo550_g15"):
            x = M.dr(m, drv)
            row[drv] = None if not x["feasible"] else {"mass_kg": round(x["mass_kg"], 3), "stow_s": round(x["stow_s"], 1),
                                                       "deploy_s": round(x["deploy_s"], 1), "line_d_mm": round(x["line_d_m"] * 1000, 2),
                                                       "r_core_mm": round(x["r_core_m"] * 1000)}
        drt[str(m)] = row
    tables["dr"] = drt
    add("dr_stow_s_3p4kg_37d_70", drt["3.4"]["37d_70"]["stow_s"], [10.2, 14.0], "s", "computed", "dr_trade.toml (datasheet) + s5_tow; reproduces report 11.9 s", "DB-01 option A")
    add("dr_stow_s_10kg_savox", drt["10.0"]["savox_2290"]["stow_s"], None, "s", "estimate", "dr_trade.toml Savox (reseller) scaled by tow tension", f"mass {drt['10.0']['savox_2290']['mass_kg']} kg")
    add("dr_stow_s_10kg_neo550_g15", drt["10.0"]["neo550_g15"]["stow_s"], None, "s", "estimate", "NEO 550 (verified) + 15:1 gearbox (estimate)", f"mass {drt['10.0']['neo550_g15']['mass_kg']} kg")
    tc = M.tow_check()
    tables["tow"] = {"tension": tc["tension_n"], "shape": tc["shape"], "clearance_6kg": {k: v for k, v in tc["clearance"].items() if "6.0kg" in k}}
    t10 = tc["tension_n"]["10.0kg_n4.0"]
    add("tow_tension_10kg_n4", round(t10["T_n"], 1), [round(tc["tension_n"]["6.0kg_n3.0"]["T_n"], 1), round(t10["T_n"], 1)], "N", "computed",
        "s5_tow.tow_tension, q 374 Pa", f"line {t10['line_d_mm']:.2f} mm, break margin {t10['line_break_margin']:.1f}; 3.4 kg at n 4 is 133 N")
    sh = tc["shape"]["6.0kg_n1.0"]
    add("hang_angle_from_vertical_6kg_n1", round(sh["hang_from_vertical_deg"], 2),
        [round(tc["shape"]["10.0kg_n1.0"]["hang_from_vertical_deg"], 2), round(tc["shape"]["3.0kg_n1.0"]["hang_from_vertical_deg"], 2)], "deg", "computed",
        "line_shape: weights, cross-flow line drag (Cd 1.1), sensor CdA", f"sensor {sh['aft_m']:.2f} m aft and {sh['depth_m']:.2f} m below the exit")
    add("line_aft_of_exit_1kg_n1", round(M.line_shape(1.0, 1.0, M.Q_REF, 0.003)["aft_m"], 2), None, "m", "computed", "line_shape",
        "light M3 ballast trails further aft: the tail clearance case")
    lt = M.m3_lap_table()
    tables["m3_lap"] = lt["rows"]
    add("m3_laps_39p1s_lap_12s_stow", R.m3_laps(8.0, 39.1, 12.0), None, "laps", "computed", "floor((300 - 8 - stow)/lap)",
        "7 laps for any stow up to 18.3 s; an 8th lap needs lap <= 35.0 s at 12 s stow")
    add("m3_lap_time_for_8_laps_at_12s_stow", round((300 - 8 - 12) / 8, 2), None, "s", "computed", "(300 - 8 - 12)/8", "stow gain alone never buys the 8th lap at 39.1 s")
    li = M.lights_note()
    add("light_intensity_per_light", round(li["intensity_cd"]), [100, 400], "cd", "estimate", "4 x 3 W LED class, 100 lm/W, 20 % optics, 4.3 sr band",
        "no primary visibility source read; outdoor test at 150 m")
    add("light_energy_per_m3", round(li["energy_wh"], 2), None, "Wh", "estimate", "SOLID lap 2 then FLASH 50 % duty", "battery at 2x margin")
    st = M.staging_note()
    add("staging_m2_total_1_unit", st["M2_total_s"]["1"], [150, 240], "s", "estimate", "drill estimate", "3 units 285 s: crowds the 300 s box")
    h1 = {}
    for f in sorted(glob.glob(str(OUT / "h1_*.json"))):
        h1[Path(f).stem[3:]] = json.loads(Path(f).read_text(encoding="utf-8"))
    tables["h1"] = h1
    for k, v in h1.items():
        for sk, r in v["rows"].items():
            add(f"h1_{k}_{sk}_tech_total", round(r["tech"]["total"], 3), [round(r["frozen"]["total"], 3), round(r["oracle_mean"], 3)], "points", "computed",
                "h1_study + S12 adapter, 120 paired draws (seed 2027), expected field, ONE container per range",
                f"range {v['range']} kg {'recut pads' if v['recut'] else 'as-built pads'}, planning rho {v.get('rho_tech', 1.075)}; frozen {r['frozen']['total']:.3f} "
                f"(m {r['frozen_m']}), oracle {r['oracle_mean']:.3f}, REF-D01 {v['ref_d01_mean']:.4f}; tech M2/M3/GM {r['tech']['M2']:.2f}/{r['tech']['M3']:.2f}/{r['tech']['GM']:.2f}, "
                f"P(M2) {r['tech']['p_m2']:.3f}, mean pick {r['tech_pick_mean_kg']:.2f} kg, P10 {r['tech_p10']:.2f}")
    return {"schema": 1, "stream": "S8", "generated": time.strftime("%Y-%m-%dT%H:%M+03:00"), "items": items}, tables


if __name__ == "__main__":
    res, tables = build()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    (OUT / "tables.json").write_text(json.dumps(tables, indent=1, default=str), encoding="utf-8")
    print(len(res["items"]), "items")
