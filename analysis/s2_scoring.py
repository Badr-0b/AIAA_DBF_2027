# Copyright © 2026 the members of the AUM AIAA DBF team. All rights reserved.
"""Script 2: scoring model.

Question: given our performance, what do we score?

Bodies written by Claude at the team lead's direction (12 Oct 2026, Pair mode
lifted), checked against analysis/tests/test_s2_scoring.py.
The scoring formulas are rules Sec. 3.3.3.1-3.3.4 and Sec. 6.3, copied verbatim
into analysis/inputs/rules.toml [scoring].

The "Max" in each mission score is the highest value "of all teams", ours
included. The field_* arguments below are the best value among the OTHER
teams (from competitor.toml via common.field_maxima).
Units: SI (kg, s, m); every score ratio is unit-free (rules Sec. 6.2).
"""
import math
from decimal import ROUND_HALF_UP, Decimal

from common import RULES

S = RULES["scoring"]
G = RULES["ground"]
M2_LAPS = RULES["missions"]["m2_laps"]
EPS = 1e-9   # float guard: 48 x 0.0254 / 0.0254 = 47.99999999999999


def _bonus(ours, field):
    """ours / Max over all teams (ours included); 0 when there is nothing to score."""
    best = max(ours, field)
    return ours / best if best > 0 else 0.0


def m1(completed):
    """Mission 1 score (rules Sec. 3.3.3.1): 1.0 for a successful mission, or a
    successful M2 after M1 was waived (Sec. 3.3.3)."""
    return S["m1"] if completed else 0.0


def m2_payload_mass(n_sim, m_container, m_sensor_max, sim_offset=0.0):
    """Total M2 payload W flown: the sensor (at its declared maximum) in its
    container plus n_sim simulators, each sim_offset heavier than container +
    sensor (allowed +/- 1 oz, rules Sec. 3.1.3). returns kg."""
    unit = m_container + m_sensor_max
    return (1 + n_sim) * unit + n_sim * sim_offset


def m2(w, t, field_wt, completed=True):
    """Mission 2 score (rules Sec. 3.3.3.2): 1 + (W/t) / Max(W/t)."""
    if not completed:
        return 0.0
    return S["m2_base"] + _bonus(w / t, field_wt)


def m3(laps, m_sensor, field_nws, completed=True):
    """Mission 3 score (rules Sec. 3.3.3.3): 2 + (laps x Ws) / Max(laps x Ws)."""
    if not completed:
        return 0.0
    return S["m3_base"] + _bonus(laps * m_sensor, field_nws)


def gm(m_sensor_max, h, field_wh, completed=True):
    """Ground Mission score (rules Sec. 3.3.4): 0.5 + (Ws h) / Max(Ws h)."""
    if not completed:
        return 0.0
    return S["gm_base"] + _bonus(m_sensor_max * h, field_wh)


def declared_drop_inches(h):
    """Whole inches to declare (rules Sec. 3.3.4): never above h, never above
    60 in. The EPS guard keeps 48 x 0.0254 m at 48 in, not 47."""
    max_in = round(G["drop_height_max_m"] / G["drop_step_m"])
    return min(max_in, math.floor(h / G["drop_step_m"] + EPS))


def declared_drop_height(h):
    """declared_drop_inches(h) in metres."""
    return declared_drop_inches(h) * G["drop_step_m"]


def total_mission(m1_score, m2_score, m3_score, gm_score):
    """Total Mission Score = M1 + M2 + M3 + GM (rules Sec. 6.3)."""
    return m1_score + m2_score + m3_score + gm_score


def total_report(proposal, design_report):
    """Total Report Score = 0.15 Proposal + 0.85 Design Report (rules Sec. 6.3)."""
    return S["proposal_weight"] * proposal + S["design_report_weight"] * design_report


def competition(total_report_score, total_mission_score, participation):
    """Competition Score = Total Report x Total Mission + Participation (Sec. 6.3)."""
    return total_report_score * total_mission_score + participation


def round_rule(x, places=2):
    """Rules Sec. 6.2 conventional rounding (>= 0.5 rounds up), on the decimal
    value as written; Python's round() rounds half to even."""
    quantum = Decimal(1).scaleb(-places)
    return float(Decimal(repr(x)).quantize(quantum, rounding=ROUND_HALF_UP))
