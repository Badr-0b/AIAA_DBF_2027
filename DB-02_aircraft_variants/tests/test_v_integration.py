"""S12 integration tests (unittest; pytest is not installed).

    PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s DB-02_aircraft_variants/tests -p "test_v_*.py"

Regression anchors (REPO/analysis/out/s6_report.txt and prop_trade_report.txt, both computed by
the DB-01 pipeline with s6.draws(120, 2027), expected field):
  0.9 m2 / 4 kg straight: mean 6.33 (DB-01 robust optimum), 1.0/4: 6.29, 0.8/4: 6.23
  8S TP3300-8SE55 / AT7215 KV270 / APC 20x15E at 0.9/4: 6.37
"""
import math
import os
import sys
import unittest
import warnings
from pathlib import Path

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True
warnings.simplefilter("ignore", ResourceWarning)     # unclosed CSVs inside REPO/analysis (not ours)
W = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(W / "src"))

import numpy as np                                    # noqa: E402

from integration import adapter as A                  # noqa: E402


def setUpModule():
    warnings.simplefilter("ignore", ResourceWarning)   # the unittest runner resets filters per run


def _out_state():
    out = A.ANALYSIS / "out"
    return {p.name: p.stat().st_mtime_ns for p in out.iterdir() if p.is_file()}


class TestAdapterRegression(unittest.TestCase):
    """With no overrides the adapter is s6.evaluate bit for bit."""

    @classmethod
    def setUpClass(cls):
        cls.before = _out_state()
        cls.Ps = A.draws(120, 2027)

    def test_db01_robust_optimum_6_33(self):
        r = A.robust(A.REF_D01, self.Ps)
        self.assertEqual(round(r["mean"], 2), 6.33)
        self.assertAlmostEqual(r["mean"], 6.3326001152054685, places=12)
        self.assertEqual(round(100 * r["p_m2"]), 98)          # s6_report: P(M2 feasible) 98 %

    def test_db01_plateau(self):
        for (s, u), want in A.DB01_ROBUST.items():
            with self.subTest(s=s, unit=u):
                self.assertEqual(round(A.robust(A.REF_D01.with_(s=s, unit=u), self.Ps)["mean"], 2), want)

    def test_identical_to_s6_evaluate_per_draw(self):
        for P in self.Ps[:40]:
            a = A.evaluate(A.REF_D01, P)
            b = A.s6.evaluate("straight", 0.9, 4.0, P)
            self.assertEqual(a["expected"]["total"], b["expected"]["total"])
            self.assertEqual(a["aggressive"]["total"], b["aggressive"]["total"])
            self.assertEqual((a["laps"], a["m3_mass"]), (b["laps"], b["m3_mass"]))

    def test_baseline_reference_6_64(self):
        r = A.evaluate(A.REF_D01, None, fine=True)            # s6_report: 1.00 + 1.57 + 3.00 + 1.07 = 6.64
        e = r["expected"]
        self.assertEqual([round(e[k], 2) for k in ("M1", "M2", "M3", "GM", "total")], [1.0, 1.57, 3.0, 1.07, 6.64])
        self.assertEqual((e["n_sim"], r["laps"], round(e["t2"], 1)), (1, 7, 207.1))

    def test_8s_propulsion_6_37(self):
        d = A.ref_d01_8s()
        r = A.robust(d, self.Ps)
        self.assertEqual(round(r["mean"], 2), 6.37)            # prop_trade_report: 6.37, P10 6.04
        self.assertEqual(round(r["p10"], 2), 6.04)

    def test_no_writes_to_analysis_out(self):
        self.assertEqual(_out_state(), self.before)


class TestInjection(unittest.TestCase):
    """New families and overrides reach s4 without editing sizing.toml."""

    @classmethod
    def setUpClass(cls):
        cls.Ps = A.draws(120, 2027)[:24]

    def test_registered_clone_of_straight_is_identical(self):
        def straight_clone(s, P=None):
            ar = A.SPAN_M ** 2 / s
            c = A.SZ["config"]["straight"]
            return ar, A.s3.oswald_straight(ar), c["clmax_flapped"], c["clmax_clean"]
        A.register_family("s12_clone", straight_clone, clmax_key="straight")
        for P in self.Ps:
            a = A.evaluate(A.REF_D01.with_(family="s12_clone"), P)["expected"]["total"]
            b = A.evaluate(A.REF_D01, P)["expected"]["total"]
            self.assertEqual(a, b)

    def test_aero_override_equal_to_baseline_is_identical(self):
        s = 0.9
        ar = A.SPAN_M ** 2 / s
        aero = {"cd0_parts": {"wing": A.SZ["aero"]["cd_wing_per_area"], "body": A.SZ["aero"]["f_body_m2"] / s},
                "e": A.s3.oswald_straight(ar), "clmax_landing": 1.6, "clmax_clean": 1.25}
        for P in self.Ps:
            a = A.evaluate(A.REF_D01.with_(aero=aero), P)["expected"]["total"]
            b = A.evaluate(A.REF_D01, P)["expected"]["total"]
            self.assertAlmostEqual(a, b, places=9)

    def test_winglet_style_e_gain_helps(self):
        s = 0.9
        ar = A.SPAN_M ** 2 / s
        base = {"cd0_parts": {"wing": 0.0086, "body": 0.013 / s}, "clmax_landing": 1.6, "clmax_clean": 1.25}
        lo = A.robust(A.REF_D01.with_(aero={**base, "e": A.s3.oswald_straight(ar)}), self.Ps)["mean"]
        hi = A.robust(A.REF_D01.with_(aero={**base, "e": 1.15 * A.s3.oswald_straight(ar)}), self.Ps)["mean"]
        self.assertGreater(hi, lo)

    def test_dispatchers_installed_once_and_default_untouched(self):
        A.install()
        A.install()
        self.assertTrue(getattr(A.s4.family, "_s12", False))
        self.assertIs(A._ORIG["family"].__module__, "s4_sizing")
        self.assertEqual(A.s4.family("straight", 0.9), A._ORIG["family"]("straight", 0.9))

    def test_st_patch_restores(self):
        h = A.ST["design"]["drop_height_m"]
        with A.st_patch({"drop_height_m": 1.0}):
            self.assertEqual(A.ST["design"]["drop_height_m"], 1.0)
        self.assertEqual(A.ST["design"]["drop_height_m"], h)

    def test_mass_override_median_equals_fit(self):
        s = 0.9
        med = A.s4.Params.airframe(A.base_params(), s)
        for P in self.Ps[:8]:
            a = A.evaluate(A.REF_D01.with_(mass={"airframe": {"median": med}}), P)["expected"]["total"]
            b = A.evaluate(A.REF_D01, P)["expected"]["total"]
            self.assertAlmostEqual(a, b, places=9)

    def test_anchored_map(self):
        src = (0.006, 0.013, 0.028)
        dst = (0.004, 0.010, 0.020)
        self.assertAlmostEqual(A.anchored_map(0.013, src, dst), 0.010)
        self.assertAlmostEqual(A.anchored_map(0.006, src, dst), 0.004)
        self.assertAlmostEqual(A.anchored_map(0.028, src, dst), 0.020)
        xs = np.linspace(0.006, 0.028, 23)
        ys = [A.anchored_map(x, src, dst) for x in xs]
        self.assertTrue(all(b > a for a, b in zip(ys, ys[1:])))

    def test_draws_are_crn_and_tagged(self):
        Ps = A.draws(120, 2027)
        self.assertIs(Ps[0], A.draws(120, 2027)[0])
        self.assertTrue(all(0.92 <= P.pf_draw <= 1.08 and 0.85 <= P.tf_draw <= 1.15 for P in Ps))
        self.assertFalse(math.isnan(Ps[5].f_body))


if __name__ == "__main__":
    unittest.main()
