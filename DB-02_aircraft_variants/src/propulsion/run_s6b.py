"""S6 study runs, part 2 (twin, M3, props, install, thermal). Imported by run_s6.py main dispatch."""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
W = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(W / "src"))
from propulsion import model as M          # noqa: E402
from propulsion import run_s6 as R         # noqa: E402

d, np = R.d, R.np
slim, dump, max_gross, ref_from = R.slim, R.dump, R.max_gross, R.ref_from


def twin_candidates(ref):
    """All twin motor/prop/pack combinations meeting the turn limits at the end-of-pack voltage (prop_trade screen logic)."""
    import prop_trade as pt
    motors, props, packs = pt.candidates()
    pb = d.pb
    cand_packs = [("tp2250-6sr70", pb.Battery.from_components("tp2250-6sr70"))]
    for k, h in M.HYP_PACKS.items():
        cand_packs.append((k, pb.Battery(h["name"], h["cells"], h["cap_ah"], h["mass"], h["i_max"])))
    rows = []
    for pid, pack in cand_packs:
        for mot in (m for m in motors if m.cells_rated[0] <= pack.cells <= m.cells_rated[1]):
            for prop in (p for p in props if p.D <= 18.0 * 0.0254 + 1e-9):
                sysm = pb.System(prop, mot, pack, n=2)
                ok, pw = True, 0.0
                for mis in ("M2", "M3"):
                    r = ref[mis]
                    pe = sysm.point(M.RHO, np.array([r["d1"], r["dn"]]), r["v"], d.V_END)
                    pm = sysm.point(M.RHO, np.array([r["d1"], r["dn"]]), r["v"], d.V_MID)
                    ok &= bool(pe["ok"][1]) and bool(np.isfinite(pe["p_batt"]).all())
                    pw += r["fs"] * pm["p_batt"][0] + r["ft"] * pm["p_batt"][1]
                if ok:
                    rows.append((pw / (2 * pack.energy_wh), pid, sysm))
    rows.sort(key=lambda x: x[0])
    return rows


def sec_twin():
    S = 1.1
    aero = M.accepted_aero(S, "slotted")
    base = M.system("8s", "end")
    out = {"note": "twin = two identical systems, each own pack <= 50 Wh and own fuse <= 100 A (rules L734-750, L776-777)"}
    res = {}
    for g2, g3 in ((14.0, 10.0), (16.0, 11.0)):
        r2 = M.margins(base, g2, S, aero, usable=0.90)
        r3 = M.margins(base, g3, S, aero, mission="M3", n_laps_m3=6, usable=0.90)
        ref = {"M2": ref_from(r2), "M3": ref_from(r3)}
        rows = twin_candidates(ref)
        e = {"n_ok_end": len(rows),
             "top": [{"pack": pid, "motor": s.motor.name, "prop": s.prop.name, "w_per_wh": mtr, "i_cap": s.i_cap}
                     for mtr, pid, s in rows[:12]], "margins": {}}
        picks, seen = [], set()
        for mtr, pid, sysm in rows:
            key = (pid, sysm.motor.name)
            if key in seen:
                continue
            seen.add(key)
            picks.append((pid, sysm))
            if len(picks) >= 4:
                break
        for pid, sysm in picks:
            ps = M.from_objects(f"twin:{pid}:{sysm.motor.name}:{sysm.prop.name}", sysm, layout=M.TWIN_LAYOUT, v_check="end")
            ent = {"static_thrust_n": ps.static_thrust_n, "pack_kg": ps.pack_kg, "wh": ps.wh, "i_cap": ps.i_max,
                   "max_gross": {f"{u:.2f}": max_gross(ps, S, aero, u) for u in (0.80, 0.90)}}
            for g in (14, 16, 17):
                ent[f"g{g}"] = slim(M.margins(ps, g, S, aero, usable=0.90))
            e["margins"][f"{pid}|{sysm.motor.name}|{sysm.prop.name}"] = ent
        res[f"{g2}_{g3}"] = e
        print("twin", g2, len(rows), flush=True)
    out["search"] = res
    eo = {}
    S_v = 0.04 * S * 1.82 / 0.9
    for y in (0.30, 0.35, 0.45):
        for t_one in (25.0, 40.0):
            eo[f"y{y}_T{t_one}"] = M.engine_out(15.0, S, 1.82, y, t_one, 20.0, S_v, 0.9, windmill_cd_a=0.0012)
    out["engine_out"] = {"S_v_m2": S_v, "l_v_m": 0.9, "cases": eo,
                         "assumptions": "tail volume 0.04, lever 0.9 m, rudder tau 0.5 at 25 deg, a_v 3.0/rad, "
                                        "windmilling prop CdA 0.0012 m2 (ESTIMATE); grade computed"}
    sl = {}
    for lab, n_p, dp, cl_ in (("single_20in", 1, 0.508, True), ("twin_14in", 2, 0.356, False), ("twin_15in", 2, 0.381, False)):
        for T, V in ((47.0, 29.5), (80.0, 15.0)):
            f, fimm, qr = M.slipstream_clmax_factor(T, V, dp, n_p, 1.82, centerline=cl_)
            sl[f"{lab}_T{T}_V{V}"] = {"factor": f, "f_imm": fimm, "qs_over_q": qr}
    out["slipstream"] = sl
    dump("twin.json", out)
    return out


def sec_m3():
    S = 1.1
    aero = M.accepted_aero(S, "slotted")
    res = {}
    for k in ("8s", "12s", "twin"):
        ps = M.system(k, "end")
        res[k] = {}
        for g in (9, 10, 11, 12, 13, 14):
            for laps in (6, 7):
                for stow in (14.0, 30.0):
                    res[k][f"g{g}_L{laps}_stow{int(stow)}"] = slim(
                        M.margins(ps, g, S, aero, mission="M3", n_laps_m3=laps, stow_s=stow, usable=0.90))
        print("m3", k, flush=True)
    dump("m3.json", res)
    return res


def sec_props():
    import prop_trade as pt
    motors, props, packs = pt.candidates()
    S = 1.1
    aero = M.accepted_aero(S, "slotted")
    base = M.system("8s", "end")
    out = {}
    for g2, g3, tag in ((16.0, 11.0, "heavy"), (14.0, 10.0, "mid")):
        r2 = M.margins(base, g2, S, aero, usable=0.90)
        r3 = M.margins(base, g3, S, aero, mission="M3", n_laps_m3=6, usable=0.90)
        ref = {"M2": ref_from(r2), "M3": ref_from(r3)}
        rows = pt.screen(motors, props, packs, ref)
        for lab, mkey, pk in (("8S", "KV270", "TP3300-8SE55"), ("12S", "KV200", "2000mAh 12S")):
            sel = [r for r in rows if mkey in r["motor"].name and "AT7215" in r["motor"].name and pk in r["pack"].name]
            lst = [{"prop": r["prop"].name, "D_in": r["prop"].D / 0.0254, "ok_mid": r["ok"], "ok_end": r["ok_end"],
                    "m2_w": r["m2_w"], "m3_w": r["m3_w"], "v_margin_end": r["v_margin_end"], "i_margin_end": r["i_margin_end"]}
                   for r in sel]
            out[f"{tag}_{lab}"] = {"M2_best": sorted([x for x in lst if x["ok_end"]], key=lambda x: x["m2_w"])[:8],
                                   "M3_best": sorted([x for x in lst if x["ok_end"]], key=lambda x: x["m3_w"])[:8],
                                   "M2_best_mid": sorted([x for x in lst if x["ok_mid"]], key=lambda x: x["m2_w"])[:5],
                                   "n_ok_end": sum(x["ok_end"] for x in lst), "n_ok_mid": sum(x["ok_mid"] for x in lst),
                                   "n_total": len(lst)}
    dump("props.json", out)
    return out


def sec_install():
    res = {}
    for dname, dd in (("19in", 0.4826), ("20in", 0.508), ("205in", 0.5207), ("21in", 0.5334), ("22in", 0.5588)):
        for lp in (0.8, 1.0, 1.2):
            res[f"{dname}_Lp{lp}"] = M.gear_height(dd, lp)
    dump("install.json", res)
    return res


def sec_thermal():
    S = 1.1
    aero = M.accepted_aero(S, "slotted")
    res = {}
    for k in ("8s", "12s", "twin"):
        ps = M.system(k, "end")
        for g in (14, 16):
            r = M.margins(ps, g, S, aero, usable=0.90)
            if not r["feasible"]:
                continue
            for t_amb in (30.0, 35.0):
                th = M.thermal(ps, r["d_straight_n"], r["d_turn_n"], r["v"], r["m2_clock_s"], 0.45, t_amb)
                th_hi = M.thermal(ps, r["d_turn_n"], r["d_turn_n"], r["v"], 30.0, 1.0, t_amb)
                res[f"{k}_g{g}_T{int(t_amb)}"] = {"lap_mix": th, "full_turn_power_30s": th_hi}
    dump("thermal.json", res)
    return res


if __name__ == "__main__":
    for sec in sys.argv[1:]:
        globals()["sec_" + sec]()
