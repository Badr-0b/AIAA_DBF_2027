# Copyright © 2026 the members of the AUM AIAA DBF team. All rights reserved.
"""Hand-checked expected values for Script 3b (s3b_propulsion.py) and its data readers. TOOLING.

Closed-form values were computed on 14 Oct 2026 with the math module only (not by
s3b_propulsion). Data-anchored checks compare with numbers printed in the cached
primary sources (APC PER3 table, T-Motor test table, T-Motor spec table).
Battery: 8S, 3.3 Ah, k_ir 0.014 Ohm*Ah -> r_pack 0.0339394 Ohm; 2000 W at 3.9 V/cell.
First-order motor: Kv 300, Rm 0.03 Ohm, I0 1.5 A, ESC 0.97; w 600 rad/s, Q 1.2 N*m.
"""
import math
import unittest

import numpy as np

from _support import Case
import s3b_propulsion as pb
import s4_sizing as s4
import s3_performance as s3


class Battery(Case):
    def setUp(self):
        self.b = pb.Battery("test 8S", 8, 3.3, 0.68, 231.0, k_ir=0.014)

    def test_pack_resistance(self):
        self.assertClose(self.b.r_pack, 0.03393939393939394)

    def test_current_for_power(self):
        self.assertClose(float(self.b.current(2000.0, 3.9)), 69.3314626206404)

    def test_terminal_voltage(self):
        self.assertClose(float(self.b.volts(69.3314626206404, 3.9)), 28.84693217772372)

    def test_rated_energy(self):
        self.assertClose(self.b.energy_wh, 8 * 3.7 * 3.3)

    def test_power_beyond_pack(self):
        self.assertTrue(math.isnan(float(self.b.current(1e6, 3.9))))


class FirstOrder(Case):
    def setUp(self):
        self.m = pb.FirstOrderMotor("test", 300.0, 0.03, 1.5, eta_esc=0.97)

    def test_current(self):
        self.assertClose(float(self.m.current(1.2)), 39.19911184307752)

    def test_input_power(self):
        self.assertClose(float(self.m.p_in(600.0, 1.2)), 819.324743128994)

    def test_volts_needed(self):
        self.assertClose(float(self.m.volts_needed(600.0, 1.2, 0.0)), 20.90161497558739)


class PropTable(Case):
    """Against APC's own printed columns (PER3_20x10E.dat, v2022-0915): 4000 rpm static,
    30.357 N and 327.652 W. Coefficients are printed to 4 decimals, so 1 % tolerance."""

    def test_static_thrust_power_matches_apc(self):
        p = pb.Prop("20x10E")
        t, pw = p.thrust_power(1.225, 4000.0, 0.0)
        self.assertClose(float(t), 30.357, rel=0.01)
        self.assertClose(float(pw), 327.652, rel=0.01)

    def test_rpm_limit(self):
        self.assertClose(pb.Prop("20x15E").rpm_limit, 7500.0)       # 150,000 / 20 in (APC Rev 5)

    def test_rpm_for_thrust_inverts(self):
        p = pb.Prop("18x12E")
        rpm = float(p.rpm_for_thrust(1.064, 40.0, 25.0))
        t, _ = p.thrust_power(1.064, rpm, 25.0)
        self.assertClose(float(t), 40.0, rel=1e-6)

    def test_unreachable_thrust_is_nan(self):
        self.assertTrue(math.isnan(float(pb.Prop("14x7E").rpm_for_thrust(1.064, 5000.0, 30.0))))


class MeasuredMap(Case):
    def setUp(self):
        self.m = pb.MapMotor("tmotor-at7215", "KV220")

    def test_spec_parse(self):
        # T-Motor AT7215 spec table: "Long Shaft KV220 ... 565g ... 24mΩ ... Idle Current(10V) 2.4A ... 100A"
        self.assertClose(self.m.kv, 220.0)
        self.assertClose(self.m.mass, 0.565)
        self.assertClose(self.m.rm, 0.024)
        self.assertClose(self.m.i0, 2.4)
        self.assertClose(self.m.i_peak, 100.0)
        self.assertEqual(self.m.cells_rated, (10, 12))

    def test_fit_reproduces_measured_point(self):
        # T-Motor test table, 20*10 prop, 100 %: 42.10 V, 91.96 A (3871.53 W), 8365 rpm, 3.363 N*m
        w = 8365 * math.pi / 30
        self.assertClose(float(self.m.p_in(w, 3.363)), 3871.53, rel=0.03)


class Calibration(Case):
    def test_flight_factor_regression(self):
        # Regression pin (model output, not a hand value): ERAU 2023 M2 with ERAU's hardware.
        c = pb.calibrate_flight()
        self.assertClose(c["k_fl"], 1.035, rel=0.01)
        self.assertTrue(c["ok_turn"])


class LegacyPath(Case):
    def test_battery_power_matches_script3(self):
        """With no propulsion model, Script 4's battery_power equals Script 3's lumped model."""
        P = s4.Params()
        k = s3.induced_factor(3.68, 0.9457)
        V, B = np.array([[29.5]]), np.array([[70.0]])
        p_mean, p_peak, ok = s4.battery_power(P, V, B, 0.9, 0.023, k, 14.4)
        res = s3.mission(P.rho, V, B, 0.9, 0.023, k, 14.4, 5, P.eta, P.t_to)
        one = lambda a: np.asarray(a).item()
        self.assertClose(one(p_mean), one(res["p_mean"]))
        self.assertClose(one(p_peak), one(res["p_peak"]))
        self.assertEqual(bool(one(ok)), bool(one(res["p_peak"]) <= P.p_max))


class GridModel(Case):
    def test_grid_matches_point(self):
        sysm = pb.erau_2023_system()
        model = pb.PropulsionModel(sysm, 1.064, 1.0, v_check=3.925)
        t, v = float(model.t[20]), float(model.v[30])          # a grid node: no interpolation error
        direct = sysm.point(1.064, t, v, 0.5 * (pb.PR["battery"]["v_oc_start"] + pb.PR["battery"]["v_oc_end"]))
        self.assertClose(float(model.p_batt(t, v)), float(direct["p_batt"]), rel=1e-9)


class DataVerified(Case):
    def test_verify_prop_passes(self):
        import io
        import contextlib
        import verify_prop
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(verify_prop.main(), 0)


if __name__ == "__main__":
    unittest.main()
