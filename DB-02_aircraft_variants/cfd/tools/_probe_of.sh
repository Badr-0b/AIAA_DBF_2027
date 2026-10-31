#!/bin/bash
. /opt/openfoam14/etc/bashrc
grep -rn "decayControl" $FOAM_SRC/MomentumTransportModels 2>/dev/null | head -5
ls $FOAM_SRC/MomentumTransportModels/momentumTransportModels/RAS/ 2>/dev/null | head -40
find $FOAM_SRC/MomentumTransportModels -name "kOmegaSSTLM*" | head
find $FOAM_TUTORIALS -path "*T3A*" -maxdepth 4 | head
find $FOAM_TUTORIALS -iname "*airfoil*" -maxdepth 4 | head
which gmsh; gmsh --version 2>&1 | head -1
nproc; free -m | head -2
