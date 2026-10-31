# S8 early output: payload API and the envelope numbers (v1, 29 Oct 2026)

Code: `W\src\payload\model.py` (import `from payload import model as M` with `W\src` on `sys.path`).
Run Python with `PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8`. Import is side-effect free; the module reads
`REPO\analysis\cushion_study.py` (tables only) and `s5_tow.py` (pure physics), and never calls a `main()`.

## 1. Functions

| Call | Returns |
|---|---|
| `M.container(sensor_kg, g_rating, h_m=1.524, ballast="steel", fins="cruciform", sling_deg=15)` | `dims_m` (outer L, W, H), `mass_kg`, `foam_mm`, `ok_381`, `ring_to_bottom_m` {L, W, H, worst}, `volume_l`, `sensor` (geometry), `notes`. Scans sensor length 0.17-0.32 m and returns the lightest container whose three axes all stay under 381 mm. |
| `M.sensor(mass_kg, g_rating, ballast, length_m, fins)` | diameter, length, envelope, ballast kg and litres, CG, Barrowman CP, pitch frequency, CdA |
| `M.simulator(sensor_max_kg, container_dict)` | dims, mass (container + declared sensor), ballast kg, trim step |
| `M.declaration_range(container_dict, recut=False)` | (m_lo, m_hi, rows): declared masses one built container serves |
| `M.dr(sensor_kg, drive="auto")` | `mass_kg`, `deploy_s`, `stow_s`, `p_fail`, `drive`, `line_d_m` (drives: `37d_50 37d_70 37d_131 2x37d_131 savox_2290 neo550 neo550_g15`) |
| `M.bay(n_units, unit_dims, sensor_dims, reel, abreast=1)` | `volume_m3`, `length_m`, `width_m`, `height_m`, `cg_note` |
| `M.payload_for_adapter(sensor_kg_max, g_rating=100, drive="auto", ballast=..., h_m=1.524)` | the adapter's `payload` dict (below) |
| `M.tow_check()`, `M.line_shape()`, `M.dart_stability()` | tension, hang angle, line shape, clearance, Barrowman |
| `M.m3_lap_table()` | laps in 300 s against lap time and stow time, and the stow gain that buys one lap |

## 2. Adapter payload

```python
from payload import model as M
pl = M.payload_for_adapter(6.0, 150.0, drive="savox_2290", ballast="tungsten")
meta = pl.pop("_meta")                          # container dims, ok_381, stow at max
d = A.REF_D01.with_(s=0.9, unit=6.0 + meta["container_kg_at_max"], payload=pl)
```

Keys: `container_kg` (callable of sensor kg), `container_range_kg` (0.75-1.25 of the central value), `dr` {`mass_kg`,
`stow_s` (callable(m_array, P): the drum built for the declared maximum stowing the ballast actually flown)}, `extra_kg` 0,
`f_m2` 0 (bay drag is S3/S7's). `unit` = declared sensor + `meta["container_kg_at_max"]`.

## 3. Envelope numbers other streams can use now (150 g sensor, tungsten ballast, 15 deg sling, 1.524 m, PE 2 pcf; computed)

| Declared sensor | Container L x W x H (mm) | Container mass | Foam | Worst ring-to-bottom | < 381 mm |
|---|---|---|---|---|---|
| 3.0 kg | 288 x 228 x 228 | 0.63 kg | 41 mm | 350 mm | yes |
| 4.4 kg | 298 x 257 x 257 | 0.81 kg | 41 mm | 366 mm | yes |
| 6.0 kg | 298 x 288 x 288 | 1.00 kg | 41 mm | 372 mm | yes |
| 8.0 kg | 288 x 303 x 303 | 1.18 kg | 41 mm | 378 mm | yes (3 mm margin) |
| 10.0 kg | 308 x 305 x 305 | 1.37 kg | 41 mm | 385 mm | no at 15 deg; see the memo for 10 deg |

- **A 100 g-rated sensor needs 62 mm of foam and breaks 381 mm for every mass from 3 to 10 kg** (385-435 mm at 15 deg). The sensor must be built for 150 g.
- The sensor is 170-210 mm long and 50-90 mm in diameter with tungsten ballast (fins add 40-100 mm to the cross-section).
- Grades: foam minima verified (MIL-HDBK-304B, read 16 Oct), the curve shape between minima is read by eye (E), pad bearing area, shell mass, carrier mass and sensor base mass are estimates.
- Tow eye above the CG, not at the nose: a nose tow hangs the dart nose-up at 60-80 deg (memo section 4).
- M3 stow time grows with the sensor: 14 s (3.4 kg) to 30 s (10 kg) on the Savox drum; 3 s on a geared NEO 550 (0.65-0.78 kg).

## 4. One physical container for a declared range (added 29 Oct, after the orchestrator review)

`M.design_for_range(m_lo, m_hi, g_rating=150, recut=True, sling_deg=15)` builds ONE container for the top of the range;
`["servable"]` lists the declared masses (0.25 kg grid) it serves within the g rating, `["mass_for"](m)` is its mass for a declaration m
(container mass counts in M2 W). Study driver: `src/payload/h1_study.py` (`hw_design` builds the adapter Design).

- Pads re-cut at tech: 3-6 kg container 298 x 288 x 288 mm, 1.00 kg (0.86 kg at 3 kg); 3-8 kg 288 x 303 x 303 mm, 1.18 kg; 4.4-10 kg needs a 10 deg sling (375 mm).
- As-built pads need 48-53 mm foam and break 381 mm (388-404 mm).
- H1 (adapter, 120 draws, S 0.9): declare at tech planning at rho 1.04 -> 6.735 ([3,6]) and 6.764 ([3,8]) against 6.34 / 6.30 frozen and 6.333 REF-D01.
  Heavy ranges ([4.4,10]) fall to 5.79 (M2 must carry the declared unit). Known bias: the adapter picks n_sim and M3 ballast per draw with full knowledge.
