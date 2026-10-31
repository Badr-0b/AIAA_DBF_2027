"""S1 rules and strategy tests."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
W = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(W / "src"))
from rules import compliance as C   # noqa: E402
from rules import model as R        # noqa: E402
from rules import strategy as S     # noqa: E402


class TestCompliance(unittest.TestCase):
    def test_ids_complete_and_unique(self):
        ids = [r["ID"] for r in C.build_rows()]
        self.assertEqual(ids, [f"C{i:02d}" for i in range(1, 100)])

    def test_every_quote_is_in_the_rules_text(self):
        bad = [r["ID"] for r in C.build_rows() if not r["quote_in_layout"]]
        self.assertEqual(bad, [])

    def test_csv_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.csv"
            n = C.write_csv(p)
            rows = list(csv.DictReader(p.open(encoding="utf-8")))
            self.assertEqual(len(rows), n)
            self.assertIn("impact_HV", rows[0])

    def test_check_flags_db01_container(self):
        geom = {"container": {"dims_m": [0.392, 0.202, 0.202], "sling_angle_deg": 15.0}}
        rows = R.check(geom, {"gm": {"height_in": 60}})
        self.assertTrue(any(r["id"] == "C57" and r["status"] in ("RISK", "FAIL") for r in rows))

    def test_limits(self):
        self.assertAlmostEqual(R.LIMITS["ring_to_bottom_lt_m"], 0.381)
        self.assertAlmostEqual(R.LIMITS["sim_mass_tol_kg"], 0.028349523125)


class TestStrategy(unittest.TestCase):
    def test_waiver_helps(self):
        for p in (0.57, 0.65, 0.73):
            for a in (3, 4):
                self.assertGreater(S.m1_waiver(p, a)["gain_waive"], 0.0)
        r = S.m1_waiver(0.65, 3)
        self.assertGreater(r["waive"]["P_M3"], r["fly"]["P_M3"])

    def test_report_vs_mission(self):
        r = S.report_vs_mission(88.0, 6.3, 0.0)
        self.assertAlmostEqual(r["dC_per_report_point"], 6.3)
        self.assertAlmostEqual(r["dC_per_mission_point"], 88.0)
        self.assertAlmostEqual(r["report_points_per_mission_point"], 88.0 / 6.3)

    def test_field_2026(self):
        f = S.field_by_year()["2026"]
        self.assertAlmostEqual(f["winning_score"], 501.26)
        self.assertAlmostEqual(S.needed_mission(f, 88.0), (501.26 - 3.0) / 88.0)

    def test_choose_at_tech_uses_only_given_info(self):
        best, _ = S.choose_at_tech(lambda c, d: -(c - d["opt"]) ** 2 + d.get("rho", 0), [3, 4, 5, 6], {"opt": 5.2}, [{"rho": 0.0}, {"rho": 1.0}])
        self.assertEqual(best, 5)

    def test_info_sets_disjoint(self):
        tech, day = set(S.INFO["tech_april"]), set(S.INFO["attempt_day"])
        self.assertFalse(tech & day)
        self.assertIn("rho", day)

    def test_lap_value(self):
        self.assertAlmostEqual(S.lap_value(4.4, 20.25), 4.4 / 20.25)


if __name__ == "__main__":
    unittest.main()
