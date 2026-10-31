#!/bin/bash
# Battery guard for the DB-02 CFD runs, inside WSL (reads /sys/class/power_supply, which WSL2 mirrors
# from Windows). Bash replacement for battery_guard.ps1, so no PowerShell execution-policy change is needed.
#   PowerShell: Start-Process wsl.exe -WindowStyle Hidden -ArgumentList '-d','Ubuntu','--','bash','/mnt/c/Users/Nitro/Documents/GitHub/AIAA_DBF/DB-02_aircraft_variants/cfd/tools/battery_guard.sh'
# Every 30 s: if the battery is at or below THRESH % (default 10) and discharging, it checkpoints and
# stops every running sweep (sweep_stop.sh <case> for each held lock in /home/nitro/dbf_cfd), harvests
# it, and stops the 2-D validation queue (stop_2d.sh). It never terminates WSL and never kills other
# processes (other agents share this PC). It exits once no sweep and no 2-D run has been seen for 2 min.
# Log: DB-02_aircraft_variants/cfd/battery_guard.log.  DRY=1: log one reading and the planned actions, exit.
T=/mnt/c/Users/Nitro/Documents/GitHub/AIAA_DBF/DB-02_aircraft_variants/cfd/tools
LOG=/mnt/c/Users/Nitro/Documents/GitHub/AIAA_DBF/DB-02_aircraft_variants/cfd/battery_guard.log
B=/home/nitro/dbf_cfd
TH=${THRESH:-10}
exec 8> "$B/.battery_guard.lock"
flock -n 8 || { echo "a guard is already running"; exit 1; }
say() { echo "$(date '+%F %T')  $*" >> "$LOG"; }
running_cases() {
    for l in "$B"/*.lock; do
        c=${l##*/}; c=${c%.lock}
        [ -f "$l" ] && ! flock -n "$l" true 2>/dev/null && echo "$c"
    done
}
two_d() { pgrep -f run_2d_queue.sh > /dev/null; }
say "guard started (pid $$), threshold $TH %"
gone=0
while true; do
    cap=$(cat /sys/class/power_supply/BAT1/capacity 2>/dev/null)
    st=$(cat /sys/class/power_supply/BAT1/status 2>/dev/null)
    ac=$(cat /sys/class/power_supply/AC1/online 2>/dev/null)
    cases=$(running_cases | tr '\n' ' ')
    if [ "${DRY:-0}" = 1 ]; then
        say "DRY RUN: battery $cap % ($st, AC $ac); sweeps: ${cases:-none}; 2-D queue: $(two_d && echo yes || echo no)"
        exit 0
    fi
    if [ -n "$cap" ] && [ "$cap" -le "$TH" ] && [ "$st" = "Discharging" ]; then
        say "battery $cap % ($st, AC $ac): stopping CFD"
        for c in $cases; do
            bash "$T/sweep_stop.sh" "$c" 2>&1 | while read -r x; do say "  stop $c: $x"; done
            bash "$T/harvest.sh" "$c" 2>&1 | tail -1 | while read -r x; do say "  harvest $c: $x"; done
        done
        bash "$T/stop_2d.sh" 2>&1 | while read -r x; do say "  2-D: $x"; done
        say "done; resume the sweeps with sweep.sh when on AC"
        exit 0
    fi
    if [ -n "$cases" ] || two_d; then gone=0; else gone=$((gone + 1)); fi
    [ $gone -ge 4 ] && { say "no CFD running for 2 min; guard exiting (battery $cap %, $st)"; exit 0; }
    sleep 30
done
