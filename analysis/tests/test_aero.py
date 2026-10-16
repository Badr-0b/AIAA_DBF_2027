# Copyright © 2026 the members of the AUM AIAA DBF team. All rights reserved.
"""Hand-checked values for the aerodynamics data readers and the wing CLmax helpers. TOOLING.

Data-anchored checks compare with numbers printed in the cached primary files
(UIUC LSATs Vol. 1 LIFT01.TXT, Vol. 6 w1015-30_fp40_lift.dat, UIUC coordinate files),
read by eye on 15 Oct 2026. Closed forms were derived by hand:
  flapped area, linear taper lambda, flap over eta of the semispan:
    S_f / S = (eta - (1 - lambda) eta^2 / 2) / (1 - (1 - lambda) / 2)
    lambda 0.2, eta 0.6: (0.6 - 0.144) / 0.6 = 0.76;  lambda 1: eta.
  trim: CL_w + (Cm_ac + CL_w h) / (l_t / cbar); CL_w 1.5, Cm_ac -0.2, h 0.05, l_t/cbar 3:
    1.5 + (-0.2 + 0.075) / 3 = 1.4583333...
The tests that read the cached files skip when analysis/data/raw/aero/ is absent
(run analysis/data/aero/fetch_aero.py).
"""
import sys
import unittest
from pathlib import Path

from _support import ANALYSIS, Case

sys.path.insert(0, str(ANALYSIS / "data" / "aero"))
import coords  # noqa: E402
import lsat  # noqa: E402
import wing_clmax as wc  # noqa: E402

RAW = ANALYSIS / "data" / "raw" / "aero"
HAVE_RAW = (RAW / "uiuc-lsat-v1-data.zip").exists()


@unittest.skipUnless(HAVE_RAW, "raw aero cache absent: run analysis/data/aero/fetch_aero.py")
class LsatReader(Case):
    @classmethod
    def setUpClass(cls):
        cls.runs = lsat.runs()

    def find(self, airfoil, re):
        return next(r for r in self.runs if r["airfoil"] == airfoil and r["re"] == re)

    def test_sd7037b_vol1_clmax(self):
        r = self.find("SD7037 (B)", 304400.0)
        self.assertEqual(len(r["alpha"]), 33)
        cm, a = lsat.clmax(r)
        self.assertClose(cm, 1.277)
        self.assertClose(a, 12.48)

    def test_upsweep_ends_at_highest_alpha(self):
        r = self.find("SD7037 (B)", 304400.0)
        k = lsat.upsweep(r)
        self.assertClose(r["alpha"][k - 1], 18.27)      # then 17.01 on the way down

    def test_vol6_first_row_and_flap(self):
        r = next(x for x in self.runs if x["member"] == "w1015-30_fp40_lift.dat" and abs(x["re"] - 100103.7) < 1)
        self.assertEqual((r["alpha"][0], r["cl"][0], r["cm"][0]), (-10.10, 0.06, -0.1347))
        self.assertEqual(lsat.flap(r), (0.30, 40.0))

    def test_vol1_moments_not_read(self):
        self.assertIsNone(self.find("SD7037 (B)", 304400.0)["cm"])


class LsatMaths(Case):
    def run_(self, a, cl, cm=None):
        return {"alpha": a, "cl": cl, "cm": cm}

    def test_interpolation(self):
        r = self.run_([-4.0, 0.0, 4.0], [-0.2, 0.2, 0.6])
        self.assertClose(lsat.at_alpha(r, 1.0), 0.3)
        self.assertIsNone(lsat.at_alpha(r, 5.0))

    def test_increment_is_mean_offset(self):
        a = [-4.0, -2.0, 0.0, 2.0, 4.0]
        ref = self.run_(a, [0.1 * x for x in a], [0.0] * 5)
        fl = self.run_(a, [0.1 * x + 0.9 for x in a], [-0.15] * 5)
        self.assertClose(lsat.increment(fl, ref), 0.9)
        self.assertClose(lsat.increment(fl, ref, "cm"), -0.15)

    def test_lift_slope(self):
        a = [-2.0, 0.0, 2.0, 4.0]
        self.assertClose(lsat.lift_slope(self.run_(a, [0.1 * x + 0.3 for x in a])), 0.1)


@unittest.skipUnless(HAVE_RAW, "raw aero cache absent: run analysis/data/aero/fetch_aero.py")
class Coordinates(Case):
    def test_selig_thickness(self):
        _, p = coords.read("coord-sd7037")              # named SD7037-092-88: 9.2 % thick
        self.assertClose(coords.max_thickness(p), 0.092, rel=0.01)

    def test_lednicer_converted(self):
        _, p = coords.read("coord-clarky")              # Lednicer, 61 + 61 points, leading edge shared
        self.assertEqual(len(p), 121)
        self.assertClose(p[0][0], 1.0)
        self.assertClose(p[-1][0], 1.0)
        self.assertClose(min(x for x, _ in p), 0.0, abs_tol=1e-9)
        self.assertClose(coords.max_thickness(p), 0.117, rel=0.01)


class WingHelpers(Case):
    def test_flapped_area(self):
        self.assertClose(wc.flapped_area(0.2, 0.6), 0.76)
        self.assertClose(wc.flapped_area(1.0, 0.6), 0.6)
        self.assertClose(wc.flapped_area(0.7, 1.0), 1.0)

    def test_trim(self):
        cfg = wc.CFG["trim"]
        saved = dict(cfg)
        try:
            cfg["lt_over_cbar"], cfg["h_minus_hac"] = [3.0], [0.05]
            lo, hi = wc.trimmed(1.5, -0.2)
            self.assertClose(lo, 1.4583333333333333)
            self.assertClose(hi, 1.4583333333333333)
        finally:
            cfg.update(saved)


if __name__ == "__main__":
    unittest.main()
