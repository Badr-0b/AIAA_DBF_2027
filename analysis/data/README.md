# Data

Evidence gathered for the design decisions. Every value carries its source and
can be re-checked by anyone with one command.

## Rules for this folder
- **Primary sources only.** The publisher of a document is the authority for it (AIAA for DBF documents; NOAA ASOS via the Iowa Environmental Mesonet for weather). Distributor or third-party copies are not used as values.
- **Every value has a verbatim quote.** `verify.py` checks that the quote is on the stated page of the cached source text, and that the value is inside the quote. Where a table has no text layer (an embedded image), the value is read on the rendered page and tagged `IMAGE:`; those rows are counted separately.
- **Nothing is typed twice.** Unit conversion to SI happens in `verify.py`, never by hand.
- **Estimates are labelled.** Anything that is not read in a source says so, with its reasoning (for example `inputs/competitor.toml`).

## Reproduce
```bash
python analysis/data/fetch.py          # download every source in sources.toml (raw/ is gitignored, ~300 MB)
python analysis/data/parse_results.py  # every team's published scores, 2022-2026
python analysis/data/verify.py         # check every value against its source; writes dbf_aircraft.csv
python analysis/data/aircraft_model.py # one row per aircraft, airframe-mass fit, calibration factors
python analysis/data/config_evidence.py # configuration of the 19 top-3 aircraft vs fly-off outcome
python analysis/data/field_stats.py    # field statistics and charts
python analysis/data/aircraft_charts.py
python analysis/data/fetch_wind.py     # mid-April wind at the fly-off site
python analysis/data/attempts.py       # M1 waiver model
python analysis/decision_maps.py       # M2 and GM decision maps
```
`sources.lock` records the SHA-256 of each document read, so a re-fetch can be confirmed identical.

## Datasets
| File | What | Source | Check |
|---|---|---|---|
| `dbf_results.csv` | Every team's published scores (GM, M1, M2, M3, proposal, report), 2022-2026: 513 rows | AIAA competition summaries | Each row's line is in the source; GM+M1+M2+M3 = total; report x total + participation = score; 0.15 P + 0.85 D = report |
| `dbf_aircraft.toml` → `.csv` | Top-3 design reports, 2021-2026: geometry, weighed masses, batteries, drag, propulsion, predicted and flight-test performance (352 values, 19 aircraft) | AIAA top-3 design reports | Verbatim quote on the stated page; `IMAGE:` rows read on the rendered page |
| `dbf_airframes.csv` | One row per aircraft in SI: span, area, airframe mass (no battery or payload), gross masses, wing loading, same-pack Wh/kg, CD0, each with how it was derived | Derived from `dbf_aircraft.csv` | Recomputed by `aircraft_model.py` (derivations in its docstring) |
| `calibration.csv` | Measured / predicted pairs (time, speed, mass, thrust, power, drag) for the same aircraft | Derived from `dbf_aircraft.csv` | Recomputed by `aircraft_model.py` |
| `dbf_config.csv` | Wing position, gear, tail, propulsion and fuselage of the 19 top-3 aircraft (verbatim quotes), with that year's fly-off rank and M2/M3 completion | `dbf_aircraft.csv` + `dbf_results.csv` | Recomputed by `config_evidence.py` |
| `field_stats.csv`, `field_bonus.csv` | Completion counts and bonus distributions per year | Derived from `dbf_results.csv` | Recomputed by `field_stats.py` |
| `wind_timpa.csv` | Sustained wind, 15-18 April 1996-2025, 07-18 h, at RYN, AVQ and TUS | IEM ASOS archive (raw CSV in `raw/`) | Recomputed by `fetch_wind.py` |

## Not yet gathered (and why)
- **Foam crush properties** (container, Ground Mission): JSP (ARPRO EPP) and Zotefoams (Plastazote PE) datasheets were not reachable from the manufacturers on 12 Oct 2026, and the distributor copies disagree. TC-02 (drop test) measures what we need directly.
- **Propeller and motor performance**: next, for Script 3.

## Findings so far (12 Oct 2026)
- Completing M3 is what places a team: 15-31 teams per year complete it, and every top-20 team in 2023-2025 did. In 2026, ranks 19-20 placed without M3 on near-max M2 scores of 1.93 and 2.00.
- The leader in each mission is an outlier: the median completer scores 9-54 % of the field max.
- 2024-25 was a weight/time M2 with a 6 ft span, 100 Wh and TIMPA, the closest analog to 2026-27. It anchors the M2 competitor (`inputs/competitor.toml`). Both heavy-payload designs among its top-3 reports failed M2 at the fly-off.
- Flight-test lap and mission times against the teams' own predictions (13 Oct, 24 pairs from 7 aircraft): median x1.15 per pair, x1.07 per aircraft, range 0.80-1.48. Straight-line speeds scatter both ways (0.87-1.21 per aircraft). Turns cost speed: USC 2024 flew turns at 66-69 % of its straight speed, UNSW 2025 at 84-85 %.
- Airframe mass (no battery, no payload) of 14 top-3 aircraft follows m = 5.96 S^0.94 kg (S in m2), R2 0.65, scatter x1.31 at 1 sd: about 6 kg per m2 of wing.
- 100 Wh packs, energy and mass of the same pack: 9 packs, 130-158 Wh/kg, median 142.
- CD0 spans an order of magnitude: 0.015 (GT 2026 build-up) to 0.155 (WashU 2022 build-up); ERAU 2023 measured 0.0583 against 0.0575 predicted.
- Propulsion models: static thrust measured x1.01-1.39 of prediction (3 aircraft), USC 2024 found thrust 20 % above QPROP/eCalc and scaled eCalc power by 1.15; ERAU 2023's mean in-air M2 power was 2.5 times its design value (1,243 W vs 500 W).
- The 2022-23 lap is the 2026-27 lap (two 1,000 ft straights, two 180-deg turns, one 360-deg turn; VT 2023 p130), so 2023 lap data are directly comparable.
- Configuration of the 19 top-3 aircraft (13 Oct):
  - practice: high wing 13, low wing 6; tricycle 13, taildragger 5, quadricycle 1; conventional tail 16; single motor 12, twin 6;
  - outcomes, 2022-26 (15 aircraft): 9 completed M3;
  - no feature separates success from failure: high vs low wing 4/9 vs 5/6, p = 0.29; single vs twin motor 7/10 vs 1/4, p = 0.24; tricycle vs taildragger p = 1.00 (Fisher exact).
- Fixed-gear drag areas: GT 2026 measured 9.9 cm2 in a wind tunnel; Joanneum 2022 19.4 cm2 and WashU 2022 123.5 cm2 by build-up.
- Fuselage drag (build-up) on wing area: Joanneum 0.0052, Ljubljana 2024 0.0037, GT 0.0016, WashU 0.0254 (a box fuselage).
- Teams that passed tech got 2.4-2.9 official attempts each; 57-73 % of attempts scored.
- Mid-April afternoon wind near TIMPA: median 3.6-4.1 m/s, 90th percentile 7.2-8.2 m/s.
