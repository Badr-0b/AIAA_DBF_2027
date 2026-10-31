# DB-02 variants: bare specification (revision B)

30 Oct 2026. Source: DB-02 rev B (`report/DB-02_aircraft_variants.pdf`), `out/variants/variants_geometry.json` and `out/integration/finalists.json`.
Status: recommendation only. Nothing here is signed by the team.

**Plan:** build A. Switch to B if, by 15 Jan 2027, TC-07 (Fowler bench test) gives trimmed landing C_L,max < 1.75 or more than 1 jam in 100 full-load cycles. Switch earlier if the team rates the chance of that above 0.29.

**What differs:** the wing (area, chords, flap type), the tail size, the boom length, the declared range and the container. The fuselage, gear, propulsion, sensor, drum and radio are shared.

Basis: **R** rules text · **V** primary source or datasheet · **C** our computation · **E** estimate · **A** assumed, no analysis behind it.
Positions `x` are measured aft of the propeller plane.

## Configuration

| Quality | Variant A | Variant B | Basis |
|---|---|---|---|
| Layout | Conventional monoplane, single tractor | same | C |
| Wing position | High wing, on top of the fuselage box | same | C (packaging, tow-line clearance; no field edge, p ≥ 0.24) |
| Tail | Conventional: low-set horizontal tail + single fin, on a boom | same, longer boom | C (full-up + full-right-rudder fail-safe, rules §4.2.5) |
| Gear | Fixed tricycle, faired, tall nose leg | same | C |
| Motors | 1 | 1 | C |

## Wing

| Quality | Variant A | Variant B | Basis |
|---|---|---|---|
| Span | 1.820 m (limit 1.829 m (6 ft)) | 1.820 m | R |
| Area | **1.00 m²** | **1.20 m²** | C |
| Aspect ratio | 3.31 | 2.76 | C |
| Planform | Straight, unswept quarter-chord line, taper 0.7 | same | carried from DB-01 |
| Root / tip chord | 0.646 / 0.452 m | 0.776 / 0.543 m | C |
| Mean chord (MAC) | 0.555 m | 0.666 m | C |
| Root leading edge | x = 0.226 m | x = 0.244 m | C |
| Airfoil | SD7037, whole span | same | V (UIUC tunnel data) |
| Washout | 2° at the tip | same | A |
| Dihedral | 2° | 2° (may need more: weaker roll stability, C_lβ −0.006 vs A's −0.012 /rad) | A |
| Incidence | 2° (AVL model) | same | A |
| High-lift device | **Fowler flap** (slides aft on tracks) | **Single-slotted flap** (hinged, with a gap) | C |
| Flap extent | 30 % chord, inner 60 % of each half-span; 35° landing | 30 % chord, inner 60 % of each half-span; 30° landing | C |
| Ailerons | Outboard of the flaps | same | A |
| Trimmed landing C_L,max (at its own layout) | 1.93 | 1.64 | E |
| Structure | Rib and spar, carbon-tube spar | same | A |
| Joint | Two-piece wing | same | A |

## Fuselage

| Quality | Variant A | Variant B | Basis |
|---|---|---|---|
| Shape | Rectangular box, 1.20 m long × 0.345 m wide × 0.355 m tall, then a tail boom | same box, longer boom | C (sized around A's 303 mm container, 21–26 mm clearance) |
| Overall length | 1.60 m (propeller plane to tail) | 1.88 m | C |
| Tail station (tail aerodynamic centre) | x = 1.41 m | x = 1.67 m | C |
| Nose | Motor, then the 8S pack (x ≈ 0.20 m) | same | C |
| Payload bay | ≈ 0.43 m long, centred on the CG | same | C |
| Bay centre | x = 0.433 m | x = 0.485 m | C |
| Tow-line exit | Belly, on the CG (bay centre + 0.05 m) | same | C |
| D&R drum | x ≈ 0.63 m (CG + 0.20 m) | x ≈ 0.69 m | C |
| Styling | RQ-4 look allowed only where it adds no drag; no RQ-4 proportions | same | C (CFD) |

## Tail

| Quality | Variant A | Variant B | Basis |
|---|---|---|---|
| Sections | NACA 0009 | same | A |
| Tail volumes | V_h 0.55, V_v 0.040 | same | C |
| Tail arm | 1.05 m (1.89 mean chords) | 1.26 m (1.89 mean chords) | C |
| Horizontal tail area | 0.291 m² | 0.349 m² | C |
| Horizontal tail span | 1.08 m | 1.18 m | C |
| Horizontal tail AR / taper | 4.0 / 0.7 | same | A |
| Horizontal tail position | 0.12 m below the wing | same | C |
| Fin area | 0.069 m² | 0.069 m² | C |
| Fin height | 0.323 m | 0.323 m | C |
| Fin AR / taper | 1.5 / 0.6, swept leading edge | same | A |

## Propulsion and electrics (shared)

| Quality | Both variants | Basis |
|---|---|---|
| Motor | T-Motor AT7215 KV270, single tractor | C (DB-01 + S6) |
| Propeller | APC 20x15E (508 mm diameter) | C |
| Propeller axis height | 0.369 m above the ground (0.115 m tip clearance) | C |
| Pack | 8S 3300 mAh, 97.7 Wh, 0.674 kg (limit 100 Wh) | R / V |
| Fuse | Littelfuse MAXI 58 V slow-blow, 80 A blade (the 100 A MAXI is rated only 32 V) | V / R |
| Static thrust | 101 N | C |
| Radio | ExpressLRS 2.4 GHz, PWM; fail-safe set per output | A (radio) / R (fail-safe) |

## Payload

| Quality | Variant A | Variant B | Basis |
|---|---|---|---|
| Sensor | Tungsten-ballasted dart: ogive nose, fins, three LED bands; at 8 kg ≈ 190 mm long, 85 mm diameter, 205 mm fin span | same dart, ballasted to 6 kg max (≈ 200 × 70 mm, 190 mm fins) | E |
| Sensor rating | Survives 150 g | same | E (MIL-HDBK-304B) |
| Tow point | Tow eye above the sensor CG, not at the nose | same | C |
| Declared sensor mass | **3–8 kg**, chosen at tech (mean 6.2 kg); plan for a hot day (ρ 1.04 kg/m³) | **3–6 kg** (mean 5.6 kg) | R / C |
| Container | 288 × 303 × 303 mm, 1.18 kg, 41 mm PE foam, pads re-cut at tech | 298 × 288 × 288 mm, 1.00 kg | E |
| Deployment and recovery | Closed-loop drum, slip ring, docking latch, Savox servo drive; 0.30 kg (sized for 8 kg) | same drive, 0.26 kg if sized for 6 kg | C |
| Stow time at max declaration | 24.6 s (8 kg): costs the 7th lap, so Mission 3 is flown lighter | 19.0 s (6 kg) | C |
| Tow line | At least 2.73 m (1.5 × span) | same | R |
| Lights | Three LED arrays of ≈ 220 cd, 1–2 Hz flash, one-button sequencing | same | E |

## Mass, balance and performance

| Quality | Variant A | Variant B | Basis |
|---|---|---|---|
| Empty mass (with pack and D&R) | 6.96 kg | 7.20 kg | E (DB-01 fit, wing and tail scaled only; ±31 % 1σ) |
| Mission 2 gross: median as scored (incl. any simulators) / one unit at max declaration | 14.6 / 16.1 kg | 14.3 / 14.2 kg | C / E |
| Design CG | x = 0.433 m | x = 0.485 m | C |
| Neutral point (wing + tail) | x = 0.521 m | x = 0.591 m | C (AVL) |
| Static margin | 16 % MAC in every loading (a layout input); ≈ 12 % with the fuselage | same | C / E |
| Stall speed at Mission 2 gross (median) | 11.9 m/s | 11.7 m/s | C |
| Mission 1 | Waived; credited by the first successful Mission 2 | same | R |
| Ground Mission drop height | 1.524 m (60 in) | same | R |

## Scores (base case, 120 draws × 5,000 simulated fields)

| Quality | Variant A | Variant B | DB-01 control | Basis |
|---|---|---|---|---|
| P(top mission total) | 0.313 (0.285–0.342) | 0.295 (0.268–0.322) | 0.128 | C |
| A − B, paired | +0.018 (0.011–0.025) | — | — | C |
| P(top) if the Fowler underdelivers | 0.251 | 0.295 | 0.128 | C |
| Largest regret over 5 scenarios | 0.044 | **0.018** (smallest of all finalists) | — | C |
| Mean mission total / P10 | 6.76 / 6.25 | 6.71 / 6.19 | 6.33 / 6.00 | C |
| P(1st), report score 90 | 0.369 | 0.359 | 0.193 | C |

**Not yet defined by any analysis:**
- control-surface sizes (aileron, elevator, rudder);
- Fowler track geometry and flap deflection travel;
- nose and cowl shape;
- fuselage corner radii and the boom section;
- materials beyond "rib and spar".

**Changes from rev A (same day):**
- A: 0.9 → 1.0 m², declared range 3–6 → 3–8 kg.
- B: 1.0 → 1.2 m².
- Fuselage widened for the 8 kg container.
- Tail arm held at 1.89 chords for both variants.

Why each changed: rev B report §5.5 (Table 04).
