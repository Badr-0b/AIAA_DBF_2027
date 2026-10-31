"""S8 payload tests. Run: PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s W/tests -p "test_v_payload.py"."""
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
W = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(W / "src"))
from payload import model as M      # noqa: E402
from rules import model as R        # noqa: E402


class TestCushion(unittest.TestCase):
    def test_curve_shape_minimum_at_one(self):
        self.assertAlmostEqual(M.cushion_factor(1.0), 1.0)
        self.assertGreater(M.cushion_factor(0.3), 1.2)
        self.assertGreater(M.cushion_factor(3.0), 1.4)
        fs = [M.cushion_factor(x) for x in (0.2, 0.4, 0.7, 1.0)]
        self.assertEqual(fs, sorted(fs, reverse=True))

    def test_foam_matches_cushion_report(self):
        # cushion_report.txt: 100 g -> 61 mm, 150 g -> 40 mm at 60 in (thicker extrapolation)
        self.assertAlmostEqual(M.foam_thickness(100.0, 1.524) * 1000, 61.0, delta=1.0)
        self.assertAlmostEqual(M.foam_thickness(150.0, 1.524) * 1000, 40.0, delta=1.0)

    def test_gmin_roundtrip(self):
        t = M.foam_thickness(120.0, 1.524)
        self.assertLessEqual(M.gmin_thickness(t, 1.524), 120.0 * 1.02)


class TestContainer(unittest.TestCase):
    def test_db01_container_fails_381(self):
        self.assertGreater(R.container_ring_to_bottom((0.392, 0.202, 0.202), 0.0, 0.0)["worst"], 0.381)

    def test_150g_6kg_fits(self):
        c = M.container(6.0, 150.0, ballast="tungsten")
        self.assertTrue(c["ok_381"])
        self.assertLess(c["ring_to_bottom_m"]["worst"], 0.381)
        self.assertTrue(0.8 < c["mass_kg"] < 1.3)
        self.assertGreaterEqual(c["sensor"]["length_m"], 0.1524)
        self.assertTrue(30 < c["foam_mm"] < 50)

    def test_100g_heavy_breaks_381(self):
        for m in (4.4, 6.0, 8.0, 10.0):
            self.assertFalse(M.container(m, 100.0, ballast="tungsten")["ok_381"])

    def test_mass_grows_with_sensor(self):
        ms = [M.container(m, 150.0, ballast="tungsten")["mass_kg"] for m in (3.0, 6.0, 10.0)]
        self.assertEqual(ms, sorted(ms))

    def test_every_axis_checked(self):
        c = M.container(6.0, 150.0, ballast="tungsten")
        self.assertEqual(set(c["ring_to_bottom_m"]), {"L", "W", "H", "worst"})

    def test_range_one_container(self):
        c = M.design_for_range(3.0, 8.0, recut=True)
        self.assertEqual(c["servable"][0], 3.0)
        self.assertEqual(c["servable"][-1], 8.0)
        self.assertLess(c["mass_for"](3.0), c["mass_for"](8.0))
        self.assertFalse(M.serve(c, 12.0, recut=True)["ok"])

    def test_asbuilt_pads_need_thicker_foam(self):
        a, b = M.design_for_range(3.0, 8.0, recut=True), M.design_for_range(3.0, 8.0, recut=False)
        self.assertGreater(b["foam_mm"], a["foam_mm"])


class TestSensorSim(unittest.TestCase):
    def test_sensor_length_and_ballast(self):
        s = M.sensor(6.0, 150.0, "tungsten", 0.20)
        self.assertGreaterEqual(s["length_m"], 0.1524)
        self.assertAlmostEqual(s["ballast_kg"] * (1 + M.STRUCT_FRAC) + M.BASE_KG, 6.0, places=6)
        self.assertLess(M.sensor(6.0, 150.0, "tungsten")["diameter_m"], M.sensor(6.0, 150.0, "steel")["diameter_m"])

    def test_cp_aft_of_cg_and_nose_tow_hangs_up(self):
        s = M.sensor(6.0, 150.0, "tungsten", 0.20)
        self.assertGreater(s["x_cp_m"], s["cg_from_nose_m"])
        self.assertGreater(s["theta_nose_tow_deg"], 30.0)

    def test_simulator_mass(self):
        c = M.container(6.0, 150.0, ballast="tungsten")
        sim = M.simulator(6.0, c)
        self.assertAlmostEqual(sim["mass_kg"], c["mass_kg"] + 6.0)
        self.assertAlmostEqual(sim["mass_tol_kg"], R.OZ)
        self.assertEqual(sim["dims_m"], c["dims_m"])


class TestDR(unittest.TestCase):
    def test_reproduces_db01(self):
        d = M.dr(3.4, "37d_70")
        self.assertAlmostEqual(d["stow_s"], 11.9, delta=0.2)
        self.assertAlmostEqual(d["mass_kg"], 0.322, delta=0.03)

    def test_stow_grows_with_mass_and_geared_is_fast(self):
        a, b = M.dr(3.4, "savox_2290")["stow_s"], M.dr(10.0, "savox_2290")["stow_s"]
        self.assertGreater(b, a)
        self.assertLess(M.dr(10.0, "neo550_g15")["stow_s"], 6.0)

    def test_line_strength_scales(self):
        self.assertLessEqual(M.line_diameter(3.4), 0.00160)
        self.assertGreater(M.line_diameter(10.0), M.line_diameter(3.4))
        self.assertGreater(M.line_break_n(M.line_diameter(10.0)), 3 * 4 * 10 * M.G0 * 0.99)

    def test_adapter_payload(self):
        import numpy as np
        pl = M.payload_for_adapter(6.0, 150.0, "savox_2290", ballast="tungsten")
        self.assertTrue(callable(pl["container_kg"]))
        self.assertTrue(0.5 < pl["container_kg"](5.6) < 1.5)
        v = pl["dr"]["stow_s"](np.array([1.0, 3.4, 5.6]), type("P", (), {"rho": 1.064})())
        self.assertTrue(v[0] < v[1] < v[2])
        self.assertIn("container_range_kg", pl)


class TestTow(unittest.TestCase):
    def test_line_hangs_near_vertical_for_heavy(self):
        sh = M.line_shape(6.0, 1.0, M.Q_REF, 0.003)
        self.assertLess(sh["hang_from_vertical_deg"], 6.0)
        self.assertAlmostEqual(sh["t_exit_n"], 6.0 * M.G0, delta=3.0)
        self.assertGreater(M.line_shape(1.0, 1.0, M.Q_REF, 0.003)["aft_m"], sh["aft_m"])

    def test_tension_n4(self):
        tc = M.tow_check(sensor_masses=(3.4,), loads=(1.0, 4.0))
        self.assertAlmostEqual(tc["tension_n"]["3.4kg_n4.0"]["T_n"], 133.4, delta=3.0)

    def test_lap_table(self):
        t = {(r["t_lap_s"], r["stow_s"]): r for r in M.m3_lap_table()["rows"]}
        self.assertEqual(t[(39.1, 12.0)]["laps"], 7)
        self.assertEqual(t[(35.0, 12.0)]["laps"], 8)
        self.assertEqual(t[(39.1, 30.0)]["laps"], 6)
        self.assertAlmostEqual(t[(39.1, 30.0)]["gain_for_extra_lap_s"], 11.7, delta=0.05)

    def test_bay(self):
        b = M.bay(2, (0.3, 0.29, 0.29), (0.2, 0.2, 0.2))
        self.assertGreater(b["volume_m3"], 2 * 0.3 * 0.29 * 0.29)


if __name__ == "__main__":
    unittest.main()
