import sys, unittest, math, time
from pathlib import Path
sys.dont_write_bytecode = True
W = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(W / "src"))
from aero_mono import model as M   # noqa: E402

KEYS = {"cd0_parts", "cd0", "e", "k", "clmax_clean", "clmax_landing", "clmax_turn_avail", "cm0", "mass_delta_kg", "notes", "ranges"}


def FL(t, cf):
    return {"type": t, "span_frac": 0.6, "chord_frac": cf, "defl_land_deg": 30.0, "defl_turn_deg": 0.0}


class TestAero(unittest.TestCase):
    def test_keys_and_sum(self):
        a = M.aero({"S": 0.9})
        self.assertTrue(KEYS <= set(a))
        self.assertAlmostEqual(sum(a["cd0_parts"].values()), a["cd0"], 9)
        self.assertEqual(set(a["cd0_parts"]), {"wing", "body", "tail", "gear", "other"})
        for k in ("f_body_m2", "e", "clmax_factor"):
            self.assertLessEqual(a["ranges"][k][0], a["ranges"][k][1])

    def test_k_consistent(self):
        a = M.aero({"S": 1.0})
        self.assertAlmostEqual(a["k"], 1 / (math.pi * 1.82 ** 2 / 1.0 * a["e"]), 9)

    def test_oswald_decomposition(self):
        a = M.aero({"S": 0.9})
        p = a["e_parts"]
        self.assertAlmostEqual(p["1/e_osw"], 1 / (p["e_inv"] * p["k_fuse"]) + math.pi * (1.82 ** 2 / 0.9) * p["K_visc"], 2)
        self.assertTrue(0.85 < a["e"] < 0.95)       # below Raymer 0.946, above ERAU 0.842

    def test_plain_flap_matches_williamson(self):
        d, _, cm = M.sec_dclmax("plain", 30, 0.25)
        self.assertAlmostEqual(d, 0.48, delta=0.03)
        self.assertLess(cm, 0)

    def test_clmax_ordering_and_existing_range(self):
        p = M.aero({"S": 0.9, "flap": FL("plain", 0.25)})
        s = M.aero({"S": 0.9, "flap": FL("slotted", 0.30)})
        f = M.aero({"S": 0.9, "flap": FL("fowler", 0.30)})
        self.assertLess(p["clmax_landing"], s["clmax_landing"])
        self.assertLess(s["clmax_landing"], f["clmax_landing"])
        self.assertTrue(1.34 <= p["clmax_landing"] <= 1.56)          # REPO wing_clmax_report trimmed band
        self.assertTrue(1.1 < p["clmax_clean"] < 1.25)

    def test_trim_reduces_clmax(self):
        a = M.aero({"S": 0.9})
        self.assertLessEqual(a["clmax_landing"], a["clmax_landing_untrimmed"] + 1e-9)

    def test_turn_flap_raises_turn_limit(self):
        c = M.aero({"S": 0.9})
        t = M.aero({"S": 0.9, "flap": dict(FL("plain", 0.25), defl_turn_deg=10.0)})
        self.assertGreater(t["clmax_turn_avail"], c["clmax_turn_avail"] * 1.05)
        self.assertLess(t["e_turn_flap"], t["e"])

    def test_winglet_small_gain_positive_cost(self):
        c = M.aero({"S": 0.9})
        w = M.aero({"S": 0.9, "winglet": {"h_frac": 0.15}})
        self.assertGreater(w["e"], c["e"])
        self.assertLess(w["e"] - c["e"], 0.06)
        self.assertGreater(w["cd0"], c["cd0"])
        self.assertGreater(w["mass_delta_kg"], c["mass_delta_kg"])

    def test_biplane_k_ratio(self):
        c = M.aero({"S": 0.9})
        b = M.aero({"S": 0.9, "config": "biplane"})
        self.assertGreater(b["e"], c["e"] * 1.1)
        self.assertLess(b["clmax_landing"], c["clmax_landing"])

    def test_speed_and_area_trend(self):
        t = time.time()
        for S in (0.8, 1.0, 1.3):
            M.aero({"S": S})
        self.assertLess(time.time() - t, 2.0)
        self.assertLess(M.aero({"S": 0.8})["e"], M.aero({"S": 1.3})["e"])   # lower AR: profile term is a smaller share

    def test_polar(self):
        self.assertGreater(M.polar({"S": 0.9}, 1.0), M.polar({"S": 0.9}, 0.3))


if __name__ == "__main__":
    unittest.main()
