#!/usr/bin/env bash
# Build the decision briefs into PDFs in decisions/.
#   ./build.sh            (all briefs)   ./build.sh DB-01_...tex  (one brief)
# Figures come from analysis/out/: run the analysis scripts first (analysis/README.md).
set -uo pipefail
cd "$(dirname "$0")"
docs=("$@")
[ ${#docs[@]} -eq 0 ] && docs=(DB-*.tex)
for d in "${docs[@]}"; do
  ../design-system/tools/build.sh "$d" "${d%.tex}.pdf" || exit 1
done
