# S12 adapter: plug your model into the mission evaluator (early output, v1, 27 Oct 2026)

Status: **adapter live and regression-locked.** With no overrides it reproduces DB-01 exactly:
0.9 m² straight / 4 kg unit = **6.3326** mean over `s6.draws(120, 2027)`, expected field
(DB-01: 6.33; plateau 1.0/4 = 6.2932 → 6.29 and 0.8/4 = 6.2298 → 6.23; P(M2 feasible) 98 %).
The DB-01 propulsion trade also reproduces: 8S TP3300-8SE55 / AT7215 KV270 / APC 20x15E = 6.367 (6.37),
12S = 6.313 (6.31), twin AT4130 = 6.208 (6.21). Test: `tests/test_v_integration.py` (14 tests, 11 s).
Code: `W\src\integration\adapter.py`. Owner: S12.

## 1. Use it

```python
import sys; sys.path.insert(0, r"C:\Users\Nitro\Documents\GitHub\AIAA_DBF\DB-02_aircraft_variants\src")
from integration import adapter as A

Ps = A.draws()                         # the DB-01 paired draws (120, seed 2027), cached
r  = A.robust(A.REF_D01, Ps)           # {"mean", "p10", "p50", "p90", "p_m2", "totals", "results"}
d  = A.REF_D01.with_(id="mine", s=1.0, unit=5.0, aero=my_aero, propulsion=A.prop_bundle("8s"))
one = A.evaluate(d, Ps[0])             # exactly s6.evaluate's dict (expected/aggressive parts, n_sim, laps ...)
```

Run Python with `PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8`. The adapter also sets
`sys.dont_write_bytecode`. It imports `s4_sizing` / `s6_studies` read-only and never calls a `main()`.

## 2. `Design` (dataclass, SI)

| Field | Meaning | Default |
|---|---|---|
| `id` | label, e.g. `"REF-D01"` | required |
| `family` | `"straight"`, `"delta"` (sizing.toml) or a registered family | `"straight"` |
| `s` | wing reference area, m² (span 1.82 m unless `aero["span_m"]`) | 0.9 |
| `unit` | payload unit = container + declared max sensor, kg | 4.0 |
| `aero` | **S3/S4** `aero(geom)` dict, below | None = family |
| `mass` | **S7** `mass(geom, loads)` dict, below | None = airframe fit 5.96 S^0.94 |
| `propulsion` | **S6** `system(name)` object, or `A.prop_bundle("8s" / "12s" / "twin")` | None = lumped η 0.58 |
| `payload` | **S8** dict, below | None = container 0.6 kg drawn 0.4-1.0, D&R 0.32 kg, 37D reel stow |
| `ops` | `vs_max`, `n_struct`, `cl_margin`, `drop_height_m`, `n_sim_max`, `t_stow_extra_s`, or any `s4.Params` attribute | {} |
| `meta` | tags for the search and reliability: `taper`, `high_lift`, `winglet`, `gear`, `bay`, `prop`, `config`, `tail`, `complexity` | {} |

## 3. What each stream hands over, and how the adapter maps it

The DB-01 draws stay paired (common random numbers). When an override replaces a drawn input, the draw
is carried over either by its **relative factor** or by an **anchored range map** (piecewise-linear
quantile map: the DB-01 low/baseline/high go to your low/central/high), so your central value is used
at baseline inputs.

| Stream | Keys read | Mapping into s4 |
|---|---|---|
| S3 / S4 `aero` | `cd0_parts` {wing, body, tail, gear, other} on S_ref (or `cd0`); `e` (or `k`); `clmax_landing`; `clmax_clean`; `clmax_turn_avail` (optional, used for the turn limit in place of `clmax_clean`); `mass_delta_kg`; optional `f_tow_m2`, `span_m`, `ranges` {`f_body_m2`: [lo, hi], `e`: [lo, hi], `clmax_factor`: [lo, hi]} | wing part → `cd_wing_per_area`; sum of the rest × S → non-wing drag area `f_body` (draw kept as a factor, or range-mapped). `e` replaces Raymer, and the ±10 % e draw stays unless `ranges.e` is given. Stall check uses `clmax_landing`; turn check is `CL_turn ≤ 0.80 × clmax_turn_avail`. CLmax draw (×0.90-1.0625) multiplies both unless `ranges.clmax_factor` is given. `mass_delta_kg` is added to empty mass. |
| S7 `mass` | `airframe` {median, p10, p90} in kg, **on the s4 fit basis**: no battery, payload or D&R; includes a 0.50 kg class motor. Also `growth_bias` (×) and `extra_kg` | The draw's z-score in the fit scatter (×1.31 at 1 sd) is re-applied with your p10-p90 scatter: airframe = median × growth × exp(z σ_new). |
| S6 `propulsion` | `p_batt(thrust_N, V)` (total battery W, NaN where a limit breaks), `pack_kg` (all packs), `wh` (all packs), `motor_mass_delta_kg` (vs 0.50 kg), `layout_penalties` {mass_kg, f_m2}, `thrust_factor` attribute (optional), `t_takeoff_s` (optional), `draw_factors` (True: apply prop_trade's power ×0.92-1.08 / thrust ×0.85-1.15 draws) | Exactly `s4.with_propulsion` plus prop_trade's layout handling: usable energy = 0.80 × wh, layout mass and drag area added. |
| S8 `payload` | `container_kg` (kg, or callable sensor_kg → kg; solved by fixed point for the unit), `container_range_kg` [lo, hi], `dr` {`mass_kg`, `stow_s` (s, or callable(m_sensor_array, P) → s)}, `extra_kg`, `f_m2` (bay drag area) | `container_kg` replaces the 0.6 kg (draw kept as ratio or range-mapped); `dr.mass_kg` → `m_dr`; `stow_s` replaces the 37D reel model inside `s6.evaluate`. |
| S1 | `check(geom, ops)` | Called by the search harness as a gate, not by the adapter. |
| S2 | `p_attempt`, `simulate`, `p_first`, `sample_completion`, `day_conditions` per `S2_api.md` | Used by `integration.scoring` (Phase 1b), not by the adapter. |

## 4. New families without editing sizing.toml

Two equivalent routes, both in-process only (nothing on disk changes):

```python
# (a) register a named family once
def winglet_mono(s, P=None):            # -> (AR, e, CLmax landing, CLmax turn), before the CLmax draw
    ar = 1.82 ** 2 / s
    return ar, 1.10 * A.s3.oswald_straight(ar), 1.6, 1.25
A.register_family("winglet_mono", winglet_mono, clmax_key="straight")
A.robust(A.REF_D01.with_(id="WL", family="winglet_mono"), Ps)

# (b) per design: pass the aero dict (S3/S4 output); the adapter builds the family function
A.robust(A.REF_D01.with_(id="WL", aero=s3_model.aero(geom)), Ps)
```

How it works:
- `DParams` subclasses `s4.Params` (copies a draw; adds `af_kg`, `m_extra`, `family_fn`, `stow_fn`).
- On import, `install()` rebinds `s4.family` and `s4.stow_time` to dispatchers (idempotent).
  - A dispatcher uses the hook the Params carries, then the registry, then the original s4 function.
  - So every DB-01 call is unchanged (a test checks identity per draw).
- `ops` keys that live in `s6.ST["design"]` (drop height, `n_sim_max`, `t_stow_extra_s`) are patched only inside a context manager.
- `A.uninstall()` restores s4.

## 5. Reference designs

| ID | Adapter object | Value (120 draws, expected field) |
|---|---|---|
| REF-D01 (DB-01 control, lumped η) | `A.REF_D01` | 6.33 |
| REF-D01 with 8S | `A.ref_d01_8s()` | 6.37 |
| REF-D01b | `A.REF_D01B` (1.0 m², 5 kg) | computed by the harness |
| REF-RQ4 | needs the S3 aero dict for the CFD mock (S 0.232 m², AR 14.3) | pending S3 |

## 6. Limits you should know

- Physics is DB-01's: constant-speed laps, parabolic polar, lap factor ×1.15 drawn from 24 pairs, stall bound 14 m/s.
- No wind, and no structural load cap beyond the load factor `n_struct`.
- `s6.evaluate` peeks: it picks the simulator count per field scenario and the M3 ballast with the whole draw known.
  - Phase 1b (`integration.timing`) removes that.
  - The adapter keeps it so that DB-01 reproduces.
- `cm0` (trim) is not used yet. S5 trim drag would enter as a `cd0` increment.

Questions or extra keys: write them in `W\early\S12_requests.md` or in your memo; S12 reads both.
