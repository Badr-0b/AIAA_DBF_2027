#!/usr/bin/env bash
# Build any dbfdoc document with XeLaTeX (two passes for page references).
#
#   design-system/tools/build.sh path/to/main.tex [output.pdf]
#
# Outputs go to <doc dir>/build/. If [output.pdf] is given, the finished PDF
# is copied there (e.g. the contest-mandated file name).
# --enable-installer lets MiKTeX fetch any missing package without a dialog.
set -euo pipefail

src="$1"
out="${2:-}"
ds="$(cd "$(dirname "$0")/.." && pwd)"           # design-system/
dir="$(cd "$(dirname "$src")" && pwd)"
name="$(basename "$src" .tex)"

texinputs="$ds/latex//"
command -v cygpath >/dev/null 2>&1 && texinputs="$(cygpath -m "$ds/latex")//"
export TEXINPUTS="$texinputs;"

cd "$dir"
mkdir -p build
for pass in 1 2; do
  if ! xelatex --enable-installer -interaction=nonstopmode -halt-on-error \
       -output-directory=build "$name.tex" < /dev/null > "build/$name.console" 2>&1; then
    echo "FAIL  $name (pass $pass)"
    grep -A6 "^!" "build/$name.log" | head -16 || tail -20 "build/$name.console"
    exit 1
  fi
done

pages="$(pdfinfo "build/$name.pdf" | awk '/^Pages/{print $2}')"
tbd="$( (grep -o "Unfinished value \[[^]]*\]" "build/$name.log" || true) | sort -u | wc -l)"
over="$(grep -c "^Overfull" "build/$name.log" || true)"
echo "ok    $name.pdf  ${pages} pages  | unfinished values: $tbd | overfull boxes: $over"

if [ -n "$out" ]; then
  cp "build/$name.pdf" "$out"
  echo "      -> $out"
fi
