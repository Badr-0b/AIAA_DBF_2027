# S2 draft API: field model and reliability (DRAFT v0, 27 Oct 2026)

Status: **DRAFT. Signatures are frozen; numbers inside are provisional** until the calibrated
version lands (this file will say "v1" and list what moved). Code: `W\src\field\model.py`.
Everything is SI. Every coefficient inside is an `estimate` until the memo
`W\memos\02_field_reliability.md` grades it.

```python
import sys; sys.path.insert(0, r"C:\Users\Nitro\Documents\GitHub\AIAA_DBF\DB-02_aircraft_variants\src")
from field import model as fm
```

Import is side-effect free (reads two CSV and one TOML lazily on first call; writes nothing).

## 1. `fm.simulate(n, seed, year=2027, scale=None) -> Field`

`n` field draws (one draw = one whole competition), vectorised; 5,000 draws take well under 1 s.

| Attribute | Shape | Unit | Meaning |
|---|---|---|---|
| `n`, `T` | int | - | draws, team slots (T = 100; unused slots are masked) |
| `attend` | (n, T) bool | - | rival attends the fly-off (about 81-96 per draw, resampled from 2023-26) |
| `tech` | (n, T) bool | - | passed tech (about 80) |
| `flew` | (n, T) bool | - | attempted a flight (participation 3) |
| `participation` | (n, T) int | - | 0/1/2/3 per rules Sec. 6.3 |
| `report` | (n, T) float | 0-100 | Total Report Score = 0.15 P + 0.85 DR |
| `done` | dict M1/M2/M3/GM -> (n, T) bool | - | mission completed (M3 implies M2 implies M1-credit) |
| `m2_wt` | (n, T) float | kg/s | W/t of the best scored M2 (0 if not done) |
| `m3_lxs` | (n, T) float | kg·laps | laps × sensor mass (0 if not done) |
| `gm_wh` | (n, T) float | kg·m | declared sensor mass × drop height (0 if not done) |
| `rival_max` | dict m2/m3/gm -> (n,) | as above | max over rivals only (ours is added in `p_first`) |
| `scale` | (n, 3) float | - | drawn multiplier on the competitor.toml aggressive anchors (M2, M3, GM) |
| `year` | int | - | 2027 uses the 2027 formulas; 2022-2026 reproduce that year's field for back-tests |

Strength is joint: one latent strength per team drives report score, completion and value
(correlations calibrated on `dbf_results.csv`, 513 rows).

## 2. `fm.p_first(our, rivals, report_score) -> dict`

`our`: dict of arrays of length n (scalars broadcast). Draw i of ours is paired with field draw i
(if lengths differ, ours is tiled/truncated to `rivals.n`).

| Key | Unit | Meaning |
|---|---|---|
| `m2_wt` | kg/s | our W/t when M2 is scored |
| `m3_lxs` | kg·laps | our laps × sensor mass when M3 is scored |
| `gm_wh` | kg·m | our declared sensor mass × drop height |
| `done_m1`, `done_m2`, `done_m3`, `done_gm` | bool | completion per draw (use `sample_completion` below to make them) |
| `flew` (optional) | bool | default True (participation 3) |

`report_score`: our Total Report Score (0-100), scalar or (n,) array.

Returns (all P are fractions, `*_ci95` = Monte Carlo 95 % interval, Wilson for probabilities):

| Key | Meaning |
|---|---|
| `p_mission_top`, `p_mission_top_ci95` | P(our Total Mission Score > every rival's); ties count half |
| `p_first`, `p_first_ci95` | P(our Competition Score is highest), report × mission + participation |
| `rank_mean`, `rank_mean_ci95` | expected competition rank (1 = first) |
| `rank_p10`, `rank_p50`, `rank_p90` | rank distribution |
| `our_total` | (n,) our Total Mission Score per draw (max includes ours) |
| `our_parts` | dict M1/M2/M3/GM -> (n,) |
| `winner_rival_total` | (n,) best rival mission total in each draw |
| `n` | draws used |

Also `fm.p_first_curve(our, rivals, report_scores=(70, 75, ..., 96)) -> list[dict]` for the
P(1st) vs report-score curve.

## 3. `fm.p_attempt(margins, complexity, mission="M2") -> float`

Probability that one attempt at `mission` ("M2", "M3" or "M1") is scored (take-off, laps, landing
without significant damage, payload/D&R works). Physics-informed logistic:
`logit p = b0[mission] + sum_k b_k * h_k(margin_k) - sum_f c_f(complexity feature f)`.

`margins` keys (any missing key takes the field-typical value, so `p_attempt({}, "simple")`
returns the field-typical per-attempt success):

| Key | Unit | Meaning | Field-typical |
|---|---|---|---|
| `v_stall` | m/s | 1 g stall speed at the mission mass, landing configuration | 12.0 |
| `v_ref` | m/s | reference stall speed the pilot is proven on (default 12.0) | 12.0 |
| `tw_takeoff` | - | static thrust / weight at mission mass | 0.45 |
| `cl_turn_ratio` | - | CL needed in the race turn / CLmax available in that config | 0.80 |
| `n_gust_p90` | - | gust load-factor increment at the P90 gust (13.9 m/s), sharp-edged with alleviation | 1.0 |
| `staging_margin_s` | s | 300 s minus the planned staging time | 120 |
| `energy_reserve` | - | usable energy left at mission end / usable energy | 0.15 |
| `crosswind_ratio` | - | landing crosswind / v_stall | 0.25 |

`complexity`: `"simple"` (fixed-gear single tractor, one flapped wing, conventional tail) plus
any `+`-joined features: `+retract`, `+twin`, `+multi_surface`, `+slotted_flap`, `+fowler`,
`+vtail`, `+pusher`, `+tailless`, `+dr_drum` (default D&R, already in M3 base), `+dr_complex`.
Example: `fm.p_attempt(m, "simple+retract+vtail", mission="M3")`.

Also `fm.p_attempt_breakdown(margins, complexity, mission)` returns each term's logit
contribution, for the PDF.

## 4. `fm.sample_completion(p_m2, p_m3, rng, n, waive_m1=True, p_m1=0.97, p_gm=0.9, attempts=None) -> dict`

Draws completion booleans (n,) for M1/M2/M3/GM from per-attempt probabilities and the flight
attempt budget (default: a distribution over 3-5 official attempts, from the 2022-26 field data
and Sec. 3.3.3 one extra M2 and M3 attempt after all three). Reuses the logic of
`analysis/data/attempts.p_complete`. Also returns `n_m2_scores`, `n_m3_scores` (how many scored
M2/M3 attempts we got, so S12 can take the best of several draws). `fm.p_complete(probs, A)` is
re-exported.

## 5. `fm.day_conditions(n, seed, hour=None) -> dict`

Mid-April (15-18 Apr) conditions at TIMPA for "the day" of an attempt, vectorised (n,):

| Key | Unit | Meaning |
|---|---|---|
| `hour` | h | local time 07-18 (uniform over flying hours unless given) |
| `rho` | kg/m³ | air density (range about 1.04-1.13; from KTUS hourly T, p, dew point) |
| `wind` | m/s | sustained wind (TIMPA-area ASOS, median 3.6-4.1, P90 7.2-8.2) |
| `gust` | m/s | gust when reported, else = wind |
| `xwind_deg` | deg | wind angle off the runway/course axis |
| `temp_c` | °C | temperature |

Helpers: `fm.lap_time_wind_factor(V, wind, r_turn)` (multiplier on a still-air lap time, upwind
and downwind straights plus turn drift) and `fm.crosswind(wind, xwind_deg)`.

## 6. v0 behaviour (LIVE since 27 Oct ~21:00; importable and tested end to end)

- `simulate`: the final structure (Gaussian copula, empirical marginals from the 2022-26 results,
  binomial completion counts, empirical fraction-of-max shapes resampled per mission), with
  provisional loadings `PARAMS`; scale prior lognormal, median 0.80 × aggressive, 90 % range
  0.50-1.29. 5,000 draws: about 1.4 s. `rivals.rival_max` already = 0 when no rival completes.
- `p_first`: final logic (vectorised, max includes ours, tie-break on report score); 0.14 s at 5,000.
- `p_attempt`: logistic plus multiplicative staging/energy OK-probabilities plus per-feature hazards,
  provisional coefficients (`COEF`, `HAZARD`); `p_attempt({}, "simple")` = 0.65 (M2), 0.55 (M3).
- `sample_completion`: attempt budget 3/4/5 with probabilities 0.3/0.4/0.3 and P(airframe out | failed
  attempt) 0.25 (v0 estimates; v1 calibrates them on the 2022-26 attempt statistics).
- `day_conditions`: wind, gust and direction resampled from the IEM hourly observations
  (RYN + AVQ + TUS, 15-18 Apr, 07-18 h, the data behind `wind_timpa.csv`); rho from a provisional
  diurnal model (v1: KTUS hourly T, dew point, altimeter, the `\nRho` method).
- Smoke test (5,000 draws, our M2 0.070 kg/s, M3 24 kg·laps, GM 5.2 kg·m, p_attempt 0.85/0.75,
  report 88): P(mission top) 0.51, P(1st) 0.55, median rank 1. Illustrative only.

Contact: S2. Questions or extra keys needed: write them in `W\early\S2_requests.md`.
