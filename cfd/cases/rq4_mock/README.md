# rq4_mock — external aerodynamics of the RQ-4-style mock

Badr's CAD (`assets/3D_Models/RQ4_BadrObtel.stl`, 24 Oct 2026): straight tapered wing, bulged nose, V-tail, and a dorsal through-flow nacelle on a two-plate mount. Steady RANS on a half model with a symmetry plane, using the Langtry–Menter γ-Reθ transition SST model (`kOmegaSSTLM`, OpenFOAM 14).

**All inputs live in `case.toml`.** Values marked PARAMETER are placeholders until the team supplies them.

## Run

```bash
# 1. Windows: STL -> outer skin, reference geometry, case parameters (~2 min)
PYTHONIOENCODING=utf-8 python cfd/tools/prep_geometry.py cfd/cases/rq4_mock
# 2. WSL: mesh once, then one run per angle in case.toml (MESH_ONLY=1 stops after the mesh;
#    WARM=1 starts each angle from the previous one's solution)
wsl -d Ubuntu -- bash /mnt/c/Users/Nitro/Documents/GitHub/AIAA_DBF/cfd/tools/run_case.sh rq4_mock 6
# 3. Copy results back (no mesh, no fields)
wsl -d Ubuntu -- bash /mnt/c/Users/Nitro/Documents/GitHub/AIAA_DBF/cfd/tools/harvest.sh rq4_mock
```

If you change only the angles, speed or turbulence, rerun step 1, then step 2: the mesh in `~/dbf_cfd/rq4_mock` is reused. If you change the scale, the STL or the mesh settings, delete that run directory first.

## What the steps do

| Step | File | Notes |
|---|---|---|
| Geometry | `cfd/tools/prep_geometry.py` → `constant/geometry/rq4_mock.obj`, `geometry_report.txt`, `geometry_preview.png` | The CAD is a ~1 mm hollow shell made of overlapping bodies. A voxel flood fill finds the outside air; faces that never touch it are dropped (93,000 mm² of inner skin and buried roots). The skin is split into `wing`, `fuselage`, `vtail` and `nacelle` patches (rules in `case.toml`) for a per-part force breakdown. |
| Reference | `constant/geometry/reference` | Trapezoidal reference wing fitted to 13 section cuts, extended to the centreline. Half model: `refArea` = S/2, so the coefficients are full-aircraft values. |
| Mesh | `system/blockMeshDict`, `snappyHexMeshDict`, `snappyHexMeshDict.layers`, `meshQualityDict` | Background cell = span/6. Skin at span/768, edges at span/1536, distance and wake refinement. Two snappyHexMesh passes: castellate and snap with the default quality limits, then 20 prism layers from a first cell sized for y+ ≈ 1 (10.5 µm at 26.5 m/s). The layer pass relaxes the determinant and tet checks, which reject such flat prisms on 2.4 mm skin faces, and keeps a pyramid-volume check so no cell inverts. `renumberMesh` follows. |
| Solve | `Allrun`, `0.orig/`, `system/fv*` | Far-field freestream conditions on every outer face. The angle of attack rotates the freestream, so the body and the mesh stay fixed. Second-order schemes, SIMPLEC, relaxation 0.9 (U) / 0.8 (turbulence), after the OpenFOAM T3A transition tutorial. `cfd/tools/converge_watch.py` stops an angle once the 200-iteration means of C_L and C_D stop moving (within the WP-01 tolerance in `report_case.py`) and their spread is within twice that tolerance; 2000 is the cap. α 0 holds a steady ±0.45 % C_L oscillation that does not decay, so the stricter WP-01 spread limit stays a report check (CHECK), not a stop condition. A checkpoint is written every 100 iterations (`purgeWrite 1` keeps one). `Allrun` is resumable: it skips finished angles and carries an interrupted one on from its checkpoint. `cfd/tools/sweep.sh` runs the sweep detached from any terminal; `sweep_status.sh` and `sweep_stop.sh` go with it. |
| Output | `results/alpha±XX.X/` | Force-coefficient histories (total every iteration, per patch every 10th), residuals, y+, logs, `run_summary` (iterations, wall time, warm or cold start) and ParaView images (`cfd/tools/render_aero.py`). `cfd/tools/report_case.py` writes `RESULTS.md`. |

Speed on this laptop (i9-13900H, WSL, 24 Oct): about 8.5 s per iteration for the 2.58M-cell mesh at the 1.82 m span, on 6 processes. The run is limited by memory bandwidth: 6 processes beat 10 (11.0 against 11.7 s on a 2.9M-cell test mesh), and AC power barely helped. Plan up to about 4.7 h for a cold-start angle (2000 iterations) and less for warm starts that settle early.

## Known issue: the fuselage interior is meshed (24 Oct)

The extracted skin leaks into the hollow fuselage, so snappyHexMesh meshes its interior too. ParaView probes at four points inside the fuselage found cells with 0.1–0.3 m/s of flow; the wing interior is correctly empty. The gap is sub-millimetre: 7,500 rays fired from inside all hit skin. It is probably a sliver at a seam where two CAD bodies tessellate the same cross-section differently (the open-edge chains at x = 120 and 450 mm and around the nose).

- **Forces: negligible.** The trapped air is nearly still, the inner side of the skin is closed at uniform pressure (zero net force), and its shear is about 2×10⁻⁴ N against about 2.6 N of drag.
- **Cost:** about 20% extra cells.
- **y+:** the fuselage mean y+ in `RESULTS.md` includes the inner faces, so it reads low.
- **Fix:** seal the seams in `prep_geometry.py` (keep the bulkhead faces, or zip the slivers), then remesh.

## Conventions

- CFD axes: x downstream (nose at −x), y spanwise (the half model is y ≥ 0), z up. The origin is the CAD origin. Angles are body-axis angles from the fuselage datum (the CAD nose–tail axis). The wing sits at +2.48° incidence to it.
- Cm is about `refCofR`, positive nose-up. Until the CG is given it is the MAC quarter chord.
- The nacelle is an open duct, so air flows through it (no fan) unless the team says otherwise.
