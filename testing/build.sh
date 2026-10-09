#!/usr/bin/env bash
# Build all test cards into printable PDFs in testing/cards/.
#   ./build.sh            (all cards)   ./build.sh TC-01_...tex  (one card)
set -uo pipefail
cd "$(dirname "$0")/cards"
cards=("$@")
[ ${#cards[@]} -eq 0 ] && cards=(TC-*.tex)
for c in "${cards[@]}"; do
  ../../design-system/tools/build.sh "$c" "${c%.tex}.pdf" || exit 1
done
