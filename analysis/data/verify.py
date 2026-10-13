# Copyright © 2026 the members of the AUM AIAA DBF team. All rights reserved.
"""Check every gathered value against its source, then write SI tables (TOOLING).

    python analysis/data/verify.py

For each record in dbf_aircraft.toml:
  1. the quote must appear, whitespace-normalised, on the stated page of the
     cached source text (raw/<id>.txt, .layout.txt or .raw.txt from fetch.py);
  2. the value must appear inside the quote;
  3. the unit must be known; the SI value is computed here, nowhere else.
For dbf_results.csv: every row's quote (the published table line) must appear
in its source, and the row must have passed parse_results.py's arithmetic.
Writes dbf_aircraft.csv (one row per value, SI). Exits non-zero on any failure.
"""
import csv
import re
import sys
import tomllib
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"

TO_SI = {  # unit -> (factor, SI unit); exact definitions
    "m": (1.0, "m"), "ft": (0.3048, "m"), "in": (0.0254, "m"), "mm": (0.001, "m"),
    "m2": (1.0, "m2"), "ft2": (0.09290304, "m2"), "in2": (0.00064516, "m2"),
    "kg": (1.0, "kg"), "g": (0.001, "kg"), "lb": (0.45359237, "kg"), "lbm": (0.45359237, "kg"), "oz": (0.028349523125, "kg"),
    "m/s": (1.0, "m/s"), "ft/s": (0.3048, "m/s"), "mph": (0.44704, "m/s"), "km/h": (1 / 3.6, "m/s"),
    "s": (1.0, "s"), "min": (60.0, "s"), "deg": (1.0, "deg"), "-": (1.0, "-"), "Wh": (1.0, "Wh"), "W": (1.0, "W"),
    "lb/min": (0.45359237 / 60.0, "kg/s"), "kg/s": (1.0, "kg/s"),
    "N": (1.0, "N"), "lbf": (0.45359237 * 9.80665, "N"), "kgf": (9.80665, "N"),
    "gf": (0.00980665, "N"), "ozf": (0.028349523125 * 9.80665, "N"),
    "A": (1.0, "A"), "V": (1.0, "V"), "kg/m2": (1.0, "kg/m2"),
    "lb/ft2": (0.45359237 / 0.09290304, "kg/m2"), "oz/ft2": (0.028349523125 / 0.09290304, "kg/m2"),
    "Wh/kg": (1.0, "Wh/kg"),
}
TEXT = "text"  # a name (motor, propeller, airfoil): checked inside its quote, no SI value
CELL_V = 3.7   # nominal LiPo cell voltage, V (manufacturer convention; Wh = cells x 3.7 x Ah)


def norm(s):
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    s = s.replace("\u00ad", "")            # soft hyphen
    s = re.sub("[\u200e\u200f\u202a-\u202e\u2066-\u2069]", " ", s)   # bidi controls used as word gaps
    return " ".join(s.split())


_cache = {}


def pages(source):
    if source not in _cache:
        texts = []
        for suffix in (".txt", ".layout.txt", ".raw.txt"):
            f = RAW / f"{source}{suffix}"
            if f.exists():
                texts.append([norm(p) for p in f.read_text(encoding="utf-8").split("\f")])
        _cache[source] = texts
    return _cache[source]


def find(source, page, quote):
    """True if quote is on the page; else the pages where it is (to report)."""
    q = norm(quote)
    texts = pages(source)
    if not texts:
        return None
    if any(page - 1 < len(t) and q in t[page - 1] for t in texts):
        return True
    return sorted({i + 1 for t in texts for i, p in enumerate(t) if q in p})


def si(value, unit):
    if unit == "cells mAh":
        m = re.fullmatch(r"(\d+)(?:[Ss]|-cell) (\d+(?:\.\d+)?) mAh", value)
        return (int(m.group(1)) * CELL_V * float(m.group(2)) / 1000.0, "Wh") if m else (None, None)
    factor, si_unit = TO_SI[unit]
    num = re.match(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
    return (float(num.group()) * factor, si_unit) if num else (None, None)


def check_aircraft():
    data = tomllib.loads((HERE / "dbf_aircraft.toml").read_text(encoding="utf-8"))
    out, bad = [], []
    for t in data["team"]:
        for param, mission, value, unit, kind, page, quote, where in t["rows"]:
            tag = f"{t['year']} {t['team']} {param} {mission} {value} {unit} p{page}"
            image = quote.startswith("IMAGE:")      # table with no text layer: read on the rendered page
            hit = True if image else find(t["source"], page, quote)
            if hit is None:
                bad.append(f"{tag}: source not cached (run fetch.py)")
                continue
            if hit is not True:
                bad.append(f"{tag}: quote not on page {page}" + (f" (found on {hit})" if hit else " (not found)"))
                continue
            parts = value.replace(" mAh", "").split() if unit == "cells mAh" else [value]
            if not image and not all(norm(p) in norm(quote) for p in parts):
                bad.append(f"{tag}: value not inside its quote")
                continue
            if unit not in TO_SI and unit not in ("cells mAh", TEXT):
                bad.append(f"{tag}: unknown unit {unit!r}")
                continue
            v_si, u_si = ("", TEXT) if unit == TEXT else si(value, unit)
            if v_si is None:
                bad.append(f"{tag}: value not numeric")
                continue
            out.append({"year": t["year"], "team": t["team"], "aircraft": t.get("aircraft", ""),
                        "param": "battery_wh" if unit == "cells mAh" else param, "mission": mission,
                        "kind": kind, "value": value, "unit": unit, "value_si": v_si if unit == TEXT else round(v_si, 6),
                        "unit_si": u_si, "source": t["source"], "page": page, "where": where,
                        "verified": "page image" if image else "text", "quote": quote})
    return out, bad


def check_results():
    rows = list(csv.DictReader((HERE / "dbf_results.csv").open(encoding="utf-8")))
    bad = []
    for r in rows:
        if r["check"] != "ok":
            bad.append(f"results {r['year']} rank {r['rank']}: arithmetic check failed")
        texts = pages(r["source_id"])
        if not texts or not any(norm(r["quote"]) in p for t in texts for p in t):
            bad.append(f"results {r['year']} rank {r['rank']}: line not found in source")
    return len(rows), bad


def main():
    rows, bad_a = check_aircraft()
    n_res, bad_r = check_results()
    if rows:
        with (HERE / "dbf_aircraft.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    n_img = sum(r["verified"] == "page image" for r in rows)
    print(f"dbf_aircraft: {len(rows)} values verified ({len(rows) - n_img} against the text layer, "
          f"{n_img} read on the rendered page where the table has no text), {len(bad_a)} failed")
    print(f"dbf_results:  {n_res - len(bad_r)} of {n_res} rows verified")
    for b in bad_a + bad_r:
        print("  FAIL", b)
    return 1 if bad_a or bad_r else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
