"""Builds out/aero_mono/xfoil_polars.json (XFoil 6.99 sections at the real Re). Not imported by model.py.
Run:  PYTHONDONTWRITEBYTECODE=1 python build_xfoil.py   (about 5 min, 4 threads)"""
import json, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
W = Path(__file__).resolve().parents[2]
REPO = W.parent
WORK = W / "out" / "aero_mono" / "work" / "tmp"
WORK.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(WORK)          # XFoil run directories stay inside W
sys.dont_write_bytecode = True
sys.path.insert(0, str(REPO / "analysis"))
import xfoil_tools as xt              # noqa: E402  (import-safe: only defines functions)
AF = REPO / "dbf_airfoil_study_handoff" / "dbf_airfoil_study" / "airfoils"
JOBS = []
for re in (4e5, 6e5, 8e5, 1.1e6):
    for nc in (9.0, 5.0):
        JOBS.append(("sd7037", re, nc))
for name in ("sd7034", "e387", "mh114"):
    for re in (5e5, 8e5):
        JOBS.append((name, re, 9.0))
        JOBS.append((name, re, 5.0))

def run(j):
    name, re, nc = j
    rows, restarts = xt.sweep_up(AF / f"{name}.dat", re, -4.0, 18.0, 0.5, None, nc)
    cl, a, cap = xt.clmax(rows)
    return {"airfoil": name, "re": re, "ncrit": nc, "rows": rows, "clmax": cl, "alpha_clmax": a, "stall_captured": cap}

if __name__ == "__main__":
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(run, JOBS))
    (W / "out" / "aero_mono" / "xfoil_polars.json").write_text(json.dumps(res), encoding="utf-8")
    for r in res:
        print(r["airfoil"], r["re"], r["ncrit"], round(r["clmax"], 3), r["alpha_clmax"], r["stall_captured"], len(r["rows"]))
