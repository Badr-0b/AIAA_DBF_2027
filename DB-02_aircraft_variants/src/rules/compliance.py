"""Clause-by-clause compliance matrix (C01-C99) built from rules.model.RULES plus per-configuration impacts.

build_rows() -> list[dict]; write_csv(path) writes W/out/rules/compliance.csv (path argument only; nothing on import).
Quotes are checked against the 2 Sep 2026 draft layout text (whitespace-normalised, fragments split at ' ... ').
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
W = Path(__file__).resolve().parents[2]
REPO = W.parent
sys.path.insert(0, str(W / "src"))
from rules import model as R                      # noqa: E402

LAYOUT = REPO / "analysis" / "data" / "raw" / "aiaa-dbf-2027-rules-draft.layout.txt"
CONFIGS = {
    "REF": "REF-D01 class: monoplane, conventional tail, fixed tricycle, single tractor, door bay",
    "WL": "Winglets or tip plates on the 1.82 m wing",
    "VT": "V-tail, ruddervators, elevons or flaperons",
    "TW": "Twin propulsion systems (2 x 50 Wh, 2 fuses)",
    "HV": "One heavy declared unit (6-10 kg sensor declared at tech)",
    "MB": "Biplane, box, tandem or joined wing",
}
# clause id -> {config: impact}; anything not listed is "none" for that configuration
IMPACT = {
    "C01": {"WL": "RISK: wingspan undefined; keep overall width <= 1.8288 m so cant and plates add no width", "MB": "span of every surface <= 1.8288 m"},
    "C03": {"HV": "tip-test mass = empty + pack + (1 + n_sim_max) x (container + declared sensor); size the spar for the top of the declared range", "MB": "tip lift points on the main lifting surface (Q&A: undefined for stacked wings)", "TW": "heaviest pack count included"},
    "C04": {"HV": "the recorded mass is a permanent TOGW cap; declare no higher than the spar passed"},
    "C06": {"HV": "tow line sized for 3 x n 4 x sensor weight (about 1.1 kN at 10 kg); a line break is a dropped part"},
    "C09": {"TW": "two COTS motors, no modification"},
    "C10": {"VT": "a rate-gyro stabiliser is allowed and can restore V-tail control authority", "WL": "gyro allowed for roll damping"},
    "C17": {"WL": "winglet presence and size on the configuration drawing", "VT": "tail type is frozen at 19 Feb", "TW": "motor count frozen at 19 Feb", "MB": "wing configuration frozen at 19 Feb"},
    "C24": {"TW": "two plugs, one per system"},
    "C26": {"TW": "each plug >= 152.4 mm from every prop plane; wing-mounted tractors put both planes at one x, plugs go aft on the top surface"},
    "C27": {"TW": "push-pull only if both plugs are reachable without reaching over either prop (RISK)"},
    "C28": {"TW": "both plugs on the top surface"},
    "C33": {"TW": "one pack per system"},
    "C34": {"TW": "identical packs: 2 x 50 Wh class"},
    "C36": {"TW": "two blade-fuse harnesses of up to 100 A each (power cap about doubled)"},
    "C37": {"TW": "sum of the two packs <= 100 Wh"},
    "C39": {"TW": "fuse <= min(pack continuous, 100 A) per system"},
    "C42": {"HV": "dense compact dart with tow eye above the CG; pitch frequency 0.3-0.6 Hz on aero stiffness only (memo S8); tow test needed"},
    "C43": {"HV": "ballast bay sized for the top of the range; slugs removable for M3 (internal)"},
    "C44": {"HV": "fins cannot be removed for the container: the finned envelope (170-230 mm cross-section) sets the container"},
    "C45": {"HV": "strength member grows 0.6 mm to 1.1 mm with sensor mass; leads alongside"},
    "C49": {"HV": "docking latch rated for the heaviest sensor at n 4"},
    "C52": {"REF": "line >= 2.743 m + eye offset (+0.1 m margin)", "HV": "same line length; the heavy sensor hangs nearly vertical so the static test equals the flight geometry"},
    "C55": {"HV": "bay accepts one 0.3 m class cube TOP up"},
    "C57": {"HV": "100 g-rated sensor cannot meet 381 mm at 3-10 kg; 150 g rating, 41 mm foam, 10-15 deg sling or rigid yoke (Q&A) required", "REF": "DB-01's 100 g / 392 mm container fails; redesign"},
    "C59": {"HV": "simulators sized to the one container; reusable across the range"},
    "C60": {"HV": "adjustable-ballast simulators trimmed to +-10 g at tech when the declared mass is fixed"},
    "C63": {"REF": "high wing with a door: enter with the hatch open or load through a latch-only door", "HV": "single heavy unit means one load, so the hatch question matters less"},
    "C66": {"HV": "1 heavy unit loads in about 195 s versus 285 s for 3 units (estimate); more margin in the 300 s box"},
    "C79": {"HV": "stow time 14-30 s on a servo drum for 3.4-10 kg; 3 s with a geared brushless drive (0.65-0.78 kg): matters at the lap cliff"},
    "C81": {"HV": "heavier unit, same 6 drops: foam bearing area set by the mass, not the rating"},
    "C84": {"HV": "declared mass is chosen at tech after weighing and flying the airframe (decision timing)"},
    "C90": {"VT": "RISK: full up elevator and full right rudder on the same two surfaces conflict; inspector discretion (L1301-1302)", "TW": "throttle closed on both systems"},
    "C96": {"REF": "frozen: tricycle, conventional tail, monoplane, tractor, 1 motor", "VT": "V tail frozen", "TW": "2 motors frozen", "MB": "biplane or box frozen"},
    "C98": {"TW": "push-pull arming access (RISK)"},
}


def _norm(s):
    s = s.replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"- +", "-", re.sub(r"\s+", " ", s)).strip().lower()


_TEXT = None


def layout_text():
    global _TEXT
    if _TEXT is None:
        _TEXT = _norm(LAYOUT.read_text(encoding="utf-8", errors="replace"))
    return _TEXT


def quote_found(quote):
    """True when every fragment of the quote (split at ' ... ' or '...') occurs in the layout text."""
    txt = layout_text()
    frags = [f for f in re.split(r"\s*\.\.\.\s*", quote) if f.strip()]
    return all(_norm(f).strip(" .") in txt for f in frags)


def build_rows():
    rows = []
    for cid, section, lines, quote, req, ver in R.RULES:
        imp = IMPACT.get(cid, {})
        row = {"ID": cid, "section": section, "lines": lines, "verbatim_quote": quote, "design_requirement": req,
               "verification": ver, "quote_in_layout": quote_found(quote)}
        for k in CONFIGS:
            row[f"impact_{k}"] = imp.get(k, "none")
        rows.append(row)
    return rows


def write_csv(path):
    rows = build_rows()
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return len(rows)
