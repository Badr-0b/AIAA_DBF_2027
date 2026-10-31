#!/bin/bash
# Where a case's sweep is: running or not, current angle and iteration, speed, time left, results so far.
#   wsl -d Ubuntu -- bash /mnt/c/Users/Nitro/Documents/GitHub/AIAA_DBF/cfd/tools/sweep_status.sh <case>
CASE=${1:?usage: sweep_status.sh <case>}
B=/home/nitro/dbf_cfd
RUN=$B/$CASE
cd "$RUN" 2>/dev/null || { echo "no run directory $RUN"; exit 1; }
echo "now $(date '+%F %H:%M')"
if ! flock -n "$B/$CASE.lock" true 2>/dev/null; then
    echo "sweep: RUNNING (pid $(cat "$B/$CASE.sweep.pid" 2>/dev/null))"
elif pgrep -x foamRun > /dev/null; then
    echo "sweep: foamRun is running without the sweep lock (started some other way)"
else
    echo "sweep: not running"
fi
echo "--- log ($B/$CASE.sweep.out, last lines)"
tail -4 "$B/$CASE.sweep.out" 2>/dev/null

NMAX=$(awk '$1 == "endTime" { sub(/;/, "", $2); print $2 }' system/controlDict)
for s in log.start.*; do
    [ -e "$s" ] || continue
    tag=${s#log.start.}
    L=log.foamRun.$tag
    echo "--- in progress: $tag ($(head -1 "$s"); $(sed -n '2,$p' "$s" | tail -1))"
    [ -f "$L" ] || { echo "setting up (no solver log yet)"; continue; }
    # per-iteration times; the solver clock restarts on resume, so a backwards step is skipped
    awk -v nmax="$NMAX" '/^Time = / { t = $3; sub(/s$/, "", t) }
        /^ExecutionTime/ { if (p != "" && $3 > p) d[++k] = $3 - p; p = $3 }
        END { m = (k < 50) ? k : 50; s = 0; for (i = k - m + 1; i <= k; i++) s += d[i]; r = m ? s / m : 0;
              printf "iteration %d of at most %d, %.1f s/iteration lately\n", t, nmax, r;
              if (r > 0) printf "to the cap: %.1f h; the watcher can stop it earlier (see below)\n", (nmax - t) * r / 3600 }' "$L"
    echo "checkpoint: $(ls -d processor0/[1-9]* 2>/dev/null | sed 's|.*/||' | sort -g | tail -1)"
    echo "watcher: $(tail -1 "log.converge.$tag" 2>/dev/null)"
done
echo "--- finished angles"
for r in results/alpha*/run_summary; do
    [ -e "$r" ] || { echo "none yet"; break; }
    d=${r%/run_summary}
    n=$(ls "$d/images" 2>/dev/null | wc -l)
    echo "${d#results/}: $(cat "$r"); $n images"
done
echo "--- resources"
free -m | awk 'NR == 2 { printf "WSL memory: %d MB used, %d MB available\n", $3, $7 }'
df -h /mnt/c | awk 'NR == 2 { print "C: free " $4 }'
df -h /home | awk 'NR == 2 { print "WSL disk free " $4 }'
