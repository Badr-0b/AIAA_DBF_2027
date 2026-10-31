# S8 payload system memo (29 Oct 2026)

**Status:** core API stable (`src/payload/model.py`, 21 tests pass), H1 tested with one physical container, results in `out/payload/results.json` (S8-R01..R52). Dynamic cable model not built (optional).

| ID | Quantity | Value | Range | Grade | Source |
|---|---|---|---|---|---|
| S8-R01 | DB-01 100 g container (202x202x392) worst ring-to-bottom, 15 deg sling | 449 mm | 392-494 mm | computed | S1 geometry, L538-542; limit 381 mm |
| S8-R02-R06 | Container mass, 150 g sensor, tungsten, 3 / 4.4 / 6 / 8 / 10 kg | 0.63 / 0.81 / 1.00 / 1.18 / 1.37 kg | -25 %..+25 % | estimate | MIL-HDBK-304B minima (V); shell, pads (E) |
| S8-R07 | 100 g-rated sensor, worst ring-to-bottom, 3-10 kg | 385-435 mm | all above 381 | computed | model.container |
| S8-R08 | Declared range one container serves, pads re-cut at tech | 3-8 kg (298/288/288 mm class) | 3-10 with 10 deg sling | estimate | design_for_range |
| S8-R09 | Same, pads as built | 3-8 kg but 53 mm foam, 404 mm: fails 381 | | estimate | design_for_range |
| S8-R11-13 | 6 kg sensor body diameter: tungsten / lead / steel | 70 / 86 / 103 mm | L 200 mm | estimate | densities V/E |
| S8-R14-15 | Static margin (tow eye at CG) / nose-tow hang angle, 6 kg | 0.27 cal / 77 deg nose-up | 50-82 | computed | Barrowman |
| S8-R16-18 | Stow 3.4 kg (37D 70:1) / 10 kg Savox / 10 kg geared NEO | 11.9 s / 30.3 s / 3.3 s | | computed, estimate | dr_trade + s5_tow |
| S8-R19-21 | Line tension 10 kg at n 4 / hang 6 kg n 1 / light 1 kg trail | 392 N / 3.1 deg / 0.56 m aft | | computed | s5_tow, line_shape |
| S8-R22-23 | M3 laps at 39.1 s lap, 12 s stow / lap for 8 laps | 7 / 35.0 s | | computed | rules arithmetic |
| S8-R27-R52 | H1 tech vs frozen totals (table below) | 6.74 vs 6.34 | | computed | adapter, 120 draws |

**Findings that matter for the aircraft choice**
1. **H1 holds, with a limit.** One container for declared masses 3-6 kg or 3-8 kg, with the declaration chosen at tech and planned at a hot-day density (1.04), scores 6.735 and 6.764 at S 0.9 m2 against 6.340 and 6.297 for freezing one mass on the same hardware and 6.333 for REF-D01 (+0.40 to +0.43). At S 1.0 the gain is 6.697-6.702 against REF-D01b 6.070; at S 1.2 it is 6.31-6.34 (frozen 5.83-5.85).
2. **The gain is GM.** GM rises from 0.99-1.08 to 1.40 (mean declared 5.5-6.1 kg); M2 stays at 1.44-1.48 because one 5-6 kg unit replaces the 4 kg unit plus a simulator (mean n_sim 0.00-0.02); M3 stays at 2.89; P(M2 feasible) stays 0.975 and P10 rises from 5.98 to 6.1-6.2.
3. **Heavier is worse.** Range 4.4-10 kg drops to 5.79-5.99 and P(M2) to 0.73-0.82: M2 must carry the declared unit (L524-525), so a heavy declaration fails on hot draws. The practical top of the range is 6-8 kg.
4. **Planning density decides it.** Choosing at the mean density 1.075 gives 6.56 ([3,6]) and 6.42 ([3,8]) with P10 as low as 2.5; at 1.04 the policy reaches 83-93 % of the perfect-foresight value.
5. **The sensor must be rated 150 g, short (170-210 mm) and dense.** A 100 g rating needs 62 mm of foam and breaks 381 mm at every mass from 3 to 10 kg. At 150 g the foam is 41 mm and the container 0.63-1.37 kg, 336-375 mm worst ring-to-bottom at a 10-15 deg sling.
6. **Pads must be re-cut at tech.** With as-built pads the foam must carry a 1.09-1.19 margin, which grows the container to 388-409 mm and fails the 381 mm envelope; with re-cut pads one 150 g container serves the whole range at 41 mm.
7. **Tow eye above the CG, not at the nose.** A nose tow hangs a 6 kg dart nose-up at about 77 deg; the line hangs within 3.1 deg of vertical, and a heavy sensor sits 0.03-0.1 m aft of the exit, so tail and prop clearance is not the limit.
8. **Stow time grows with the sensor** (Savox drum 14 s at 3.4 kg to 30 s at 10 kg) and costs a lap at 39.1 s laps beyond 18.3 s; a geared NEO 550 drive stows in 3 s for 0.65-0.78 kg.

**What would change them:** TC-02 foam drop tests (curve shape is read by eye, bearing area assumed (p+t)(q+t)); a real rate for sensor mass growth of structure; the Q&A on rigging (rank 4); the adapter's n_sim and M3 ballast peeking.
**Open issues:** (a) bias, see section 6; (b) dynamic cable and swing in 72 deg banked turns not modelled; (c) fin ring option not computed; (d) grades of lead and steel density are textbook values.

## 1. Method and API

`src/payload/model.py` imports `analysis/cushion_study.py` tables and `analysis/s5_tow.py` physics read-only; no module is run as a script and nothing is written outside W.

- **Cushion.** Minimum peak g per thickness is read from MIL-HDBK-304B (verified 16 Oct). Above 48 in the thicker of the "measured p" and "p = 1" extrapolations is used (cushion_study's rule). Off-optimum stress uses a normalised curve g/g_min versus stress/stress_opt read on Graphs 10.42 and 10.48 (curves 3 and 4): 1.80, 1.45, 1.15, 1.04, 1.00, 1.05, 1.15, 1.50, 1.90 at 0.15, 0.25, 0.4, 0.6, 1, 1.5, 2, 3, 4 (estimate, +-10 %).
- **Container.** Foam on six faces, uniform thickness t; each face's pad must have area (m + carrier) g / sigma_opt and bears over (p + t)(q + t); the inner cross-section is grown until every axis has the area. Outer = inner + 2t + 2 x 3 mm. Shell 1.0 kg/m2, carrier 3 % of sensor mass (min 0.08 kg), hardware 0.03 kg. Sensor length is scanned 0.17-0.32 m and the lightest container with worst ring-to-bottom < 381 mm is returned.
- **Ring-to-bottom (L538-542).** Each of the three axes can be the hang axis (the die picks O or E faces, L1002), so L, W and H are checked: axis length + half-diagonal of the opposite face x tan(sling) + 19.05 mm ring. A rigid yoke is Q&A rank 4.
- **Declaration range.** `design_for_range(lo, hi, recut)` builds for `hi`; `serve()` gives the peak g for any other mass on the same foam; `recut_mass()` the container mass when pads are cut to the declared mass.

## 2. Containers by declared mass (150 g, tungsten, 15 deg sling, 60 in; full table in tables.json)

| Sensor | Outer L x W x H (mm) | Mass | Foam | Worst rtb | Sensor L x diameter x fin span (mm) |
|---|---|---|---|---|---|
| 3.0 kg | 288 x 228 x 228 | 0.63 kg | 41 mm | 336 mm (10 deg) / 350 | 190 x 50 x 130 |
| 4.4 kg | 298 x 257 x 257 | 0.81 kg | 41 mm | 366 mm | 200 x 59 x 159 |
| 6.0 kg | 298 x 288 x 288 | 1.00 kg | 41 mm | 372 mm | 200 x 70 x 190 |
| 8.0 kg | 288 x 303 x 303 | 1.18 kg | 41 mm | 378 mm | 190 x 85 x 205 |
| 10.0 kg | 308 x 305 x 305 | 1.37 kg | 41 mm | 385 mm (375 at 10 deg) | 210 x 87 x 207 |

Container mass counts in M2's W: the 1.0 kg container of a 6 kg unit is part of the W the aircraft carries. A 100 g rating gives 0.82-1.59 kg and 366-412 mm at 10 deg, 385-435 mm at 15 deg.

## 3. Ballast materials (sizing the sensor)

| Material | Density (kg/m3) | Grade | Price | 6 kg sensor diameter |
|---|---|---|---|---|
| Tungsten heavy alloy (ASTM B777 class 1, design value) | 17,000 (class 1 16,850-17,250; class 3 17,750-18,350) | verified (GS Alloy datasheet, 29 Oct) | US$1,100-1,800 per kg retail (tungsten.com 1 lb bags, reseller); bulk US$58-65/kg unverified | 70 mm |
| Tungsten putty | 10,000 minimum | reseller | US$220-390 per kg (US$6.25-10.95 per 28 g) | trim only |
| Lead | 11,340 | estimate (textbook) | US$2-2.6 per kg ingot (commodity, reseller) | 86 mm; toxic, encapsulate |
| Steel | 7,850 | estimate (textbook) | price not sourced | 103 mm |

Tungsten is the only option that keeps the cross-section under about 90 mm at 10 kg (87 mm); lead works to about 8 kg. Funding is not the limit, procurement lead time is. Sensor geometry: ogive nose 45 mm, ballast cylinder (75 % fill) in the middle, 45 mm fin section; three LED bands (nose, mid, fins), tow eye above the CG, ballast slugs on a central clamped rod. The fins must stay on in the container (L451-453), so the finned envelope sets the inner box: ring-shrouded fins are 30 mm proud against 80-120 mm tip-to-tip for plain fins (stability of the shroud is not computed).

## 4. Tow check

- **Tension** (q 374 Pa, line sized for 3 x n 4 x weight, 2 mm SK78 reference 3.9 kN, reseller): 3.4 kg 33.5 N at n 1 and 133 N at n 4 (DB-01); 6 kg 59 N at n 1, 177 N at n 3; 10 kg 98 N / 392 N at n 4. Line 1.5 mm (3.4 kg) to 2.0 mm (10 kg).
- **Hang angle and shape** (weights, line cross-flow drag Cd 1.1, sensor CdA 0.003): 6 kg hangs 3.1 deg from vertical at n 1, 10 kg 2.4 deg, 3 kg 4.7 deg; at n 3.24 under 1 deg. The sensor is 0.03-0.10 m aft of the exit at 2.84 m depth; a 1 kg ballast trails 0.56 m aft. Candidate exits 0.10, 0.55 and 0.80 m ahead of the tail leading edge all clear by 0.09-0.80 m minus the 0.56 m light trail; for a pusher the exit must be at least 0.15 m ahead of the prop plane, because the line is 0.006 m aft at 0.25 m depth.
- **Pitching moment on the aircraft** is n m g times the exit offset from the CG: 6 kg at n 3: 18 N m per 0.1 m. Put the exit on the CG line.
- **Barrowman**: 6 kg tungsten dart, CP 139 mm, CG 100 mm from the nose, margin 0.27 cal, pitch natural frequency 0.5 Hz on aerodynamic stiffness alone (pendulum 0.27 Hz): lightly damped. Nose tow equilibrium tan(theta) = W x_cg / (q A CNa x_cp) gives 50-82 deg nose-up. A tow eye 5 mm aft of the CG adds W x e = 0.3 N m/rad of gravity stiffness at 6 kg. This needs a tow test (TC card).
- Turn geometry: in a 72 deg bank the line follows the aircraft's body-down axis, so the sensor sits 2.7 m inboard and 0.9 m below: altitude above 10 m is a procedure item.

## 5. D&R scaled to heavier sensors

Closed-loop drum A (DB-01), sized with `s5_tow` against the n 1 stow tension, checks at n 1.5 and 2. Savox is a modified servo (reseller).

| Sensor | 37D 70:1 | Savox 2290 | 2 x 37D 131:1 | NEO 550 + 15:1 |
|---|---|---|---|---|
| 3.4 kg | 11.9 s, 0.32 kg | 14.0 s, 0.20 kg | 12.4 s | 3.0 s, 0.65 kg |
| 6 kg | 19.7 s | 19.0 s, 0.26 kg | 16.0 s | 3.1 s, 0.70 kg |
| 10 kg | 32.2 s, 0.46 kg | 30.3 s, 0.34 kg | 25.8 s, 0.69 kg | 3.3 s, 0.78 kg |

p_fail (option A, benign 1.2 %, catastrophic 1.3 %, signal 2.7 %, estimates from dr_trade) scaled by 1 + 0.15 (m - 3.4)/3.4 (estimate): 5.2 % at 3.4 kg to 5.9 % at 10 kg. Slip ring (Adafruit 1195 class) carries the light mode signal only; the strength member carries the tension. A non-rotating spool with a fixed inner end removes the joint but twists the line, so it needs a swivel at the sensor.

## 6. H1 study (120 paired draws, seed 2027, expected field, adapter regression 6.3326)

Method (`src/payload/h1_study.py`): one container per range, declared mass on a 0.25 kg grid in the servable set; "tech" = argmax over the grid of the score at the planning density with the draw's tech-known inputs; "frozen" = the single best declared mass on the same hardware; "oracle" = best mass with the draw's density known.

| Range, pads, planning density | S | Frozen | Tech | Oracle | Tech M2 / M3 / GM | P(M2) tech (frozen) | Tech P10 | mean pick |
|---|---|---|---|---|---|---|---|---|
| 3-6, re-cut, 1.04 | 0.9 | 6.340 | **6.735** | 6.814 | 1.44 / 2.89 / 1.40 | 0.975 (0.967) | 6.20 | 5.46 |
| 3-6, re-cut, 1.04 | 1.0 | 6.239 | 6.697 | 6.740 | 1.43 / 2.86 / 1.41 | 0.967 (0.975) | 6.07 | 5.50 |
| 3-6, re-cut, 1.04 | 1.1 | 6.068 | 6.497 | 6.511 | 1.37 / 2.72 / 1.41 | 0.917 | 5.85 | 5.55 |
| 3-6, re-cut, 1.04 | 1.2 | 5.853 | 6.312 | 6.354 | | | | 5.55 |
| 3-8, re-cut, 1.04 | 0.9 | 6.297 | **6.764** | 6.798 | 1.48 / 2.89 / 1.40 | 0.975 (0.975) | 6.09 | 6.13 |
| 3-8, re-cut, 1.04 | 1.0 | 6.197 | 6.702 | 6.754 | 1.46 / 2.83 / 1.41 | 0.958 | 5.92 | 6.34 |
| 3-8, re-cut, 1.04 | 1.1 | 5.987 | 6.530 | 6.545 | 1.39 / 2.71 / 1.42 | 0.917 | 5.78 | 6.40 |
| 3-8, re-cut, 1.04 | 1.2 | 5.833 | 6.341 | 6.380 | | | | 6.39 |
| 3-5, re-cut, 1.075 | 0.9 | 6.345 | 6.485 | 6.680 | 1.40 / 2.82 / 1.27 | 0.95 | 6.05 | 4.66 |
| 3-6, re-cut, 1.075 | 0.9 | 6.340 | 6.561 | 6.814 | 1.39 / 2.77 / 1.41 | 0.933 | 6.03 | 5.52 |
| 3-8, re-cut, 1.075 | 0.9 | 6.297 | 6.416 | 6.798 | 1.36 / 2.64 / 1.42 | 0.892 | 2.50 | 6.34 |
| 3-8, as-built, 1.075 | 0.9 | 6.188 | 6.292 | 6.749 | 1.33 / 2.56 / 1.40 | 0.867 | 2.50 | 6.20 |
| 3-8, geared NEO, 1.075 | 0.9 | 6.176 | 6.268 | 6.719 | 1.30 / 2.57 / 1.39 | 0.867 | 2.50 | 6.07 |
| 4.4-10, re-cut 10 deg, 1.075 | 0.9 | 5.890 | 5.788 | 6.215 | 1.14 / 2.17 / 1.47 | 0.725 | 2.50 | 6.82 |

Reading: tech picks 6.0 kg in 74-81 % of draws for the 3-6 range (the top of the range) and a spread from 3 to 8 kg for 3-8, so the hardware range, not the per-draw choice, is the main lever. M3 flies 5.2-5.8 kg of ballast at 5.2-5.7 laps on average. Adapter limitations: the lumped eta (0.58), s6.evaluate's per-draw choice, no wind.

**Known bias (to the integration agent):** `adapter.evaluate`, inherited from `s6.evaluate`, still picks the simulators flown and the M3 ballast per draw with full knowledge of that draw (it can see the realised lap factor and density). Every tech-minus-frozen number above therefore overstates the attempt-level optimisation equally for tech and frozen policies; phase 1b should remove it. The tech declaration itself uses only tech-known inputs and the planning density.

## 7. M3 lap cliff (8 s take-off, stow inside the window; `m3_lap_table`)

Laps = floor((292 - stow)/lap).

| Lap time | stow 3 s | 12 s | 20 s | 30 s | Stow gain that buys one more lap |
|---|---|---|---|---|---|
| 33 s | 8 | 8 | 8 | 7 | 2 s at 30 s |
| 35 s | 8 | 8 | 7 | 7 | 18 s at 30 s |
| 37 s | 7 | 7 | 7 | 7 | 8th lap needs lap <= 36.5 s at 3 s stow |
| 39.1 s | 7 | 7 | 7 | 6 | 11.7 s at 30 s; none at 12 s |
| 41 s | 7 | 6 | 6 | 6 | 7 s at 12 s |
| 43 s | 6 | 6 | 6 | 6 | |

At 39.1 s the stow can be as slow as 18.3 s with no loss; the fast drive pays only near a cliff, about 4 s of lap time or 11-18 s of stow away. One extra lap at 4.4 kg is worth 0.217 M3 points (expected field) until the 1.0 cap.

## 8. Lights, staging, lifting sensor

- **Lights (estimate, no primary visibility source read).** Four 3 W white LEDs per light, 100 lm/W and 20 % to the optics through a 360 deg band of about 4.3 sr gives about 220 cd per light (target 100-400 cd); flash 2 Hz at 50 % duty so it differs from SOLID; energy 1.4 Wh for a full M3 (lap 2 SOLID, rest FLASH), so a COTS 2S 0.5-1 Ah pack is 2x margin. Test outdoors at noon at 150 m.
- **Staging (estimate, replace by drills).** M2: 120 s fixed plus 75 s per unit gives 195 / 240 / 285 s for 1 / 2 / 3 units, so three units crowd the 300 s box and a single heavy unit helps. M3 unpack and attach 90 s. GM: three rig changes of 50 s plus 60 s unpacking, 210 s of the 300 s.
- **Lifting sensor.** Fixed wings are legal in the text (L451) and not worth it: carrying 5 kg at 26.5 m/s needs 0.16 m2 (q 374 Pa, CL 0.8), which does not stow internally (L484), cannot be removed for the container, breaks the 381 mm envelope, and needs CL 2.5 at n 3.2. Keep small fins.

## 9. Bay

A 6 kg unit (298 x 288 x 288 mm) with the reel and dock needs a bay of about 0.044 m3, 0.43 m long, 0.32 m wide and 0.31 m high (`M.bay`). The unit sits on the CG line; keep the reel and dock on the CG too, and a fore-aft trim tray for the empty-bay M1 and M3 cases.

## 10. Files

`src/payload/model.py`, `h1_study.py`, `run_s8.py`; `tests/test_v_payload.py`; `out/payload/results.json`, `tables.json`, `h1_*.json` and logs; `early/S8_envelope.md`; `sources/S8.toml`.
