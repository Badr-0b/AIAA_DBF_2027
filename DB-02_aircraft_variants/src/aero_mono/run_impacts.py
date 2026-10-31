"""Lever impact runs through the S12 adapter. Writes out/aero_mono/impacts.json. Heavy (~minutes): run once.
PYTHONDONTWRITEBYTECODE=1 python run_impacts.py"""
import copy, json, math, sys, time
from pathlib import Path
sys.dont_write_bytecode = True
W = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(W / "src"))
from integration import adapter as A     # noqa: E402
from aero_mono import model as M         # noqa: E402

Ps = A.draws()
RAY = lambda S: A.s3.oswald_straight(1.82 ** 2 / S)

def base_dict(S):
    """DB-01 inputs written as an aero dict (reproduces the DB-01 family: Raymer e, 0.0086 + 0.013/S, CLmax 1.6 / 1.25)."""
    return {"cd0_parts": {"wing": 0.0086, "body": 0.013 / S, "tail": 0, "gear": 0, "other": 0}, "e": RAY(S),
            "clmax_landing": 1.6, "clmax_clean": 1.25, "mass_delta_kg": 0.0}

def geom(S, **kw):
    g = {"S": S}
    g.update(kw)
    return g

def lever_dict(S, lever, variant=None):
    b = base_dict(S)
    F = {"flap": {"type": "plain", "span_frac": 0.6, "chord_frac": 0.25, "defl_land_deg": 30.0, "defl_turn_deg": 0.0}}
    if lever == "baseline":
        return b
    if lever == "e_AVL":                                     # AVL e + Kroo fuselage + profile CL^2 term; CD0 as DB-01
        a = M.aero(geom(S)); b["e"] = a["e"]; b["ranges"] = {"e": a["ranges"]["e"]}; return b
    if lever == "CD0_buildup":
        a = M.aero(geom(S)); b["cd0_parts"] = a["cd0_parts"]; b["ranges"] = {"f_body_m2": a["ranges"]["f_body_m2"]}; return b
    if lever.startswith("hl_"):
        t = lever[3:]
        fl = {"type": t, "span_frac": 0.6, "chord_frac": 0.25 if t == "plain" else 0.30, "defl_land_deg": 30.0 if t != "fowler" else 35.0, "defl_turn_deg": 0.0}
        a = M.aero(geom(S, flap=fl))
        b["clmax_landing"] = a["clmax_landing"]; b["clmax_clean"] = a["clmax_clean"]
        b["mass_delta_kg"] = a["mass_delta_kg"]; b["ranges"] = {"clmax_factor": a["ranges"]["clmax_factor"]}
        b["cd0_parts"] = {**b["cd0_parts"], "other": M.EPS_SLOT[t] / S}
        return b
    if lever.startswith("turnflap"):
        dt = float(lever.split("_")[1])
        fl = {"type": "plain", "span_frac": 0.6, "chord_frac": 0.25, "defl_land_deg": 30.0, "defl_turn_deg": dt}
        a = M.aero(geom(S, flap=fl))
        b["clmax_turn_avail"] = a["clmax_turn_avail"]; b["clmax_clean"] = a["clmax_clean"]
        # energy-weighted e penalty: 85 % of induced energy is in turns (ledger O-03/O-04), flap deployed only there
        k0 = 1 / (math.pi * 1.82 ** 2 / S * a["e"]); kt = 1 / (math.pi * 1.82 ** 2 / S * a["e_turn_flap"])
        b["e"] = RAY(S) / (1 + 0.85 * (kt / k0 - 1))
        b["ranges"] = {"clmax_factor": a["ranges"]["clmax_factor"]}
        return b
    if lever.startswith("winglet"):
        h = float(lever.split("_")[1])
        a0 = M.aero(geom(S)); a = M.aero(geom(S, winglet={"h_frac": h, "kind": "winglet"}))
        b["e"] = RAY(S) * a["e"] / a0["e"]                       # relative change on the DB-01 e
        b["cd0_parts"] = {**b["cd0_parts"], "other": (a["cd0"] - a0["cd0"])}
        b["mass_delta_kg"] = a["mass_delta_kg"]
        return b
    if lever == "biplane":
        a = M.aero(geom(S, config="biplane", gap_over_b=0.15)); a0 = M.aero(geom(S))
        b["e"] = RAY(S) * a["e"] / a0["e"]
        b["cd0_parts"] = {**b["cd0_parts"], "wing": 0.0086 * a["cd0_parts"]["wing"] / a0["cd0_parts"]["wing"], "other": a["cd0_parts"]["other"] - a0["cd0_parts"]["other"]}
        b["clmax_landing"] = 1.6 * a["clmax_landing"] / a0["clmax_landing"]; b["clmax_clean"] = 1.25 * a["clmax_clean"] / a0["clmax_clean"]
        b["mass_delta_kg"] = a["mass_delta_kg"]; return b
    if lever == "ALL_mono":                                   # full S3 aero: AVL e, build-up, plain flap, no winglet
        return M.aero(geom(S))
    if lever == "ALL_slotted":
        return M.aero(geom(S, flap={"type": "slotted", "span_frac": 0.6, "chord_frac": 0.30, "defl_land_deg": 30.0, "defl_turn_deg": 0.0}))
    if lever == "ALL_fowler":
        return M.aero(geom(S, flap={"type": "fowler", "span_frac": 0.6, "chord_frac": 0.30, "defl_land_deg": 35.0, "defl_turn_deg": 0.0}))
    raise KeyError(lever)

def score(S, unit, lever, ranges=True):
    a = lever_dict(S, lever)
    if not ranges:
        a = {k: v for k, v in a.items() if k != "ranges"}
    d = A.REF_D01.with_(id=f"{lever}", s=S, unit=unit, aero=a)
    r = A.robust(d, Ps)
    return {"mean": float(r["mean"]), "p10": float(r["p10"]), "p_m2": float(r["p_m2"])}

LEVERS = ["baseline", "e_AVL", "CD0_buildup", "hl_plain", "hl_slotted", "hl_fowler", "turnflap_5", "turnflap_10",
          "winglet_0.10", "winglet_0.15", "biplane", "ALL_mono", "ALL_slotted", "ALL_fowler"]
DESIGNS = [("REF-D01", 0.9, 4.0), ("REF-D01b", 1.0, 5.0), ("S1.1/6kg", 1.1, 6.0), ("S1.2/7kg", 1.2, 7.0)]

if __name__ == "__main__":
    out = {}
    t0 = time.time()
    for name, S, unit in DESIGNS:
        for lv in LEVERS:
            out[f"{name}|{lv}"] = {"with_ranges": score(S, unit, lv, True), "central": score(S, unit, lv, False)}
            print(name, lv, out[f"{name}|{lv}"]["central"], round(time.time() - t0), flush=True)
    (W / "out" / "aero_mono" / "impacts.json").write_text(json.dumps(out, indent=1))
