# Copyright © 2026 the members of the AUM AIAA DBF team. All rights reserved.
"""Hand-checked values for cushion_study.py (container foam, E05). TOOLING.

Derived by hand on 16 Oct 2026 from data/cushion_pe2.toml (MIL-HDBK-304B readings):
- At 48 in, a 75 g rating lies between 2 in (101 G) and 3 in (60 G). Log-log interpolation:
  f = ln(75/101) / ln(60/101) = 0.57153; t = exp(ln 2 + f ln 1.5) = 2.5216 in.
- A tabulated value is returned as is: 4 in at 48 in is 46 G, so a 46 g rating gives 4 in.
- Ideal-cushion extrapolation (p = 1) of 3 in from 48 to 60 in: 60 x 60/48 = 75 G.
- Measured-exponent extrapolation of 3 in: p = ln(60/48)/ln(48/36) = 0.775661;
  G(60) = 60 x 1.25^0.775661 = 60 x 1.188954 = 71.337 G.
- Container: inner box 80 x 80 x 270 mm + 2 x 3 in (76.2 mm) -> 232.4 x 232.4 x 422.4 mm;
  shell area 2(0.2324^2 + 2 x 0.2324 x 0.4224) = 0.50064 m2.
"""
import math

from _support import Case
import cushion_study as cs


class Cushion(Case):
    def test_interpolated_thickness(self):
        t, g = cs.thickness_for(75, 48, "data")
        self.assertClose(t, math.exp(math.log(2) + (math.log(75 / 101) / math.log(60 / 101)) * math.log(1.5)))
        self.assertClose(t, 2.5216, rel=1e-4)
        self.assertClose(g, 75.0)

    def test_tabulated_point(self):
        t, g = cs.thickness_for(46, 48, "data")
        self.assertClose(t, 4.0)

    def test_extrapolations(self):
        self.assertClose(cs.gmin_at(2, 60, "p = 1"), 75.0)
        self.assertClose(cs.gmin_at(2, 60, "measured p"), 60 * 1.25 ** (math.log(60 / 48) / math.log(48 / 36)))
        self.assertClose(cs.gmin_at(2, 60, "measured p"), 71.337, rel=1e-4)

    def test_container_shell_area(self):
        c = cs.container(3.0, 3.4, 1.0)
        self.assertEqual(c["outer_mm"], (232, 232, 422))
        self.assertClose(c["shell_kg"], 2 * (0.2324 ** 2 + 2 * 0.2324 * 0.4224), rel=1e-9)
