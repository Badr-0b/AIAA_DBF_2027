# Copyright © 2026 Badr Obtel. All rights reserved.
"""Gathered data still matches its sources (TOOLING).

Re-runs analysis/data/verify.py's checks: every value's verbatim quote is on
its stated page of the cached AIAA document, the value is inside the quote, and
every results row passed its arithmetic. Skipped where the sources have not
been fetched (python analysis/data/fetch.py), because raw/ is not in git.
"""
import sys
import unittest

from _support import ANALYSIS, Case

DATA = ANALYSIS / "data"
sys.path.insert(0, str(DATA))


class DataMatchesSources(Case):
    def setUp(self):
        if not any((DATA / "raw").glob("*.txt")):
            self.skipTest("optional, not written yet: sources not cached (run analysis/data/fetch.py)")
        import verify
        self.verify = verify

    def test_aircraft_values(self):
        rows, bad = self.verify.check_aircraft()
        self.assertGreater(len(rows), 0)
        self.assertEqual(bad, [], "\n".join(bad))

    def test_results_rows(self):
        n, bad = self.verify.check_results()
        self.assertGreater(n, 500)
        self.assertEqual(bad, [], "\n".join(bad))


if __name__ == "__main__":
    unittest.main()
