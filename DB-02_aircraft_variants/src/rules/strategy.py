"""S1 strategy helpers: decision timing reference policy, M1 waiver value, report-versus-mission value, lap-cliff value.

Pure functions plus loaders that READ analysis data (never write). Import-safe. SI units.
Decision timing is specified in W/early/S1_decision_timing.md; `choose_at_tech` below is its reference implementation.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.dont_write_bytecode = True
W = Path(__file__).resolve().parents[2]
REPO = W.parent
sys.path.insert(0, str(REPO / "analysis"))
sys.path.insert(0, str(REPO / "analysis" / "data"))

from attempts import p_complete                    # noqa: E402  (read-only; main() is guarded)

# --------------------------------------------------------------------------- decision timing (reference implementation)
# Information sets. Each key is revealed at the stage on the left and known at every later stage.
INFO = {
    "freeze_19feb": [],                                     # nothing measured: priors only
    "tech_april": ["airframe_kg", "clmax", "eta", "f_body", "container_kg", "lap_factor", "e_factor", "pack_wh_per_kg"],
    "attempt_day": ["rho", "wind", "field"],                # revealed on the day, before each attempt only in part
}
FROZEN_AT_FREEZE = ["span", "wing_config", "tail_type", "gear_type", "tractor_pusher", "motor_count",
                    "wing_area_cm_level", "container_and_sensor_hardware", "range_of_declared_mass"]
CHOSEN_AT_TECH = ["declared_sensor_max_kg", "n_sim_max", "tip_test_mass_kg"]
CHOSEN_PER_ATTEMPT = ["n_sim_flown", "prop", "pack", "m3_ballast_kg"]
CHOSEN_AT_GM = ["drop_height_in"]


def choose_at_tech(score_fn, candidates, tech_draw, day_samples):
    """Pick the declared mass (or any tech decision) using only tech-known inputs.
    score_fn(candidate, draw_dict) -> expected total for that candidate; tech_draw: dict of the tech-known inputs for this
    airframe; day_samples: list of dicts of day-only inputs (rho, wind) to average over. Returns (best, scores)."""
    scores = []
    for c in candidates:
        v = [score_fn(c, {**tech_draw, **d}) for d in day_samples]
        scores.append(sum(v) / len(v))
    j = max(range(len(candidates)), key=lambda k: scores[k])
    return candidates[j], scores


# --------------------------------------------------------------------------- M1 waiver
def m1_waiver(p_m2=0.65, attempts=3, p_m1=0.95, parts=(1.0, 1.58, 3.0, 1.10), gm_attempts=2):
    """Expected total mission score and P(M3) when M1 is flown first versus waived (rules L879-882: after waiving, a
    failed M2 cannot fall back to M1). Attempt model of data/attempts.py (each attempt one try at the current mission).
    parts = (M1, M2, M3, GM) scores if completed. M1 flown: M1 is credited when its own attempt succeeds, M2 and M3 need
    the preceding ones. Waived: a successful M2 credits M1."""
    m1s, m2s, m3s, gms = parts
    p3 = p_m2
    pgm = 1.0 - (1.0 - p_m2) ** gm_attempts
    fly = {"P_M1": p_complete((p_m1,), attempts), "P_M2": p_complete((p_m1, p_m2), attempts),
           "P_M3": p_complete((p_m1, p_m2, p3), attempts)}
    waive = {"P_M1": p_complete((p_m2,), attempts), "P_M2": p_complete((p_m2,), attempts),
             "P_M3": p_complete((p_m2, p3), attempts)}
    e_fly = m1s * fly["P_M1"] + m2s * fly["P_M2"] + m3s * fly["P_M3"] + gms * pgm
    e_wav = (m1s + m2s) * waive["P_M2"] + m3s * waive["P_M3"] + gms * pgm
    return {"fly": fly, "waive": waive, "E_fly": e_fly, "E_waive": e_wav, "gain_waive": e_wav - e_fly}


# --------------------------------------------------------------------------- report vs mission
def results_rows():
    with (REPO / "analysis" / "data" / "dbf_results.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def report_vs_mission(tr=88.0, tm=6.3, participation=3.0):
    """Competition = TR x TM + participation (L1650s, section 6.3). d/dTR = TM, d/dTM = TR."""
    c = tr * tm + participation
    return {"C": c, "dC_per_report_point": tm, "dC_per_mission_point": tr,
            "mission_points_per_report_point": tm / tr, "report_points_per_mission_point": tr / tm,
            "pct_per_report_point": 100 * tm / c, "pct_per_mission_point": 100 * tr / c}


def field_by_year():
    out = {}
    rows = results_rows()
    for y in sorted({r["year"] for r in rows}):
        rs = [r for r in rows if r["year"] == y and r["report"] and r["total"] and r["score"]]
        rep = sorted((float(r["report"]) for r in rs), reverse=True)
        tot = sorted((float(r["total"]) for r in rs), reverse=True)
        sc = sorted((float(r["score"]) for r in rs), reverse=True)
        out[y] = {"n": len(rs), "report_max": rep[0], "report_top10_median": rep[4 if len(rep) > 9 else 0] if False else _med(rep[:10]),
                  "report_median_all": _med(rep), "mission_max": tot[0], "mission_top10_median": _med(tot[:10]),
                  "winning_score": sc[0], "second_score": sc[1]}
    return out


def _med(x):
    x = sorted(x)
    n = len(x)
    return x[n // 2] if n % 2 else 0.5 * (x[n // 2 - 1] + x[n // 2])


def needed_mission(year_stats, tr, participation=3.0):
    """Mission total needed to beat that year's winning score at report score tr."""
    return (year_stats["winning_score"] - participation) / tr


# --------------------------------------------------------------------------- lap value
def lap_value(sensor_kg, field_m3=None, scenario="expected"):
    """Mission-3 points per extra lap at sensor_kg (below the field-maximum cap): kg / field max of laps x kg."""
    import common
    f = field_m3 or common.field_maxima(scenario)["m3"]
    return sensor_kg / f
