#!/usr/bin/env bash
# DB-02 rev B pipeline, in dependency order (written 30 Oct 2026 after the rev A review).
#   trim geometry -> screen (162 designs) -> gates + shortlist -> finalists (5 scenarios, paired selection)
#   -> drag-upside check -> A/B layout -> F_ export -> figures -> numbers.tex
# Run from anywhere:  bash DB-02_aircraft_variants/tools/rerun_chain.sh   (about 6 minutes)
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
W="$(cd "$(dirname "$0")/.." && pwd)"
cd "$W/src"
python variants/geometry_variants.py trim
python integration/search.py screen > "$W/out/integration/screen.log" 2>&1
tail -1 "$W/out/integration/screen.log"
python integration/select.py
python integration/finalists.py > "$W/out/integration/finalists.log" 2>&1
grep -E "SELECTION|^done" "$W/out/integration/finalists.log"
python integration/finalists.py cd0
python variants/geometry_variants.py
python variants/export_finalists.py
cd "$W"
python report/figs_orch.py regret p1st threeviews
python report/make_numbers.py
echo "chain done"
