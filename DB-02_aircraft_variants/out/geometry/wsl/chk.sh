which gmsh; gmsh --version 2>&1 | head -2
python3 -c "import gmsh; print('gmsh py', gmsh.__version__)" 2>&1
python3 -c "import numpy; print('np', numpy.__version__)" 2>&1
python3 --version
ls /usr/lib/python3/dist-packages | grep -i gmsh
dpkg -l | grep -i -E "gmsh|occt|opencascade" | head
free -m