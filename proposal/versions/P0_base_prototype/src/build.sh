#!/usr/bin/env bash
# Build the proposal and run the contest compliance checks (rules Sec. 5.1).
#
#   ./build.sh
#
# Produces
#   build/main.pdf    DRAFT: writer notes visible (for editing and review)
#   2027DBF_American_University_of_the_Middle_East_PROPOSAL.pdf
#                     SHIPPING build (notes removed): the file to submit,
#                     and the one every check below is run against.
set -uo pipefail
cd "$(dirname "$0")"
DS=../design-system
OUT="2027DBF_American_University_of_the_Middle_East_PROPOSAL.pdf"

echo "---- charts ----"
python make_charts.py || exit 1        # Gantt + org chart from data/*.toml

echo "---- analysis ----"
python ../analysis/s7_export.py || exit 1   # data/analysis.tex from analysis/ (Scripts 1-2)

echo "---- build ----"
$DS/tools/build.sh main.tex || exit 1
$DS/tools/build.sh final.tex "$OUT" || exit 1

echo "---- compliance (shipping build) ----"
fails=0
check() { if [ "$1" = ok ]; then echo "PASS  $2"; else echo "FAIL  $2"; fails=$((fails+1)); fi; }

pages=$(pdfinfo "$OUT" | awk '/^Pages/{print $2}')
size=$(pdfinfo "$OUT" | awk -F': *' '/^Page size/{print $2}')
bytes=$(wc -c < "$OUT")
bad=$(pdffonts "$OUT" | awk 'NR>2{print $1}' | sed 's/^[A-Z]*+//' | sort -u | grep -v -E "^Geist|^IBMPlexMath" | tr '\n' ' ')
tbd=$( (grep -o "Unfinished value \[[^]]*\]" build/final.log || true) | sort -u | wc -l)

[ "$pages" -eq 6 ] && r=ok || r=no;              check $r "page count $pages (limit 6, over = rejected; target exactly 6)"
case "$size" in 612\ x\ 792*) r=ok;; *) r=no;; esac; check $r "page size $size (US Letter required)"
[ "$bytes" -lt 20000000 ] && r=ok || r=no;       check $r "file size $((bytes/1024)) KB (20 MB recommended max)"
[ -z "$bad" ] && r=ok || r=no;                   check $r "fonts: house fonts only${bad:+ (unexpected: $bad)}"
python $DS/tools/check_order.py build/final.aux || fails=$((fails+1))
an=$(python ../analysis/check.py) && r=ok || r=no; check $r "${an%%$'\n'*} (numbers come from tested code)"
[ "$tbd" -eq 0 ] && r=ok || r=no;                check $r "unfinished values and placeholder prose: $tbd distinct"

echo "----"
if [ "$fails" -eq 0 ]; then echo "READY TO SUBMIT: $OUT"; else echo "$fails check(s) failing: NOT ready to submit"; fi
