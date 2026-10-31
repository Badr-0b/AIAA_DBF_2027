#!/bin/bash
# Run a case's angle sweep detached from Claude Code and from any terminal; run it again to resume.
#   PowerShell (starts it hidden; closing Claude Code or the terminal no longer stops it):
#     Start-Process wsl.exe -WindowStyle Hidden -ArgumentList '-d','Ubuntu','--','bash','/mnt/c/Users/Nitro/Documents/GitHub/AIAA_DBF/DB-02_aircraft_variants/cfd/tools/sweep.sh','rq4_mock','6'
#   Progress: wsl -d Ubuntu -- bash /mnt/c/Users/Nitro/Documents/GitHub/AIAA_DBF/DB-02_aircraft_variants/cfd/tools/sweep_status.sh rq4_mock
#   Stop (checkpoint first, nothing lost): ... cfd/tools/sweep_stop.sh rq4_mock
# It is run_case.sh with WARM=1 HARVEST=1 (each finished angle is copied into the repo at once);
# Allrun skips finished angles and resumes an interrupted one from its last checkpoint.
# Log: ~/dbf_cfd/<case>.sweep.out. One sweep per case at a time (lock ~/dbf_cfd/<case>.lock).
# Other environment variables (ALPHAS, NITER, CKPT, CONV_*) pass through to Allrun.
CASE=${1:?usage: sweep.sh <case> [np]}
NP=${2:-6}
B=/home/nitro/dbf_cfd
mkdir -p "$B"
exec 9> "$B/$CASE.lock"
flock -n 9 || { echo "a sweep of $CASE is already running (see $B/$CASE.sweep.out)"; exit 1; }
OUT=$B/$CASE.sweep.out
echo "=== sweep start $(date '+%F %H:%M'), np $NP, pid $$" >> "$OUT"
echo $$ > "$B/$CASE.sweep.pid"
WARM=${WARM:-1} HARVEST=${HARVEST:-1} bash /mnt/c/Users/Nitro/Documents/GitHub/AIAA_DBF/DB-02_aircraft_variants/cfd/tools/run_case.sh \
    "$CASE" "$NP" >> "$OUT" 2>&1
echo "=== sweep exit $? $(date '+%F %H:%M')" >> "$OUT"
rm -f "$B/$CASE.sweep.pid"
