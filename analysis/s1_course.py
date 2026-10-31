# Copyright © 2026 Badr Obtel. All rights reserved.
"""Script 1: course and lap model.

Question: how long is a lap, and how long does it take at a given speed?

Bodies written 12 Oct 2026 (Pair mode
lifted). Every function is checked against hand-derived values in
analysis/tests/test_s1_course.py:
    python -m unittest discover -s analysis/tests -v
Equations and their derivation: 00_START_HERE_RnD.md Sec. 4, Script 1.

Course (rules Sec. 3.3.1 figure, Sec. 3.3.3): turn markers 152.4 m (500 ft)
either side of the start line, so 609.6 m of straights per lap, one 180-deg
turn beyond each marker and one 360-deg turn on the far (downwind) leg. The
airplane must be straight and level passing each marker before it turns.
Units: SI throughout (m, s, m/s, m/s^2); angles in degrees.
"""
import math

import numpy as np

from common import G0, RULES

STRAIGHTS_M = RULES["course"]["straights_per_lap_m"]   # 609.6 m
WINDOW_S = RULES["missions"]["window_s"]               # 300 s
TURN_ARC = 2 * math.pi * (RULES["course"]["turns_180_per_lap"] / 2
                          + RULES["course"]["turns_360_per_lap"])   # 4 pi: turn length / radius
EPS = 1e-9   # float guard for whole-number counts (a lap ending exactly at the limit counts)


def turn_radius(v, bank_deg, g=G0):
    """Radius of a level, coordinated turn flown at constant airspeed and bank.

    v         airspeed, m/s
    bank_deg  bank angle, deg
    g         gravitational acceleration, m/s^2
    returns   turn radius, m
    Source: J. D. Anderson, Aircraft Performance and Design (McGraw-Hill, 1999),
    accelerated-flight chapter, level turn: r = V^2 / (g tan phi).
    """
    return v * v / (g * np.tan(np.radians(bank_deg)))     # numpy: also takes arrays


def load_factor(bank_deg):
    """Load factor n = lift / weight in that level turn: n = 1 / cos(phi).

    bank_deg  bank angle, deg
    returns   n, dimensionless
    Source: as turn_radius.
    """
    return 1.0 / np.cos(np.radians(bank_deg))


def lap_length(r, straights=STRAIGHTS_M, overshoot=0.0):
    """Ground-track length of one lap (still air): straights + 4 pi r + 4 d.

    r          turn radius of every turn, m
    straights  straight-line distance per lap between the marker lines, m
    overshoot  distance d flown straight and level past each turn marker before
               rolling into its 180-deg turn, m (rules Sec. 3.3.3); the same
               distance is flown back on the other leg, so 2d per 180-deg turn
    returns    lap length, m
    Source: rules Sec. 3.3.1 figure (two 180-deg turns, one 360-deg turn).
    """
    return straights + TURN_ARC * r + 2 * RULES["course"]["turns_180_per_lap"] * overshoot


def lap_time(v, bank_deg, g=G0, straights=STRAIGHTS_M, overshoot=0.0):
    """Time for one lap flown at constant speed v, every turn at bank_deg.

    returns  lap time, s
    """
    return lap_length(turn_radius(v, bank_deg, g), straights, overshoot) / v


def best_speed(bank_deg, g=G0, straights=STRAIGHTS_M):
    """Speed V* that minimises lap_time at a fixed bank angle (no overshoot).

    t(V) = S/V + 4 pi V / (g tan phi); dt/dV = 0 gives V* = sqrt(S g tan phi / (4 pi)).
    returns  V*, m/s
    """
    return math.sqrt(straights * g * math.tan(math.radians(bank_deg)) / TURN_ARC)


def min_lap_time(bank_deg, g=G0, straights=STRAIGHTS_M):
    """The lap-time floor at a fixed bank angle: t_min = 2 sqrt(4 pi S / (g tan phi)).

    returns  t_min, s
    """
    return 2.0 * math.sqrt(TURN_ARC * straights / (g * math.tan(math.radians(bank_deg))))


def takeoff_segment(v_lof, a_ground, v_race, a_air):
    """Time and along-course distance from first throttle-up to race speed.

    A ground roll at constant acceleration a_ground (m/s^2) up to the lift-off
    speed v_lof (m/s), then constant acceleration a_air (m/s^2) up to v_race
    (m/s). Placeholder kinematics until Script 3 supplies thrust and drag.
    returns  (time s, distance m)
    """
    t_ground = v_lof / a_ground
    x_ground = v_lof ** 2 / (2.0 * a_ground)
    t_air = (v_race - v_lof) / a_air
    x_air = (v_race ** 2 - v_lof ** 2) / (2.0 * a_air)
    return t_ground + t_air, x_ground + x_air


def mission_time(t_to, x_to, lap_len, v, laps):
    """Clock time from first throttle-up to the end of lap `laps`.

    The take-off run starts at the start line and covers distance x_to (m) in
    time t_to (s); the rest of the course is flown at constant speed v (m/s)
    on laps of length lap_len (m). M2 uses laps = 5 (rules Sec. 3.3.3.2).
    returns  time, s
    """
    return t_to + (laps * lap_len - x_to) / v


def laps_in_window(t_first, t_lap, window=WINDOW_S, t_stow=0.0, stow_counts=True):
    """Number of complete laps inside the flight window (M3, rules Sec. 3.3.3.3).

    t_first      clock time at the end of lap 1, take-off included, s
    t_lap        time of each later lap, s
    window       flight window, s
    t_stow       time to stow the sensor after the last lap, s
    stow_counts  True if stowing must also finish inside the window
    returns      whole laps; 0 if lap 1 does not finish in time. A lap that
                 ends exactly at the window limit counts.
    """
    limit = window - (t_stow if stow_counts else 0.0)
    if t_first > limit + EPS:
        return 0
    return 1 + math.floor((limit - t_first) / t_lap + EPS)


def lap_time_wind(v, bank_deg, wind, g=G0, straights=STRAIGHTS_M):
    """Lap time in a steady wind blowing down the course (rules Sec. 3.3.1).

    Take-off and the near leg are upwind; the far leg with its 360-deg turn is
    downwind. Turns are flown at constant airspeed v and bank, drifting with
    the air for their duration; each leg must still reach its marker.
    Per lap, with b = pi r / v (one 180-deg turn's duration):
      upwind leg   (S/2 + w b) / (v - w)   (it starts w b past the downwind marker)
      downwind leg (S/2 - 3 w b) / (v + w) (the upwind turn and the 360 drift it on)
      turns        4 pi r / v              (unchanged in the air frame)
    Derivation: 12 Oct 2026 (00_START_HERE_RnD.md Sec. 4, Script 1 notes).
    wind: m/s, blowing down the course (|wind| < v).
    returns  lap time, s
    """
    r = turn_radius(v, bank_deg, g)
    b = math.pi * r / v
    half = straights / 2.0
    return ((half + wind * b) / (v - wind) + (half - 3.0 * wind * b) / (v + wind)
            + TURN_ARC * r / v)
