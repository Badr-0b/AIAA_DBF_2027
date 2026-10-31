#!/bin/bash
# Stop a case's sweep without losing iterations: ask foamRun for a checkpoint, wait until it is
# written, then end the sweep. Resume later with sweep.sh (Allrun carries on from the checkpoint).
#   wsl -d Ubuntu -- bash /mnt/c/Users/Nitro/Documents/GitHub/AIAA_DBF/cfd/tools/sweep_stop.sh <case>
CASE=${1:?usage: sweep_stop.sh <case>}
RUN=/home/nitro/dbf_cfd/$CASE
[ -d "$RUN" ] || { echo "no run directory $RUN"; exit 1; }
here() {   # pids of the named processes working in the run directory (never this script)
    for p in $(pgrep "$@"); do
        [ "$p" != $$ ] && [ "$(readlink "/proc/$p/cwd")" = "$RUN" ] && echo "$p"
    done
}
newest() { ls -d "$RUN"/processor0/[1-9]* 2>/dev/null | sed 's|.*/||' | sort -g | tail -1; }

if [ -n "$(here -x foamRun)" ]; then
    tag=$(ls "$RUN"/log.foamRun.* 2>/dev/null | sed 's|.*log.foamRun.||' | head -1)
    c0=$(newest)
    echo "foamRun running ($tag); asking for a checkpoint every iteration"
    sed -i "s/^writeInterval .*/writeInterval   1;/" "$RUN/system/controlDict"   # runTimeModifiable
    # wait for a new time directory and for the next iteration to begin (its write is then finished)
    for i in $(seq 600); do
        [ -z "$(here -x foamRun)" ] && break   # it finished by itself meanwhile
        c=$(newest)
        if [ -n "$c" ] && [ "$c" != "$c0" ] && grep -q "^Time = $((c + 1))s\$" "$RUN/log.foamRun.$tag"; then
            break
        fi
        sleep 1
    done
    echo "checkpoint written at iteration $c"
else
    echo "foamRun not running: stopping the sweep where it stands"
fi
# shells first (they would otherwise record the angle as failed), then the solver and watcher
B=/home/nitro/dbf_cfd
pids="$(cat "$B/$CASE.sweep.pid" 2>/dev/null) $(here -x sh) $(here -x bash)"
kill -KILL $pids 2>/dev/null
kill -TERM $(here -x mpirun) $(here -x foamRun) $(here -f converge_watch.py) $(here -x pvbatch) 2>/dev/null
for i in $(seq 30); do
    [ -z "$(here -x foamRun)$(here -x mpirun)" ] && break
    sleep 1
done
kill -KILL $(here -x mpirun) $(here -x foamRun) 2>/dev/null
sed -i "s/^writeInterval .*/writeInterval   100;/" "$RUN/system/controlDict"
rm -f "$B/$CASE.sweep.pid"
echo "=== sweep stopped by sweep_stop.sh $(date '+%F %H:%M') (checkpoint ${c:-none})" >> "$B/$CASE.sweep.out"
echo "stopped; newest checkpoint: $(newest). Resume: Start-Process wsl.exe ... cfd/tools/sweep.sh $CASE <np>"
