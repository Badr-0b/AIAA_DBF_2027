# Copyright © 2026 the members of the AUM AIAA DBF team. All rights reserved.
"""Hand-checked expected values for Script 3 (s3_performance.py). TOOLING.

Every expected value was computed on 13 Oct 2026 by an independent scalar
implementation (math module only), not by s3_performance. g = 9.80665 m/s^2.

Case A: rho 1.064, V 30 m/s, S 0.6 m^2, CD0 0.03, AR 6, e 0.8, m 8 kg.
ERAU 2023 calibration: measured M2 flight (dbf_aircraft, ERAU 2023 Table 8-3):
89 ft/s, 42 s air lap, 29.24 lb, CD0 0.0583, e 0.842; wing 6.05 ft^2, AR 5.2
(Table 5-1); 1,243 W mean in-air power; rho 1.225 (ISA sea level, Daytona Beach
assumed).
"""
import unittest

from _support import G, Case
import s3_performance as s3

A = dict(rho=1.064, v=30.0, s=0.6, cd0=0.03, mass=8.0)
K_A = 0.06631455962162305


class Polar(Case):
    def test_dynamic_pressure(self):
        self.assertClose(self.call(s3.dynamic_pressure, 1.064, 30.0), 478.8)

    def test_induced_factor(self):
        self.assertClose(self.call(s3.induced_factor, 6.0, 0.8), K_A)

    def test_lift_coefficient(self):
        self.assertClose(self.call(s3.lift_coefficient, 1.064, 30.0, 0.6, 8.0, 1.0, G), 0.27308966861598444)

    def test_drag_level(self):
        self.assertClose(self.call(s3.drag, k=K_A, n=1.0, g=G, **A), 10.039173417623475)

    def test_drag_70deg_turn(self):
        self.assertClose(self.call(s3.drag, k=K_A, n=2.9238044001630863, g=G, **A), 20.764069344763694)

    def test_power_level(self):
        self.assertClose(self.call(s3.power_required, k=K_A, n=1.0, g=G, **A), 301.17520252870423)

    def test_stall_speed(self):
        self.assertClose(self.call(s3.stall_speed, 1.064, 0.6, 8.0, 1.4, G), 13.249816757611242)


class Oswald(Case):
    def test_straight(self):
        """Raymer straight-wing estimate at AR 5.2 (ERAU 2023 measured 0.842)."""
        self.assertClose(self.call(s3.oswald_straight, 5.2), 0.8942379676757316)

    def test_swept(self):
        self.assertClose(self.call(s3.oswald_swept, 4.0, 45.0), 0.7709487591830566)


class LapAndMission(Case):
    def test_lap(self):
        t_lap, p_mean, n, cl = self.call(s3.lap, A["rho"], A["v"], 70.0, A["s"], A["cd0"], K_A, A["mass"], G)
        self.assertClose(t_lap, 34.311887718183776)
        self.assertClose(p_mean, 432.3788898637731)
        self.assertClose(n, 2.9238044001630863)
        self.assertClose(cl, 0.7984607747384943)

    def test_mission_five_laps(self):
        m = self.call(s3.mission, A["rho"], A["v"], 70.0, A["s"], A["cd0"], K_A, A["mass"], 5, 0.58, 8.0, G)
        self.assertClose(m["t"], 179.5594385909189)
        self.assertClose(m["e_wh"], 37.182811648708736)
        self.assertClose(m["p_peak"], 1074.0035867981221)

    def test_calibrate_eta_erau_2023(self):
        ft, ft2, lb = 0.3048, 0.09290304, 0.45359237
        k = self.call(s3.induced_factor, 5.2, 0.842)
        eta, bank = self.call(s3.calibrate_eta, 1.225, 89 * ft, 42.0, 6.05 * ft2, 0.0583, k, 29.24 * lb, 1243.0, G)
        self.assertClose(eta, 0.5843703377089818)
        self.assertClose(bank, 60.67363118197425)


if __name__ == "__main__":
    unittest.main()
