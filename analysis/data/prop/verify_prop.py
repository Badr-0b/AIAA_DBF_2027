# Copyright © 2026 Badr Obtel. All rights reserved.
"""Check every propulsion value against its source, then write SI tables (TOOLING).

    python analysis/data/prop/verify_prop.py

1. components.toml: each quote must be in the cached text of its source
   (raw/prop/<source>.txt, whitespace-normalised as in verify.py) and the value
   inside the quote; the unit must be known.
2. stands.toml: each quote must be on the stated page of the cached AIAA report
   (verify.find); "IMAGE:" rows were read on the rendered page and are counted
   separately; every propeller named must exist in the APC archive.
3. T-Motor pages: every spec block and test table parsed by propdata.py must be
   complete (Kv, resistance, idle current, mass; >= 10 test rows per winding).
Writes components.csv and stands.csv. Exits non-zero on any failure.
"""
import csv
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import propdata as pdat                                  # noqa: E402
from verify import find, norm                            # noqa: E402


def check_components():
    data = tomllib.loads((HERE / "components.toml").read_text(encoding="utf-8"))
    out, bad = [], []
    for kind in ("battery", "motor", "statement"):
        for rec in data.get(kind, []):
            src = pdat.RAW / f"{rec['source']}.txt"
            if not src.exists():
                bad.append(f"{rec['id']}: source {rec['source']} not cached (run fetch_prop.py)")
                continue
            text = norm(src.read_text(encoding="utf-8"))
            for param, value, unit, quote, where in rec["rows"]:
                tag = f"{kind} {rec['id']} {param} {value!r}"
                if norm(quote) not in text:
                    bad.append(f"{tag}: quote not in {rec['source']}")
                elif norm(value) not in norm(quote):
                    bad.append(f"{tag}: value not inside its quote")
                elif unit != "text" and unit not in pdat.TO_SI:
                    bad.append(f"{tag}: unknown unit {unit!r}")
                elif unit != "text" and pdat.si(value, unit) is None:
                    bad.append(f"{tag}: value not numeric")
                else:
                    out.append({"kind": kind, "id": rec["id"], "param": param, "value": value, "unit": unit,
                                "value_si": "" if unit == "text" else round(pdat.si(value, unit), 9),
                                "unit_si": "" if unit == "text" else pdat.TO_SI[unit][1],
                                "source": rec["source"], "where": where, "quote": quote})
    return out, bad


def check_stands():
    data = tomllib.loads((HERE / "stands.toml").read_text(encoding="utf-8"))
    names = set(pdat.apc_names())
    out, bad = [], []
    for p in data["point"]:
        prop = p.get("prop", "")
        if prop.startswith("apc:") and prop[4:] not in names:
            bad.append(f"stand {p['id']}: propeller {prop} not in the APC archive")
        for param, value, unit, page, quote in p["rows"]:
            tag = f"stand {p['id']} {param} {value!r} p{page}"
            image = quote.startswith("IMAGE:")
            hit = True if image else find(p["source"], page, quote)
            if hit is None:
                bad.append(f"{tag}: AIAA source not cached (run analysis/data/fetch.py)")
            elif hit is not True:
                bad.append(f"{tag}: quote not on page {page}" + (f" (found on {hit})" if hit else " (not found)"))
            elif not image and norm(value) not in norm(quote):
                bad.append(f"{tag}: value not inside its quote")
            elif unit != "text" and pdat.si(value, unit) is None:
                bad.append(f"{tag}: value not numeric or unit unknown")
            else:
                out.append({"point": p["id"], "year": p["year"], "team": p["team"], "param": param, "value": value,
                            "unit": unit, "value_si": "" if unit == "text" else round(pdat.si(value, unit), 9),
                            "unit_si": "" if unit == "text" else pdat.TO_SI[unit][1], "source": p["source"],
                            "page": page, "verified": "page image" if image else "text", "quote": quote})
    return out, bad


def check_tmotor():
    reg = tomllib.loads((HERE / "sources.toml").read_text(encoding="utf-8"))["source"]
    bad, n_spec, n_test = [], 0, 0
    for s in reg:
        if not s["id"].startswith("tmotor-"):
            continue
        specs = pdat.tmotor_specs(s["id"])
        tests = pdat.tmotor_tests(s["id"])
        if not specs:
            # AT5330-A uses a different page layout (no 'Test Item' table): spec values not parsed
            continue
        for sp in specs:
            n_spec += 1
            for key in ("kv", "rm", "i0", "mass"):
                if sp[key] is None:
                    bad.append(f"{s['id']} {sp['variant']}: {key} missing")
        for var, rows in tests.items():
            n_test += len(rows)
            if len(rows) < 10:
                bad.append(f"{s['id']} {var}: only {len(rows)} test rows")
            if pdat.variant_key(var) not in {pdat.variant_key(sp["variant"]) for sp in specs}:
                bad.append(f"{s['id']} {var}: test table has no spec block")
    return n_spec, n_test, bad


def main():
    comp, bad_c = check_components()
    st, bad_s = check_stands()
    n_spec, n_test, bad_t = check_tmotor()
    for name, rows in (("components.csv", comp), ("stands.csv", st)):
        if rows:
            with (HERE / name).open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
    n_img = sum(r["verified"] == "page image" for r in st)
    print(f"components: {len(comp)} values verified against manufacturer pages, {len(bad_c)} failed")
    print(f"stands:     {len(st)} values verified ({len(st) - n_img} against the text layer, {n_img} read on the "
          f"rendered page), {len(bad_s)} failed")
    print(f"T-Motor:    {n_spec} Kv windings parsed, {n_test} measured test rows, {len(bad_t)} failed")
    for b in bad_c + bad_s + bad_t:
        print("  FAIL", b)
    return 1 if bad_c or bad_s or bad_t else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
