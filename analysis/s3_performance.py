# Copyright © 2026 Badr Obtel. All rights reserved.
"""Script 3: aerodynamics, power and energy (R&D Sec. 4, Script 3).

Written 13 Oct 2026 after Pair mode was lifted; the team reviews and
owns the numbers (rules Sec. 1.3). SI units, angles in degrees.

Model: a constant-speed lap (Script 1 geometry). Straights are flown at n = 1;
every turn is a level, coordinated turn at bank phi, n = 1/cos(phi).
  CL = n m g / (q S)         CD = CD0 + K CL^2       K = 1 / (pi e AR)
  D  = q S CD                P_shaft = D V
A single effective efficiency eta converts mean shaft power to mean battery
power over a whole mission; it absorbs propeller, motor, ESC and wiring losses
and the take-off and climb transients, and is calibrated on measured flight
data (calibrate_eta). All functions accept numpy arrays.
"""
import math

import numpy as np

import s1_course as s1
from common import G0, RULES

STRAIGHTS_M = RULES["course"]["straights_per_lap_m"]
TURN_ARC = s1.TURN_ARC              # 4 pi: turn length / radius per lap (Script 1)


def dynamic_pressure(rho, v):
    """q = rho V^2 / 2 (Pa)."""
    return 0.5 * rho * v * v


def induced_factor(aspect_ratio, e):
    """K = 1 / (pi e AR) in CD = CD0 + K CL^2."""
    return 1.0 / (np.pi * e * aspect_ratio)


def oswald_straight(aspect_ratio):
    """Oswald efficiency of a straight wing: 1.78 (1 - 0.045 AR^0.68) - 0.64 (Raymer ch. 12)."""
    return 1.78 * (1.0 - 0.045 * aspect_ratio ** 0.68) - 0.64


def oswald_swept(aspect_ratio, sweep_le_deg):
    """Oswald efficiency of a swept wing (LE sweep > 30 deg):
    4.61 (1 - 0.045 AR^0.68) (cos LE)^0.15 - 3.1 (Raymer ch. 12)."""
    return 4.61 * (1.0 - 0.045 * aspect_ratio ** 0.68) * np.cos(np.radians(sweep_le_deg)) ** 0.15 - 3.1


def lift_coefficient(rho, v, s, mass, n=1.0, g=G0):
    """CL needed to carry n times the weight at speed v."""
    return n * mass * g / (dynamic_pressure(rho, v) * s)


def drag(rho, v, s, cd0, k, mass, n=1.0, g=G0):
    """Drag (N) at speed v and load factor n with the parabolic polar."""
    q = dynamic_pressure(rho, v)
    cl = n * mass * g / (q * s)
    return q * s * (cd0 + k * cl * cl)


def power_required(rho, v, s, cd0, k, mass, n=1.0, g=G0):
    """Shaft power (W) = D V."""
    return drag(rho, v, s, cd0, k, mass, n, g) * v


def stall_speed(rho, s, mass, clmax, g=G0):
    """1 g stall speed: sqrt(2 m g / (rho S CLmax))."""
    return np.sqrt(2.0 * mass * g / (rho * s * clmax))


def lap(rho, v, bank_deg, s, cd0, k, mass, g=G0, overshoot=0.0):
    """One constant-speed lap: (time s, mean shaft power W, load factor, turn CL).

    Straights (and any marker overshoot) at n = 1, the 4 pi r of turns at n.
    """
    r = s1.turn_radius(v, bank_deg, g)
    n = s1.load_factor(bank_deg)
    straight = s1.lap_length(r, STRAIGHTS_M, overshoot) - TURN_ARC * r
    turns = TURN_ARC * r
    p1 = power_required(rho, v, s, cd0, k, mass, 1.0, g)
    pn = power_required(rho, v, s, cd0, k, mass, n, g)
    length = straight + turns
    return length / v, (p1 * straight + pn * turns) / length, n, lift_coefficient(rho, v, s, mass, n, g)


def mission(rho, v, bank_deg, s, cd0, k, mass, laps, eta, t_takeoff, g=G0, overshoot=0.0):
    """Clock time (s), battery energy (Wh) and peak battery power (W) for `laps` laps.

    Clock: t_takeoff + laps x lap time (rules Sec. 3.3.3.2: from first throttle-up).
    Energy: mean shaft power / eta over that clock time (the calibration convention).
    Peak: turn shaft power / eta.
    """
    t_lap, p_mean, n, cl_turn = lap(rho, v, bank_deg, s, cd0, k, mass, g, overshoot)
    t = t_takeoff + laps * t_lap
    p_turn = power_required(rho, v, s, cd0, k, mass, n, g)
    return {"t": t, "t_lap": t_lap, "e_wh": p_mean / eta * t / 3600.0, "p_peak": p_turn / eta,
            "p_mean": p_mean / eta, "n": n, "cl_turn": cl_turn}


def calibrate_eta(rho, v, lap_time, s, cd0, k, mass, p_battery_mean, g=G0):
    """Effective efficiency that makes the model's mean shaft power over a measured lap
    equal a measured mean battery power. Returns (eta, bank_deg).

    The bank follows from the lap: length = v x lap time, radius from Script 1's
    geometry (straights + 4 pi r), bank from r = v^2 / (g tan phi).
    """
    length = v * lap_time
    r = (length - STRAIGHTS_M) / TURN_ARC
    bank = math.degrees(math.atan(v * v / (g * r)))
    _, p_mean, _, _ = lap(rho, v, bank, s, cd0, k, mass, g)
    return p_mean / p_battery_mean, bank
