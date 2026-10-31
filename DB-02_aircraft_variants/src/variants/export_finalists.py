"""Export the finalist numbers the PDF cites (IDs F-...) to W/out/finalists/F_results.json, plus the P(1st) curves.
Run: PYTHONDONTWRITEBYTECODE=1 python src/variants/export_finalists.py"""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
W = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(W / "src"))
import numpy as np                                    # noqa: E402

FIN = json.loads((W / "out/integration/finalists.json").read_text(encoding="utf-8"))
SEL = FIN.pop("selection")
ROWS = json.loads((W / "out/integration/finalists_rows.json").read_text(encoding="utf-8"))
GEO = json.loads((W / "out/variants/variants_geometry.json").read_text(encoding="utf-8"))
BT = json.loads((W / "out/field/backtest_orch.json").read_text(encoding="utf-8"))
SRC_FIN = "src/integration/finalists.py (orchestrator, 30 Oct 2026): 120 paired draws, reliability-aware declaration, 5,000 S2 v1 fields"
SRC_GEO = ("src/variants/geometry_variants.py (orchestrator, 30 Oct 2026): AVL 3.52 wing+tail; family mass "
           "(variants/mass_family.py: DB-01 fit anchored at 0.9 m2, only wing and tail scale)")
items = {}


def put(i, name, v, unit, grade="computed", src=SRC_FIN, rng=None, note=""):
    if isinstance(v, (int, np.integer)) and not isinstance(v, bool):
        v = int(v)
    elif isinstance(v, (float, np.floating)):
        v = float(v)
    d = {"name": name, "value": v, "unit": unit,
         "grade": grade, "source": src, "note": note}
    if rng is not None:
        d["range"] = [float(rng[0]), float(rng[1])]
    items[i] = d


MAP = {"CTRL": "C", SEL["A"]: "A", SEL["B"]: "B"}
for cid in FIN["base"]:
    MAP.setdefault(cid, cid)
for cid, tag in MAP.items():
    s = FIN["base"][cid]
    put(f"F-{tag}-MEAN", f"{tag} mean mission total if completed", s["mean"], "points")
    put(f"F-{tag}-P10", f"{tag} P10 total", s["p10"], "points")
    put(f"F-{tag}-PTOP", f"{tag} P(top mission total)", s["p_mission_top"], "-", rng=s["p_mission_top_ci95"])
    put(f"F-{tag}-P1ST", f"{tag} P(1st), report 90", s["p_first"], "-", rng=s["p_first_ci95"])
    put(f"F-{tag}-RANK", f"{tag} expected rank", s["rank_mean"], "-")
    put(f"F-{tag}-PM2D", f"{tag} P(M2 completed)", s["p_m2_done"], "-")
    put(f"F-{tag}-PM3D", f"{tag} P(M3 completed)", s["p_m3_done"], "-")
    put(f"F-{tag}-PM2", f"{tag} per-attempt M2 success", s["pm2"], "-")
    put(f"F-{tag}-PM3", f"{tag} per-attempt M3 success", s["pm3"], "-")
    put(f"F-{tag}-M2", f"{tag} mean M2 score", s["M2"], "points")
    put(f"F-{tag}-M3", f"{tag} mean M3 score", s["M3"], "points")
    put(f"F-{tag}-GM", f"{tag} mean GM score", s["GM"], "points")
    put(f"F-{tag}-MDECL", f"{tag} mean declared sensor", s["m_decl_mean"], "kg")
    put(f"F-{tag}-VS2", f"{tag} median M2 stall speed", s["vs2"], "m/s")
    put(f"F-{tag}-G2", f"{tag} median M2 gross", s["g2"], "kg")
    put(f"F-{tag}-FEAS", f"{tag} P(M2 feasible)", s["p_feas"], "-")
    for sc in FIN:
        put(f"F-{tag}-PTOP-{sc}", f"{tag} P(top) in scenario {sc}", FIN[sc][cid]["p_mission_top"], "-",
            rng=FIN[sc][cid]["p_mission_top_ci95"])
    if cid != "CTRL":
        put(f"F-{tag}-CLMAX", f"{tag} trimmed landing CLmax (laid-out geometry, scored)", s["clmax_landing"], "-",
            "estimate")
# regret: best P(top) per scenario minus each candidate's, paired 95 % interval over the 120 draws
for sc in FIN:
    for cid, tag in MAP.items():
        if cid == "CTRL":
            continue
        rg = SEL["regret"][cid][sc]
        put(f"F-{tag}-REG-{sc}", f"{tag} regret in {sc} (leader {rg['leader']})", rg["regret"], "-", rng=rg["ci95"])
for cid, tag in MAP.items():
    if cid == "CTRL":
        continue
    put(f"F-{tag}-MAXREG", f"{tag} max regret", max(items[f'F-{tag}-REG-{sc}']['value'] for sc in FIN), "-")

# P(1st) against our report score
from field import model as fm                          # noqa: E402
rivals = fm.simulate(5000, 2027)
H = 1.524
curves = {}
for cid in (SEL["A"], SEL["B"]):
    rr = ROWS["base"][cid]
    rows, pm2, pm3 = rr["rows"], np.array(rr["pm2"]), np.array(rr["pm3"])
    n = rivals.n
    idx = np.arange(n) % len(rows)
    feas = np.array([r["feas"] for r in rows])[idx]
    comp = fm.sample_completion(pm2[idx] * feas, pm3[idx], np.random.default_rng(11), n)
    our = {"m2_wt": np.array([r["w"] / r["t2"] if r["feas"] else 0.0 for r in rows])[idx],
           "m3_lxs": np.array([r["laps"] * r["m3"] for r in rows])[idx],
           "gm_wh": np.array([r["sensor_max"] * H for r in rows])[idx],
           "done_m1": comp["done_m1"], "done_m2": comp["done_m2"] & (feas > 0),
           "done_m3": comp["done_m3"] & (feas > 0), "done_gm": comp["done_gm"]}
    cv = fm.p_first_curve(our, rivals, report_scores=tuple(range(70, 97, 2)))
    curves[cid] = [(c.get("report_score", rs), c["p_first"]) for rs, c in zip(range(70, 97, 2), cv)]
curves = {MAP[k]: v for k, v in curves.items()}
for tag in ("A", "B"):
    d = dict(curves[tag])
    for rs in (80, 86, 90, 94):
        put(f"F-{tag}-P1ST-R{rs}", f"{tag} P(1st) at report {rs}", d.get(rs, np.nan), "-")

# selection facts (paired, cluster bootstrap over the 120 draws)
for sc, (m, ci) in SEL["A_minus_B"].items():
    put(f"F-AB-{sc}", f"P(top) A minus B in {sc}", m, "-", rng=ci)
put("F-SEL-GATE-M3", "gate: P(M3 completed) needed", SEL["gate_complete_need"], "-")
put("F-SEL-GATE-P10", "gate: P10 needed (control)", SEL["gate_p10_need"], "points")
put("F-SEL-NTIED", "candidates tied with the P(top) leader", len(SEL["tied_with_leader"]), "-")
dB, dF = SEL["A_minus_B"]["base"][0], SEL["A_minus_B"]["fowler_low"][0]
put("F-AB-BREAKEVEN", "P(Fowler underdelivers) above which B has the higher expected P(top)", dB / (dB - dF), "-",
    note="from the base and fowler_low paired differences; linear in the probability")
put("F-SEL-NFIN", "finalists scored", len(FIN["base"]) - 1, "-")


def _lab(s):
    lab = f"{s['s']:.1f}~m², {dict(fowler='Fowler').get(s['flap'], s['flap'])}, 3--{s['m_hi']:g}~kg"
    return lab + (", twin" if s["prop"] == "twin" else "")


SCN = ("base", "fowler_low", "mass_up", "reliab_low", "combined")
order = [SEL["A"], SEL["B"]] + sorted((k for k in FIN["base"] if k not in ("CTRL", SEL["A"], SEL["B"])),
                                      key=lambda k: -FIN["base"][k]["p_mission_top"])
L = ["% generated by src/variants/export_finalists.py; do not edit (tabularray reads its body verbatim, so the whole",
     "% table is generated, not just the rows)",
     r"\begin{widetable}[h]{Probability of the top mission total by scenario for every finalist, and each one's largest "
     r"regret: how far it falls short of the best finalist in its worst scenario.}{tab:h2h}",
     r"\begin{brieftable}{width=\fullw, colspec={X[1.6,l] Q[c] Q[c] Q[c] Q[c] Q[c] Q[c]},",
     r"  column{2}={bg=dbfBone}, cell{1}{2}={bg=dbfInk, fg=white}}",
     r"Candidate & Base & Fowler low & Mass $+15$\,\% & Reliability low & Combined & Max regret \\"]
for k in order:
    tg = MAP[k]
    s = FIN["base"][k]
    name = {"A": r"\textbf{A}: ", "B": r"\textbf{B}: "}.get(tg, "") + _lab(s)
    if not all(SEL["gates"][k].values()):
        name += " (fails gates)"
    L.append(name + " & " + " & ".join(rf"\val{{F-{tg}-PTOP-{sc}}}" for sc in SCN) + rf" & \val{{F-{tg}-MAXREG}} \\")
L.append("DB-01 control & " + " & ".join(rf"\val{{F-C-PTOP-{sc}}}" for sc in SCN) + r" & -- \\")
L += [r"\end{brieftable}", r"\end{widetable}"]
(W / "report/data/h2h_table.tex").write_text("\n".join(L) + "\n", encoding="utf-8")
leaders = {sc: MAP[SEL["regret"][SEL["A"]][sc]["leader"]] for sc in SCN}
put("F-SEL-ALEADS", "scenarios A leads", sum(1 for v in leaders.values() if v == "A"), "-", note=str(leaders))
CD = W / "out/integration/cd0_upside.json"
if CD.exists():
    for role, d in json.loads(CD.read_text(encoding="utf-8")).items():
        put(f"F-{role}-CD0UP", f"{role} mean-total change if S3's drag build-up proves right", d["d_mean"], "points",
            "estimate", "src/integration/finalists.py cd0 (S3 build-up CD0 kept, same draws)")
        put(f"F-{role}-CD0UPP", f"{role} P(top) change if S3's drag build-up proves right", d["d_p_top"], "-",
            "estimate", "src/integration/finalists.py cd0")
SL = json.loads((W / "out/integration/shortlist.json").read_text(encoding="utf-8"))
put("F-SCR-N", "designs screened", SL["n_designs"], "-", src="src/integration/select.py")
put("F-SCR-NG", "designs passing the gates", SL["n_gated"], "-", src="src/integration/select.py")

# geometry and stability
for key in ("A", "B"):
    g, t, m = GEO[key]["geometry"], GEO[key]["tails"], GEO[key]["mass"]
    G = lambda i, n, v, u, gr="computed", note="": put(f"F-{key}-{i}", n, v, u, gr, SRC_GEO, note=note)
    G("S", "wing area", g["S"], "m²"); G("AR", "aspect ratio", g["AR"], "-"); G("CR", "root chord", g["cr"], "m")
    G("CT", "tip chord", g["ct"], "m"); G("MAC", "mean aerodynamic chord", g["mac"], "m")
    G("SH", "horizontal tail area", t["Sh"], "m²"); G("SV", "fin area", t["Sv"], "m²"); G("LT", "tail arm", t["lt"], "m")
    G("BH", "horizontal tail span", t["bh"], "m"); G("BV", "fin height", t["bv"], "m")
    G("XNP", "neutral point (wing+tail, AVL)", t["xnp"], "m"); G("XCG", "design CG", t["x_cg_design"], "m")
    G("CLA", "lift-curve slope (AVL)", t["CLa"], "1/rad"); G("CMA", "Cm_alpha (AVL)", t["Cma"], "1/rad")
    G("CNB", "Cn_beta (AVL)", t["Cnb"], "1/rad"); G("CLB", "Cl_beta (AVL)", t["Clb"], "1/rad")
    G("EMPTY", "empty mass with 8S pack and D&R", m["empty"], "kg", "estimate", "DB-01 fit 5.96 S^0.94 (x1.31 scatter)")
    G("LEN", "overall length", t["x_ach"] + 0.6 * t["crh"], "m")
    sms = [r["sm"] for r in m["loadings"]]
    G("SMMIN", "static margin, worst loading (wing+tail)", min(sms) * 100, "%")
    G("SMMAX", "static margin, best loading (wing+tail)", max(sms) * 100, "%")
    G("M2G", "M2 gross at 6 kg declared", m["loadings"][1]["mass_kg"], "kg", "estimate")

# field back-test and propulsion facts
put("F-FLD-2027-P50", "2027 best rival mission total, median", 6.62, "points", src="out/field/backtest_orch.json + S2 v1")
put("F-FLD-2027-P10", "2027 best rival mission total, P10", 6.22, "points", src="S2 v1 simulate(5000, 2027)")
put("F-FLD-2027-P90", "2027 best rival mission total, P90", 7.04, "points", src="S2 v1 simulate(5000, 2027)")
put("F-FLD-GMRIV", "2027 rival GM maximum, median", 11.41, "kg m", src="S2 v1 simulate(5000, 2027)")
for y, d in BT.items():
    put(f"F-BT-{y}-WIN", f"{y} actual winner total", d["win"], "points", "verified", "analysis/data/dbf_results.csv")
    put(f"F-BT-{y}-SIM50", f"{y} simulated winner median", d["sim"][1], "points", src="S2 v1 back-test")
put("F-FUSE-100-32", "Littelfuse 100 A MAXI DC rating", 32, "V", "verified",
    "Littelfuse MAXI 32 V datasheet and MAXI Smart Glow sheet (via Digikey/Mouser-hosted copies, read 29 Oct 2026)")
put("F-FUSE-58-MAXA", "Littelfuse MAXI 58 V series, highest rating", 80, "A", "reseller", "Digikey 0999080-ZXN listing, 29 Oct 2026")
put("F-PROP-T0", "8S AT7215 KV270 + 20x15E static thrust", 101.3, "N", "computed", "analysis/out/prop_trade_report.txt")
put("F-PROP-MAXG", "8S max M2 gross at 80 % usable, S 1.0", 17.48, "kg", "computed", "out/propulsion/gross_sweep.json (S6, salvaged)")
put("F-PROP-AXH", "prop axis height for 20 in prop clearance", 0.369, "m", "computed", "out/propulsion/install.json (S6, salvaged)")

(W / "out/finalists").mkdir(exist_ok=True)
(W / "out/finalists/F_results.json").write_text(json.dumps({"schema": 1, "stream": "finalists",
                                                           "generated": "2026-10-30", "items": items}, indent=1),
                                               encoding="utf-8")
(W / "out/finalists/p1st_curves.json").write_text(json.dumps(curves), encoding="utf-8")
print(len(items), "items;", {k: [round(p, 3) for _, p in v][:14] for k, v in curves.items()})
