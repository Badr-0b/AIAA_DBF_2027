# DB-02 storyline: the argument spine (orchestrator; draft 29 Oct 2026)

The writer turns this spine into prose, following these rules:
- Every number comes in through `\val{ID}`. Chapter numbering follows the brief, §10.
- The register is layered. Each decision gets the plain "why" first, then the engineering, then a derivation panel.
- Keep the voice calm, exact and confident. Write without hype, and state every claim to the strength of its evidence grade.
- Credit the user's ideas by name and date.
- No em dashes. Do not use "it's not X, it's Y". SI units throughout.

## 0. Thesis (cover deck + executive summary)
**Thesis.** The 2027 contest rewards three things, in this order:
1. **finishing every mission** (completion carries 55 % of the score weight, S6 trade weights);
2. **carrying a heavy sensor declared at the last legal moment**;
3. **a wing big enough, and with enough lift, to land that payload slowly**.

Speed matters less than any of these. Both variants are built on that reading. They differ in how they carry the risk.

**Headline numbers** (finalists TBD):
- the score each variant can reach;
- P(highest mission total) against 5,000 simulated fields, compared with the DB-01 control at 0.12;
- P(1st) at a report score of 90;
- what the team has to sign, and when.

## 1. What wins in 2027 (scoring primer with a worked example)
- **The formula.** M1 + M2 + M3 + GM, maximum 7.5. Each bonus is a ratio to the field maximum, and the maximum includes our own result.
- **Worked example.** Take the DB-01 control: 1 + 1.43 + 2.85 + 1.05 against the expected field. Then show how one heavy sensor changes GM, M2 and M3.
- **Report × Mission.** One mission point is worth 14 report points (S1).
- **Completion data.** In 2026, 17 of 83 teams completed every mission. P(M3 | M2) has run 0.35–0.66. Attempts are scarce: 2.4–2.9 official attempts per team.
- **Winning totals.** Winners' mission totals were 5.61–6.80. A winning total at report 88 needs 5.66–6.41 (S1).

## 2. What changed since DB-01 (honest corrections)
- **CLmax.** The plain-flap CLmax is 1.44 trimmed, against the 1.6 assumed, which cost about 0.15 points. Slotted flaps recover it, at 1.62 (S3).
- **Oswald e.** 0.90 against Raymer's 0.946, validated on ERAU's measured 0.842 (S3).
- **Container.** The DB-01 100 g container breaks the 381 mm drop envelope. The sensor must be rated to 150 g (S8).
- **Freezing the unit.** DB-01 froze the unit, which made heavy sensors look fragile. Declaring at tech is worth about +0.4 (S8 H1).
- **CD0.** The S3 drag build-up is lower than DB-01's figure, but it is NOT banked. The RQ-4 cross-check and the 1.15 lap factor already correct for that kind of optimism (orchestrator, ledger 05).
- **Propulsion and fuse.** S6 (pending).
- **Reliability.** No longer a flat 0.65. It now depends on stall speed, thrust-to-weight and complexity (S2).

## 3. Evidence and method
- **Data sources:**
  - 1,008 verified values from the AIAA reports;
  - 513 results rows;
  - UIUC / NACA TN 663 / TR 534 / TR 664;
  - MIL-HDBK-304B;
  - T-Motor and APC maps;
  - TIMPA weather;
  - the RQ-4 CFD.
- **Models:**
  - Scripts 1–6 and 3b, plus the DB-02 streams;
  - the adapter, regression-locked to DB-01's 6.3326;
  - common random numbers;
  - decision timing.
- **Evidence-grade legend:** verified / reseller / estimate / computed.
- **Model limits.** Bias: `n_sim` and M3 ballast are chosen per draw. Field anchors are estimates. Report scores are assumed.

## 4. Design space and eliminations (cards with kill reasons)
- **RQ-4 proportions** (the user's reference family, credited, 10 Oct). The CFD gives CLmax 0.89 on 0.232 m², so landing 7 kg needs about 25 m/s. Show the CFD images plus the quality box. What survives from the RQ-4 is a styling language only, and only where it is free: body shape costs about 0.01 points per 10 cm² of drag.
- **Delta / flying wing / BWB.** 4.60 vs 6.29 (DB-01).
- **Biplane / box wing.** −0.32 at the kill gate (S3-R22).
- **Tandem.** Munk's stagger theorem.
- **Winglets.** −0.01 to −0.05.
- **Turn flap.** −0.04.
- **Pusher.** Tow-line ingestion hazard (DB-01 R9).
- **Twin.** S6 verdict pending.
- **Retract gear.** Break-even only below 120–240 g (DB-01).
- **Heavy frozen unit.** Superseded by declaring at tech.

## 5. Shared decisions (both variants; decision cards)

| ID | Decision | Basis |
|---|---|---|
| D-S1 | Waive M1 | +0.42 to +1.05 expected (S1) |
| D-S2 | Declare the sensor at tech, planned on a hot day (ρ 1.04) | Range 3–8 kg; pads re-cut at tech (S8) |
| D-S3 | Sensor rated 150 g; tungsten ballast; 170–210 mm long; tow eye above the CG | S8 |
| D-S4 | One container, 288 × 303 × 303 mm, 1.18 kg | S8 |
| D-S5 | Adjustable-ballast simulators | They make the tech declaration real |
| D-S6 | D&R closed-loop drum with slip ring; drive sized for the declared maximum | Stow ≤ 18.3 s keeps the lap (S8) |
| D-S7 | Drop height 1.524 m | GM linear in h |
| D-S8 | ExpressLRS PWM with fail-safe set per output | Already decided 8 Oct |
| D-S9 | Airfoil SD7037 | Trip-insensitive; best L/D at CL 0.4–0.8 (airfoil study, UIUC) |

## 6–7. Variant A and Variant B
Finalists come from the S12 screen, pending.

**Per variant:**
- spec spread;
- decision cards: wing area, flaps, propulsion, gear/tail/wing position, bay and door, structure, operating modes;
- mass and CG;
- AVL stability;
- per-mission plan;
- scores;
- risks;
- build plan.

## 8. Head-to-head
- The regret table across scenarios.
- Break-even: where A and B swap.
- A P(1st) tornado.
- The recommendation, and the dated switch condition.

## 9. Decision calendar and mission-day playbook

| When | What is decided |
|---|---|
| 19 Feb freeze | Geometry |
| Tech | Declared mass (hot-day plan); simulator count = 0 or 1; tip-test mass = M2 gross at the declared maximum |
| Each attempt | Simulators flown; prop; M3 ballast; wind and density thresholds |

## 10. Tests, gates, schedule
- **TC-01:** tow stability with the eye above the CG.
- **TC-02:** 150 g drop at 3 and 8 kg, re-cut pads.
- **TC-03:** lights in sun.
- **TC-04:** staging drills.
- **TC-05:** reel cycles, with stow time at 8 kg.
- **TC-06:** propulsion bench and fuse.
- New: weigh-in and flight-test gates with kill criteria.

## 11. Q&A, glossary, sources, appendices
- Q&A: 5 round-1 questions, ranked (S1 `qa_ranked.md`).
- Sources: from `W/sources/*.toml`.
