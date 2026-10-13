# Copyright © 2026 the members of the AUM AIAA DBF team. All rights reserved.
"""Hand-checked expected values for the D&R trade's pure helpers (dr_trade.py). TOOLING.

Values derived on 14 Oct 2026 by hand or a scratch oracle, not by dr_trade:
  AHP, consistent [[1,2,4],[1/2,1,2],[1/4,1/2,1]]: priorities 4/7, 2/7, 1/7, lambda 3, CR 0.
  AHP, 3 x 3 with a12 = 3, a13 = 1/2, a23 = 1/4: closed form for n = 3,
    lambda_max = 1 + q + 1/q, q = (a12 a23 / a13)^(1/3) = 1.5^(1/3) -> 3.018295,
    CR = (lambda - 3) / (2 x 0.58) = 0.015771.
  expected_points, p 0.7, 3 attempts, 2 GM tries, parts M1 1.0, M2 1.5, M3 2.8, GM 1.2:
    fb = fc = 0 -> 5.7197 (Script 6's expected_total, test_s6_studies);
    fc = 1 (every flown M3 attempt loses the sensor): E[M1+M2] = 2.5 (1 - 0.3^3) = 2.4325;
      P(sensor intact) = 0.7 (0.3^2) + 0.21 (0.3) + 0.063 + 0.027 = 0.216;
      total 2.4325 + 1.2 x 0.91 x 0.216 = 2.668372;
    fb = 1 (every flown M3 attempt fails benignly): 2.4325 + 1.2 x 0.91 = 3.5245.
  class_probs: benign 0.1, severe 0.2, catastrophic 0.05, p_damage 0.5
    -> fb 0.1 + 0.5 x 0.2 = 0.2, fc 0.05 + 0.5 x 0.2 = 0.15.
"""
import unittest

import numpy as np

from _support import Case
import dr_trade as dr

PARTS = {"M1": 1.0, "M2": 1.5, "M3": 2.8, "GM": 1.2}


class Ahp(Case):
    def test_consistent(self):
        w, lam, cr = self.call(dr.ahp_priorities, [[1, 2, 4], [0.5, 1, 2], [0.25, 0.5, 1]])
        for got, exp in zip(w, (4 / 7, 2 / 7, 1 / 7)):
            self.assertClose(float(got), exp, rel=1e-9)
        self.assertClose(lam, 3.0, rel=1e-9)
        self.assertClose(cr, 0.0, abs_tol=1e-9)

    def test_inconsistent_lambda(self):
        w, lam, cr = self.call(dr.ahp_priorities, [[1, 3, 0.5], [1 / 3, 1, 0.25], [2, 4, 1]])
        self.assertClose(lam, 3.0182947072896305, rel=1e-9)
        self.assertClose(cr, 0.01577129938761246, rel=1e-9)


class Scales(Case):
    def test_saaty_from_difference(self):
        self.assertClose(self.call(dr.saaty_from_difference, 0.0, 1.0), 1.0)
        self.assertClose(self.call(dr.saaty_from_difference, 1.0, 1.0), 9.0)
        self.assertClose(self.call(dr.saaty_from_difference, -0.5, 1.0), 0.2)
        self.assertClose(self.call(dr.saaty_from_difference, 0.25, 0.5), 5.0)

    def test_pairwise_min_span(self):
        """A 0.001 difference against a 0.01 floor maps to 1 + 8 x 0.1 = 1.8, not 9."""
        a = self.call(dr.pairwise_from_values, [0.0, -0.001], 0.01)
        self.assertClose(float(a[0, 1]), 1.8)
        self.assertClose(float(a[1, 0]), 1 / 1.8)

    def test_interval_scores(self):
        s = self.call(dr.interval_scores, [0.0, 1.0, 2.0])
        for got, exp in zip(s, (1.0, 3.0, 5.0)):
            self.assertClose(float(got), exp)
        s = self.call(dr.interval_scores, [0.0, 1.0, 2.0], 4.0)
        for got, exp in zip(s, (3.0, 4.0, 5.0)):
            self.assertClose(float(got), exp)


class Decision(Case):
    def test_head_to_head(self):
        h = self.call(dr.head_to_head, [np.array([[1.0, 3.0], [1 / 3, 1.0]])], [1.0])
        self.assertClose(float(h[0, 1]), 0.75)
        self.assertClose(float(h[1, 0]), 0.25)

    def test_condorcet_winner(self):
        h = np.array([[0.5, 0.7, 0.6], [0.3, 0.5, 0.8], [0.4, 0.2, 0.5]])
        wins, w = self.call(dr.condorcet, h)
        self.assertEqual(list(wins), [2, 1, 0])
        self.assertEqual(w, 0)

    def test_condorcet_cycle(self):
        h = np.array([[0.5, 0.7, 0.4], [0.3, 0.5, 0.7], [0.6, 0.3, 0.5]])
        self.assertIsNone(self.call(dr.condorcet, h)[1])


class Points(Case):
    def test_no_failures_matches_script6(self):
        self.assertClose(self.call(dr.expected_points, PARTS, 0.7, 3, 2, 0.0, 0.0), 5.7197, rel=1e-9)

    def test_sensor_always_lost(self):
        self.assertClose(self.call(dr.expected_points, PARTS, 0.7, 3, 2, 0.0, 1.0), 2.668372, rel=1e-9)

    def test_always_benign_failure(self):
        self.assertClose(self.call(dr.expected_points, PARTS, 0.7, 3, 2, 1.0, 0.0), 3.5245, rel=1e-9)

    def test_class_probs(self):
        fb, fc = self.call(dr.class_probs, [(0.1, "benign"), (0.2, "severe"), (0.05, "catastrophic")], 0.5)
        self.assertClose(fb, 0.2)
        self.assertClose(fc, 0.15)


if __name__ == "__main__":
    unittest.main()
