# Copyright © 2026 Badr Obtel. All rights reserved.
"""Shared tooling for the analysis scripts: input files, constants, field maxima.

TOOLING (not physics or scoring). Every number comes from analysis/inputs/*.toml
or proposal/data/numbers.tex, so nothing is typed twice.
"""
import math
import sys
import tomllib
from pathlib import Path

ANALYSIS = Path(__file__).resolve().parent
REPO = ANALYSIS.parent
INPUTS = ANALYSIS / "inputs"
OUT = ANALYSIS / "out"
PROPOSAL = REPO / "proposal"


def load(name):
    """An input file from analysis/inputs/ as a dict."""
    with (INPUTS / f"{name}.toml").open("rb") as f:
        return tomllib.load(f)


CONSTANTS = load("constants")
RULES = load("rules")
G0 = CONSTANTS["gravity"]["g0"]
UNITS = CONSTANTS["units"]
SCENARIOS = ("aggressive", "expected", "conservative")


def is_set(x):
    """False for a target still marked nan (or missing) in an input file."""
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def number(macro):
    """A plain numeric macro from proposal/data/numbers.tex, e.g. number("nRho").

    Reuses proposal/make_charts.py:number() so the proposal and the analysis read
    the same value (imported lazily: make_charts pulls in matplotlib).
    """
    sys.path.insert(0, str(PROPOSAL))
    from make_charts import number as _number
    return _number(macro)


def aircraft(key):
    """Parameter set for one aircraft ("a01" or "a02"), shared assumptions merged in."""
    data = load("aircraft")
    return {**data["assumptions"], **data[key]}


def unset(params):
    """Names of the targets still nan in a parameter set."""
    return [k for k, v in params.items() if isinstance(v, float) and math.isnan(v)]


def field_maxima(scenario="aggressive"):
    """Field maxima for one competitor scenario: {"m2": W/t, "m3": N*Ws, "gm": Ws*h}.

    Units kg/s, kg*laps and kg*m. Anchors and reasoning are in competitor.toml.
    """
    c = load("competitor")
    scale = c["scaling"]
    factor = {"aggressive": 1.0, "expected": scale["expected"],
              "conservative": scale["conservative"]}[scenario]
    m2 = c["m2"]
    rate_3lap = m2["field_max_3lap_lb_per_min"] * UNITS["lb_kg"] / 60.0          # kg/s over 3 laps
    five_lap_s = m2["three_lap_s"] + (RULES["missions"]["m2_laps"] - 3) * m2["lap_s"]
    aggressive = {
        "m2": rate_3lap * m2["three_lap_s"] / five_lap_s,
        "m3": c["m3"]["laps"] * c["m3"]["sensor_kg"],
        "gm": c["gm"]["sensor_kg"] * c["gm"]["height_m"],
    }
    return {k: v * factor for k, v in aggressive.items()}
