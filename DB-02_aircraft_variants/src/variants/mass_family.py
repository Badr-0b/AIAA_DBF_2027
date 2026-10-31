"""Airframe mass for the DB-02 design family (orchestrator, 30 Oct 2026). Used by the scoring (integration/search.py)
and the layout (variants/geometry_variants.py), so the two cannot disagree.

The DB-01 fit, airframe kg = k S^p over 14 top-3 aircraft (s4_sizing.airframe_fit), is a cross-team trend: teams with
bigger wings also built bigger fuselages and fitted bigger motors. Inside one family the fuselage (sized by the
container), the propulsion, the gear and the avionics do not change with wing area. So the fit is anchored at the
DB-01 reference wing S_REF = 0.9 m2 (REF-D01 and the control, unchanged), and only the wing and tail shares scale with
(S / S_REF)^p. Shares are the E02 airframe split (wing 34 %, fuselage 24 %, propulsion 20 %, gear 9 %, avionics 8 %,
tail 6 %), normalised because they sum to 101 %. Grade: estimate. The fit's x1.31 scatter still applies to the whole.
Flap mechanism deltas (S3): Fowler +0.30 kg, slotted +0.12 kg, plain 0, added by the aero override, not here."""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[3]
S_REF = 0.9
_RAW = dict(wing=0.34, fuselage=0.24, propulsion=0.20, gear=0.09, avionics=0.08, tail=0.06)
SHARES = {k: v / sum(_RAW.values()) for k, v in _RAW.items()}
SCALING = ("wing", "tail")


@lru_cache(maxsize=1)
def fit():
    """(k, p) of the DB-01 airframe fit, read from REPO/analysis (read-only)."""
    sys.path.insert(0, str(REPO / "analysis"))
    import s4_sizing as s4
    k, p, _, _ = s4.airframe_fit()
    return k, p


def split(S):
    """Airframe items (kg) at wing area S: the scaling shares follow (S/S_REF)^p, the rest stay at S_REF."""
    k, p = fit()
    ref = k * S_REF ** p
    r = (S / S_REF) ** p
    return {n: ref * sh * (r if n in SCALING else 1.0) for n, sh in SHARES.items()}


def airframe(S):
    return sum(split(S).values())
