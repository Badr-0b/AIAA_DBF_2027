# Copyright © 2026 the members of the AUM AIAA DBF team. All rights reserved.
"""Hand-checked expected values for Script 5's tow and reel physics (s5_tow.py). TOOLING.

Values computed on 14 Oct 2026 by an independent scalar implementation
(scratch oracle), not by s5_tow:
  tension: 3.4 kg at n 1.5, q 479 Pa, sensor CdA 0.005, line 1.5 mm x 2.84 m at Cd 1.1
    weight 1.5 x 3.4 x g = 50.0139 N, drag 479 (0.005 + 1.1 x 0.0015 x 2.84) = 4.6396 N
    -> hypot = 50.22865 N
  drum: 2.94 m on a 40 mm core, 1.5 mm line, pitch 1.15 d, 2 dead wraps
    r_eff 0.04075 m, turns 2.94 / (2 pi 0.04075) + 2 = 13.48259, face 13.48259 x 1.15 x 1.5 mm
  capstan: exp(0.1 x 2 pi x 3) = 6.58606
"""
import math
import unittest

from _support import Case, G
import s5_tow as s5


class Tow(Case):
    def test_deploy_length(self):
        self.assertClose(self.call(s5.deploy_length, 1.8288, 1.5), 2.7432)

    def test_tow_tension(self):
        t = self.call(s5.tow_tension, 3.4, 1.5, 479.0, 0.005, 0.0015, 1.1, 2.84, G)
        self.assertClose(t, 50.22865244172951)

    def test_tow_tension_no_drag(self):
        """q = 0: the tension is the sensor's weight times n."""
        self.assertClose(self.call(s5.tow_tension, 2.0, 2.0, 0.0, 0.005, 0.0015, 1.1, 2.84, G), 4.0 * G)

    def test_drum_layout(self):
        r, turns, width = self.call(s5.drum_layout, 2.94, 0.040, 0.0015, 1.15, 2.0)
        self.assertClose(r, 0.04075)
        self.assertClose(turns, 13.482589759268032)
        self.assertClose(width, 0.023257467334737356)

    def test_fleet_angle(self):
        self.assertClose(self.call(s5.fleet_angle_deg, 0.023257467334737356, 0.3), 2.219813202621341)

    def test_drive_speed(self):
        self.assertClose(self.call(s5.drive_speed, 1.0, 2.0, 10.0), 5.0)
        self.assertClose(self.call(s5.drive_speed, 3.0, 2.0, 10.0), 0.0)

    def test_max_power(self):
        """Pololu 37D 50:1: 2.059 N m stall, 200 rpm -> 10.78 W (listed: 10 W, gearbox-limited)."""
        self.assertClose(self.call(s5.max_power, 2.059, 200 * 2 * math.pi / 60), 10.780898789568973)

    def test_capstan_ratio(self):
        self.assertClose(self.call(s5.capstan_ratio, 0.1, 3), 6.586061962694725)

    def test_drop_speed(self):
        self.assertClose(self.call(s5.drop_speed, 2.84, G), 7.463361977018131)

    def test_line_energy_capacity(self):
        self.assertClose(self.call(s5.line_energy_capacity, 356.0, 0.035, 2.94), 18.316200000000002)

    def test_run_time(self):
        self.assertClose(self.call(s5.run_time, 2.94, 0.3, 1.0), 10.8)
        self.assertEqual(self.call(s5.run_time, 1.0, 0.0), math.inf)


if __name__ == "__main__":
    unittest.main()
