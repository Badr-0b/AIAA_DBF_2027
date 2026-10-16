#!/bin/bash
# Copy a finished case's small, valuable files from the WSL run directory into the repo.
#   wsl -d Ubuntu -- bash /mnt/c/Users/Nitro/Documents/GitHub/AIAA_DBF/cfd/tools/harvest.sh <case>
# Kept: system/, constant/ (no polyMesh), 0/ or 0.orig/, postProcessing/, log.*, *.png, Allrun.
# Not kept: the mesh, time directories, processor*/ (big, regenerable from the setup).
set -euo pipefail
CASE=$1
RUN=/home/nitro/dbf_cfd/$CASE
DST=/mnt/c/Users/Nitro/Documents/GitHub/AIAA_DBF/cfd/cases/$CASE
[ -d "$RUN" ] || { echo "no run directory $RUN"; exit 1; }
mkdir -p "$DST"
cd "$RUN"
for d in system constant 0 0.orig postProcessing; do
  [ -d "$d" ] && rsync -a --exclude polyMesh --exclude 'triSurface/*.eMesh' "$d" "$DST/"
done
for f in Allrun Allclean log.* *.png; do
  [ -e "$f" ] && cp -p "$f" "$DST/"
done
du -sh "$DST"
echo "harvested $CASE -> cfd/cases/$CASE"
