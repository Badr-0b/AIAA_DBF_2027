# Rules Q&A, ranked by points at stake (round 1 opens 1 Nov 2026; 5 questions in round 1, 3 in later rounds, L204-205)

Rank is by the expected total-mission or compliance exposure. Each question lists the safe design assumption we build to until answered.

| Rank | Round | Question (wording for submission) | Why it matters (number) | Fallback design if the answer is adverse |
|---|---|---|---|---|
| 1 | 1 | "How is wingspan measured for an airplane with winglets or tip plates: projected tip-to-tip width, or including vertical extent? Is the 6 ft limit on the whole airplane's lateral extent?" | Winglets are the only way to raise e at fixed span: lap energy x0.916 at e +15 % (ledger O-05). | Overall width <= 1.8288 m with the winglet canted or vertical only; no gain lost on a vertical winglet (lateral extent = span). |
| 2 | 1 | "In Mission 3, is the time to stow the sensor after the last lap inside the 300 s flight window?" | 8 laps need a lap <= 35.0 s if counted, 36.5 s if not; stow 12 s vs 30 s moves 7 laps to 6 at 39.1 s. | Assume it counts; geared brushless drive (3 s stow) if the lap time sits within 4 s of a cliff. |
| 3 | 1 | "Staging says no adjustments such as opening hatches. May a team open or close a hatch or door inside the staging box if no tools are used, to load batteries and payload?" | A wrong reading fails staging; 300 s box. | Enter with hatches open and latch inside the box (latch-only, no tool), or load through a door-free slot. |
| 4 | 1 | "May the rigging be a rigid low-profile yoke or a sling with legs at a low angle, and does the 15 in (381 mm) ring-to-bottom limit apply to a sling to the corners as in Figure 1?" | Every container in DB-01's study broke 381 mm; a 100 g sensor cannot fit at 3-10 kg (worst 385-435 mm at a 15 deg sling). | 150 g-rated sensor, 41 mm foam, 10-15 deg sling to the corners; fall back to a lower declared drop height (55 in costs 8.3 % of the GM bonus). |
| 5 | 1 | "Do spare panels or control surfaces count as 'repair' of the original airplane, and may the sensor's ballast slugs be swapped between M3 attempts?" | A broken surface otherwise ends the day (one airframe, FAQ L1668-1669). | Carry bolt-on, identical spare parts as repair stock; ballast change is already allowed by L447-449. |
| 6 | later | "Is the deploy distance of 1.5 times the wingspan checked statically (exit to nose, with the line straight) or in flight?" | Line length 2.743 m plus the eye offset; static check is the DB-01 assumption. | Static exit-to-nose >= 1.5 b + 0.10 m margin. |
| 7 | later | "May the sensor battery stay in the sensor while the sensor is in the container for the Ground Mission, given the charging-sack rule?" | Compliance of the GM. | Removable sensor battery installed at the lights check. |

Not asked, already answered by the text:
- **Pack changes per mission**: FAQ L1670-1673 allows batteries and payloads and payload support to change; packs must be identical within one flight (L740-741).
- **Gyro**: "Flight stabilization subsystems and rate gyros are allowed" (L600).
