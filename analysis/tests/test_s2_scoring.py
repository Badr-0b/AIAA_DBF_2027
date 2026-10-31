# Copyright © 2026 Badr Obtel. All rights reserved.
"""Hand-checked expected values for Script 2 (s2_scoring.py). TOOLING.

Derived on 12 Oct 2026 from rules Sec. 3.3.3.1-3.3.4, 6.2 and 6.3, read
verbatim. Field values are the best of the OTHER teams; the rules' Max is over
all teams, ours included, so beating the field caps each score at its ceiling.

Run:  python -m unittest discover -s analysis/tests -v
"""
import unittest

from _support import Case
import s2_scoring as s2

OZ = 0.028349523125
IN = 0.0254


class MissionOne(Case):
    def test_m1(self):
        self.assertClose(self.call(s2.m1, True), 1.0)
        self.assertClose(self.call(s2.m1, False), 0.0)


class MissionTwo(Case):
    def test_payload(self):
        """Sensor in container plus 3 simulators, each 0.4 + 1.6 kg."""
        self.assertClose(self.call(s2.m2_payload_mass, 3, 0.4, 1.6), 8.0)
        self.assertClose(self.call(s2.m2_payload_mass, 0, 0.4, 1.6), 2.0)

    def test_payload_with_simulators_one_ounce_heavy(self):
        """Each simulator may be up to 1 oz heavier than container + sensor."""
        self.assertClose(self.call(s2.m2_payload_mass, 3, 0.4, 1.6, OZ), 8.085048569375)

    def test_score(self):
        cases = [
            ((8.0, 160.0, 0.05), 2.0),    # equal to the field best: the ceiling
            ((4.0, 160.0, 0.05), 1.5),    # half of it
            ((10.0, 160.0, 0.05), 2.0),   # better than the field: we ARE the max, still 2.0
            ((0.0, 160.0, 0.05), 1.0),    # the completion credit alone
        ]
        for args, score in cases:
            with self.subTest(args=args):
                self.assertClose(self.call(s2.m2, *args), score)

    def test_failed_mission_scores_nothing(self):
        self.assertClose(self.call(s2.m2, 8.0, 160.0, 0.05, completed=False), 0.0)


class MissionThree(Case):
    def test_score(self):
        cases = [
            ((9, 2.0, 27.0), 2.6666666666666665),
            ((9, 3.0, 27.0), 3.0),
            ((10, 3.0, 27.0), 3.0),       # 30 > 27: capped
            ((0, 2.0, 27.0), 2.0),
        ]
        for args, score in cases:
            with self.subTest(args=args):
                self.assertClose(self.call(s2.m3, *args), score)

    def test_failed_mission_scores_nothing(self):
        self.assertClose(self.call(s2.m3, 9, 2.0, 27.0, completed=False), 0.0)


class GroundMission(Case):
    def test_score(self):
        cases = [
            ((2.0, 1.524, 4.572), 1.1666666666666667),
            ((3.0, 1.524, 4.572), 1.5),
            ((8.0, 1.524, 4.572), 1.5),   # capped
        ]
        for args, score in cases:
            with self.subTest(args=args):
                self.assertClose(self.call(s2.gm, *args), score)

    def test_failed_mission_scores_nothing(self):
        self.assertClose(self.call(s2.gm, 2.0, 1.524, 4.572, completed=False), 0.0)

    def test_declared_inches(self):
        """48 x 0.0254 is 1.2191999999999998 in floating point, and dividing it
        back gives 47.99999999999999: flooring that declares 47 in, costing GM
        about 2 %. Same trap at 24 and 58 in (24 and 48 are TC-02 heights)."""
        cases = [(1.524, 60), (1.6, 60), (1.5, 59), (1.4986, 59),
                 (48 * IN, 48), (24 * IN, 24), (58 * IN, 58), (3 * IN, 3)]
        for h, inches in cases:
            with self.subTest(h=h):
                self.assertWhole(self.call(s2.declared_drop_inches, h), inches)

    def test_declared_height(self):
        self.assertClose(self.call(s2.declared_drop_height, 1.5), 59 * IN)
        self.assertClose(self.call(s2.declared_drop_height, 2.0), 60 * IN)


class Totals(Case):
    def test_total_mission(self):
        self.assertClose(self.call(s2.total_mission, 1.0, 2.0, 3.0, 1.5), 7.5)

    def test_total_report(self):
        for (p, dr), tr in (((80.0, 80.0), 80.0), ((100.0, 0.0), 15.0), ((0.0, 100.0), 85.0)):
            with self.subTest(proposal=p, design_report=dr):
                self.assertClose(self.call(s2.total_report, p, dr), tr)

    def test_competition(self):
        self.assertClose(self.call(s2.competition, 80.0, 5.0, 3), 403.0)

    def test_ceiling_everywhere_is_seven_and_a_half(self):
        """Your functions together: every term equal to the field best."""
        w, t, n, ws, h = 8.0, 160.0, 9, 3.0, 1.524
        total = self.call(s2.total_mission,
                          self.call(s2.m1, True),
                          self.call(s2.m2, w, t, w / t),
                          self.call(s2.m3, n, ws, n * ws),
                          self.call(s2.gm, ws, h, ws * h))
        self.assertClose(total, 7.5)


class Rounding(Case):
    """Optional: rules Sec. 6.2 conventional rounding. Python's round() gives
    0.12 and 2 here."""

    def test_half_rounds_up(self):
        self.assertClose(self.call(s2.round_rule, 0.125, optional=True), 0.13)
        self.assertClose(self.call(s2.round_rule, 2.5, 0, optional=True), 3.0)
        self.assertClose(self.call(s2.round_rule, 0.124, optional=True), 0.12)


if __name__ == "__main__":
    unittest.main()
