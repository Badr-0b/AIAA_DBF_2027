"""Regression tests for the DB-02 revision B fixes (30 Oct 2026 review)."""
import json
import math
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
W = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(W / "src"))

import numpy as np  # noqa: E402

from aero_mono import model as AM  # noqa: E402
from integration import finalists as FN  # noqa: E402
from integration import search as SE  # noqa: E402
from variants import mass_family as MF  # noqa: E402


class FlapDefinition(unittest.TestCase):
    """Fault 1: the scored flaps are S3's (30 % chord), so S3-R13/R14 reproduce at the generic geometry."""

    def test_chords(self):
        self.assertEqual(SE.FL["slotted"]["chord_frac"], 0.30)
        self.assertEqual(SE.FL["fowler"]["chord_frac"], 0.30)

    def test_s3_values_reproduce(self):
        items = json.loads((W / "out/aero_mono/results.json").read_text(encoding="utf-8"))["items"]
        for flap, rid in (("slotted", "S3-R13"), ("fowler", "S3-R14")):
            a = AM.aero({"S": 0.9, "flap": SE.FL[flap]})
            self.assertAlmostEqual(a["clmax_landing"], float(items[rid]["value"]), places=3)


class FamilyMass(unittest.TestCase):
    """Fault 2: only the wing and tail grow with area; anchored at 0.9 m2 on the DB-01 fit."""

    def test_anchor(self):
        k, p = MF.fit()
        self.assertAlmostEqual(MF.airframe(0.9), k * 0.9 ** p, places=9)

    def test_fixed_parts(self):
        a, b = MF.split(0.9), MF.split(1.3)
        for n in ("fuselage", "propulsion", "gear", "avionics"):
            self.assertAlmostEqual(a[n], b[n], places=12)
        k, p = MF.fit()
        self.assertLess(MF.airframe(1.3), k * 1.3 ** p)
        self.assertAlmostEqual(sum(MF.SHARES.values()), 1.0, places=12)


class Trim(unittest.TestCase):
    """Fault 3: trim at the layout's own tail arm and CG; nose-down Cm reduces trimmed lift."""

    def test_formula(self):
        g = {"trim": {"lt_c": 1.89, "h": 0.12}}
        tab = AM.trim_table(g)
        self.assertAlmostEqual(AM.trim(2.0, -0.4, "mid", tab), 2.0 + (-0.4 + 2.0 * 0.12) / 1.89, places=12)
        self.assertLess(AM.trim(2.0, -0.4, "mid", tab), 2.0)

    def test_default_unchanged(self):
        self.assertIs(AM.trim_table({}), AM.TRIM_BAND)


class Intervals(unittest.TestCase):
    """Fault 4: intervals resample the draws; paired differences of identical arrays are exactly zero."""

    def test_cluster_wider_than_fields(self):
        rng = np.random.default_rng(1)
        means = rng.uniform(0.0, 0.7, 120)
        cnt = np.full(120, 5000 / 120)
        lo, hi = SE.cluster_ci(means, cnt)
        p = float(np.average(means, weights=cnt))
        wilson = 1.96 * math.sqrt(p * (1 - p) / 5000)
        self.assertGreater((hi - lo) / 2, wilson)

    def test_paired_zero(self):
        a = np.linspace(0.1, 0.5, 120)
        m, ci = FN.paired_ci(a, a, np.ones(120))
        self.assertEqual(m, 0.0)
        self.assertEqual(ci, [0.0, 0.0])


class Layout(unittest.TestCase):
    """Cascade 7: larger wings keep at least a 1.89-chord tail arm."""

    def test_tail_arm(self):
        tab = json.loads((W / "out/variants/trim_geometry.json").read_text(encoding="utf-8"))
        for k, d in tab.items():
            self.assertGreaterEqual(d["lt_c"], 1.89 - 1e-9, k)


if __name__ == "__main__":
    unittest.main()
