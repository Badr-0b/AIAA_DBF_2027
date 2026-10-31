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

export PYTHONDONTWRITEBYTECODE=1
echo "---- charts ----"
python make_charts.py || exit 1        # Gantt + org chart from data/*.toml

echo "---- numbers and figures (P1) ----"
# p1_nominal.py and p1_sensitivity.py (about 4 min) are re-run only when DB-02 results change:
#   python tools/p1_nominal.py && python tools/p1_sensitivity.py && python tools/p1_payload.py
python tools/p1_data.py || exit 1      # data/p1.tex from DB-02 results + data/p1_*.json
python tools/p1_figures.py > /dev/null 2>&1 || { echo "FAIL  p1_figures"; exit 1; }

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
(cd .. && python -m unittest discover -s DB-02_aircraft_variants/tests -p "test_v_*.py" > proposal/build/db02_tests.txt 2>&1) && r=ok || r=no
check $r "DB-02 test suite: $(tail -1 build/db02_tests.txt) (numbers come from tested code)"
[ "$tbd" -eq 0 ] && r=ok || r=no;                check $r "unfinished values and placeholder prose: $tbd distinct"

echo "----"
if [ "$fails" -eq 0 ]; then echo "READY TO SUBMIT: $OUT"; else echo "$fails check(s) failing: NOT ready to submit"; fi
