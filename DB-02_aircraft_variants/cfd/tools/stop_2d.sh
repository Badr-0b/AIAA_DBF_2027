#!/bin/bash
# Stop every 2-D validation run (run directories /home/nitro/dbf_cfd/v2d_*): the queue shell first,
# then the solvers. Results already written stay in place; harvest_2d.sh copies them back.
#   wsl -d Ubuntu -- bash .../DB-02_aircraft_variants/cfd/tools/stop_2d.sh
B=/home/nitro/dbf_cfd
for p in $(pgrep -f "run_2d_queue.sh"); do [ "$p" != $$ ] && kill -KILL "$p" 2>/dev/null; done
n=0
for p in $(pgrep -x foamRun) $(pgrep -x simpleFoam); do
    case "$(readlink "/proc/$p/cwd")" in
        "$B"/v2d_*) kill -TERM "$p" 2>/dev/null && n=$((n + 1)) ;;
    esac
done
echo "stopped $n 2-D solver process(es)"
