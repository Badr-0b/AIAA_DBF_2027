# Analysis

The mission math behind proposal Section 3.0 (55 points): one Python file per
question, in the order of `00_START_HERE_RnD.md` Section 4. Standard library,
numpy and matplotlib only.

## Run
From the repo root (Git Bash or any shell):

| Command | What it does |
|---|---|
| `python -m unittest discover -s analysis/tests -v` | Every test with its hand-checked value |
| `python analysis/check.py` | One-line status: pass / fail / not written |
| `python analysis/run_all.py` | Scripts 1–2 end to end: tables in the terminal, figures in `analysis/out/` |
| `python analysis/s4_sizing.py` | Scripts 3–4 (PROVISIONAL): design points, wing-area sweep, decision and strategy tables, Monte Carlo, figures |
| `python analysis/s6_studies.py` | Script 6 (PROVISIONAL): robust design map, carpet, tornado, global sensitivity, candidate Monte Carlo, trade weights (about 30 s) |
| `python analysis/config_trades.py` | Mass-for-drag exchange rate at the robust reference, retractable-gear break-even, body-option test chart (after Script 6) |
| `python analysis/trades.py` | Audit of the team's trade matrices (arithmetic, evidence, sensitivity-derived weights, robustness); inputs in `inputs/trades.toml` |
| `python analysis/db01_data.py` | Numbers for decision brief DB-01 that no other report prints: stall-bound sweep, payload-unit table, M1 waiver (after Script 6); `decisions/build.sh` then builds the brief |
| `python analysis/dr_trade.py` | Deploy-and-recover architecture trade, proposal Table 06: rules and physics screening, drive sizing, points at stake, pairwise comparison of every option, four decision lenses, Monte Carlo (after Script 6). Physics in `s5_tow.py` |
| `python analysis/prop_validation.py` | Script 3b checked against measured data (APC vs UIUC wind tunnel, AIAA stands, T-Motor maps, ERAU 2023 flight); run before using any propulsion result |
| `python analysis/prop_trade.py` | Propulsion trade (DB-01 D9, PR-01 B07-B10): every measured-map motor x APC prop x pack, mission scoring through Scripts 4/6, Monte Carlo, twin layout, prop diameter (about 6 min) |
| `python analysis/clmax_study.py` | Section Cl_max (E03): UIUC wind-tunnel data, XFoil checked against it (clean and flapped), candidate sections SD7037/SD7034/SD7062/MH 114 with plain flaps (about 9 min first run, then cached) |
| `python analysis/wing_clmax_validation.py` | The 3-D wing method checked against NACA TN 663's measured part-span flap wings; writes the calibration `wing_clmax.py` reads |
| `python analysis/wing_clmax.py` | Wing CLmax, clean and flapped, from AVL span loading and measured sections (after the two above) |
| `python analysis/clmax_impact.py` | Script 6 robust map re-run with the measured CLmax ranges (defaults unchanged) |
| `python analysis/mass_breakdown.py` | Airframe mass by component (E02): top-3 weight tables, per-part ratios, bottom-up budget for the reference design against the Script 4 fit |
| `python analysis/cushion_study.py` | Container foam, size and mass for the Ground Mission drop (E05): MIL-HDBK-304B cushion curves, by the sensor's g rating and drop height |
| `python analysis/tc06_predictions.py` | Script 3b predictions printed on test card TC-06 (writes `testing/cards/tc06_predictions.tex`) |
| `python analysis/s7_export.py` | Writes `proposal/data/analysis.tex`; `proposal/build.sh` runs it |

A test whose function still raises `NotImplementedError` is **skipped** ("not
written yet"). **FAIL** always means a wrong answer.

## Who writes what
On 12 Oct 2026 (evening) the team lead directed Claude to write and run all
the analysis code, on condition that every datum is verified against a
reliable, cited source. Pair mode (the team writing the function bodies) is
lifted. The team reviews, decides, and owns every number. Rules Sec. 1.3: the
analysis is the team's responsibility, so every derivation is documented for
the team to defend.

| File | Role |
|---|---|
| `s1_course.py`, `s2_scoring.py` | Scripts 1-2: physics and scoring, checked by `tests/` |
| `s3_performance.py` | Script 3: drag polar, power, lap and mission energy, efficiency calibration on flight data; checked by `tests/` |
| `s4_sizing.py` | Script 4 (provisional): mass build-up from the data fit, constrained search over payload x speed x bank, 01 vs 02 |
| `s3b_propulsion.py` | Script 3b (provisional): propeller (APC tables), motor + ESC (losses fitted to manufacturer-measured maps), battery, fuse; flight factor calibrated on ERAU 2023. Scripts 4/6 use it when `Params.prop` is set (`s4.with_propulsion`); the default stays the lumped eta |
| `prop_validation.py`, `prop_trade.py` | Script 3b validation report and the propulsion trade |
| `clmax_study.py`, `wing_clmax_validation.py`, `wing_clmax.py`, `clmax_impact.py` | Maximum lift from measured data (E03): section, 3-D wing, validation on NACA TN 663, effect on the optimum. Tools: `xfoil_tools.py`, `tools/` (XFoil, AVL) |
| `s6_studies.py` | Script 6 (provisional): total mission score of complete designs under uncertainty; sensitivities and trade weights; helpers checked by `tests/` |
| `tests/` | Hand-checked expected values, derived independently of the code |
| `common.py`, `run_all.py`, `figures.py`, `s7_export.py`, `check.py` | Tooling: inputs, runner, plots, export |
| `inputs/*.toml` | Every input, each with its source; targets in `aircraft.toml` are the team's decisions |
| `data/` | Gathered datasets: every value carries its source and a verbatim quote, machine-checked by `data/verify.py` |

## Inputs
| File | Holds |
|---|---|
| `constants.toml` | g and exact unit conversions |
| `rules.toml` | Every rule limit as an exact SI value, with the rule text and section |
| `aircraft.toml` | Aircraft 01 (high-AR) and 02 (delta): geometry, plus your targets (`nan` until set) |
| `competitor.toml` | The field maximum in each mission score: per-mission specialists, three scenarios, every anchor sourced |
| `export.toml` | Which aircraft and scenario the proposal shows, and whether the numbers are confirmed |
| `sizing.toml` | Scripts 3-4: battery, efficiency, drag areas, CLmax, stall and load-factor bounds, time calibration; each sourced or a labelled ESTIMATE with its sweep |
| `studies.toml` | Script 6: grids, Monte Carlo ranges, tornado steps, attempt statistics. The reference point is computed (robust optimum), never chosen by hand |
| `trades.toml` | The team's six trade matrices (Matrix_Tables/, 10 Oct), digitised verbatim, plus audit entries with evidence |
| `propulsion.toml` | Script 3b: battery voltages and resistance, ESC, fuse, motor-mass reference, layout penalties, uncertainty bands; each ESTIMATE with its reasoning and range |
| `dr_trade.toml` | Table 06 trade: drives (verified/reseller), part masses, screened concepts, failure modes with ranges and reasons, manufacturability judgments |

Sources policy: a value is either read in a cited primary source on a stated
date (`verified`), or a labelled `estimate` with its reasoning. Nothing is
typed twice: the proposal's air density comes from `proposal/data/numbers.tex`
through `common.number("nRho")`.

## Into the proposal
`s7_export.py` writes the Table 08 and glance-panel numbers to
`proposal/data/analysis.tex`. Each macro lives in exactly one file, either that
one or `numbers.tex`; a duplicate stops the build. Until `export.toml` sets
`confirmed = true` (numbers freeze, 20 Oct), every exported value prints as an
unfinished value in the draft. `proposal/build.sh` also reports this folder's
test status and will not print READY TO SUBMIT while any required test fails or
is unwritten.
