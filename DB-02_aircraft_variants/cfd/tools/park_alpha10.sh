#!/bin/bash
# Park the interrupted alpha 10 (checkpoint 320) so a sweep of other angles does not consume it.
#   wsl -d Ubuntu -- bash .../DB-02_aircraft_variants/cfd/tools/park_alpha10.sh park|restore
# park:    copy processor*/320, postProcessing/, log.*.alpha+10.0 and log.start.alpha+10.0 to
#          /home/nitro/dbf_cfd/rq4_mock_alpha10_park/, then remove the log.start marker and the
#          in-progress postProcessing from the run directory (Allrun would delete them anyway).
#          processor*/320 stays in place: the next angle warm-starts from it.
# restore: put them back (only when no later checkpoint exists), so sweep.sh with ALPHAS="10"
#          resumes alpha 10 at iteration 321.
RUN=/home/nitro/dbf_cfd/rq4_mock
P=/home/nitro/dbf_cfd/rq4_mock_alpha10_park
T=320
cd "$RUN" || exit 1
case "$1" in
park)
    [ -d "$P" ] && { echo "already parked in $P"; ls "$P"; exit 0; }
    for d in processor*; do
        [ -f "$d/$T/U" ] || { echo "no $d/$T: nothing to park"; exit 1; }
    done
    mkdir -p "$P"
    for d in processor*; do mkdir -p "$P/$d" && cp -a "$d/$T" "$P/$d/"; done
    cp -a postProcessing "$P/" 2>/dev/null
    cp -a log.*.alpha+10.0 "$P/" 2>/dev/null
    cp -a system/controlDict "$P/controlDict.at_park"
    n0=$(find "$RUN"/processor*/$T -type f | wc -l); n1=$(find "$P"/processor*/$T -type f | wc -l)
    [ "$n0" = "$n1" ] || { echo "copy incomplete ($n0 vs $n1 files): not removing anything"; exit 1; }
    rm -rf postProcessing log.start.alpha+10.0
    mkdir -p results_parked && mv log.*.alpha+10.0 results_parked/ 2>/dev/null
    echo "parked alpha 10 checkpoint $T ($n1 files, $(du -sh "$P" | cut -f1)) in $P"
    ;;
restore)
    [ -d "$P" ] || { echo "nothing parked"; exit 1; }
    ls -d processor0/[1-9]* 2>/dev/null | grep -q . && { echo "run directory holds time directories: $(ls -d processor0/[1-9]*); clear them first"; exit 1; }
    for d in "$P"/processor*; do cp -a "$d/$T" "$RUN/${d##*/}/"; done
    rm -rf postProcessing && cp -a "$P/postProcessing" .
    cp -a "$P"/log.*.alpha+10.0 .
    rm -rf results_parked
    echo "restored alpha 10 at checkpoint $T; resume with sweep.sh and ALPHAS=10"
    ;;
*) echo "usage: park_alpha10.sh park|restore"; exit 1 ;;
esac
