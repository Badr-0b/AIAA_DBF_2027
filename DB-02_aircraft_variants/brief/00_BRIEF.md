# DB-02 shared brief: two aircraft variants for the 2027 fly-off

**Every agent in this effort reads this file first.**
- Written by the orchestrator on 27 Oct 2026, 19:15 (+03).
- Repo: `C:\Users\Nitro\Documents\GitHub\AIAA_DBF`, called **REPO** below.
- Work folder: `REPO\DB-02_aircraft_variants`, called **W** below.

## 1. What we are making and why

The team lead (Badr Ob, "the user") leads an AIAA Design/Build/Fly team. The 2026-27 theme is **"UAV with Sensor Suite"**: a towed sensor, a span of at most 1.829 m (6 ft), and a fly-off on 15-18 Apr 2027 at TIMPA, Tucson.

**The request (27 Oct):**
- Go through all the available data.
- Propose **at least two aircraft variants built to win outright** ("complete overwhelming victory").
- Deliver **one new, separate PDF** that shows the decisions that were made and *why*, with the reasoning written in plain language and backed by data. There is no page cap.

**Context:**
- The proposal (`REPO\proposal\`) is a different document. **Never touch it.**
- The incomplete CFD of the RQ-4-style CAD is to be used, with images.

**Deliverable:** `W\report\DB-02_aircraft_variants.pdf` (document ID OBTEL-DBF-27-DB-002, rev A). Its look is described in §9.

## 2. Hard rules for every agent (user directives; breaking one is a failure)

1. **Write ONLY inside `W`.** Read anything in the repo, but create or modify nothing outside `W`.
   - Allowed exceptions: WSL run directories under `/home/nitro/dbf_cfd/` (S10 only), the system temp folder and your scratchpad.
   - Set `PYTHONDONTWRITEBYTECODE=1` for every Python run so no `__pycache__` appears elsewhere.
   - Never call an existing script's `main()` or entry point. They write to tracked files in `REPO\analysis\out\` and `REPO\proposal\`.
   - Import functions instead, and redirect any output path into `W\out\<stream>\`.
   - If an imported function writes a cache (e.g. XFoil work directories), monkeypatch its path or copy the logic.
2. **No git commits, no staging, no branch changes.** Never run `git add`, `commit`, `stash`, `checkout`, `reset` or `clean`.
3. **Never modify** `REPO\proposal\`, `REPO\decisions\`, `REPO\analysis\` (inputs, out, scripts or tests), `REPO\design-system\`, `REPO\cfd\` or `REPO\claude_docs\`.
4. **SI units only:** m, kg, s, N, W, Wh, Pa, kg/m³.
   - Rule limits are written as "1.829 m (6 ft)".
   - Exact conversions: 1 ft = 0.3048 m, 1 in = 25.4 mm, 1 lb = 0.45359237 kg, 1 oz = 28.349523 g.
   - Never round a maximum limit up.
5. **Data accuracy.**
   - Every number carries a source and a date checked, and is graded `verified` (read in a primary source), `reseller` (retail listing only) or `estimate` (a reasoned range, with its derivation).
   - **Never invent a number.** If none is found, say so and use a labelled range.
   - Quote the rules verbatim from `REPO\analysis\data\raw\aiaa-dbf-2027-rules-draft.layout.txt` (the 2 Sep 2026 draft, the latest official version).
   - Prefer primary literature (NACA/NASA NTRS, UIUC LSATs, theses, handbooks) and validated tools (XFoil, AVL, OpenFOAM against data).
6. **Leanings are not decisions.**
   - The team has *leanings*: high wing, tricycle gear, an RQ-4/MQ-9 look, V or twin tail, a nose storage bay, retractable gear. They are not decisions. The configuration is chosen from data.
   - We *recommend*. The decision record in the PDF is left for the team to sign.
7. **Credit the user's ideas by name and date** in anything written for the team. Examples:
   - the RQ-4/MQ-4C/MQ-9 reference family (Badr Ob, 10 Oct 2026);
   - the nose bulge as a storage bay (10 Oct);
   - retractable tricycle gear (10 Oct);
   - the "retarded bomb" sensor idea, which became a fixed-geometry dart (11 Oct);
   - ground tracking as flight-test instrumentation (10 Oct).
8. **No institutional or national framing.** Name the university only where the house class requires it.
9. **Windows and WSL traps:**
   - Use `PYTHONIOENCODING=utf-8`.
   - Patch files with the Edit tool, not bash heredocs, which mangle backslashes.
   - `.sh` files must use LF line endings. Python `Path.write_text` writes CRLF unless you pass `newline="\n"`.
   - Run multi-command WSL work as `wsl -d Ubuntu -- bash <file.sh>`, never `bash -c '...'` from PowerShell.
   - Never wrap OpenFOAM's `etc/bashrc` in `set -u`.
   - From Git Bash, `/mnt/c` paths get rewritten. Use PowerShell to call `wsl`.
10. **Compute discipline:**
    - Only S10 launches CFD. It uses the detached `Start-Process wsl.exe ... sweep.sh` pattern, **never** a Claude Code background task, because those die with the session.
    - CFD gets 6 cores. Other agents run at most 3 heavy jobs at once (anything over about 2 min of CPU), each with at most 4 processes.
    - Keep the disk small: WSL meshes are deleted after harvest, and C: has about 11.7 GB free.
11. **Installs:** use only what is present (Python 3.14.3, numpy 2.4.4, scipy, matplotlib 3.10.9, shapely; `REPO\analysis\tools\xfoil.exe` 6.99 and `avl352.exe` 3.52; OpenFOAM 14, ParaView 5.11.2 and gmsh in WSL Ubuntu; MiKTeX XeLaTeX; pdftotext and pdftoppm).
    - If a pip package is truly needed, install it and log it in `W\tools\INSTALLED.md`: package, version, why, and the uninstall command.
12. **Writing style for anything that reaches the PDF:**
    - no em dashes;
    - no "it's not X, it's Y" phrasing;
    - captions state the takeaway, not the topic;
    - no unquantified adjectives;
    - no fake classification markings.

## 3. Folder layout inside `W`

| Path | What goes there | Owner |
|---|---|---|
| `brief/` | This brief and the orchestrator's notes | orchestrator |
| `early/` | **Phase-1a early outputs** that other streams depend on (see §7) | the named stream |
| `memos/NN_<stream>.md` | Each stream's findings memo (format in §8) | each stream |
| `ledger/` | Evidence ledger and finalist and storyline documents | orchestrator |
| `src/<stream>/` | Python package per stream (`model.py` plus helpers); import-safe with no side effects | each stream |
| `tests/test_v_<stream>.py` | unittest tests per stream (pytest is not installed) | each stream |
| `out/<stream>/` | `results.json`, CSV, figures and run logs | each stream |
| `cfd/` | CFD case setups, local tool copies, harvested results and images | S10 |
| `report/` | The PDF: master .tex, style layer, `sections/`, `figures/`, `data/`, `build/` | S11 (and S17 owns `report/sections/`) |
| `sources/<stream>.toml` | New sources: id, title, author, year, URL or DOI, date read, what was used, nature (MEASURED / SPEC / COMPUTED / RULE / METHOD) | each stream |
| `tools/INSTALLED.md` | Install log | anyone who installs |

**Imports.** Put `W\src` on `sys.path` and import modules as `<stream>.model`. Existing analysis code is imported read-only:

```python
import sys; sys.path.insert(0, r"C:\Users\Nitro\Documents\GitHub\AIAA_DBF\analysis")
import s4_sizing as s4, s6_studies as s6, s3_performance as s3, s3b_propulsion as s3b, common
```

Check whether module import has side effects before relying on it.

**Tests.**
- Run with `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s W/tests -p "test_v_*.py"`.
- Also confirm the existing suite still passes, read-only: `PYTHONDONTWRITEBYTECODE=1 python REPO/analysis/check.py` (121 tests).

## 4. Rules facts (the 2 Sep 2026 draft; quote the layout text, verbatim, for anything you rely on)

**Scoring (§6.3).**
- Competition = TotalReport × TotalMission + Participation.
- TotalReport = 0.15 × Proposal + 0.85 × Design Report, so report quality multiplies the mission score.
- TotalMission = M1 + M2 + M3 + GM, with a maximum of 7.5.

| Score | Formula | Notes |
|---|---|---|
| M1 | 1.0 | 3 laps, no payload, in 5 min. **May be waived**: a successful M2 then also scores M1, but you cannot go back to M1 if M2 fails. |
| M2 | 1 + (W/t) / max(W/t) | W = sensor-in-container plus the simulators flown. t = 5 laps, timed from the first throttle advance for take-off, so the ground roll is included. |
| M3 | 2 + (laps × sensor weight) / max | Within 300 s, with the light sequence. At least 3 laps are needed (derived). |
| GM | 0.5 + (declared max sensor weight × drop height) / max | Height ≤ 1.524 m (60 in) in whole inches. 6 drops (2 per face, die picks the O or E faces) onto concrete. Any damage or light malfunction fails it. One extra attempt. |

- **The maximum includes our own result.** Each mission's maximum may come from a different team; past maxima were often set by teams outside the top 5.
- Rounding (§6.2): s, in, oz and lb to 2 decimals.

**Course (§3.3.3).**
- Markers are 152.4 m (500 ft) either side of the start line, giving 609.6 m of straights per lap.
- Each lap has two 180° turns plus one 360° turn on the downwind leg.
- The aircraft must be straight and level passing each marker.
- Take-off and the near leg are upwind.
- **There is no take-off distance limit.**
- Landing must be on pavement. Run-off is OK; a bounce off the runway is not. "Significant damage" means no score.
- After all three flight missions, one extra attempt each for M2 and M3. The committee may ration flights.
- Teams that passed tech got only **2.4-2.9 official attempts each** in 2022-26. 57-73 % of attempts scored.

**Aircraft (§3.1-3.2, FAQ).**

| Topic | Rule |
|---|---|
| Size and mass | Span ≤ 1.8288 m. TOGW **< 24.948 kg** (55 lb). |
| Propulsion | Electric, propeller-driven, unmodified COTS motor. Commercial props; tips may be clipped; diameter and pitch may change per attempt. **Commercial ducted fans OK. Multi-motor OK.** |
| Batteries | **Total propulsion energy ≤ 100 Wh** and ≤ 100 Wh per pack. One pack per propulsion system; multiple packs identical, no series or parallel. |
| Fuse | Blade fuse rated ≤ min(pack continuous rating, 100 A) **per system**. |
| Electrical | Separate Rx battery, BEC disabled. External arming plug per system on the **top surface, ≥ 152.4 mm from any prop plane**. External RC switch. |
| Flight control | **No autopilots, flight controllers (even in manual mode), GPS, cameras or FPV. Flight stabilization subsystems and rate gyros ARE allowed.** Telemetry only through the RC link. |
| Variable geometry | Allowed if RC-controlled. No swapping parts between missions. Thrust vectoring allowed and may vary in flight. |
| **Configuration freeze (FAQ A.2)** | **Major changes after the design report (19 Feb 2027) are banned:** tricycle ↔ taildragger; tail type (conventional, T, V); wing configuration (conventional, flying wing, BWB); tractor ↔ pusher or motor count. |
| **One airframe** | One airframe only; after damage "you must repair the original airplane". Must have flown before the contest (video plus signed Pre-Tech/First-Flight form). |
| Fastening and hatches | Mechanical fastening with secondary retention. Hatches need a positive mechanical latch; **magnets are not acceptable**. |
| Fail-safe (§4.2.5) | Throttle closed, **full up elevator, full right rudder, full right aileron, full flaps down**. A V-tail cannot give full up and full right rudder at once. |
| Tech tip test (§4.2.4) | At MGTOW, lifted by the wingtips, roughly a 2.5 g case. **The demonstrated maximum mass is recorded and cannot be raised later.** |
| Nothing dropped in flight | A tow-line break is a dropped part. |

**Sensor, D&R, container and simulators (§3.1.1-3.1.3).**

| Topic | Rule |
|---|---|
| Sensor | **Exactly one.** Length ≥ 152.4 mm. **No diameter or L/D rule** this year. Must be aero-stable: fixed orientation in the horizontal plane, not spinning, and "no effect on the stability of the aircraft". Fixed fins and wings allowed but not removable or deployable. Ballast internal. M3 weight may vary per attempt up to the **maximum declared at tech** (§4.1). |
| Tow line and lights | The line is both mechanical and electrical. Rx in the aircraft. Light electronics and battery inside the sensor; the battery is COTS, labelled and in a sack. Three lights (fwd, centre, aft), each OFF / SOLID / FLASHING, commanded by the flight Tx or a second payload Tx run by the Observer. |
| Carriage | Internal. Nothing protrudes until deployed. If the M3 opening has no door, it may not be covered in M1 or M2. |
| D&R mechanism | Internal, **permanently installed in its M3 location for all missions**. Deploy ≥ 1.5 × span, measured from the exit point to the sensor nose: 2.743 m at 1.8288 m, 2.73 m at the 1.82 m design span. |
| M3 sequence | Deploy with lights OFF before the first downwind 180. After lap 1, SOLID before the next upwind turn. After lap 2, FLASHING. After the final lap, OFF, and **fully stowed before landing**. Whether stow time counts in the window is ambiguous; the model assumes yes. |
| Container | Rectangular prism, "TOP" marked, O/E face pairs. One metal lifting ring: ID ≥ 12.7 mm, cross-section ≤ 3.175 mm, on a 6.35 mm brass pin. **Ring-to-bottom distance "should be less than 15 inches" (381 mm)** to guarantee the 60 in drop, which caps sensor length plus cushion. Attachment features flush or recessed. |
| Simulators | Same size ±3.175 mm and same weight as container plus max sensor ±28.35 g. Count declared at tech. **Container mass counts in M2's W.** |
| Staging (§3.3.2) | 5 min; only the ground crew member touches the aircraft. "No adjustments ... such as opening hatches" (ambiguous). Ballast installed before staging. In M3 the sensor arrives packed and is attached within the 5 min. |
| GM | Quick release about 1.22 m above the floor. Only rigging, re-rigging, latching and final unpacking are timed. |

**Site:**
- **ρ = 1.064 kg/m³** (design; a 1-in-10 hot afternoon; typical afternoon 1.081). The time-of-day range is about 1.04-1.13.
- TIMPA is at 667 m.
- Wind: median 3.6-4.1 m/s, P90 7.2-8.2, gust P90 about 13-14 m/s (`REPO\analysis\data\wind_timpa.csv`).
- Sun is bright, so light visibility matters.

**Dates:**

| Date | Event |
|---|---|
| 31 Oct 2026 | Proposal due (another track; do not touch it) |
| 19 Feb 2027 | Design report and configuration drawing; **configuration freezes** |
| April 2027 | Tech: the max sensor weight, simulator count and tip-test mass are declared |
| 15-18 Apr 2027 | Fly-off |

## 5. Current model and evidence (read the sources; these are pointers, not gospel)

**Pipeline in `REPO\analysis\`** (README there):

| Script | Content |
|---|---|
| `s1_course` | Lap geometry: lap = 609.6 + 4πr, r = V²/(g tanφ) |
| `s2_scoring` | Mission scores |
| `s3_performance` | Polar and lap power |
| `s3b_propulsion` | APC + T-Motor maps |
| `s4_sizing` | `Params`, `m2_search`, `m2_fixed`, `m3_search`, `stow_time`, `family` |
| `s6_studies` | `evaluate(fam, s, unit, P, field=None, n_sim=None)`, `draws(n, seed)`, `robust_map`, `best_unit`, `fields()`, `expected_total` |

**Inputs:** `REPO\analysis\inputs\*.toml`.
- In sizing.toml, span is 1.82 m, AR = b²/S, and e comes from the Raymer straight-wing formula (about 0.95 at AR 3.7, optimistic; ERAU measured 0.842 at AR 5.2 against Raymer's 0.89).
- CD0 = 0.0086 (wing, per area) + f_body/S, with f_body = 0.013 m² (estimate, 0.006-0.028).
- CLmax: flapped 1.6, clean 1.25.
- Stall bound 14 m/s (estimate, the biggest lever).
- η 0.58, calibrated on one flight.
- Lap-time factor ×1.15, from 24 measured/predicted pairs.
- Airframe mass = 5.96 S^0.94 kg, ×1.31 scatter at 1 sd (n = 14).
- 100 Wh at 80 % usable.
- D&R mechanism 0.32 kg flies in every mission.

**Robust optimum (`s6_report.txt`, DB-01):**
- 0.9 m² straight flapped wing with a 4 kg unit (3.4 kg sensor + 0.6 kg container).
- Mean 6.33/7.5 over 120 draws against the expected field. P(M2 feasible) 98 %. Plateau 0.8-1.0 m².
- Reference with baseline inputs: M1 1 + M2 1.57 + M3 3.00 + GM 1.07 = 6.64.
- M2 is flown at 8 kg W (unit plus 1 simulator) in 207 s: 14.42 kg at 29.5 m/s, 70° bank (n 2.92). Drag is **14.0 N straight and 47.1 N in turns** (about 80 % induced in turns; turns are about 40 % of the lap).
- M3: 7 laps × 3.4 kg, 9.82 kg at 26.5 m/s, 72° bank, 39.1 s laps as flown. With a 12 s stow this sits close to the integer-lap cliff.

**Sensitivity:**
- Tornado: the stall bound is the only cliff, and each +1 m/s of accepted stall is worth +0.13-0.15. CLmax −10 % costs −0.24. Field maxima move it +0.29/−0.21; the lap factor ±0.25.
- Spearman: lap factor −0.68, airframe mass −0.64, η +0.20, container −0.20.

**DB-01** (`REPO\decisions\DB-01_sizing_and_configuration.tex`; unsigned recommendations):

| ID | Recommendation |
|---|---|
| D1 | 0.9 m² |
| D2 | 14 m/s stall |
| D3 | 4 kg unit |
| D4 | Waive M1 |
| D5 | Design for 1.524 m drop |
| D6 | High wing |
| D7 | Conventional tail |
| D8 | Fixed faired tricycle gear |
| D9 | Single tractor |
| D10 | Door unless the slot drag is < 2.4-4.1 cm² |
| D11 | Body from packaging |
| D12 | Closed-loop drum (A) |

- Risk register R1-R12.
- Exchange rate: 10 cm² of drag area = 123 g = about 5.3 s of M2. 1 s of M2 = 0.0028 points.
- Retractable gear breaks even only below 120-240 g.

**Since DB-01 (`REPO\claude_docs\` handoffs, `evidence_plan.md`):**
- **CLmax** (`analysis/out/wing_clmax_report.txt`; UIUC + NACA TN 663 calibration):
  - SD7037 section Cl_max is 1.22-1.30 measured and trip-insensitive. SD7062 is 1.66 smooth but −24-27 % with a trip.
  - Wing at 0.9 m², taper 0.7, 60 % span plain flap at 30°: 1.44-1.56, **trimmed 1.34-1.56**. At 70 %/40°: 1.55-1.68.
  - Optimum unchanged; mean 6.10-6.38.
- **Mass** (`mass_breakdown_report.txt`): 16 top-3 aircraft. Shares: wing 34 %, fuselage 24 %, propulsion 20 %, gear 9 %, avionics 8 %, tail 6 %. Wing 1.94 kg/m² median. Bottom-up for 0.9 m² is 5.32 kg (4.14-6.98).
- **Propulsion** (`prop_trade_report.txt`):
  - Best: **8S Thunder Power TP3300-8SE55 + T-Motor AT7215 KV270 + APC 20x15E**: MC mean 6.37; 101 N static; 2.7 s / 23 m take-off roll.
  - 12S (MaxAmps 2000 + KV200): 6.31; that pack is capped at 54 A.
  - Twins lose in 95-98 % of draws, **but that trade used 2 × 50 Wh 6S packs and did not credit two 100 A fuses**.
  - **With real 8S propulsion the optimum moves to 1.0 m² / 5 kg (6.41).**
  - Unverified: the Littelfuse MAXI voltage ratings (100 A part reportedly 32 V).
- **Container** (`cushion_report.txt`, MIL-HDBK-304B, PE 2 pcf): for a 3.4 kg sensor at 1.524 m:

  | Sensor g rating | Foam | Container | Mass |
  |---|---|---|---|
  | 50 g | 123 mm | 55 L | 0.80-2.04 kg |
  | 100 g | 61 mm | 202 × 202 × 392 mm | 0.52-1.08 kg |
  | 150 g | 40 mm | 9 L | 0.42-0.81 kg |

  - The **392 mm length breaks the < 381 mm ring-to-bottom envelope.** Recheck it.
- **D&R** (`dr_trade_report.txt`):
  - Closed-loop drum A: encoder, stop bead, slip ring, docking latch.
  - Pololu 37D 70:1: 322 g, 7.5 s deploy, 11.9 s stow. Savox (reseller): 204 g, 14 s stow.
  - Line tension 33.5 N at n 1, 108 N at n 3.24, 133 N at n 4.
  - Catastrophic failure per M3 attempt: A 1.3 %, B 2.5 %.
- **Tow stability:** NACA TM 832 guidance is heavy, compact and damped, with small fins far aft. Barrowman equations are located.
- **Airfoil study** (`REPO\dbf_airfoil_study_handoff\dbf_airfoil_study\`): XFoil, 13 sections, Re 80k-800k.
  - **Caution:** the race band has wing chord about 0.5 m, so Re is about 4e5 at 14 m/s and about 9e5 at 30 m/s. Use the higher-Re polars.

**RQ-4 CFD** (`REPO\cfd\cases\rq4_mock\RESULTS.md`, `results\alpha+*\` images; the user's CAD scaled to 1.82 m):
- Geometry: S 0.232 m², MAC 0.128 m, AR 14.3, V-tail, dorsal open-duct nacelle. kOmegaSSTLM, 2.58 M cells, U 26.5 m/s.

| α | C_L | C_D | L/D |
|---|---|---|---|
| 0 | 0.490 | 0.0545 | 9.0 |
| 4 | 0.786 | 0.0764 | 10.3 |
| 8 | 0.890 | 0.146 | 6.1 |
| 12 | 0.896 | 0.245 | 3.7 |

- Drag split at α 0: wing 44 %, fuselage 29 %, nacelle 24 %, V-tail 2 %. Non-wing drag area is about 0.0070 m².
- **Quality:**
  - y+ is about 5.8 mean (target 1.5).
  - checkMesh FAILED extra checks.
  - α 8 and 12 hit the 1000-iteration cap with a spread above the limit.
  - The fuselage interior leaked.
  - So: **"indicative"**. Use it for body, nacelle and interference drag and Cm trends, **not for CLmax calibration**.
- Left to run: α 10 (stopped at iteration 320), 6, 2, −2, −4.

**Field data (`REPO\analysis\data\`, README there):**
- 513 rows of results for 2022-26 (`dbf_results.csv`), completion counts (`field_stats.csv`) and bonus fractions (`field_bonus.csv`; the median completer reaches only 9-54 % of the field maximum, second place 67-97 %).
- Top-3 aircraft data: `dbf_airframes.csv`, `dbf_config.csv`, `dbf_aircraft.toml`.
- Winners' mission totals: 2022 5.95, 2023 6.80, 2024 6.01, 2025 6.34, 2026 5.61. Total Report maxima are 90.6-95.8.
- All mission completed: 2026 17 of 83 teams; P(M3 | M2) 0.35-0.66.
- The 2025 heavy M2 designs (ERAU 17.57 kg at 257 N/m², UNSW 22.18 kg at 248 N/m²) **scored M2 = 0**. UCLA at about 169 N/m² scored every mission.

**Competitor anchors** (`REPO\analysis\inputs\competitor.toml`; all ESTIMATES; expected = 0.75 × aggressive):

| Mission | Aggressive anchor |
|---|---|
| M2 | 0.0898 kg/s (W/t) |
| M3 | 27 kg·laps (9 × 3.0 kg) |
| GM | 12.19 kg·m (8 kg × 1.524 m) |

**Rules Q&A candidates:** `REPO\00_START_HERE_RnD.md` §11. Round 1 opens 1 Nov.

**Team facilities:** 3D printers, laser cutter and CNC, foam cutting. **No composite layup capability**; COTS carbon tubes are fine. No wind tunnel. Funding is effectively unlimited, but university procurement is slow, so lead time is the main risk.

**Team people:** the pilot can fly RC but is not yet an AMA member. Radio is ExpressLRS 2.4 GHz with PWM receivers (ER8/ER6). Fail-safe must be set per output.

**Procurement:** `REPO\procurement\pr01_items.csv`, US$8,844, with bench sets of both propulsion candidates.

**Test cards:** `REPO\testing\cards\` TC-01 to TC-06. None has been run yet.

## 6. Levers nobody has modelled (where "dominance" may come from)

1. **Decision timing.**
   - The declared maximum sensor mass, the simulator count and the tip-test mass are chosen at tech, after the airframe is built, weighed and flown.
   - Per attempt the team chooses simulators flown, prop, pack and M3 ballast. The GM drop height is declared before the drops.
   - Model each choice **using only what is known at that moment**:
     - at tech: airframe mass, CLmax, η, container mass, measured lap factor;
     - not at tech: the day's density and wind, or the field.
   - The existing `s6.evaluate` picks the simulator count and M3 mass after seeing each whole draw, so it peeks at the future. Do not copy that bias.
2. **Margin-dependent reliability.** p_attempt is a function of stall margin and landing speed, take-off T/W, turn CL margin, gust response, staging-time margin and mechanism complexity. It is not a flat 0.65.
3. **Fixed-span induced drag.** Use AVL-computed e (with the fuselage) in place of Raymer. Evaluate winglets and tip plates (vertical extent does not add span; confirm the span definition). Screen biplane and box wing.
4. **High lift.** Single-slotted and Fowler flaps (area plus ΔCl) against plain flaps, using primary NACA data. Manoeuvre flap in turns, where turn CL is near the clean limit. Also the fail-safe full-flap dive load case.
5. **Twin systems.** Two propulsion systems get two fuses of up to 100 A each (power cap about doubled). Each pack is then ≤ 50 Wh, identical.
6. **P(1st)** against a simulated field, not just the mean score against fixed scenarios.

## 7. Streams, owners and dependencies

| ID | Stream (code dir `src/<dir>`) | Phase-1a early output, due at about t0 + 2-3 h, in `W\early\` |
|---|---|---|
| S1 | Rules and strategy (`rules`) | `S1_constraints.md` + `src/rules/model.py: check(geom, ops)` with the hard-constraint list |
| S2 | Field model and reliability (`field`) | none (by about t0 + 4 h: a draft `p_attempt` API) |
| S3 | Aero, monoplane (`aero_mono`) | none |
| S4 | Multi-surface screen (`aero_multi`); time-boxed | none |
| S5 | Stability and control (`stability`) | none |
| S6 | Propulsion and energy (`propulsion`) | none |
| S7 | Structures, mass, manufacturing and logistics (`structures`) | none |
| S8 | Payload system (`payload`) | `S8_envelope.md` + `src/payload/model.py: container(...)`, `bay(...)`, `dr(...)` (first version) |
| S9 | Geometry toolkit (`geometry`) | `S9_schema.md` + `src/geometry/schema.py` (aircraft JSON schema and validator) + the reference designs as JSON |
| S10 | CFD campaign (`W\cfd`) | none |
| S11 | PDF design and build (`W\report`) | specimen pages (PNG) when ready |
| S12 | Integration and search (`integration`) | `S12_adapter.md` + `src/integration/adapter.py`, reproducing DB-01's robust 0.9 m² / 4 kg mean of 6.33 exactly with defaults (regression test) |

- Later phases add S13/S14 (Variant A/B point design), S15/S16 (red team), S17 (writer) and S18 (QA).
- **Consuming early outputs:** if one you need is not there yet, build against a clearly marked stub, carry on, and switch when it lands. Check `W\early\` for the file.

## 8. Interface contract and memo format

**Every stream ships:**
- `src/<stream>/model.py`, with the public API below (pure functions, SI, no I/O on import);
- `out/<stream>/results.json`;
- `tests/test_v_<stream>.py`;
- `sources/<stream>.toml`;
- `memos/NN_<stream>.md`.

**`results.json` schema (version 1):**

```json
{"schema": 1, "stream": "S3", "generated": "2026-10-27T21:00+03:00",
 "items": {"S3-R01": {"name": "e_monoplane_AR3.7_AVL", "value": 0.82, "range": [0.79, 0.85],
                      "dist": "uniform|normal|triangular|empirical:<file>", "unit": "-",
                      "grade": "verified|reseller|estimate|computed", "source": "<source id or method>",
                      "note": "..."}}}
```

- `computed` means it was produced by our own validated model; name the validation.
- Item IDs are stable: `S<n>-R<nn>`.

**APIs:**

| Stream | Functions |
|---|---|
| S3 / S4 | `aero(geom: dict) -> dict` with keys `cd0_parts` {wing, body, tail, gear, other} (on S_ref), `cd0`, `e`, `k` (= 1/(π AR e)), `clmax_clean`, `clmax_landing`, `clmax_turn_avail`, `cm0`, `mass_delta_kg`, `notes`. Plus `polar(geom, CL, V) -> CD` if a parabolic polar is too crude. |
| S5 | `stability(geom, loading) -> dict`: static margin, tail volumes, trim α, δe, CG limits, mode summary, pass/fail list. Plus `tail_size(geom) -> geom`. |
| S6 | `system(name) -> object` with `p_batt(D, V)`, `thrust(V, v_batt)`, `pack_kg`, `wh`, `i_max`, `fuse_a`, `layout_penalties` {mass_kg, f_m2}, `prop_diameter_m`. Plus `catalogue()`. |
| S7 | `mass(geom, loads) -> dict` per component {median, p10, p90}, a systematic growth-bias term, and `structure_ok(geom, loads)`. Also `schedule(geom)` and `cost(geom)`. |
| S8 | `container(sensor_kg, g_rating, h_m) -> {dims_m, mass_kg, ok_381}`; `bay(n_units, unit_dims, sensor_dims, reel) -> {volume_m3, length_m, cg_m}`; `dr(sensor_kg, drive) -> {mass_kg, deploy_s, stow_s, p_fail}`; `sensor(mass_kg, g_rating) -> {dims, ...}`. |
| S2 | `p_attempt(margins: dict, complexity: str) -> float`; `field.simulate(n, seed) -> rivals`; `p_first(our_draws, rivals, report_score) -> dict`. |
| S1 | `check(geom, ops) -> list[violation]`. |
| S9 | `load(json) -> geom`, `to_avl(geom, path)`, `to_stl(geom, path)`, `three_view(geom, path_pdf, style)`, `wetted(geom)`. |

**Reference designs.** Every stream evaluates these so results line up. S9 publishes them as JSON in `W\early\`; until then use these definitions:

| ID | Wing | Other |
|---|---|---|
| REF-D01 | 0.9 m² straight, span 1.82 m, taper 0.7, SD7037, 60 % semispan plain flap 25 % chord | High wing, conventional tail, fixed tricycle, single 8S tractor; unit 4 kg |
| REF-D01b | Same at 1.0 m² | Unit 5 kg |
| REF-RQ4 | The CFD mock: S 0.232 m², AR 14.3, MAC 0.128 m, taper 0.78 | V-tail, dorsal nacelle |

**Memo format (`memos/NN_<stream>.md`, NN = stream number):**
- **Page 1 header (≤ 60 lines):**
  - status line;
  - a numbered results table (ID, quantity, value, range, grade, source);
  - the 3-8 findings that matter most for the variant choice, each one sentence with its number;
  - what would change them;
  - open issues.
- **Then** method, derivations, validation, limitations and a file list.
- The orchestrator reads the header first. Keep it tight and exact.

## 9. Pre-registered variant selection rule (fixed 27 Oct, before any results)

**Gates:**
- every compliance row passes (S1);
- P(M2 and M3 both completed within the attempts) ≥ 0.90 × the best candidate's value;
- P10 total mission score ≥ the P10 of the DB-01 control (REF-D01) on the same draws.

**Variant A:**
- The gated candidate with the highest **P(highest mission total in the simulated field)**, with ≥ 5,000 field draws for finalists.
- P(1st overall) is also reported as a curve against our report score.
- If two candidates are within the Monte Carlo 95 % confidence interval, the lower-complexity one wins.

**Variant B:**
- **Physically distinct** from A in at least one frozen item: wing configuration, tail type, gear type, tractor/pusher, or motor count.
- The minimum-regret candidate in the scenarios where A loses most.
- Shares long-lead parts with A where possible: propulsion, sensor, container, D&R.
- If A beats B in every scenario, the report says plainly that B is not a real hedge.

**Also:**
- Strategy archetypes (M2-, GM- or M3-heavy, all-rounder) are *operating modes* inside each variant.
- Regret is reported across scenarios: reliability parameters, field aggressiveness and mass growth.
- DB-01 is a control column in every comparison.

## 10. The PDF (S11 builds it; S17 writes the prose)

**Look: hybrid, like DB-01.**
- Dark ink cover (`#0B0C0E`), dark chapter-divider pages and dark per-variant spec spreads. Body pages light.
- House fonts: Geist and Geist Mono, from `REPO\design-system\fonts`. Monochrome palette: Ink, Graphite, Steel, Fog, Mist, Bone. No signal colour.
- "Dark quiet luxury that whispers premium", with a **Palantir-style accent through structure only**:
  - Geist Mono coordinate and index labels;
  - registration crosshairs and hairline grid frames;
  - instrument readout panels;
  - document-control strips.
- **Banned:** gradients, shadows, clip art, rounded web boxes, emoji, fake classification markings.
- Reuse `REPO\design-system\latex\dbfdoc.cls` and `REPO\decisions\dbfbrief.sty` **read-only**. The new layer lives at `W\report\dbfdossier.sty`. Build with `REPO\design-system\tools\build.sh W\report\DB-02_aircraft_variants.tex`, which writes into `W\report\build\`.

**Prose: layered for the team.** Each decision is a card:
1. a plain-language "why" a non-aero teammate can follow;
2. the engineering argument with numbers;
3. derivations in panels.

**Outline:**
1. Cover
2. Decision register: ID, options, choice, one-line why, confidence and evidence grade, what flips it, freeze date
3. Executive summary
4. Scoring primer with a worked example
5. What wins in 2027
6. What changed since DB-01
7. Evidence and method, with an evidence-grade legend
8. Design space and eliminations, including the RQ-4 proportions with CFD images and an honest CFD-quality box
9. Shared decisions
10. Variant A
11. Variant B
12. Head-to-head: regret, break-even, P(1st) tornado, recommendation and switch condition
13. Decision calendar and mission-day playbook
14. Test gates and schedule
15. Q&A
16. Glossary
17. Sources
18. Appendices
