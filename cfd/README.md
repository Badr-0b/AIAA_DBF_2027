# CFD (OpenFOAM 14 in WSL)

Cases are set up in the repo, run in WSL's own filesystem, and only their results come back.

| Path | What |
|---|---|
| `cases/<case>/` | One case: setup (`system/`, `constant/` without the mesh, `0/`), `Allrun`, and after a run the harvested `postProcessing/`, `log.*`, images and `RESULTS.md` |
| `tools/run_case.sh` | Copies a case to `/home/nitro/dbf_cfd/<case>` (fast ext4 disk) and runs its `Allrun` |
| `tools/harvest.sh` | Copies the results back into `cases/<case>/`; meshes and time steps stay behind |
| `_install_record/` | **Gitignored, this PC only:** what the local install added and how to remove it (`LOCAL_OPENFOAM_CLEANUP.md`) |

## Run a case
```bash
wsl -d Ubuntu -- bash /mnt/c/Users/Nitro/Documents/GitHub/AIAA_DBF/cfd/tools/run_case.sh <case> 8
wsl -d Ubuntu -- bash /mnt/c/Users/Nitro/Documents/GitHub/AIAA_DBF/cfd/tools/harvest.sh <case>
```

## Look at a case in ParaView
ParaView runs in WSL and opens a window on the Windows desktop (WSLg):
```bash
wsl -d Ubuntu -- bash -lc "cd ~/dbf_cfd/<case> && paraFoam"
```
`paraFoam` opens the case. In the Pipeline Browser, tick the fields (`U`, `p`), press Apply, and pick the last time step. A run directory exists only until the case is cleaned up; the harvested copy has no mesh, so view a case before cleaning it.

## Rules for every case (from WP-01)
Report the solver and version, turbulence model, y+ (mean and maximum), cell count, residual drop (at least 3 orders), a flat force history over the last 200 iterations, and the reference area, length, density, viscosity and speed. Validate on a case with published measurements before the design case (for example NACA 0012 against the NASA TMR data, or Roshko's cutout, NACA TN 3488, before the sensor-bay slot).
