"""Build W/out/rules/results.json (S1-Rnn) and compliance.csv. Run: python src/rules/run_s1.py. Writes only to W/out/rules."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
W = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(W / "src"))
from rules import compliance as C      # noqa: E402
from rules import model as R           # noqa: E402
from rules import strategy as S        # noqa: E402

OUT = W / "out" / "rules"


def build():
    items = {}
    n = [0]

    def add(name, value, rng, unit, grade, source, note):
        n[0] += 1
        items[f"S1-R{n[0]:02d}"] = {"name": name, "value": value, "range": rng, "dist": "uniform" if rng else "point", "unit": unit,
                                    "grade": grade, "source": source, "note": note}

    rows = C.build_rows()
    add("clauses_in_compliance_matrix", len(rows), None, "-", "verified", "out/rules/compliance.csv; rules draft 2 Sep 2026",
        f"{sum(r['quote_in_layout'] for r in rows)} of {len(rows)} quotes found verbatim in the layout text (test_v_rules)")
    tab = {}
    for p in (0.57, 0.65, 0.73):
        for a in (3, 4):
            tab[f"p{p}_A{a}"] = S.m1_waiver(p, a)
    g = [v["gain_waive"] for v in tab.values()]
    add("m1_waiver_gain_expected_total", round(tab["p0.65_A3"]["gain_waive"], 3), [round(min(g), 3), round(max(g), 3)], "points", "computed",
        "attempts.p_complete (field 2.4-2.9 attempts, 57-73 % scored, verified); parts 1.0/1.58/3.0/1.10 from the DB-01 reference",
        "waiving M1 (L879-882) always wins in the attempt model; a failed M2 cannot fall back to M1")
    add("p_m3_waive_vs_fly_p0.65_A3", [round(tab["p0.65_A3"]["waive"]["P_M3"], 3), round(tab["p0.65_A3"]["fly"]["P_M3"], 3)], None, "-", "computed",
        "attempts.p_complete", "waive 0.718 against fly 0.401")
    rv = S.report_vs_mission(88.0, 6.3)
    add("mission_points_worth_one_report_point_inverse", round(rv["report_points_per_mission_point"], 2), [round(85 / 7.0, 2), round(92 / 5.5, 2)], "report points", "computed",
        "Competition = TR x TM + participation (section 6.3); TR 88, TM 6.3", "one mission point equals TR/TM report points")
    fy = S.field_by_year()
    add("mission_total_needed_to_win_at_TR88_2022_26", round(S.needed_mission(fy["2026"], 88.0), 2),
        [round(min(S.needed_mission(v, 88.0) for v in fy.values()), 2), round(max(S.needed_mission(v, 88.0) for v in fy.values()), 2)], "points", "computed",
        "dbf_results.csv winning scores 501.26-567.51, participation 3", "needed TM = (winning score - 3) / TR; 2026 value shown")
    add("m3_stow_threshold_7_laps_lap39p1", round(300 - 8 - 7 * 39.1, 2), None, "s", "computed", "300 - t_TO 8 - 7 x 39.1", "stow counted in the window")
    add("m3_lap_time_for_8_laps_stow_counted_12s", round((300 - 8 - 12) / 8, 2), [round((300 - 8) / 8, 2), round((300 - 8 - 12) / 8, 2)], "s", "computed",
        "(300 - 8 - stow)/8", "36.5 s if the stow is outside the window (L964-972 silent)")
    add("m3_points_per_lap_4p4kg_expected_field", round(S.lap_value(4.4), 3), [round(S.lap_value(4.4, scenario="aggressive"), 3), round(S.lap_value(4.4), 3)], "points", "computed",
        "competitor.toml expected 20.25 and aggressive 27 kg-laps (estimates)", "0.217 expected field, 0.163 aggressive field, until the cap at 1.0")
    add("container_ring_to_bottom_limit", R.LIMITS["ring_to_bottom_lt_m"], None, "m", "verified", "L538-542", "'should be less than 15 inches'; only 15 in of rigging plus container is guaranteed")
    add("sim_mass_tolerance", R.LIMITS["sim_mass_tol_kg"], None, "kg", "verified", "L559-560", "+-1 oz = 28.35 g")
    add("togw_limit_true_mass", round(R.togw_display_limit_kg(), 3), None, "kg", "verified", "L627 and section 6.2 rounding", "display rounding to 0.01 lb")
    return {"schema": 1, "stream": "S1", "generated": time.strftime("%Y-%m-%dT%H:%M+03:00"), "items": items}


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    C.write_csv(OUT / "compliance.csv")
    (OUT / "results.json").write_text(json.dumps(build(), indent=1), encoding="utf-8")
    print("ok")
