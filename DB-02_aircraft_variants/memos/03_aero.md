# 03 Aero (S3, monoplane): high lift, span efficiency, winglets, turn flap, CD0, multi-surface screen, lever ranking

Status: complete 29 Oct 2026. API `src/aero_mono/model.py: aero(geom)`, 11 tests pass (`tests/test_v_aero_mono.py`). Results `out/aero_mono/results.json` (27 items). Figures `out/aero_mono/fig_*.pdf/png`.
All CLmax values handed to the adapter are TRIMMED (tail download, tail arm 3.0 cbar, CG 0.05 cbar aft of the a.c.); untrimmed values sit in `clmax_*_untrimmed`.

| ID | Quantity (REF-D01: S 0.9 m2, b 1.82 m, taper 0.7, SD7037) | Value | Range | Grade | Source |
|---|---|---|---|---|---|
| S3-R01 | e_inv, AVL wing alone, inviscid | 0.993 | 0.985-1.0 | computed | AVL 3.52 Trefftz plane |
| S3-R02 | k_fuse = 1-2(df/b)^2, df 0.22 m | 0.971 | 0.96-0.98 | computed | Kroo 2001 / Raymer (method, not re-read) |
| S3-R03 | K_visc = dCd/dCL2 of the wing profile | 0.0062 | 0.0045-0.0075 | computed | XFoil Re 8.5e5 x1.11 x1.15; Kroo 0.38 CD0 = 0.0061 |
| S3-R04 | Oswald e = 1/(1/(e_inv k_fuse) + pi AR K_visc) | 0.901 | 0.849-0.906 | computed | S3-R01..03 |
| S3-R05 | Same method at AR 5.2 (check) | 0.868 | ERAU measured 0.842; Raymer 0.89 | computed | ERAU 2023 (dbf_aircraft.toml) |
| S3-R07 | Plain flap 25 % c, 30 deg: section dClmax (dCl a0 0.92, dCm -0.159) | 0.48 | +-10 % | verified | Williamson 2012, UIUC LSAT Vol 6, Re 3e5 (20 deg 0.38, 40 deg 0.52) |
| S3-R09 | Single-slotted 30 % c, 30 deg: section dClmax | 0.80 | 0.59-1.02 | estimate | TR 664 fig. 30 (slotted/plain 1.5); Leng 2022 Sec. 6.4 +1.0 measured, ESDU 0.59 |
| S3-R10 | Fowler 30 % c, 30-35 deg: effective section dClmax (retracted area) | 1.51 | 1.30-1.71 | estimate | TR 534 fig. 5 (p. 4, Re 6.1e5); TR 664 fig. 30 Fowler peak 1.45 |
| S3-R11 | Clean wing CLmax (SD7037, 0.9 m2) | 1.19 | 1.14-1.23 | computed | AVL critical section + UIUC sections x1.0-1.086 (TN 663); DB-01 used 1.25 |
| S3-R12 | clmax_landing, plain 25 % c 30 deg, 60 % semispan, trimmed | 1.44 | 1.37-1.49 | computed | area method, as REPO wing_clmax |
| S3-R13 | clmax_landing, slotted 30 % c 30 deg, 60 % | 1.62 | 1.45-1.78 | estimate | same; mass +0.12 kg |
| S3-R14 | clmax_landing, Fowler 30 % c 35 deg, 60 % | 1.92 | 1.76-2.05 | estimate | same; mass +0.30 kg; Cm -0.42 |
| S3-R15 | CD0 build-up (wing 0.0061, body 0.0046, tail 0.0033, gear 0.0013, other 0.0008) | 0.0161 | 0.0135-0.0209 | estimate | XFoil + Hoerner + GT 2026; DB-01 0.0230 |
| S3-R16 | Non-wing drag area | 0.0090 m2 | 0.0080-0.0107 | estimate | DB-01 0.013 (0.006-0.028) |
| S3-R19/20 | Winglet delta e, h = 10 / 15 % semispan (h/b 0.05 / 0.075), vertical | +0.015 / +0.028 | x0.5 to x3 | computed | AVL, toe optimised; cd0 +0.0007 / +0.0011; root bending x1.009 / x1.014 |
| S3-R21 | clmax_turn_avail with 10 deg turn flap (clean 1.18) | 1.29 | 1.25-1.33 | computed | Williamson dClmax 0.22; e in turns x0.947 |
| S3-R22 | Biplane induced k ratio, gap/span 0.15, equal span and S | 0.772 | 0.75-0.80 | computed | AVL; literature about 0.78 (Prandtl 1924, not re-read) |
| S3-R24..27 | Adapter mean, REF-D01: DB-01 / S3 plain / slotted / Fowler | 6.33 / 6.18 / 6.37 / 6.42 | P10 6.00 / 6.06 / 6.05 / 6.04 | computed | S12 adapter, 120 draws |

## Findings that matter for the choice

1. The DB-01 CLmax of 1.6 (flapped) is optimistic for a plain flap: trimmed 1.44 (1.37-1.49) at 0.9 m2 (S3-R12). Substituting the full S3 aero (plain flap) lowers the REF-D01 mean from 6.33 to 6.18; P(M2 feasible) 0.97 to 0.95.
2. A single-slotted flap (+0.18 CLmax, +0.12 kg) restores the mean to 6.37 and a Fowler (+0.48, +0.30 kg, Cm -0.42 needs a larger tail download) to 6.42. The Fowler's lead over slotted is 0.05 points, inside the CLmax range, so slotted is the cost-effective step. At REF-D01b (1.0 m2 / 5 kg) the gap is larger: baseline 6.07, S3 plain 6.09 (with ranges 6.33), slotted 6.31 (central).
3. Oswald e is 0.90 (0.85-0.91), not 0.946. Lap energy cost of using e 0.90 instead of Raymer: -0.05 (REF-D01) to -0.19 (S 1.2 m2 / 7 kg) points. The method reproduces ERAU's measured 0.842 within 3 % (0.868 at AR 5.2).
4. Parasite drag is lower than DB-01's: CD0 0.0161 against 0.0230 (non-wing drag area 0.0090 m2 against 0.013). Substituting it adds +0.09 (REF-D01) to +0.46 (REF-D01b) points. This is the largest single positive lever, and the least certain (grade estimate; upper end 0.0209 reaches DB-01).
5. Vertical winglets do not pay. AVL gives +1.5 % e at h = 10 % semispan and +2.8 % at 15 % (optimal toe, no gain from twist or chord). Even with the three-fold literature-theory bracket the adapter score change is -0.01 (REF-D01) because the wetted drag (+0.0007-0.0011) and +0.10-0.15 kg offset it. Root bending rises only 1-1.5 %.
6. A 10 deg turn flap lifts the turn CLmax from 1.18 to 1.29 (+9 %) but costs 5 % of e in turns (AVL flap twist), net -0.04 points: the turn CL limit is not binding enough to repay it. A 5 deg setting is neutral (-0.01).
7. Biplane or box wing at equal span: induced k x0.77 (gap/span 0.15) but Re halves, struts add 0.0003 m2, CLmax per area x0.92 (estimate), +0.6 kg. Adapter: -0.32 (REF-D01). KILL: the gain (+23 % on 65 % of lap energy, ie +15 %) does not clear its penalties; the family is eliminated at this span and area. Tandem is dropped by Munk's stagger theorem (induced drag unchanged by stagger; tandem has no gain over the monoplane in the same span; NACA TR 151, 1921, cited as method, not re-read).
8. Section choice: XFoil at Re 8e5, Ncrit 9, cd at cl 0.35 / 0.7 / 1.0 (counts): SD7037 50 / 65 / 94, E387 60 / 61 / 74, SD7034 67 / 63 / 82, MH114 93 / 76 / 74. SD7037 is best on the straights (cl 0.34); E387 and SD7034 win only above cl 0.7 (turns). SD7037 alone has measured data (cd/XFoil 1.11, CLmax 1.22-1.30); E387 and SD7034 are untested at this Re in the repo data. No change to the section; E387 is the one to test if turns dominate.

Lever ranking by mean change (REF-D01 / REF-D01b / S1.1-6 kg / S1.2-7 kg; central, vs DB-01 inputs): CD0 build-up +0.09 / +0.46 / +0.25 / +0.35; slotted flap vs plain flap +0.11 / +0.23 / +0.06 / +0.05; Fowler vs plain +0.01 / +0.17 / -0.04 / 0.00; Oswald e (honest) -0.05 / -0.08 / -0.16 / -0.19; turn flap 10 deg -0.04 / -0.04 / -0.08 / -0.08; winglets -0.02 / -0.04 / -0.05 / -0.04; biplane -0.32 / -0.24 / -0.17 / -0.01. Where P10 is about 2.2-2.5 (REF-D01b and larger) the baseline already has draws where M2 is infeasible; the substitutions that raise P(M2) (CD0 build-up, slotted) lift P10 to 6.3.

What would change them: a measured wing polar or tow test (CD0, e); a flapped SD7037 test (the slotted range 0.59-1.02 is the widest input); the winglet theory conflict below.

Open issues (Q&A item 1 and the rest):
- **Q&A: span definition.** Rules draft (layout line ~418) limit "wingspan"; vertical devices do not add span, but a canted winglet or tip plate that projects outboard does. Ask the committee to confirm the span is measured as the maximum lateral extent of the aircraft including winglets, so vertical devices are legal. We used 1.82 m with no projection.
- Winglet theory gap: AVL (flat wake, planar Trefftz) gives +4 % e at h/b 0.10 against +10-20 % in the literature the orchestrator quoted (Whitcomb NASA TN D-8260; Kroo). Neither was re-read here. AVL passed a box/biplane check against the 0.78 literature value, so its nonplanar machinery works; the low winglet gain is reported as computed with a x3 bracket. Cant outward adds span and was excluded.
- AVL BODY returned unphysical lift (CL 1.8 at 4 deg); the fuselage effect uses the Kroo factor.
- All CLmax values lack fuselage lift loss and slipstream gain (second is positive).
- Mass deltas (slotted +0.12, Fowler +0.30, winglets +0.10-0.15, biplane +0.6 kg) are estimates until S7 reports.
- RQ-4 cross-check (indicative only): our Hoerner body + nacelle gives 0.0042 m2 against CFD 0.0067 (fuselage + nacelle), 0.62 ratio; CFD includes an open duct and y+ 5.8. Not used to calibrate.

## Method

1. Section data. Plain flap: AG40d-02r 25 % flap, Re 3e5, read from the UIUC LSAT Vol 6 files (dClmax 0.12, 0.22, 0.32, 0.38, 0.43, 0.48, 0.52 at 5-40 deg). Slotted: plain x1.5 (TR 664 fig. 30, 20-40 deg), anchored at 0.80 (cf 0.30, 30 deg) between ESDU 0.59 and Leng 2022's 1.02; lift saturates beyond 30 deg at low Re. Fowler: TR 534 fig. 5 full-span increments on retracted area (1.16, 1.54, 1.88 for 0.20c, 0.30c, 0.40c) divided by the 0.9 area-method factor; deflection shape from TR 664 fig. 30. Chord scaling cf^0.7 (from TR 534 fig. 5). TR 664 states the slotted increment is practically independent of Re (p. 1).
2. Wing CLmax. `clmax = k_c CLclean + k_f 0.9 dClmax Sf/S` with AVL critical-section CLclean (SD7037 sections, S 0.8-1.3, taper 0.5-1.0 in `tables.json`), k_c 1.0-1.086 and k_f 1.0-1.075 from the NACA TN 663 validation. Trim: `CL + (Cm_ac + CL (h-hac)) cbar/lt`, band lt 2.5-3.5 cbar, h-hac -0.05 to +0.10. Pitching moment: plain dCm of Williamson x flapped c2 share; slotted -0.173 per unit dCl(a0) (TR 664 p. 29); Fowler -0.42 per unit dCl(a0) (TR 534 Tables II-III).
3. Fail-safe load: a full-flap dive at speed is a structural case. Slotted and Fowler flaps need tracks that carry the extended flap load (TR 534 p. 4-5: the Fowler carries about 1.5x its proportional share of the load at CLmax). Cap the flap travel mechanically, or size the flap hinge for 1.5 q S_f CL at the structural speed; this is for S7 and S5.
4. Span efficiency. AVL 3.52, taper 0.5/0.7/1.0, S 0.8-1.3, 28 strips per semispan, 10 chordwise. Oswald e per the decomposition in R01-R04 above. Profile drag: XFoil 6.99, SD7037 at Re 4e5-1.1e6, Ncrit 9 and 5, fit `cd = a + K_visc CL2` over cl 0.3-1.1; calibration 1.11 from UIUC SD7037 clean models at Re 3e5 (measured cdmin 0.0071-0.0077, cd(0.7) 0.0092-0.0097, cd(1.0) 0.0131-0.0145; XFoil 0.0070, 0.0085, 0.0121); build factor 1.0/1.15/1.5 (estimate: hinge gaps, finish, tip). Wing cd0 includes +0.0004 m2 (slotted) and +0.0008 m2 (Fowler) retracted-hardware drag, estimates.
5. Winglets: vertical fin of 0.5 tip chords, toe 0-3 deg optimised, S 0.9 and 1.1; root bending from AVL strip loads (the winglet side force acts at mid-height, adding to the wing's bending moment, sign assumed). Wetted drag: Hoerner flat-plate with form factor 1.2 and a 1.25 junction allowance.
6. Turn flap: flap as an equivalent twist on the flapped strips (as `wing_clmax.py`), AVL e of the twisted wing: 0.994 clean, 0.941 (10 deg), 0.912 (30 deg), 0.894 (dCl 1.2). The adapter gets an energy-weighted e (85 % of induced energy is in turns, ledger O-03/O-04).
7. Multi-surface: AVL, equal span 1.82 m, total S 0.9 m2, two surfaces of S/2, no stagger or decalage, gap/span 0.10-0.25: k ratio 0.817, 0.770, 0.734, 0.704. Box end plates add nothing in AVL (0.770 for both): the box advantage in theory is not captured. Kill gate applied with the adapter score and the complexity cost.
8. Adapter runs: `src/aero_mono/run_impacts.py`, 120 DB-01 draws, expected field, lumped eta. Each lever replaces only its own fields of a DB-01-equivalent aero dict (Raymer e, 0.0086 + 0.013/S, CLmax 1.6/1.25); "central" drops the S3 ranges, "with ranges" keeps them (results in `impacts.json`).

Validation: plain-flap values reproduce the REPO report (1.44-1.56 untrimmed at 0.9 m2, 60 %/30 deg). Kroo's K_visc rule agrees. AVL biplane k matches the literature 0.78. ERAU's e within 3 %.

Files: `src/aero_mono/{model,avl_tools,build_xfoil,build_tables,build_nonplanar,run_impacts,run_results}.py`, `out/aero_mono/{tables.json,impacts.json,results.json,xfoil_polars*.json,winglet_x3.json,fig_*}`, `tests/test_v_aero_mono.py`, `sources/S3.toml`.
