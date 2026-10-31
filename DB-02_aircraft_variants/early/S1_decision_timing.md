# S1 early output: decision timing (v1, 29 Oct 2026)

Audience: the integration agent (S12, phase 1b `integration.timing`). Each decision is modelled using **only what is known when it is made**.
Reference implementation: `W\src\rules\strategy.py` (`INFO`, `FROZEN_AT_FREEZE`, `CHOSEN_AT_TECH`, `CHOSEN_PER_ATTEMPT`, `choose_at_tech`).
Rule line numbers `L<n>` refer to `REPO\analysis\data\raw\aiaa-dbf-2027-rules-draft.layout.txt` (2 Sep 2026 draft).

## 1. Stages, what is revealed, what is chosen

| Stage | When | Revealed before it | Chosen at it | Rule basis |
|---|---|---|---|---|
| **S0 Freeze** | 19 Feb 2027 (design report and configuration drawing) | nothing measured; priors only | span and tip devices, wing configuration, tail type, gear type, tractor or pusher, motor count (FAQ L1693-1704); wing area; **the one physical sensor body, container and simulator hardware and the range of declared masses it can serve [m_lo, m_hi]**; D&R drum and drive; spar strength (tip test at the top of the range) | L638-642, FAQ L1693-1709 |
| **S1 Build and flight test** | Feb-Apr 2027 | airframe mass, CLmax (stall tests), eta (power on the bench and in flight), f_body (drag), e, our lap factor with its residual noise, container mass, stow time | nothing binding; trims the model | L629-633 (must fly before tech) |
| **S2 Tech inspection** | April 2027, before the fly-off | all of S1 | **declared maximum sensor mass m_decl in [m_lo, m_hi]**; **maximum simulator count n_sim_max**; **tip-test mass** (permanent cap, cannot be raised); packs presented (every pack to be flown, L1149-1153) | L578-584, L1144-1147, L1265-1268 |
| **S3 Each flight attempt** | fly-off | S2 plus the day's measured density (met station), wind (windsock, forecast), which attempts are left | simulators flown n_sim <= n_sim_max; prop (diameter, pitch); pack (identical set); M3 ballast m_b <= m_decl; M2 or M3 first order within the rule that missions are in order | L622, L1144-1147, FAQ L1670-1673, L877-887 |
| **S4 Ground Mission** | any time slot the committee gives | S2 and the results so far | **drop height h in whole inches, <= 60 in**; sensor is at the declared maximum (L1002, L998) | L1002-1008 |
| Day-only, unknown at S2 | the attempt | air density rho (design 1.064, range about 1.04-1.13 over the day), wind (median 3.6-4.1 m/s, gust P90 13-14 m/s), the field's maxima, whether the committee rations flights | none: model as noise | `wind_timpa.csv` |

## 2. Information sets (the keys of `strategy.INFO`)

- `freeze_19feb`: [] (priors from the evidence base only).
- `tech_april`: `airframe_kg`, `clmax`, `eta`, `f_body`, `container_kg`, `lap_factor` (the realised factor, with the residual noise of one lap), `e_factor`, `pack_wh_per_kg`.
- `attempt_day`: `rho`, `wind`, `field`. **Not available at tech.** The declared mass must be chosen over a distribution of these.

## 3. Implementation rules for `integration.timing`

1. For each Monte Carlo draw split the draw dict into tech-known keys and day-only keys.
2. **Tech decision** (`m_decl`, `n_sim_max`, tip mass): argmax over candidates of the mean score over day samples, with the tech-known keys fixed at their realised values.
   - Candidate grid for `m_decl`: 0.25 kg steps in [m_lo, m_hi] that the hardware serves (`payload.model.design_for_range(...)["servable"]`).
   - Day samples: the density distribution only (the adapter has no wind). **Plan at a hot density**: our runs show that choosing at rho 1.04 beats choosing at the mean 1.075 by 0.17-0.35 points (section 5).
   - A risk-neutral argmax of the mean is not enough: a heavy declaration that fails M2 on a hot day loses M2, M3 and keeps only GM. Evaluate the P10 as well and take the declared mass with the best mean among those whose P(M2 feasible) >= 0.95.
3. **Attempt decisions** (`n_sim`, prop, pack, M3 ballast): argmax given the tech decision and the day's density. The existing `s6.evaluate` (and `adapter.evaluate`) picks `n_sim` and the M3 ballast **per draw with full knowledge of that draw**, including quantities not known at that attempt. Treat it as an upper bound until you replace it: choose with the day's density known and the airframe parameters known, never with the realised lap factor of the attempt itself.
4. **GM height**: whole inches, `R.drop_inches(h_m)`; the model never declares above 60 in. Declare 60 in unless the container's guaranteed height (ring-to-bottom, C57) is lower.
5. **Waiver of M1**: decided at S3 before the first attempt (strategy.m1_waiver).
6. **The declared mass binds all missions**: M2 must carry "the sensor shipping container with the maximum weight sensor declared" (L524-525), GM uses it (L998), M3 ballast <= it (L447-449). A heavy declaration therefore raises the minimum M2 payload W_min = container + m_decl. It can make M2 infeasible on a hot day (stall bound): P(M2) is the cost of declaring heavy.
7. **Tip-test mass** = empty + heaviest pack + (1 + n_sim_max) x (container + m_decl): choose n_sim_max and m_decl together; the spar is built for the largest value of that sum over the range, not the planned one.

## 4. Reference skeleton

```python
from rules import strategy as S
best_m, scores = S.choose_at_tech(
    score_fn=lambda m, d: adapter_total(design_with_declared(m), draw_with(d)),
    candidates=hardware["servable"],           # 0.25 kg grid
    tech_draw=tech_known_keys_of(P),           # airframe, CLmax, eta, f_body, container, lap factor ...
    day_samples=[{"rho": 1.04}, {"rho": 1.065}, {"rho": 1.10}])
```

## 5. What the adapter says (120 paired draws, seed 2027, expected field; S 0.9-1.2 m2; REF-D01 = 6.3326, REF-D01b = 6.0704)

One physical container per range (150 g sensor, tungsten ballast, 41 mm PE foam, pads re-cut at tech; full table in `memos/08_payload.md`):

| Range, planning density | S 0.9 tech / frozen | S 1.0 | S 1.1 | Mechanism at S 0.9 |
|---|---|---|---|---|
| [3, 6] kg, rho 1.04 | 6.735 / 6.340 | 6.697 / 6.239 | 6.497 / 6.068 | GM 0.99 to 1.40; M2 1.44 (n_sim 0, one unit replaces unit + simulator); M3 2.89; P(M2) 0.975; mean pick 5.46 kg |
| [3, 8] kg, rho 1.04 | 6.764 / 6.297 | 6.702 / 6.197 | 6.530 / 5.987 | GM 1.40; mean pick 6.13 kg; M3 flown at 5.8 kg |
| [3, 6] kg, rho 1.075 | 6.561 / 6.340 | 6.568 / 6.239 | 6.363 / 6.068 | P(M2) 0.933, P10 6.03 |
| [4.4, 10] kg, rho 1.075 | 5.788 / 5.890 | 5.990 / 5.883 | 5.953 / 5.795 | P(M2) 0.725: too heavy; M2 fails on hot draws |

- Declaring at tech beats freezing the declared mass on the same hardware by **+0.40 to +0.47** (S 0.9, rho 1.04) and beats DB-01's REF-D01 by **+0.40 to +0.43**.
- Perfect knowledge of the day (oracle) adds only +0.03-0.08 more at rho 1.04: the hot-day planning rule captures 83-93 % of the value the oracle gets over freezing.
- The gain is almost all **GM** (+0.32 to +0.41 points) because M2 stays flat: one 5-6 kg unit replaces DB-01's unit plus simulator.

Other quantities (all computed with `rules.strategy`, `attempts.py`, `dbf_results.csv`):

- **M1 waiver** (attempt model, p per attempt 0.57-0.73, 3-4 attempts): waiving raises expected total mission by **+0.42 to +1.05 points** and P(M3 completed) from 0.31-0.81 to 0.60-0.94 (table in memo).
- **Lap cliff**: at 39.1 s laps and 8 s take-off, 7 laps holds for any stow up to 18.3 s; an 8th lap needs a lap of 35.0 s or less at 12 s stow. A stow of 30 s drops it to 6 laps and 11.7 s of stow gain restores the 7th.
- **Report versus mission**: Competition = TR x TM. At TR 88 and TM 6.3, one mission point is worth **14.0 report points**; one report point is worth 0.072 mission points (1.1 % of the score versus 15.8 % for a mission point). Winning scores 2022-26 were 501-568, needing TM 5.7-6.4 at TR 88.
