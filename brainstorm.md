# Brainstorm

## Configuration direction (Oct 9)
- We will likely have to adhere to an **MQ-4C / MQ-9-esque design**.
- We **can't use fly-by-wire**, so we have to use a primitive version: an **onboard gyro that auto-stabilizes with the tail fins**.

### Rule check (2026-27 draft rules)
- §3.2.1: "No autopilots/flight controllers are allowed under any circumstances, even in manual mode." This is why fly-by-wire is out.
- §3.2.1: "Flight stabilization subsystems and rate gyros are allowed." This is why the gyro approach is legal.
- §3.2.1: "The airplane must be radio-controlled with manual flight by the pilot." The gyro may only assist; the pilot flies.
- §4.2.1: tech inspection checks for "illegal components or subsystems (autopilots/flight controllers, GPS, cameras)". Pick a gyro that is clearly a stabilization unit, not a flight controller.

---

## Ground tracking + pilot guidance display (Oct 10)
> **Idea: Badr Ob (team lead), 10 Oct 2026.** Not for the proposal.
> Feasibility was checked by Claude on 10–11 Oct 2026 against the 2026-27 draft rules and public sources.

### The idea
- A **phased-array radar** and a **live camera** sit on the ground, pointed at the sky. Both connect to the pilot's controller.
- The controller is in the style of DJI or Anduril: a screen and two sticks. It runs a custom UI showing:
  - what the camera sees;
  - what the radar sees;
  - an autopilot-like guide that shows how the sticks *would* move to fly the mission path. The pilot can follow it as a cue.
- It never flies the aircraft. Nothing on board is fly-by-wire, and the pilot stays in the loop throughout.

### Rule check
| Part of the idea | Status | Rule |
|---|---|---|
| A custom controller as the RC transmitter | **Not allowed** | §3.2.1 and §4.2.5: the transmitter/receiver "must be a commercially available controller with fail-safe capability" |
| An ML model or software that moves the controls | **Not allowed** | §3.2.1: "No autopilots/flight controllers are allowed under any circumstances, even in manual mode." |
| A camera on the ground | Allowed as a camera | §3.2.1 bans cameras "on or in the airplane". The FAQ also bans flying FPV |
| Ground radar plus a guidance display, used during a mission | **Grey zone** | §3.2.1: "Telemetry systems using stand-alone transmitters and receivers or ground stations are not allowed." Radar is not telemetry *from* the airplane, but it is a ground station feeding the pilot. The Contest Administration decides |
| The pilot looking at a screen in flight | **Conflicts** | §3.3.3: altitude must be "low enough to maintain good visual contact with the airplane". DBF is AMA-sanctioned (§3.2.1), and the AMA Safety Code (effective 1 Jan 2018) says: "I will maintain visual contact of an RC model aircraft without enhancement other than corrective lenses prescribed to me." |

- **If it is ruled illegal:** §1.7 allows penalties "up to disqualification from the contest for deliberate attempts to misinform officials, violate the contest rules, or safety infractions."
- **The only safe route to competition use is a Q&A ruling.** Round 1 opens 1 Nov. But answers are "posted on the website Q&A and delivered by email to all teams" (§1.5), so asking reveals the idea to every team.

### Technical check
- **Range needed: about 190–215 m.** This is an estimate:
  - markers 152.4 m from the start line (§3.3.3);
  - plus a turn radius of about 35 m at 24.4 m/s and 60° bank (Script 1 example);
  - plus the offset of the pilot station from the course.
- **Radar is the weak link.**
  - **TI mmWave modules** (IWR6843 at 60 GHz, AWR1843 at 77 GHz):
    - TI staff on the E2E forum quote about 100–120 m detection for *cars*.
    - They say drones were not tested.
    - No measured range for a small drone was found.
  - **Analog Devices EVAL-CN0566 "Phaser":** an 8-element X-band (10–10.5 GHz) phased-array dev kit, with a PlutoSDR and a Raspberry Pi.
    - Price: €2,487.76 ex VAT at DigiKey DE (39-week lead time, none in stock), and €2,954 at Farnell SI (out of stock). Both prices came from search results, not page reads.
    - Its range against a small RC aircraft is **unverified**.
  - **Licensing:** transmitting radar needs authorised equipment.
    - In the US, an example is 60 GHz radar under FCC §15.255 (rules amended in 2023).
    - In Kuwait, CITRA's rules apply. These were not checked.
  - **Bottom line:** nothing found shows that dev-kit radar hardware can reliably track a 1.8 m foam aircraft at about 200 m. Radar is the expensive, uncertain part of the idea.
- **Camera tracking is feasible.**
  - A 1.83 m span at 200 m subtends 1.83 / 200 = 9.1 mrad ≈ 0.52°.
  - A 1920 px sensor over a 60° horizontal field of view gives 32 px/deg, so the span covers about 17 px.
  - An airplane against the sky at that size can be tracked with standard computer vision.
  - One camera gives bearing and elevation. Range needs a second camera (stereo) or the known span.

### Verdict
- **As a pilot aid at the competition: don't.** It risks disqualification and conflicts with the AMA visual-contact rule, and the gain is small, because marker turns are flown by eye anyway.
- **Build it as flight-test instrumentation instead.** Use the camera version first and add radar later if it proves out. That makes it fully legal, and it earns points:
  - It measures lap time, turn radius, ground speed and the flown line. The airplane can't log these itself, because onboard GPS is banned (§3.2.1).
  - It validates Scripts 1 and 3 against real flights.
  - It feeds the design report's **Performance Results (10 pts)**, which asks teams to "compare test results to predictions and explain any differences" (§5.2).
  - It trains the pilot: replay the flown line against the ideal line after each flight. This is the "guide" part of the idea, used where it is legal.
- **Bonus:** the camera ban applies "during the competition" (§3.2.1). On home test flights, an onboard camera can film the towed sensor's stability. Remove it before tech.
- **Timing:** start after the proposal (31 Oct).
- **If we still want it at the competition:** send one generic Q&A question and accept that it costs the surprise. For example: "Is a ground-based display showing the airplane's position, with no connection to the RC system, permitted under §3.2.1?"

### Sources (checked 10 Oct 2026)
- `rules/2027_DBF_Rules_Draft.pdf`: §1.5, §1.7, §3.2.1, §3.3.3, §4.2.5, §5.2, and the FAQ.
- [AMA Safety Code (PDF)](https://modelaircraft.org/files/105.PDF), effective 1 Jan 2018.
- TI E2E forum: [long-range small-object detection](https://e2e.ti.com/support/sensors-group/sensors/f/sensors-forum/1407271/iwr6843aopevm-long-range-small-object-detction), [drone tracking](https://e2e.ti.com/support/sensors-group/sensors/f/sensors-forum/1587447/awr1843aopevm-drone-tracking-capabilities).
- EVAL-CN0566 listings: [DigiKey DE](https://punchouttest.digikey.de/en/products/detail/analog-devices-inc/EVAL-CN0566-RPIZ/18729877), [Farnell SI](https://si.farnell.com/analog-devices/eval-cn0566-rpiz/evaluation-brd-phased-array-beamforming/dp/4206237).
- FCC 60 GHz rules: [Cooley summary](https://cooley.com/news/insight/2023/2023-06-12-fcc-adopts-new-rules-for-field-disturbance-sensor-devices-operating-in-60-ghz-band), [Federal Register, 24 Jul 2023](https://www.govinfo.gov/content/pkg/FR-2023-07-24/html/2023-15367.htm).

---

## "Retarded bomb" sensor with pop-out wings (Oct 11)
> **Idea: sensor team (relayed by Badr Ob), 11 Oct 2026.** Rule check by Claude, 11 Oct 2026.

### The idea
- A towed sensor shaped like a retarded bomb: a thick dart about the size of a large Red Bull can.
- Instead of drag fins, it pops out small LRASM-style wings after it leaves the airplane, making it a tethered mini-plane that the reel can still pull back in.

### Rule check
- **Pop-out surfaces are not allowed.** §3.1.1 (verbatim): "The sensor may have fixed fins, wings or other aero stability surfaces. These may not be removed for installation in the sensor shipping container or deployed during the deployment process. The sensor must remain in the same external geometric configuration for all missions."
- **Fixed wings and fins are allowed.** But "aerodynamically stable" means "remaining in a fixed orientation in the horizontal plane (not spinning or rotating) with no effect on the stability of the aircraft" (§3.1.1). Wings that make lift can make the sensor kite or swing behind the airplane.
- **Length:** at least 152.4 mm (6 in, §3.1.1). A large can is about 157 mm long, only about 5 mm over (non-authoritative size). Aim for at least 170 mm.
- **No radio in the sensor:** "The Rx for the payload signal must be in the airplane, it may not be in the sensor" (§3.1.1). The light mode arrives over the tow line.

### Legal version: keep the look, fix the geometry
- **S1: ring tail.** A fixed annular fin: compact, strong in drop tests, and it packs well in a rectangular box.
- **S2: four fixed fins.** Fin span limited by the airplane's exit opening.
- **S3: fixed drag cone.** The literal retarded bomb: very stable, but its drag costs M3 laps.
- If wings are kept, make them symmetric at 0° incidence, so they steady the sensor without lifting it.
- **Ballast:** a can-sized body holds about 2 kg of steel or 3 kg of lead at half fill (estimate). Sensor mass scores in M2, M3 and the Ground Mission, so it can be heavy.
- All three get CAD and CFD screening in work package WP-01 (C1), then a blower test on TC-01.
