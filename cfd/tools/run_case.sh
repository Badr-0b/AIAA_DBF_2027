#!/bin/bash
# Copy a case's setup from the repo to the WSL run directory and run its Allrun there.
#   wsl -d Ubuntu -- bash /mnt/c/Users/Nitro/Documents/GitHub/AIAA_DBF/cfd/tools/run_case.sh <case> [np]
# OpenFOAM writes thousands of files; on /mnt/c (the Windows drive) that is very slow, so runs
# happen in /home/nitro/dbf_cfd/<case> (ext4) and only results come back (harvest.sh).
set -eo pipefail   # not -u: OpenFOAM etc/bashrc reads unset variables
CASE=$1
NP=${2:-8}
SRC=/mnt/c/Users/Nitro/Documents/GitHub/AIAA_DBF/cfd/cases/$CASE
RUN=/home/nitro/dbf_cfd/$CASE
. /opt/openfoam14/etc/bashrc
[ -d "$SRC" ] || { echo "no case $SRC"; exit 1; }
mkdir -p "$RUN"
# setup only: never copy harvested results or logs back over a run
rsync -a --delete --exclude postProcessing --exclude 'log.*' --exclude '*.png' --exclude RESULTS.md "$SRC/" "$RUN/"
cd "$RUN"
export NP
[ -x ./Allrun ] || chmod +x ./Allrun
./Allrun
echo "done: $RUN   next: cfd/tools/harvest.sh $CASE"
