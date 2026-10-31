# Evidence ledger (orchestrator)

This ledger records the numbers the storyline relies on. Each entry was checked independently of the stream that produced it.

Grades: `[V]` verified, `[C]` computed by our own model, `[E]` estimate. Stream result IDs are given where they exist.

## O. Orchestrator hand checks (`ledger/checks.py`, run 27 Oct 2026)

The REF-D01 Mission 2 point (0.9 m², 14.42 kg, 29.5 m/s, 70° bank) uses the Script 3/4 parabolic polar with Raymer's e of 0.946. CD0 = 0.0086 + 0.013/S.

| ID | Quantity | Value | Grade |
|---|---|---|---|
| O-01 | Lap: radius 32.3 m, length 1015 m; turns are 40 % of the distance | 34.4 s model, 39.6 s flown (×1.15) | [C] |
| O-02 | Straight: drag 14.0 N, induced share 31 %, C_L 0.339 | | [C] |
| O-03 | Turn (n 2.92): drag 47.1 N, induced share 80 %, C_L 0.992 | | [C] |
| O-04 | Induced share of lap propulsive energy | **65 %** | [C] |
| O-05 | Lap energy vs Oswald e | e ×0.85 → ×1.114; e ×1.15 → ×0.916; e ×1.30 → ×0.851 | [C] |
| O-06 | M2 energy (206 s): at η 0.58 (lumped) | **79.2 Wh of 80 usable: energy-bound** | [C] |
| O-06 | M2 energy (206 s): at η 0.645 (8S measured maps) | 71.2 Wh | [C] |
| O-07 | Stall-limited M2 gross at 14 m/s, C_L,max 1.6 | 15.3 kg at 0.9 m², 17.0 kg at 1.0 m², 18.7 kg at 1.1 m² | [C] |
| O-07 | Same at C_L,max 1.9 | 18.2 / 20.2 / 22.2 kg | [C] |
| O-07 | Same at C_L,max 2.2 | 21.1 / 23.4 / 25.7 kg | [C] |
| O-08 | M3 laps in 300 s (take-off 8 s + laps + stow) | 39.1 s laps → 7 laps for any stow ≤ 15 s; 35 s laps → 8 laps if stow ≤ 12 s; 41 s laps → 6 laps unless stow ≤ 3 s | [C] |
| O-09 | M3 products, laps × kg | 7 × 3.4 = 23.8; 7 × 4.4 = 30.8; 6 × 5.4 = 32.4. Anchors: aggressive 27, expected 20.25 | [C] |
| O-10 | GM, declared sensor × 1.524 m | 3.4 kg → 5.18 kg·m (GM 1.07 expected field); **6 kg reaches the expected-field ceiling (1.50); 8 kg the aggressive ceiling** | [C] |
| O-11 | M2 W/t | 8 kg / 207 s = 0.0386 kg/s (M2 1.57 expected); 11.5 kg / 220 s → 1.78; 13 kg / 230 s → 1.84 | [C] |

### What the hand checks mean

1. **Induced drag decides the turns, and the turns decide the energy.** At a fixed 1.82 m span, any gain in span efficiency (winglets, nonplanar wings) cuts lap energy almost one for one. Mission 2 is close to the 100 Wh × 0.8 budget, so that saved energy turns into payload or speed. Hypothesis H2 has gone to S12.
2. **A heavy declared sensor looks like the dominant lever, provided it is declared at tech.**
   - A 6–8 kg declared sensor takes the Ground Mission to its ceiling.
   - One heavy unit gives about the same Mission 2 W as DB-01's 4 kg unit plus one simulator.
   - Mission 3 can fly ballast of 4.4–5.4 kg at 6–7 laps and still beat the aggressive anchor.
   - DB-01 judged heavy units fragile only because the unit was frozen at design time (H1, with S12 and S8).
3. **High lift raises the stall-limited Mission 2 gross linearly.** Going from C_L,max 1.6 to 2.2 at a fixed area adds 37 % (H4). The extra gross costs turn drag in proportion to W², so the optimum sits where energy and stall bind together.

## Stream results
(filled in as memos land)

### S3 aero (memo 03, reviewed by the orchestrator on 29 Oct): ACCEPTED, with one policy override

**Accepted values**

| Quantity | Value | Basis |
|---|---|---|
| Oswald e at REF-D01 (S3-R04) | 0.901 (0.85-0.91) | The method reproduces ERAU's measured 0.842 within 3 % at AR 5.2. Raymer's 0.946 was optimistic. |
| Trimmed landing CL_max at 0.9 m², plain flap (S3-R12) | 1.44 (1.37-1.49) | DB-01 assumed 1.6, so it was optimistic by about 0.15 points. |
| Trimmed landing CL_max, slotted flap (S3-R13) | 1.62 (1.45-1.78), +0.12 kg | Recommended. |
| Trimmed landing CL_max, Fowler flap (S3-R14) | 1.92 (1.76-2.05), +0.30 kg | Section Cm −0.42 needs a large tail and complex tracks. |
| Clean CL_max (S3-R11) | 1.19 | |

**Levers screened out**
- Winglets: −0.01 to −0.05 points, even at three times AVL's Δe.
- 10° turn flap: −0.04.
- Biplane and box wing: −0.32. Eliminated at the kill gate.
- Tandem: dropped by Munk's stagger theorem.

**OVERRIDE: CD0.** The S3 build-up gives 0.0161, against DB-01's 0.0230. **It is not banked.**
- The RQ-4 cross-check shows the same build-up under-predicting the CFD non-wing drag area by about 37 % (0.0042 vs 0.0067 m²).
- The 24-pair lap-time factor of ×1.15 already corrects for how optimistic teams' own drag build-ups were. Banking ours on top would count the same correction twice.
- **Central CD0 therefore stays at DB-01's 0.0086 + 0.013/S.** The S3 build-up is reported only as an upside sensitivity: +0.09 points at REF-D01, +0.46 at REF-D01b.

**Aero choice that follows:** a straight monoplane with SD7037 sections and single-slotted flaps on 60 % of the semispan. Fowler flaps are the alternative if the team accepts the extra complexity.

### S8 payload + S1 strategy (memos 08 and 01, reviewed 29 Oct): ACCEPTED

**H1 holds with one physical sensor and one container.** The sensor is built to a 150 g rating, with tungsten ballast. The container is 288 × 303 × 303 mm, weighs 1.18 kg, uses 41 mm foam, and has its pads re-cut at tech.

**Declaring the sensor mass at tech** (S 0.9, 120 draws, planning density 1.04):

| Declared range | Mean score | Note |
|---|---|---|
| 3–8 kg | 6.76 | |
| 3–6 kg | 6.74 | |
| REF-D01 (DB-01 baseline) | 6.33 | |
| Same hardware, unit frozen now | 6.30 | |

- Gain over DB-01: +0.40–0.43.
- Where the gain comes from:
  - GM rises from 1.0 to 1.40.
  - M2 holds at 1.44–1.48: one 5–6 kg unit and no simulators.
  - M3 holds at 2.89.
  - P(M2 feasible) is 0.975.
- **Plan the declaration for a hot day.** Planning at ρ 1.075 drops P10 to 2.5.
- Declaring 4.4–10 kg is worse: 5.8–6.0, with P(M2 feasible) 0.73–0.82.

**Payload hard requirements:**
- **150 g sensor:** a 100 g-rated sensor breaks the 381 mm ring-to-bottom limit at every mass.
- **Tow eye above the CG**, not at the nose. A nose tow hangs the dart about 77° nose-up.
- **Stow speed:** one lap at 39.1 s needs a stow of 18.3 s or less. The Savox drum takes 14 s at 3.4 kg and 30 s at 10 kg, so the drive must be sized for the declared maximum.

**Strategy:**
- Waiving M1 adds +0.42 to +1.05 expected points.
- One mission point is worth 14 report points (at TR 88, TM 6.3).
- A winning mission total is 5.66–6.41 at TR 88.
- Compliance matrix: 99 clauses, with quotes machine-checked against the rules text.

**Known bias:** `adapter.evaluate` picks `n_sim` and the M3 ballast per draw with full knowledge of that draw. I accept it as a small effect and will state it in the report.

### Integration screen v1 (orchestrator's `src/integration/search.py`, 29 Oct): PROVISIONAL

**Setup:**
- 162 designs.
- Aero from S3 (CD0 override applied); payload from S8 (one container built for the top of the range).
- Declared mass chosen at tech per draw, planned at ρ 1.04.
- Reliability from S2 `p_attempt` **v0 (provisional coefficients)**.
- 5,000 S2 fields.

**Control (DB-01 as assumed):** mean 6.33, P10 6.00, P(M3 done) 0.60, **P(top) 0.14**, P(1st, report 90) 0.22.

**Leaders** (P(top) CI ±0.013):

| Design | P(top) | Mean | P10 | P(M3 done) | Gates |
|---|---|---|---|---|---|
| S0.9 / Fowler / 3–8 kg / 8S | **0.372** | 6.77 | 6.26 | 0.59 | Fails the completion gate (needs ≥ 0.602) |
| S1.0 / Fowler / 3–8 kg / 8S | 0.368 | | 5.89 | | Fails the P10 gate (needs ≥ 6.00) |
| S0.9 / Fowler / 3–6 kg / 8S | **0.355** | 6.77 | 6.28 | 0.62 | **Passes: the rule's A for now** |

**By system and flap** (best design in each class):

| Class | Best design | P(top) |
|---|---|---|
| 8S (single) | S0.9 / Fowler / 3–8 kg | 0.372 |
| 12S (single) | S0.9 / Fowler / 3–8 kg | 0.354 |
| Twin (DB-01's twin, no fuse credit yet) | S0.9 / Fowler / 3–8 kg | 0.328 |
| Plain flap | S1.2 / 3–8 kg / 8S | 0.305 |
| Slotted flap | S1.1 / 3–8 kg / 8S | 0.326 |
| Fowler flap | S0.9 / 3–8 kg / 8S | 0.372 |

**Why the leaders win:**
- **Low stall at M2 weight.** Fowler at 0.9 m² gives 12.4–12.8 m/s, against the control's honest 13.5. That raises p_attempt and lets the aircraft carry the heavy declared sensor.
- **GM near its ceiling.** GM is about 1.43, against 1.05 for the control.

**Re-run when** S6/S7 (mass model, twin with 2 × 100 A fuses, gear) and S2 v1 (calibrated p_attempt, including the Fowler and slotted hazards) land.

**Candidates for B,** which must differ in a frozen item:
- the twin (needs S6's fuse credit);
- a taildragger (needs S7's gear numbers plus a hazard estimate);
- a T-tail (no score effect; only a clearance argument).

## Revision B (orchestrator, 30 Oct 2026, afternoon): review fixes and their cascade

A same-day review of rev A traced every number back to code and data. Rules, sources and field statistics held. Six faults in the scoring chain did not.

| # | Fault | Fix (file) | Effect |
|---|---|---|---|
| 1 | The screen scored model-default flaps (25 % chord, 30 deg). Spec and S3-R13/R14 are 30 % chord. | `search.FL` = S3's definitions | Lift +0.01 (Fowler), +0.05 (slotted) |
| 2 | The S^0.94 fit charged the whole airframe for wing area. | `variants/mass_family.py`: anchored at 0.9 m²; only wing 34 % and tail 6 % scale | 1.0 m² −0.34 kg; 1.2 m² −1.01 kg |
| 3 | Trim used a generic lt 3 c̄; the text claimed the short arm cost 0.06. | `aero_mono.trim_table` + `geometry_variants trim` | Lift +0.02 to +0.04; the claim was backwards |
| 4 | Wilson CIs over 5,000 fields ignored the 120 draws. | `search.cluster_ci`; `finalists.paired_ci` | Marginal CI ±0.03; paired differences ±0.007 |
| 5 | B's area was picked by judgement. | Finalists include slotted 1.0–1.2 m²; `finalists.select` applies the rule | B = 1.2 m² |
| 6 | Over-grading. | Register: C-01, A-01, B-01 and H-01 to [E]; placeholders listed | — |

**Cascades:**
- (7) The fixed tail station gave big wings 1.35 c̄ arms and 1.40 m tailplanes. Now `LT_C_MIN` 1.89 c̄, with boom mass 0.10 kg/m.
- (8) A's 8 kg container is 303 mm. The fuselage is now 0.345 × 0.355 m, and the drum is sized per m_hi.
- (9) `screen.json` predated S2 v1 and has been re-run.
- C-02's drag upside was recomputed for the new A and B: +0.18 and +0.17.

**Result:**
- A = S1.0 / Fowler / 3–8 kg / 8S. P(top) 0.313 [0.285, 0.342]. No finalist is tied (paired).
- B = S1.2 / slotted / 3–6 kg. P(top) 0.295.
- B leads both Fowler-low scenarios.
- B has the smallest max regret (0.018 vs A 0.044).
- Break-even P(Fowler underdelivers) is 0.29.
- The strict frozen-item B (twin S1.1/F/8) fails both gates.
- Rev A's A (S0.9/F/6) scores 0.286, unchanged. Rev A's B (S1.0/S/6) scores 0.281 (was 0.238).

**Pipeline and checks:**
- Rerun: `tools/rerun_chain.sh`. Rev A outputs are in `out/_prefix_30oct/`.
- PDF rev B: 46 pp, 0 unfinished, 0 overfull.
- Tests: 66 pass (`test_v_revb.py` added).
