# Copyright © 2026 the members of the AUM AIAA DBF team. All rights reserved.
"""Script 5, part 1: tow line and reel physics (PROVISIONAL).

Question: what does the deployment-and-recovery (D&R) mechanism have to do, and
how long does it take? Pure functions, used by dr_trade.py (the Table 06 trade)
and later by the rest of Script 5 (sensor and container). Every function is
checked against hand-derived values in analysis/tests/test_s5_tow.py.

Rules: tow line, deploy >= 1.5 x span from the exit to the sensor's forward tip
(Sec. 3.1.2); mechanical and electrical connection over the line (Sec. 3.1.1).
Units: SI (m, s, N, kg, rad/s); angles in degrees where named _deg.
"""
import math

import numpy as np


def deploy_length(span, factor=1.5):
    """Minimum deploy distance, exit to sensor tip: factor x span (rules Sec. 3.1.2), m."""
    return factor * span


def tow_tension(m, n, q, cda_sensor, line_d, line_cd, length, g):
    """Line tension at the airplane end, N.

    Upper bound on a straight line: the sensor's weight times the load factor n
    (it follows the airplane through the same manoeuvre), combined with the drag of
    the sensor (q CdA) and of the whole line taken normal to the flow
    (q Cd d L; Hoerner, Fluid-Dynamic Drag, ch. 3, cylinder in cross-flow).
    q is the dynamic pressure, Pa.
    """
    drag = q * (cda_sensor + line_cd * line_d * length)
    return float(np.hypot(n * m * g, drag))


def drum_layout(length, r_core, line_d, pitch_factor=1.15, dead_wraps=2.0):
    """Single-layer helical-groove drum holding `length` of line.

    r_core        groove root radius, m; the line centre sits at r_core + d/2
    pitch_factor  groove pitch over line diameter
    dead_wraps    wraps kept on the drum at full deployment
    returns       (effective radius m, turns, drum face width m)
    """
    r_eff = r_core + line_d / 2.0
    turns = length / (2.0 * math.pi * r_eff) + dead_wraps
    return r_eff, turns, turns * pitch_factor * line_d


def fleet_angle_deg(width, distance):
    """Largest angle between the line and the drum's normal plane, for a fairlead
    centred on a drum of face `width` at `distance` from it, deg."""
    return math.degrees(math.atan(0.5 * width / distance))


def drive_speed(torque, tau_stall, w_free):
    """Output speed of a DC drive under load, rad/s: the linear speed-torque line
    w = w_free (1 - torque / tau_stall), floored at zero (stalled)."""
    return w_free * max(0.0, 1.0 - torque / tau_stall)


def max_power(tau_stall, w_free):
    """Peak mechanical output of the linear speed-torque line, W: tau_s w_f / 4."""
    return tau_stall * w_free / 4.0


def capstan_ratio(mu, wraps):
    """Euler-Eytelwein capstan equation: largest load / holding tension, exp(mu theta)."""
    return math.exp(mu * 2.0 * math.pi * wraps)


def drop_speed(height, g):
    """Speed after a free fall of `height` (no drag), m/s."""
    return math.sqrt(2.0 * g * height)


def line_energy_capacity(f_break, strain_break, length):
    """Strain energy a linear-elastic line of `length` stores at its breaking load, J:
    1/2 F_b eps_b L."""
    return 0.5 * f_break * strain_break * length


def stow_time(length, tension, r_eff, tau_stall, w_free, dock_zone=0.0, dock_speed=math.inf, extra=0.0):
    """Time to reel in `length` against `tension` with a DC drive on a drum of radius
    r_eff (drive_speed), slowing to dock_speed for the last dock_zone metres, plus a
    fixed `extra` (door, latch), s. inf if the drive stalls."""
    v = drive_speed(tension * r_eff, tau_stall, w_free) * r_eff
    if v <= 0.0:
        return math.inf
    zone = min(dock_zone, length)
    return (length - zone) / v + zone / min(dock_speed, v) + extra


def run_time(length, speed, extra=0.0):
    """Time to pay out or reel in `length` at constant `speed`, plus fixed `extra` s."""
    return math.inf if speed <= 0.0 else length / speed + extra
