#!/usr/bin/env bash
# Build a DB-02 report document with XeLaTeX (two passes). Writes only into report/build/.
#   bash build.sh DB-02_aircraft_variants.tex [copy-to.pdf]
# TEXINPUTS finds dbfdoc.cls + dbf-identity.tex (design-system/latex) and dbfbrief.sty
# (decisions/) read-only; nothing outside DB-02_aircraft_variants/ is written.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
src="$1"; out="${2:-}"
name="$(basename "$src" .tex)"
lat="$repo/design-system/latex"; dec="$repo/decisions"
if command -v cygpath >/dev/null 2>&1; then lat="$(cygpath -m "$lat")"; dec="$(cygpath -m "$dec")"; fi
export TEXINPUTS="$lat//;$dec//;"
cd "$here"
[ -e BUILD.lock ] && { echo "BUILD.lock present: another build is running"; exit 1; }
touch BUILD.lock; trap 'rm -f BUILD.lock' EXIT
mkdir -p build
for pass in 1 2; do
  if ! xelatex --enable-installer -interaction=nonstopmode -halt-on-error \
       -output-directory=build "$name.tex" < /dev/null > "build/$name.console" 2>&1; then
    echo "FAIL  $name (pass $pass)"; grep -A6 "^!" "build/$name.log" | head -20 || tail -20 "build/$name.console"; exit 1
  fi
done
pages="$(pdfinfo "build/$name.pdf" | awk '/^Pages/{print $2}')"
tbd="$( (grep -o "Unfinished value \[[^]]*\]" "build/$name.log" || true) | sort -u | wc -l)"
over="$(grep -c "^Overfull" "build/$name.log" || true)"
echo "ok    $name.pdf  ${pages} pages | unfinished: $tbd | overfull: $over"
[ -n "$out" ] && cp "build/$name.pdf" "$out" && echo "      -> $out"
exit 0
