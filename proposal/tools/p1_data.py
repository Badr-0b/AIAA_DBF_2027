"""Proposal P1 number layer (31 Oct 2026): writes proposal/data/p1.tex, one macro per number.

Every value is read from a result file; nothing is typed here except the P1 budget lines, whose basis
(listing, quote or estimate) and source sit beside each line in BUDGET below.
Sources:
  DB-02 out/finalists/F_results.json          F-* (finalists, rev B, 30 Oct 2026)
  DB-02 out/variants/variants_geometry.json   Variant A layout (AVL 3.52)
  proposal/data/p1_nominal.json               tools/p1_nominal.py (design point and 120-draw medians)
  proposal/data/p1_sens.json                  tools/p1_sensitivity.py (tornado, declared-mass sweep)
  analysis/out/s6_trade_weights.csv, dr_trade_table.csv   DB-01 Script 6 and D&R trade
  procurement/pr01_items.csv                  PR-01 hardware (via proposal/data/budget.tex rows)
Run: PYTHONDONTWRITEBYTECODE=1 python proposal/tools/p1_data.py
"""
from __future__ import annotations

import csv
import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PROP = HERE.parent
REPO = PROP.parent
DB02 = REPO / "DB-02_aircraft_variants"


def J(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


FR = J(DB02 / "out/finalists/F_results.json")["items"]
GEO = J(DB02 / "out/variants/variants_geometry.json")["A"]
NOM = J(PROP / "data/p1_nominal.json")
SEN = J(PROP / "data/p1_sens.json")


def F(k):
    return FR[k]["value"]


# ---------------------------------------------------------------- budget (USD)
# PR-01 rows come from procurement/pr01_items.csv (PR-01, 9-16 Oct 2026). P1 adds the DB-02 changes and travel.
USD_PER_GBP = 1.3229   # procurement/make_pr.py, currencyconvert.online 8 Oct 2026
USD_PER_EUR = 1.137    # currencyconvert.online, EUR/USD day range 1.1357-1.1376, read 31 Oct 2026
TRAVELLERS = 7         # team lead, 31 Oct 2026: "6-7 ish"; budgeted at 7
ROOMS = 4              # 2 per room
MEMBERS = 21           # team lead, 31 Oct 2026: 21 on the roster (AIAA student dues each)
AIRFARE_EUR = 1359.14  # lastminute.ie, KWI-TUS return 12-20 Apr 2027, Turkish Airlines + Southwest, read 31 Oct 2026
ROOM_GBP = 539.34      # lastminute, Royal Sun Hotel & Suites Tucson, 13-19 Apr 2027, 6 nights, 2 adults, read 31 Oct 2026
FUND_KWD = 10000       # team lead, 31 Oct 2026: university funding, about 10,000 KWD, confirmed
KWD_PER_USD = 0.310829 # procurement/make_pr.py (currencyconvert.online, 8 Oct 2026)
# Tungsten heavy alloy (ASTM B777, W-Ni-Fe) bar/rod: online listing mid-points, $/kg, read 31 Oct 2026
# (team lead asked for the online average). Pure-W bar (~$240/kg, SMM May 2026) and hobby retail shot
# ($1,100+/kg) are different products and are excluded.
TUNGSTEN_LISTINGS = {
    "accio.ai 95WNiFe bar/rod, MOQ 5 kg, $20-30": 25.0,
    "accio.ai ASTM B777 bar/rod 17.1-18.5 g/cc, MOQ 1 kg, $70-75": 72.5,
    "accio.ai WNiFe/WNiCu bar, $80-110": 95.0,
    "accio.ai Zhuzhou Zhenfang Yaguang 95WNiFe rod, MOQ 5 kg, $58-65": 61.5,
    "accio.ai Hao Carbide WNiFe rod, MOQ 10 kg, $71": 71.0,
    "IndiaMART Ladhani 95W-3.5Ni-1.5Fe bar, INR 6,000/kg at ~88 INR/USD": 68.0,
}
TUNGSTEN_USD_PER_KG = sum(TUNGSTEN_LISTINGS.values()) / len(TUNGSTEN_LISTINGS)
# P1.2 (mock-judging note M3, 31 Oct 2026): the costs the rubric's "all other expenses" expects, each with its basis.
VISA_USD = 185 + 250   # US B1/B2 MRV fee $185 (travel.state.gov) + $250 visa integrity fee (2025 law; posts began
                       # collecting in 2026, BU ISSO 19 May 2026); budgeted for all 7, read 31 Oct 2026
MIE_USD = 80           # GSA FY2027 M&IE, Tucson (Pima County), $/day; 75 % on the first and last day (GSA rule)
MEAL_DAYS = 5 + 2 * 0.75   # 13-19 Apr 2027 in Tucson (hotel nights 13-19 Apr): 5 full days + 2 travel days
AMA_USD = 85 + 4 + 3   # AMA adult membership $85 (enrollment form) + $4 rise from 1 Jan 2026 + $3 card fee (AMA blog)
HAZMAT_USD = 100       # paint, glue, solvent bought in Tucson and disposed of there (rules 2.4); estimate
# AVL 3.52 about the design CG (mock-judging note C7): DB-02 writes variant_A.avl with Xref at the wing's
# aerodynamic centre (0.365 m), so its Cm_alpha is not about the CG. Re-run here with Xref = F-A-XCG.
AVL_EXE = REPO / "analysis" / "tools" / "avl352.exe"
AVL_A = DB02 / "out" / "variants" / "avl" / "variant_A.avl"


def pr01():
    rows = list(csv.DictReader(open(REPO / "procurement/pr01_items.csv", encoding="utf-8-sig")))
    tot = {}
    for r in rows:
        usd = float(r["qty"]) * float(r["ref_price"]) * (USD_PER_GBP if r["ref_cur"] == "GBP" else 1.0)
        if r["id"] == "B10c":      # 12S flight set on hold; DB-02 chose 8S: 4 x TP3300-8SE55 at the B10 listing
            usd = 4 * 151.99
        tot[r["budget_row"]] = tot.get(r["budget_row"], 0.0) + usd
    return tot


def budget():
    t = pr01()
    lines = [
        # key, label, usd, basis
        ("airframe", "Prototype airframe, test rigs and tools (PR-01)", t["airframe"], "PR-01"),
        ("comp", "Competition airframe and Variant B wing kit", 2 * (4 * 99.99 + 150 + 6 * 15 + 4 * 30 + 2 * 60) * 0.75, "est."),
        ("fowler", "Fowler tracks, carriages, test section", 180, "est."),
        ("propulsion", "Motors, ESCs, radio, servos (PR-01)", t["propulsion"], "PR-01"),
        ("batteries", "8S packs, chargers, sacks, 58 V fuses", t["batteries"], "PR-01"),
        ("sensor", "Sensor lights, drum, slip ring, test box", t["sensor"], "PR-01"),
        ("tungsten", "Tungsten alloy ballast, 8 kg", 8 * TUNGSTEN_USD_PER_KG, "online average"),
        ("containers", "Containers, simulators, drop rig", t["containers"], "PR-01"),
        ("consumables", "Spare props, adhesives, consumables", t["consumables"], "PR-01"),
        ("crating", "Shipping crate", t["crating"], "PR-01"),
        ("hazmat", "Paint, glue, solvent bought in Tucson", HAZMAT_USD, "est."),
        ("airfare", f"Airfare, Kuwait--Tucson, {TRAVELLERS} travellers", TRAVELLERS * AIRFARE_EUR * USD_PER_EUR, "quote"),
        ("lodging", f"Lodging, 6 nights, {ROOMS} rooms", ROOMS * ROOM_GBP * USD_PER_GBP, "quote"),
        ("meals", f"Meals, {TRAVELLERS} travellers, GSA Tucson rate", TRAVELLERS * MEAL_DAYS * MIE_USD, "GSA"),
        ("ground", "Van hire, fuel, excess baggage for the crate", 1200, "est."),
        ("visas", f"US visa fees, {TRAVELLERS} travellers", TRAVELLERS * VISA_USD, "fee"),
        ("fees", "Fly-off fee, AIAA student dues, pilot AMA dues", 550 + 37 * MEMBERS + AMA_USD, "rules, fee"),
    ]
    sub = sum(v for _, _, v, _ in lines)
    cont = 0.15 * sub
    # proposal Table 02 groups (same money, fewer rows)
    v = {k: val for k, _, val, _ in lines}
    groups = [("hwProto", v["airframe"]),                              # P1.4: lumped rows split (grader)
              ("hwComp", v["comp"] + v["fowler"]),
              ("hwMotors", v["propulsion"]),
              ("hwPacks", v["batteries"]),
              ("hwAirframe", v["airframe"] + v["comp"] + v["fowler"]),
              ("hwPower", v["propulsion"] + v["batteries"]),
              ("hwPayload", v["sensor"] + v["containers"] + v["tungsten"]),
              ("hwCrate", v["crating"] + v["hazmat"])]
    lines += [(k, k, val, "group") for k, val in groups]
    return lines, sub, cont


def avl_cg(x_cg):
    """Stability derivatives about the CG: DB-02's Variant A AVL file with Xref moved to x_cg, alpha 4 deg."""
    with tempfile.TemporaryDirectory() as td:
        lines = AVL_A.read_text(encoding="ascii").splitlines()
        lines[4] = f"{x_cg:.6f} 0.0 0.0"                      # line 5: Xref Yref Zref
        f = Path(td) / "a_cg.avl"
        f.write_text("\n".join(lines) + "\n", encoding="ascii")
        out = subprocess.run([str(AVL_EXE)], input=f"LOAD {f}\nOPER\nA A 4.0\nX\nST\n\n\nQUIT\n", capture_output=True,
                             text=True, cwd=td, timeout=120).stdout
    get = lambda k: float(re.search(k + r"\s*=\s*([-\d.Ee+]+)", out).group(1))
    return {"CLa": get("CLa"), "Cma": get("Cma"), "Cnb": get("Cnb"), "Clb": get("Clb"), "Xnp": get("Xnp")}


def fmt(v, d=2):
    return f"{v:.{d}f}"


def r10(v):
    return math.floor(v / 10 + 0.5) * 10                     # half up, so 7 x 435 prints 3,050


def money(v):
    return f"{r10(v):,.0f}".replace(",", "{,}")


def main():
    A = NOM["A"]
    D = A["draws"]
    m2, m3 = A["m2"], A["m3_at_median_mass"]
    g, t, mm = GEO["geometry"], GEO["tails"], GEO["mass"]
    T = SEN["tornado"]
    tor = {r["key"]: r["delta"] for r in T["rows"]}
    sw = SEN["sweep"]
    frozen_best = max(sw, key=lambda s: s["total"])
    s8 = next(s for s in sw if abs(s["m"] - 8.0) < 1e-9)
    tw = {r["criterion"]: float(r["weight"]) for r in csv.DictReader(open(REPO / "analysis/out/s6_trade_weights.csv", encoding="utf-8"))}
    m = {}

    def put(name, val, src):
        if isinstance(val, str) and re.fullmatch(r"-[\d.]+", val):
            val = "$-$" + val[1:]                  # typographic minus in text (P1.3 proofread)
        m[name] = (val, src)

    # aircraft, Variant A
    put("nSpan", "1.82", "rules cap 1.829 m; DB-02 spec")
    put("nWingArea", fmt(F("F-A-S")), "F-A-S")
    put("nAR", fmt(F("F-A-AR")), "F-A-AR")
    put("nMAC", fmt(F("F-A-MAC"), 3), "F-A-MAC")
    put("nRootChord", fmt(F("F-A-CR"), 3), "F-A-CR")
    put("nTipChord", fmt(F("F-A-CT"), 3), "F-A-CT")
    put("nLength", fmt(F("F-A-LEN")), "F-A-LEN")
    put("nEmptyMass", fmt(F("F-A-EMPTY")), "F-A-EMPTY (DB-01 fit, estimate)")
    put("nGrossMtwo", fmt(D["g2"]["p50"], 1), "120-draw median g2")
    put("nGrossMthree", fmt(D["g3"]["p50"], 1), "120-draw median g3")
    put("nStallMtwo", fmt(F("F-A-VS2"), 1), "F-A-VS2")
    put("nStallMthree", fmt(D["vs3"]["p50"], 1), "120-draw median vs3")
    put("nCLmaxLand", fmt(F("F-A-CLMAX")), "F-A-CLMAX (NACA TR 534 + TN 663 method, estimate)")
    put("nStaticMargin", "16", "F-A-SMMIN/SMMAX 16.0-16.1 % MAC")
    put("nXcg", fmt(F("F-A-XCG"), 3), "F-A-XCG"); put("nXnp", fmt(F("F-A-XNP"), 3), "F-A-XNP")
    put("nSh", fmt(F("F-A-SH"), 3), "F-A-SH"); put("nSv", fmt(F("F-A-SV"), 3), "F-A-SV")
    put("nTailArm", fmt(F("F-A-LT")), "F-A-LT")
    put("nPackWh", "97.7", "TP3300-8SE55 datasheet, 8S 3300 mAh (DB-02 A-03)")
    put("nUsableWh", fmt(m2["e_usable"], 1), "80 % usable, sizing.toml")
    put("nThrust", f"{F('F-PROP-T0'):.0f}", "F-PROP-T0")
    put("nTWstatic", fmt(D["tw2"]["p50"]), "120-draw median tw2")
    # missions: design point (baseline inputs) and 120-draw medians
    put("nDeclMed", fmt(D["m_decl"]["p50"]), "median declaration, finalists_rows S10F8")
    put("nDeclLo", fmt(D["m_decl"]["p10"], 1), "P10"); put("nDeclHi", fmt(D["m_decl"]["p90"], 1), "P90")
    put("nContainer", fmt(A["container_kg"]), "S8 container for 8 kg")
    put("nMtwoPayload", fmt(D["w"]["p50"], 1), "median M2 payload")
    put("nMtwoTimeDP", f"{m2['t5']:.0f}", "design point five-lap time (p1_nominal m2.t5)")
    put("nMtwoTime", f"{D['t2']['p50']:.0f}", "median t2"); put("nMtwoTimeLo", f"{D['t2']['p10']:.0f}", "P10")
    put("nMtwoTimeHi", f"{D['t2']['p90']:.0f}", "P90")
    put("nMtwoV", f"{m2['v']:.0f}", "design point"); put("nMtwoBank", f"{m2['bank']:.0f}", "design point")
    put("nMtwoN", fmt(m2["n"]), "design point"); put("nMtwoLap", fmt(m2["t_lap"], 1), "design point")
    put("nMtwoWh", fmt(m2["e_wh"], 1), "design point energy")
    put("nMthreeLaps", f"{D['laps']['p50']:.0f}", "median laps"); put("nMthreeLapsLo", f"{D['laps']['p10']:.0f}", "P10")
    put("nMthreeLapsHi", f"{D['laps']['p90']:.0f}", "P90")
    put("nMthreeMass", fmt(D["m3"]["p50"], 1), "median flown M3 sensor")
    put("nMthreeProd", fmt(D["prod3"]["p50"], 1), "median laps x mass")
    put("nMthreeProdLo", fmt(D["prod3"]["p10"], 1), "P10"); put("nMthreeProdHi", fmt(D["prod3"]["p90"], 1), "P90")
    put("nMthreeV", f"{m3['v']:.0f}", "design point at the median mass"); put("nMthreeN", fmt(m3["n"]), "")
    put("nMthreeLap", fmt(m3["t_lap"], 1), ""); put("nStowMed", fmt(m3["stow"], 1), "stow at the median M3 mass")
    put("nStowEight", fmt(A["stow_by_mass"]["8"], 1), "stow at 8 kg")
    put("nDrop", "1.524", "rules cap 60 in"); put("nDropIn", "60", "")
    put("nGMprod", fmt(D["m_decl"]["p50"] * 1.524), "median declaration x 1.524 m")
    put("nTow", fmt(1.5 * 1.82), "1.5 x span")
    import tomllib
    dr = tomllib.loads((REPO / "analysis/inputs/dr_trade.toml").read_text(encoding="utf-8"))
    put("nTowDesign", fmt(1.5 * 1.82 + dr["geometry"]["deploy_margin_m"]), "rule minimum + dr_trade deploy margin")
    # scores
    put("sMtwo", fmt(F("F-A-M2")), "F-A-M2"); put("sMthree", fmt(F("F-A-M3")), "F-A-M3")
    put("sGM", fmt(F("F-A-GM")), "F-A-GM"); put("sTotal", fmt(F("F-A-MEAN")), "F-A-MEAN")
    put("sTotalPten", fmt(F("F-A-P10")), "F-A-P10"); put("sPtop", f"{F('F-A-PTOP'):.3f}", "F-A-PTOP")
    put("sPfirst", f"{F('F-A-P1ST'):.3f}", "F-A-P1ST (report 90)")
    put("sPtopB", f"{F('F-B-PTOP'):.3f}", "F-B-PTOP"); put("sTotalB", fmt(F("F-B-MEAN")), "F-B-MEAN")
    put("sPtopPct", f"{100 * F('F-A-PTOP'):.0f}", "F-A-PTOP in %"); put("sPtopCtlPct", f"{100 * F('F-C-PTOP'):.0f}", "F-C-PTOP in %")
    put("nMGTOW", f"{max(r['mass_kg'] for r in mm['loadings']):.1f}", "heaviest loading: M2 at declared max (variants_geometry.json)")
    put("sPtopCtl", f"{F('F-C-PTOP'):.3f}", "F-C-PTOP"); put("sTotalCtl", fmt(F("F-C-MEAN")), "F-C-MEAN")
    put("sPtopAlow", f"{F('F-A-PTOP-fowler_low'):.3f}", "F-A-PTOP-fowler_low")
    put("sBreakeven", f"{F('F-AB-BREAKEVEN'):.2f}", "F-AB-BREAKEVEN")
    put("sRegA", f"{F('F-A-MAXREG'):.3f}", "F-A-MAXREG"); put("sRegB", f"{F('F-B-MAXREG'):.3f}", "F-B-MAXREG")
    put("sFieldMed", fmt(F("F-FLD-2027-P50")), "F-FLD-2027-P50"); put("sFieldLo", fmt(F("F-FLD-2027-P10")), "")
    put("sFieldHi", fmt(F("F-FLD-2027-P90")), ""); put("sFieldGM", fmt(F("F-FLD-GMRIV"), 1), "F-FLD-GMRIV")
    put("sWinLo", fmt(min(F(f"F-BT-{y}-WIN") for y in range(2022, 2027))), "F-BT-*-WIN")
    put("sWinHi", fmt(max(F(f"F-BT-{y}-WIN") for y in range(2022, 2027))), "F-BT-*-WIN")
    # sensitivity
    put("tRef", fmt(T["ref_mean"]), "p1_sens tornado ref (= F-A-MEAN)")
    put("tLapUp", fmt(-tor["time_cal"]["+0.1"]), "lap factor +10 %, loss")
    put("tLapDn", fmt(tor["time_cal"]["-0.1"]), "lap factor -10 %, gain")
    put("tRhoDn", fmt(-tor["rho"]["-0.1"]), "density -10 %, loss")
    put("tEtaDn", fmt(-tor["power_factor"]["-0.1"]), "efficiency -10 %, loss")
    put("tMassUp", fmt(-tor["af_kg"]["+0.1"]), "airframe +10 %, loss")
    put("tMassUpTwenty", fmt(-tor["af_kg"]["+0.2"]), "airframe +20 %, loss")
    put("tAreaMax", fmt(max(abs(tor["s"]["+0.1"]), abs(tor["s"]["-0.1"])), 2), "wing area +-10 %")
    put("tClDn", fmt(-tor["clmax"]["-0.1"]), "CLmax -10 %, loss")
    put("tFieldUp", fmt(-tor["field"]["+0.1"]), "field +10 %, loss")
    put("tFrozenBest", fmt(frozen_best["total"]), "frozen sweep max"); put("tFrozenM", f"{frozen_best['m']:.0f}", "")
    put("tDeclGain", fmt(F("F-A-MEAN") - frozen_best["total"]), "tech declaration gain")
    put("tFeasEight", f"{s8['feas']:.2f}", "frozen 8 kg P(M2 feasible)")
    put("tCompletion", f"{tw.get('Mission completion (reliability)', 0) * 100:.0f}" if tw else "55", "s6 trade weights")
    # budget
    lines, sub, cont = budget()
    for k, lab, v, basis in lines:
        put("b" + k.capitalize(), money(v), f"{lab} [{basis}]")
    shown = {k: r10(val) for k, _, val, _ in lines}
    printed = ("hwProto", "hwComp", "hwMotors", "hwPacks", "hwPayload", "consumables", "hwCrate", "airfare", "lodging", "meals", "ground",
               "visas", "fees")
    sub_d = sum(shown[k] for k in printed)
    cont_d = r10(0.15 * sub_d)
    # Table 02 shows grouped rows; subtotal and total are the sums of the printed (rounded) rows
    put("bSubtotal", money(sub_d), "sum of printed rows"); put("bContingency", money(cont_d), "15 %")
    put("bTotal", money(sub_d + cont_d), "sum of printed rows")
    put("bTotalK", f"{(sub_d + cont_d) / 1000:.1f}", "total, thousands")
    put("bTravellers", str(TRAVELLERS), "team lead, 31 Oct")
    put("bAirfareEach", f"{AIRFARE_EUR * USD_PER_EUR:,.0f}".replace(",", "{,}"), "quote, whole dollars")
    put("bRooms", str(ROOMS), "2 per room"); put("bMembers", str(MEMBERS), "team lead, 31 Oct")
    put("bTungstenKg", f"{TUNGSTEN_USD_PER_KG:.0f}", f"mean of {len(TUNGSTEN_LISTINGS)} heavy-alloy listings")
    put("bTungstenN", str(len(TUNGSTEN_LISTINGS)), "")
    put("bVisa", str(VISA_USD), "MRV 185 + integrity fee 250"); put("bMIE", str(MIE_USD), "GSA FY2027 Tucson M&IE")
    fund_usd = FUND_KWD / KWD_PER_USD
    put("bFundKWD", money(FUND_KWD).replace("{,}", "{,}"), "team lead, 31 Oct")
    put("bFundUSD", money(fund_usd), f"at {KWD_PER_USD} KWD/USD")
    put("bBalance", money(sub_d + cont_d - fund_usd), "total minus the 10,000 KWD allocation")
    # Team lead, 31 Oct 2026: university funded, "genuinely a blank cheque"; the allocation is the first tranche.
    print(f"  funding allocation {fund_usd:,.0f} USD; total {sub_d + cont_d:,.0f}; balance from the university "
          f"{sub_d + cont_d - fund_usd:,.0f}")
    # stability about the CG (AVL re-run), performance and payload numbers added in P1.2
    st = avl_cg(F("F-A-XCG"))
    put("nCma", fmt(st["Cma"]), "AVL about the CG (p1_data.avl_cg)"); put("nCnb", fmt(st["Cnb"], 3), "AVL about the CG")
    put("nClb", fmt(st["Clb"], 3), "AVL about the CG"); put("nCLa", fmt(st["CLa"]), "AVL")
    k = 1.0 / (math.pi * m2["e"] * m2["ar"])
    cl2 = 2 * m2["gross"] * 9.80665 / (1.064 * F("F-A-S") * m2["v"] ** 2)
    put("nCDzero", f"{m2['cd0']:.4f}", "p1_nominal m2.cd0 (wing + body)")
    put("nLDcruise", f"{cl2 / (m2['cd0'] + k * cl2 ** 2):.1f}", "M2 level flight at the design-point speed")
    put("nLDmax", f"{0.5 / math.sqrt(m2['cd0'] * k):.1f}", "1 / (2 sqrt(CD0 k))")
    p_mean = m2["e_wh"] * 3600 / m2["t5"]
    put("nPowerMtwo", f"{p_mean / 1000:.1f}", "M2 mean battery power, kW (design point)")
    put("nAmpsMtwo", f"{p_mean / 29.6:.0f}", "M2 mean current at 8S nominal 29.6 V")
    put("nMtwoGrossDP", fmt(m2["gross"], 1), "design-point M2 gross")
    put("nMthreeGrossDP", fmt(m3["gross"], 1), "design-point M3 gross at the median flown mass")
    put("nTensionMed", f"{D['m3']['p50'] * 9.80665 * m3['n']:.0f}", "m g n at the median M3 mass, design-point n")
    put("nTensionEight", f"{8 * 9.80665 * m3['n']:.0f}", "m g n at 8 kg, same n")
    S6F = J(PROP / "data/p1_payload.json")["field"]
    FB = J(DB02 / "out/integration/finalists.json")["base"]
    put("sExpected", fmt(FB["S10F8"]["our_total_mean"]), "A total with failed attempts sampled (field_stats)")
    put("sExpectedCtl", fmt(FB["CTRL"]["our_total_mean"]), "first iteration, same")
    put("tSpanEDn", fmt(-tor["e_factor"]["-0.1"]), "span efficiency -10 %, loss")
    put("sPMtwoDone", f"{F('F-A-PM2D'):.2f}", "F-A-PM2D"); put("sPMthreeDone", f"{F('F-A-PM3D'):.2f}", "F-A-PM3D")
    put("sFieldGMexp", fmt(S6F["gm"]), "expected-field GM best, kg m (s6.fields)")
    put("sFieldMthreeExp", f"{S6F['m3']:.1f}", "expected-field M3 best, lap kg (s6.fields)")
    # Fig. 05 finalists: how far every other finalist trails A (paired, base case)
    sel = J(DB02 / "out/integration/finalists.json")["selection"]
    gaps = [v[0] for k, v in sel["vs_leader"].items() if k != sel["leader"]]
    put("sTrailLo", f"{min(gaps):.3f}", "finalists vs A, paired"); put("sTrailHi", f"{max(gaps):.3f}", "")
    put("sPtopFtwelve", f"{J(DB02 / 'out/integration/finalists.json')['base']['S12F6']['p_mission_top']:.3f}", "1.2 m2 Fowler")
    # payload trades (tools/p1_payload.py)
    PL = J(PROP / "data/p1_payload.json")
    sim = next(r for r in PL["m2"] if r["n_sim"] == 1 and abs(r["m"] - 6.0) < 1e-9)
    put("pSimFeas", f"{sim['feas']:.2f}", "P(M2 feasible), one simulator at a 6 kg declaration")
    best = max(PL["m3"], key=lambda r: r["exp1"])
    flat = [r["m"] for r in PL["m3"] if r["exp1"] >= best["exp1"] - 0.01]
    put("pMthreeLo", f"{min(flat):.2f}".rstrip("0").rstrip("."), "M3 per-attempt optimum, within 0.01")
    put("pMthreeHi", f"{max(flat):.2f}".rstrip("0").rstrip("."), "")
    put("pStowFree", f"{PL['stow_free_delta']:.3f}", "mean-total gain if the stow fell outside the window")

    out = ["% GENERATED by proposal/tools/p1_data.py (31 Oct 2026). Do not edit: change the sources and re-run.",
           "% Each macro: value % source key (DB-02 F-* = out/finalists/F_results.json)."]
    for k, (v, src) in m.items():
        out.append(f"\\newcommand\\{k}{{{v}}}" + (f"  % {src}" if src else ""))
    (PROP / "data/p1.tex").write_text("\n".join(out) + "\n", encoding="utf-8")
    for k, lab, v, basis in lines:
        print(f"  {lab:48s} {v:9.0f}  {basis}")
    print(f"  subtotal {sub:,.0f}  contingency {cont:,.0f}  total {sub + cont:,.0f}")
    print(f"wrote data/p1.tex ({len(m)} macros)")


if __name__ == "__main__":
    main()
