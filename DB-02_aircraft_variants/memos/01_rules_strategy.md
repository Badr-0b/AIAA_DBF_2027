# S1 rules and strategy memo (29 Oct 2026)

**Status:** hard constraints (`early/S1_constraints.md`, `src/rules/model.py` `check()`), decision timing (`early/S1_decision_timing.md`), 99-clause compliance matrix (`out/rules/compliance.csv`, 99 of 99 quotes verified against the layout text), ranked Q&A (`out/rules/qa_ranked.md`), results `out/rules/results.json` (S1-R01..R11), 11 tests pass. Newer rules version on aiaa.org was **not re-checked this session**: check before 1 Nov.

| ID | Quantity | Value | Range | Grade | Source |
|---|---|---|---|---|---|
| S1-R01 | Clauses in the matrix, quotes verified | 99, 99 | | verified | rules draft 2 Sep 2026 |
| S1-R02 | M1 waiver gain, expected total mission (p 0.65, 3 attempts) | +1.05 points | +0.42 to +1.05 | computed | attempts.p_complete |
| S1-R03 | P(M3 completed), waive vs fly (p 0.65, 3 attempts) | 0.718 vs 0.401 | 0.60-0.94 vs 0.31-0.81 | computed | attempts.p_complete |
| S1-R04 | Report points equal to one mission point (TR 88, TM 6.3) | 13.97 | 12.1-16.7 | computed | section 6.3 |
| S1-R05 | Mission total needed to win at TR 88 (2026) | 5.66 | 5.66-6.41 over 2022-26 | computed | dbf_results.csv |
| S1-R06 | Stow slack for 7 laps at 39.1 s lap | 18.3 s | | computed | arithmetic |
| S1-R07 | Lap time for 8 laps at 12 s stow (3 s stow outside the window) | 35.0 s (36.5 s) | | computed | arithmetic |
| S1-R08 | M3 points per lap at 4.4 kg | 0.217 | 0.163-0.217 | computed | competitor.toml (estimates) |
| S1-R09-11 | Ring-to-bottom limit, simulator tolerance, true TOGW limit | 381 mm, 28.35 g, 24.945 kg | | verified | L538-542, L559-560, L627 |

**Findings that matter for the aircraft choice**
1. **Declare the sensor mass at tech, plan it at a hot-day density.** On one physical 150 g container for 3-6 or 3-8 kg, the adapter gives 6.735-6.764 at S 0.9 m2 against 6.297-6.340 frozen and 6.333 for REF-D01 (S8-R27..; memo 08). Planning at the mean density instead gives 6.42-6.56 with a P10 as low as 2.5.
2. **Waive M1.** It adds +0.42 to +1.05 expected points and lifts P(M3) by 0.13-0.32 across 57-73 % attempt success and 3-4 attempts; waiving never lost in the attempt model.
3. **One mission point is worth 14 report points** at TR 88 / TM 6.3 (1 report point = 1.1 % of the score, 1 mission point = 15.8 %). Report quality still multiplies: TR 85 against 92 is 7 points, about 0.5 mission points at TM 6.3.
4. **Winning scores 2022-26 were 501-568** (participation 3); at TR 88 that needs a total mission score of 5.66-6.41. REF-D01 (6.33) and the declared-at-tech designs (6.5-6.8) sit at or above the top of that band, with the field maxima uncertain.
5. **The M3 lap cliff is 4 s of lap time or 11-18 s of stow away at typical settings** (39.1 s lap, 12 s stow). A slow stow (30 s for a 10 kg sensor on a servo drum) costs a lap; below a cliff the 3 s geared drive is worth its 0.3-0.5 kg.
6. **Container envelope is the sharpest compliance risk:** DB-01's 100 g, 392 mm container fails 381 mm even with no sling (449 mm at 15 deg); a 150 g sensor with 41 mm foam and a 10-15 deg sling to the corners passes (336-385 mm).
7. **Configuration freezes on 19 Feb**: gear type, tail type, wing configuration, tractor/pusher and motor count (FAQ L1693-1704); a V-tail or elevons cannot meet the fail-safe list literally (RISK, C90); winglets are a span-definition RISK (C01).

**What would change them:** the Q&A answers (ranks 1-4 of `qa_ranked.md`); a newer rules version; field maxima beyond the expected 75 % anchors; the removal of the per-draw peeking in the adapter.
**Open issues:** compliance matrix per-configuration impacts are our reading, not an inspector's; Barrowman and tow tests pending; staging times are estimates until drilled.

## 1. Compliance matrix

`out/rules/compliance.csv` has one row per clause C01-C99 with: ID, section, rule lines, verbatim quote, design requirement, verification, `quote_in_layout`, and an impact column for six configurations: REF (REF-D01 class), WL (winglets/tip plates), VT (V-tail, ruddervators, elevons), TW (twin systems), HV (one heavy declared unit), MB (biplane, box, tandem). The IDs are those used by `src/rules/model.py` `check()`. Quotes were repaired where line breaks, hyphenation or table text had broken them (C38, C64, C74, C76, C88, C89, C90, C93, C30).

Largest per-configuration impacts:

| Configuration | Clauses | Impact |
|---|---|---|
| WL | C01, C17 | span undefined; keep whole-airplane width <= 1.8288 m; winglets on the drawing |
| VT | C90, C10, C17 | full up + full right rudder conflict (RISK); a rate gyro is allowed; tail frozen 19 Feb |
| TW | C26-C28, C33-C39, C98 | two plugs >= 152.4 mm from every prop plane, top surface; 2 x 50 Wh identical packs; two fuses up to 100 A each; push-pull is a RISK |
| HV | C03, C04, C42-C45, C57, C59-C60, C66, C79, C84 | tip-test mass sized at the top of the range and permanent; 150 g sensor; adjustable simulators; stow time; declared at tech |
| MB | C01, C03, C88, C96 | tip lift points on the main surface undefined; configuration frozen |

## 2. Decision timing

`early/S1_decision_timing.md` lists the stages (freeze, build, tech, attempt, GM), what is revealed before each, and what is chosen. Two points the adapter has to respect: the declared mass binds M2 (the container with the declared sensor must be carried, L524-525), and the tip-test mass is a permanent cap. The reference implementation is `src/rules/strategy.py`.

## 3. M1 waiver (attempt model, `data/attempts.py`)

Each attempt is one try at the current mission; parts 1.0 / 1.58 / 3.0 / 1.10 (M1, M2, M3, GM) from the DB-01 reference; GM has two tries.

| p per attempt | Attempts | E(total) fly M1 | E(total) waive | Gain | P(M3) fly | P(M3) waive |
|---|---|---|---|---|---|---|
| 0.57 | 3 | 4.09 | 5.08 | +1.00 | 0.31 | 0.60 |
| 0.57 | 4 | 5.11 | 5.74 | +0.63 | 0.59 | 0.79 |
| 0.65 | 3 | 4.54 | 5.59 | +1.05 | 0.40 | 0.72 |
| 0.65 | 4 | 5.58 | 6.13 | +0.55 | 0.70 | 0.87 |
| 0.73 | 3 | 4.99 | 6.01 | +1.03 | 0.51 | 0.82 |
| 0.73 | 4 | 5.98 | 6.40 | +0.42 | 0.81 | 0.94 |

Limits: attempts are independent; the one extra attempt for M2 and M3 after all three missions (L885-887) is not modelled; the rule that a failed M2 after a waiver ends M1 is included.

## 4. Report versus mission

Competition = TR x TM + participation (section 6.3). dC/dTR = TM, dC/dTM = TR.

| Year | Winning score | Top report score | Top-10 median report | Max mission total | TM needed at TR 88 |
|---|---|---|---|---|---|
| 2022 | 526.59 | 93.33 | 89.7 | 6.05 | 5.95 |
| 2023 | 567.51 | 91.42 | 89.3 | 6.80 | 6.41 |
| 2024 | 547.96 | 93.60 | 90.2 | 6.01 | 6.19 |
| 2025 | 518.23 | 95.83 | 88.3 | 6.34 | 5.85 |
| 2026 | 501.26 | 90.60 | 87.5 | 5.61 | 5.66 |

(Source: `analysis/data/dbf_results.csv`, 513 rows; needed TM = (score - 3)/88.) Median team report scores are 74.7-78.9 against 87.5-90.2 for the top ten, so the report is mostly a gate: a 5-point report gain (0.36 mission points at TM 6.3) is smaller than the swing from one lap or from GM declared at 6 kg (+0.32-0.41).

## 5. Ranked Q&A

See `out/rules/qa_ranked.md`: (1) span with winglets, (2) stow time in the window, (3) hatches in the staging box, (4) rigging and the 381 mm envelope, (5) spare panels as repair; later rounds: deploy-length verification, sensor battery in the container. Pack changes per mission (FAQ L1670-1673) and gyros (L600) are already answered by the text.

## 6. Files

`src/rules/model.py` (check), `compliance.py`, `strategy.py`, `run_s1.py`; `tests/test_v_rules.py`; `out/rules/compliance.csv`, `results.json`, `qa_ranked.md`; `early/S1_constraints.md`, `S1_decision_timing.md`; `sources/S1.toml`.
