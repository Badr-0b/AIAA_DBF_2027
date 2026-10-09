#!/usr/bin/env bash
# Build PR-01: regenerate the tables and the spreadsheet from pr01_items.csv,
# then the PDF.   ./build.sh
set -euo pipefail
cd "$(dirname "$0")"
python make_pr.py
../design-system/tools/build.sh PR-01_initial_request.tex PR-01_initial_request.pdf
