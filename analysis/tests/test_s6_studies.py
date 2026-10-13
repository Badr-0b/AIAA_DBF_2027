# Copyright © 2026 the members of the AUM AIAA DBF team. All rights reserved.
"""Hand-checked expected values for Script 6's pure helpers (s6_studies.py). TOOLING.

Values computed on 13 Oct 2026 by an independent scalar implementation
(scratch oracle), not by s6_studies.

expected_total, p = 0.7 per attempt, 3 flight attempts, 2 GM tries:
  P(M2) = 1 - 0.3^3 = 0.973; P(M2 then M3) = SS + FSS + SFS = 0.784;
  P(GM) = 1 - 0.3^2 = 0.91; parts M1 1.0, M2 1.5, M3 2.8, GM 1.2
  -> (1 + 1.5)(0.973) + 2.8(0.784) + 1.2(0.91) = 5.7197.
"""
import unittest

import numpy as np

from _support import Case
import s6_studies as s6


class Helpers(Case):
    def test_normalised_weights(self):
        w = self.call(s6.normalised_weights, {"a": -0.2, "b": 0.3, "c": 0.5})
        self.assertClose(w["a"], 0.2)
        self.assertClose(w["b"], 0.3)
        self.assertClose(w["c"], 0.5)

    def test_normalised_weights_all_zero(self):
        self.assertEqual(self.call(s6.normalised_weights, {"a": 0.0, "b": 0.0}), {"a": 0.0, "b": 0.0})

    def test_expected_total(self):
        parts = {"M1": 1.0, "M2": 1.5, "M3": 2.8, "GM": 1.2}
        self.assertClose(self.call(s6.expected_total, parts, 0.7, 3, 2), 5.7197)

    def test_expected_total_certain(self):
        """p = 1: every mission completes, so the expectation is the plain sum."""
        parts = {"M1": 1.0, "M2": 1.5, "M3": 2.8, "GM": 1.2}
        self.assertClose(self.call(s6.expected_total, parts, 1.0, 3, 2), 6.5)

    def test_spearman(self):
        self.assertClose(self.call(s6.spearman, np.array([1.0, 2, 3, 4]), np.array([10.0, 30, 20, 40])), 0.8)


if __name__ == "__main__":
    unittest.main()
