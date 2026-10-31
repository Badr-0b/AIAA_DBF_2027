# S1 early output: hard constraints to design against

- Stream S1 (rules and strategy). Written 27 Oct 2026. Status: **v1, complete for design use**. The memo `memos/01_rules_strategy.md` carries the full matrix.
- **Source:** the 2026-27 rules DRAFT dated 2 Sep 2026 (`REPO/rules/2027_DBF_Rules_Draft.pdf`, SHA-256 `d94773fb…ae1`).
  - Quotes come from `REPO/analysis/data/raw/aiaa-dbf-2027-rules-draft.layout.txt`; **L<n> = line number** in that file.
  - The aiaa.org check for a newer version is recorded in the memo, item A.
- **Machine check:** `W/src/rules/model.py`, function `check(geom, ops)`.
  - It returns FAIL / RISK / WARN / UNVERIFIABLE rows with IDs C01-C99, the same IDs as `out/rules/compliance.csv`.
  - Its constants live in `LIMITS`. The geometry schema is provisional and will be aligned to S9's schema when that lands.
- **Conversions:** exact (1 in = 25.4 mm, 1 lb = 0.45359237 kg, 1 oz = 28.349523 g). Maximum limits are never rounded up.

## 1. Numbers every stream uses

| # | Constraint | Limit (SI, exact) | Rule text | Lines | Grade |
|---|---|---|---|---|---|
| K1 | Wing span | **≤ 1.8288 m (6 ft)** | "Maximum allowable wingspan is 6 feet." | L418 | verified |
| K2 | Take-off gross weight | **< 24.948 kg (55 lb)**. Scored weights are shown to 0.01 lb (§6.2), so the true mass must be **< 24.945 kg** | "must be less than 55-lb" | L627, L1631-1641 | verified |
| K3 | Propulsion energy | **≤ 100 Wh in total** and ≤ 100 Wh per pack (rated capacity × rated voltage) | "shall not exceed 100 Watt-hours" | L771-774 | verified |
| K4 | Fuse, **per propulsion system** | Blade fuse ≤ min(pack continuous current, 100 A). TP3300-8SE55: 3.3 Ah × 55 C = 181.5 A, so the 100 A cap binds | "up to 100 amps" | L776-777 | verified (pack: reseller label) |
| K5 | Multiple propulsion systems | One pack each, **identical packs**, no series/parallel; each system has its own fuse and arming plug | L734-750 | L734-750 | verified |
| K6 | Arming plug | Per system; **top surface**, exposed; **≥ 152.4 mm (6 in) from every prop plane**, where the planes extend beyond the airframe; reached from behind (tractor) or the front (pusher); on the + wire between fuse and ESC | L671-706, L1224-1235 | | verified |
| K7 | Sensor length | **≥ 152.4 mm (6 in)**. There is no diameter or L/D limit | "minimum overall length of six inches" | L441 | verified |
| K8 | Deploy distance (exit point to sensor nose) | **≥ 1.5 × span: 2.743 m at 1.8288 m, 2.730 m at 1.82 m**. If the line attaches a distance d behind the nose, the line must be ≥ 1.5 b + d | L502-504 | | verified |
| K9 | Container ring-to-bottom, **every face** | **< 381 mm (15 in)** for the guaranteed 60 in drop: the container dimension along the drop axis plus the sling height over the opposite face. A "should", so breaking it is a RISK to the drop height (see §3) | L538-542 | | verified |
| K10 | Lifting ring | ID ≥ 12.7 mm, wire ≤ **3.175 mm** (a 3.2 mm metric ring fails), on a 6.35 mm brass pin | L533-535 | | verified |
| K11 | Simulators | Size within **±3.175 mm** of the container; mass within **±28.35 g** of the container plus the **declared** max sensor | L556-560 | | verified |
| K12 | GM drop height | Whole inches, **≤ 1.524 m (60 in)**; six drops onto concrete, two on each face of the die-chosen O/E set | L996-1008 | | verified |
| K13 | Flight windows | 300 s from the first throttle advance. M1: 3 laps. M2: 5 laps. M3: laps × sensor mass; **at least 3 laps** (derived from the light sequence, L958-963). Landing is outside the window | L913-976 | | verified; the M3 minimum is derived |
| K14 | Staging | 300 s; ground crew only; restraints and aircraft ballast fitted beforehand; M3 sensor unpacked and attached inside the 300 s | L798-853 | | verified |
| K15 | Tip test | Lifted at both wing tips at the **declared MGTOW** (about 2.5 g). **The demonstrated mass is recorded and cannot be raised afterwards** | L578-584, L1265-1268 | | verified |
| K16 | Fail-safe at tech | Throttle closed, **full up elevator, full right rudder, full right aileron, full flaps down** | L1288-1302 | | verified |

## 2. Binary rules (pass/fail at tech)

**Flight control and radio**
- No autopilot or flight controller (even in manual mode), no GPS, no camera, no FPV (L598-609, FAQ L1733).
- Stand-alone RC gyros and stabilisers are allowed (L600).
- Telemetry only over the RC link (L605-607).

**Propulsion hardware**
- Electric, propeller-driven, unmodified COTS motor (L595-596).
- Commercial ducted fan units are allowed (L615). Multiple motors are allowed (L611). Gear or belt drives are allowed (L613).
- Commercial props only: clip the tips, balance with paint, ream the bore with a commercial tool (L617-620, FAQ L1717-1718).
- **The prop may change every attempt** (L622).

**Configuration**
- The configuration freezes with the **19 Feb 2027** report and drawing. Changes that are banned afterwards:
  - tricycle ↔ taildragger;
  - tail type (conventional / T / V);
  - wing type (conventional / flying wing / BWB);
  - tractor ↔ pusher, and motor count (FAQ L1693-1704).
- Variable geometry is allowed **only if RC-actuated**. No part swaps between missions (FAQ L1707-1709).
- Only batteries, payloads and payload support may change between missions (FAQ L1670-1673).

**Airframe**
- **One airframe**. Repair only; no copy airframe (L1100, FAQ L1668-1669).
- The contest airframe must have flown before the contest, with video and a signed Pre-Tech/First-Flight form (L629-633, L1105-1120).

**Retention and electrics**
- Hatches need a **positive mechanical latch. Magnets fail**; Velcro is at the inspector's discretion (L1198-1201).
- All parts mechanically fastened, with secondary retention on fasteners and locked clevises (L589-590, L651-654).
- External Rx switch, not under a hatch, and separate from the arming plug (L647-649).
- Separate Rx battery; BEC disabled (L717-720).

**Sensor and payload**
- **Exactly one sensor** (L438). M3 ballast is internal and ≤ the declared maximum (L447-449).
- Fins are fixed, and the external geometry stays the same in all missions (L451-453).
- Three lights, OFF/SOLID/FLASHING (L459-471). The Rx is in the airplane and the electronics and battery are in the sensor (L473-482).
- Carried internally, with nothing outside until the deploy command. If the M3 opening has no door, it may not be covered in M1/M2 either (L484-486).
- The **D&R is internal and permanently installed in its M3 location for all missions** (L497-500).
- **Nothing may drop in flight** (L585-587). A tow-line break counts as a dropped part.

## 3. Derived constraints that other streams must design against (computed by `model.py`)

**S8: the container envelope binds the sensor length.**
- Figure 1 (rules p. 12) shows a four-leg sling from the corners of the top face to one ring.
- Ring-to-bottom on each axis = the container dimension along that axis + (half-diagonal of the opposite face × tan of the sling angle) + the ring (19.05 mm, the smallest legal ring OD).
- **Longest sensor-plus-inner-box** for a container that stays under 381 mm on every axis (80 mm square inner box, 3 mm walls; computed):

  | Foam (rating, from `cushion_report.txt`) | Sling 10° | 15° | 20° | 30° | 45° |
  |---|---|---|---|---|---|
  | 40 mm (150 g) | 255 mm | 244 | 233 | 208 | 159 |
  | 61 mm (100 g) | 208 mm | 195 | 180 | **149 (below the 152.4 mm sensor minimum)** | 87 |
  | 76 mm (75 g) | 174 mm | 159 | 143 | 107 | 0 |
  | 123 mm (50 g) | impossible | | | | |

- **Every container in `cushion_report.txt` breaks 381 mm.**
  - At a 30° sling: 100 g / 202×202×392 mm reaches 494 mm; 150 g / 160×160×350 mm reaches 434 mm.
  - A 392 mm container fails even with no sling at all.
- Consequences:
  - The sensor must be **rugged (≥ 100 g, better 150 g), short (about 155-200 mm) and dense**.
  - The sling must be **low-angle or a rigid low-profile yoke**. Whether a rigid yoke counts as "as shown in Figure 1" is a Q&A item.
  - The sensor mass is not capped by this; only its length and the foam are.
- If the container exceeds 381 mm, the 60 in drop is no longer guaranteed. At 494 mm, only about 55 in is guaranteed if the fixture has no spare travel.
- GM scales with height: 55/60 costs 8.3 % of the GM bonus.

**S8 / S5 / S12: the deploy line.**
- The exit-to-nose distance must be ≥ 2.730 m at a 1.82 m span.
- The line length must add the nose-to-attachment offset and, if verified in flight, the sag.
- Tech documents the "minimum sensor deployment length" (L1327); the method is not stated (Q&A).

**S7: the tip test.**
- The declared tip-test mass = empty + heaviest pack + the heaviest payload ever to be flown: (1 + n_sim,max) × (container + declared max sensor).
- It becomes the **permanent TOGW cap**.
- The spar is sized to pass the tip test at the **highest** MGTOW the team might want to declare, not at the planned one. Declaring lower at tech is free; declaring higher than the spar allows is impossible.

**S5 / S7: the fail-safe load case.**
- Loss of link at M2 top speed (about 29.5 m/s) commands full up + full flaps + full right roll and yaw with the throttle closed.
- Analyse:
  - the flap hinge moment and flap placard at that speed;
  - the peak load factor before stall-limited flight;
  - flutter margin.
- Detailed numbers are in the memo, item C.

**S5: V-tail, elevons and flaperons.**
- These **cannot meet the fail-safe list literally**: full up and full right rudder (or full right aileron, or full flaps down) conflict on a shared surface.
- L1301-1302 lets the inspector accept "the intended function". That is a RISK and a Q&A item. Conventional, T and H tails and separate ailerons and flaps have no conflict.

**S6: twin propulsion systems.**
- Two identical packs of ≤ 50 Wh each.
- Two fuses of ≤ 100 A each, so the fuse-limited power doubles.
- Two arming plugs, each ≥ 152.4 mm from **every** prop plane, with the plane extended across the whole airplane.
- With wing-mounted tractors both planes sit at about the same x, so the plugs go aft on the top surface.
- **Push-pull**: a plug between the two planes is reached from the side, which L1231 bars and FAQ L1712-1714 only conditionally allows. Rated RISK.

**S3 / S4: winglets and tip plates.**
- "Wingspan" is undefined.
- Conventional reading (projected tip-to-tip): vertical extent adds nothing; the lateral component of cant counts.
- Safe fallback: keep the **whole airplane** (cant, tip plates, wing-mounted props) inside 1.8288 m wide. `check()` returns RISK if `max_width_m` exceeds 1.8288 m.
- Biplane, box and joined wings: "one lift point at each wing tip" (L1265) is undefined. Provide tip hard points on the main lifting surface; Q&A item.

**S12: the M3 time budget.**
- Laps = floor((300 − t_TO − t_stow) / t_lap) if the stow counts in the window (conservative), or floor((300 − t_TO) / t_lap) if not (L964-972 is silent).
- At t_TO 8 s, a 39.1 s lap and a 12 s stow: **7 laps** either way.
  - It flips to 8 laps only at a lap ≤ 35.0 s with the stow counted (280/8), or ≤ 36.5 s without (292/8).
  - Details are in the memo, item D.

**S12: decision timing.**
- Declared at tech, not at the 19 Feb freeze: the maximum sensor mass, the maximum simulator count and the tip-test mass.
- Chosen per attempt: simulators flown (≤ declared), M3 ballast (≤ declared), prop, and pack.
  - Packs may change between missions (FAQ L1672: "i.e., batteries").
  - Multiple systems must stay identical within one flight.
- Chosen at the GM: height in whole inches.
- Full specification in `early/S1_decision_timing.md`.

## 4. Open interpretations: design to the safe reading until Q&A answers

| # | Question | Safe design reading |
|---|---|---|
| Q-A | Does stow time after the last M3 lap count in the 300 s window? | It counts |
| Q-B | "No adjustments ... such as opening hatches" (L800-802): may a hatch be opened inside the staging box? | Enter with hatches already open, and close and latch them inside the 300 s; or load through a latch-only door |
| Q-C | Wingspan definition with winglets or tip plates | Overall width ≤ 1.8288 m |
| Q-D | V-tail fail-safe | Full up with the remaining travel as right yaw |
| Q-E | Rigid low-profile rigging yoke vs Figure 1 | A sling of at least 10-15° with legs to the corners |
| Q-F | How the deploy length is verified (static or in flight) | Static exit-to-nose ≥ 1.5 b + 0.10 m margin |
| Q-G | Sensor battery inside a packed container vs the charging-sack rule (L723-727) | Removable sensor battery |
| Q-H | GM attempt timing relative to the flights (one sensor, L438) | Fly the GM after M3 |
