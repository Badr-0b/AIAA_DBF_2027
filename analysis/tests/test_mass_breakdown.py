# Copyright © 2026 the members of the AUM AIAA DBF team. All rights reserved.
"""Checks for the component-mass dataset (data/dbf_components.toml) and mass_breakdown.py. TOOLING.

Hand-checked values (16 Oct 2026, read on the rendered pages):
- ERAU 2023 Table 5-4 (p103): rows sum to 10.78 lb against the printed Empty 10.77 lb.
- VT 2023 Table 26 (p160), Mass (Actual) g: rows sum exactly to the printed 2305.05 g.
- VT 2024: airframe = rows 5061.1 g (printed total 5061.2, table rounding) - 702.2 g batteries = 4358.9 g.
- Unit conversion: 1 lb = 0.45359237 kg (exact).
Quote checks need the cached AIAA texts (analysis/data/fetch.py) and skip without them.
"""
import unittest

from _support import ANALYSIS, Case
import mass_breakdown as mb

HAVE_RAW = (ANALYSIS / "data" / "raw" / "aiaa-dbf-2023-reports.txt").exists()


class Dataset(Case):
    @classmethod
    def setUpClass(cls):
        cls.acs = mb.load()

    def get(self, year, short):
        return next(a for a in self.acs if a["year"] == year and mb.SHORT[a["team"]] == short)

    def test_categories_known(self):
        for a in self.acs:
            for r in a["rows"]:
                self.assertIn(r[1], set(mb.CATS) | mb.NOT_AIRFRAME, f"{a['year']} {a['team']} {r[0]}")

    @unittest.skipUnless(HAVE_RAW, "cached AIAA texts absent: run analysis/data/fetch.py")
    def test_every_quote_on_its_page(self):
        bad, _ = mb.check(self.acs)
        self.assertEqual(bad, [])

    def test_sum_checks(self):
        _, sums = mb.check(self.acs)
        by = {s[0]: s for s in sums}
        self.assertClose(by["2023 ERAU p103"][2], 10.78, rel=1e-9)
        self.assertClose(by["2023 VT p160"][2], 2305.05, rel=1e-9)

    def test_airframe_excludes_battery(self):
        rows = {(r["year"], r["short"]): r for r in mb.per_aircraft(self.acs, {})}
        self.assertClose(rows[(2024, "VT")]["airframe_kg"], 4.3589, rel=1e-9)

    def test_lb_conversion(self):
        self.assertClose(mb.kg("1", "lb"), 0.45359237)


if __name__ == "__main__":
    unittest.main()
