# Copyright © 2026 the members of the AUM AIAA DBF team. All rights reserved.
"""Readers for the cached propulsion sources (TOOLING, no physics).

Everything is read from analysis/data/raw/prop/ (fetch_prop.py), so no number is
typed by hand:
  apc_table(name)      APC computed performance (PER3 file inside the APC archive)
  uiuc_runs(name)      UIUC wind-tunnel measurements of APC Thin Electric props
  tmotor_specs(src)    T-Motor spec table per Kv winding (product page)
  tmotor_tests(src)    T-Motor measured test table per Kv winding
  components()         batteries / motors / statements from components.toml, in SI
  stands()             AIAA test points from stands.toml, in SI
Units: SI; propeller names follow APC (e.g. "20x13E"); diameters in metres.
"""
import re
import tomllib
import zipfile
from functools import lru_cache
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RAW = HERE.parent / "raw" / "prop"
IN_M = 0.0254
LBF_N = 0.45359237 * 9.80665
APC_RHO = 1.225          # APC's coefficients use sea-level density (checked by test_propdata: T = Ct rho n^2 D^4)

TO_SI = {  # unit -> (factor, SI unit); exact definitions
    "mAh": (0.001, "Ah"), "C": (1.0, "1/h"), "A": (1.0, "A"), "g": (0.001, "kg"), "oz": (0.028349523125, "kg"),
    "lb": (0.45359237, "kg"), "mm": (0.001, "m"), "Wh": (1.0, "Wh"), "V": (1.0, "V"), "mOhm": (0.001, "Ohm"),
    "rpm": (1.0, "rpm"), "rpm/V": (1.0, "rpm/V"), "lbf": (LBF_N, "N"), "kgf": (9.80665, "N"), "N": (1.0, "N"),
    "W": (1.0, "W"), "mph": (0.44704, "m/s"), "ft/s": (0.3048, "m/s"), "s": (1.0, "s"), "cells": (1.0, "cells"),
    "rpm*in": (1.0, "rpm*in"),
}


def number(value):
    """First number in a printed value ("150,000" -> 150000.0)."""
    m = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
    return float(m.group()) if m else None


def si(value, unit):
    if unit == "text":
        return None
    f, _ = TO_SI[unit]
    x = number(value)
    return None if x is None else x * f


# ---------------------------------------------------------------- APC (computed)
def apc_diameter_m(name):
    """Diameter from an APC name: '20x13E' -> 20 in; APC drops the decimal point
    ('205x14E' is 20.5 in), so a 3-digit diameter is read as tenths."""
    d = re.match(r"(\d+)x", name).group(1)
    return (float(d) / 10.0 if len(d) == 3 else float(d)) * IN_M


@lru_cache(maxsize=None)
def _apc_zip():
    return zipfile.ZipFile(RAW / "apc-perfiles-202602.zip")


def apc_names():
    return sorted(Path(n).stem[5:] for n in _apc_zip().namelist() if Path(n).name.upper().startswith("PER3_"))


@lru_cache(maxsize=None)
def apc_table(name):
    """APC PER3 data for one propeller: {"name", "version", "date", "D", "rpm": array,
    "runs": [(rpm, J, Ct, Cp, thrust_N, power_W) arrays per RPM]} (COMPUTED by APC)."""
    z = _apc_zip()
    member = next(n for n in z.namelist() if Path(n).name.lower() == f"per3_{name.lower()}.dat")
    text = z.read(member).decode("latin-1")
    version = re.search(r"\b(v\d{4}-\d{4})\b", text)
    date = re.search(r"Simulation Date:\s*(\S+)", text)
    runs, rpm, rows = [], None, []

    def close():
        if rpm is not None and rows:
            a = np.array(rows)
            runs.append((rpm, a[:, 0], a[:, 1], a[:, 2], a[:, 3], a[:, 4]))

    for line in text.splitlines():
        m = re.search(r"PROP RPM =\s*(\d+)", line)
        if m:
            close()
            rpm, rows = float(m.group(1)), []
            continue
        p = line.split()
        if rpm is not None and len(p) >= 11:
            try:
                v = [float(x) for x in p[:11]]
            except ValueError:
                continue
            rows.append([v[1], v[3], v[4], v[10], v[8]])      # J, Ct, Cp, thrust (N), power (W)
    close()
    return {"name": name, "version": version.group(1) if version else "", "date": date.group(1) if date else "",
            "D": apc_diameter_m(name), "rpm": np.array([r[0] for r in runs]), "runs": runs}


# ---------------------------------------------------------------- UIUC (measured)
@lru_cache(maxsize=None)
def _uiuc_zip():
    return zipfile.ZipFile(RAW / "uiuc-propdb-zip.zip")


UIUC_VOL4 = ("12x6", "12x8", "12x10", "13x65", "13x8", "13x10", "14x7", "14x85", "14x10", "16x8", "16x10", "16x12",
             "18x8", "18x10", "18x12", "20x10", "21x13")
UIUC_VOL1_LARGE = ("14x12", "17x12", "19x12")


def uiuc_apc_name(uiuc_name):
    """UIUC 'apce_13x65' -> APC '13x65E' (APC writes 13x6.5 as 13x65 too)."""
    return uiuc_name + "E"


@lru_cache(maxsize=None)
def uiuc_runs(name, volume="volume-4"):
    """UIUC measurements of APC Thin Electric prop `name` (e.g. "20x10"):
    {"static": array[[rpm, CT, CP]], "runs": [(rpm, J, CT, CP)]} (MEASURED, wind tunnel)."""
    z = _uiuc_zip()
    pre = f"UIUC-propDB/{volume}/data/apce_{name}_"
    static, runs = None, []
    for n in sorted(x for x in z.namelist() if x.startswith(pre) and x.endswith(".txt")):
        tail = n[len(pre):-4]
        if tail == "geom":
            continue
        rows = []
        for line in z.read(n).decode("latin-1").splitlines()[1:]:
            p = line.split()
            try:
                rows.append([float(x) for x in p])
            except ValueError:
                continue
        a = np.array(rows)
        if tail.startswith("static"):
            static = a[:, :3]
        else:
            rpm = float(tail.rsplit("_", 1)[1])
            runs.append((rpm, a[:, 0], a[:, 1], a[:, 2]))
    return {"static": static, "runs": sorted(runs, key=lambda r: r[0])}


# ---------------------------------------------------------------- T-Motor (spec + measured)
def _lines(source):
    return (RAW / f"{source}.txt").read_text(encoding="utf-8").splitlines()


SPEC_KEYS = ("Weight", "Internal Resistance", "Idle Current", "Peak Current", "Max Power", "Rated Voltage",
             "Configuration", "Motor Dimensions")


def tmotor_specs(source):
    """[{"variant", "kv", "mass", "rm", "i0", "i0_v", "i_peak", "p_max", "raw": {...}}] per Kv winding."""
    L = _lines(source)
    out = []
    for i, l in enumerate(L):
        if l == "Test Item" and i + 1 < len(L) and "KV" in L[i + 1].upper():
            raw, k = {}, i + 2
            while k < len(L) - 1 and L[k] != "Test Item" and not L[k].startswith("Type"):
                if any(L[k].startswith(s) for s in SPEC_KEYS):
                    raw[L[k]] = L[k + 1]
                    k += 2
                else:
                    k += 1
            get = lambda key: next((v for kk, v in raw.items() if kk.startswith(key)), "")
            idle_key = next((kk for kk in raw if kk.startswith("Idle Current")), "")
            out.append({"variant": L[i + 1], "kv": number(re.search(r"KV\s*(\d+)", L[i + 1], re.I).group(1)),
                        "mass": number(get("Weight")) * 1e-3, "rm": number(get("Internal Resistance")) * 1e-3,
                        "i0": number(get("Idle Current")), "i0_v": number(idle_key) if idle_key else None,
                        "i_peak": number(get("Peak Current")), "p_max": number(get("Max Power")), "raw": raw})
    return out


def tmotor_tests(source):
    """{variant: [(prop, throttle %, V, A, W, rpm, N*m, thrust g)]} from the measured test table."""
    L = _lines(source)
    try:
        start = next(i for i, l in enumerate(L) if l == "Type" and "Propeller" in L[i + 1:i + 3])
    except StopIteration:
        return {}
    notes = [i for i in range(start, len(L)) if L[i].startswith("Note: Motor temperature")]
    end = notes[-1] if notes else len(L)
    out, var, prop, k = {}, None, None, start
    while k < end:
        l = L[k]
        if re.fullmatch(r"(Long Shaft )?KV\d+[A-Za-z]*", l):
            var, prop = l, None
            out.setdefault(var, [])
        elif re.fullmatch(r"[A-Za-z]*\d+(\.\d+)?\s?[*xX]\s?\d+(\.\d+)?[A-Za-z]*", l):
            prop = l
        elif var and re.fullmatch(r"\d+%", l) and k + 7 < len(L):
            try:
                v = [float(x) for x in L[k + 1:k + 8]]
            except ValueError:
                v = None
            if v:
                out[var].append((prop, float(l[:-1]), *v[:6]))
                k += 8
                continue
        k += 1
    return {kk: vv for kk, vv in out.items() if vv}


def variant_key(variant):
    """'Long Shaft KV220' and 'KV220' -> 'KV220' (spec and test tables label windings differently)."""
    return re.search(r"KV\d+", variant, re.I).group().upper()


# ---------------------------------------------------------------- verified records
def _load(name):
    with (HERE / name).open("rb") as f:
        return tomllib.load(f)


def components():
    """{"battery": {id: {...}}, "motor": {id: {...}}} with each row's SI value (and the printed one)."""
    data = _load("components.toml")
    out = {}
    for kind in ("battery", "motor", "statement"):
        out[kind] = {}
        for rec in data.get(kind, []):
            d = {"name": rec.get("name", rec["id"]), "source": rec["source"],
                 **{k: v for k, v in rec.items() if k not in ("id", "name", "source", "rows")}}
            for param, value, unit, _quote, _where in rec["rows"]:
                d[param] = value if unit == "text" else si(value, unit)
            out[kind][rec["id"]] = d
    return out


def stands():
    """{point id: {meta..., param: SI value}} from stands.toml."""
    out = {}
    for p in _load("stands.toml")["point"]:
        d = {k: v for k, v in p.items() if k != "rows"}
        for param, value, unit, _page, _quote in p["rows"]:
            if unit != "text":
                d[param] = si(value, unit)
        out[p["id"]] = d
    return out
