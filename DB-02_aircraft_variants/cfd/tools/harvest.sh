#!/bin/bash
# Copy a finished case's small, valuable files from the WSL run directory into the repo.
#   wsl -d Ubuntu -- bash /mnt/c/Users/Nitro/Documents/GitHub/AIAA_DBF/DB-02_aircraft_variants/cfd/tools/harvest.sh <case>
# Kept: postProcessing/, results/, log.*, *.png; and system/, constant/ (no polyMesh), 0/, 0.orig/, Allrun
# only when the repo case has none yet (a case set up in the repo keeps its own setup: the run
# edits controlDict, alphaState and decomposeParDict as it goes).
# Not kept: the mesh, time directories, processor*/ (big, regenerable from the setup).
set -euo pipefail
CASE=$1
RUN=/home/nitro/dbf_cfd/$CASE
DST=/mnt/c/Users/Nitro/Documents/GitHub/AIAA_DBF/DB-02_aircraft_variants/cfd/$CASE
[ -d "$RUN" ] || { echo "no run directory $RUN"; exit 1; }
mkdir -p "$DST"
cd "$RUN"
for d in system constant 0 0.orig; do
  [ -d "$d" ] && [ ! -d "$DST/$d" ] && rsync -a --exclude polyMesh --exclude 'triSurface/*.eMesh' "$d" "$DST/"
done
for d in postProcessing results; do
  [ -d "$d" ] && rsync -a "$d" "$DST/"
done
for f in Allrun Allclean; do
  [ -e "$f" ] && [ ! -e "$DST/$f" ] && cp -p "$f" "$DST/"
done
for f in log.* *.png; do
  [ -e "$f" ] && cp -p "$f" "$DST/"
done
du -sh "$DST"
echo "harvested $CASE -> cfd/cases/$CASE"
