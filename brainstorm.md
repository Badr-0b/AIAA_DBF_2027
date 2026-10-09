# Brainstorm

## Configuration direction (Oct 9)
- We will likely have to adhere to an **MQ-4C / MQ-9-esque design**.
- We **can't use fly-by-wire**, so we have to use a primitive version: an **onboard gyro that auto-stabilizes with the tail fins**.

### Rule check (2026-27 draft rules)
- §3.2.1: "No autopilots/flight controllers are allowed under any circumstances, even in manual mode." This is why fly-by-wire is out.
- §3.2.1: "Flight stabilization subsystems and rate gyros are allowed." This is why the gyro approach is legal.
- §3.2.1: "The airplane must be radio-controlled with manual flight by the pilot." The gyro may only assist; the pilot flies.
- §4.2.1: tech inspection checks for "illegal components or subsystems (autopilots/flight controllers, GPS, cameras)". Pick a gyro that is clearly a stabilization unit, not a flight controller.
