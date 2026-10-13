# Copyright © 2026 the members of the AUM AIAA DBF team. All rights reserved.
"""Integrity of analysis/inputs/*.toml (TOOLING): exact rule conversions, the
competitor scenarios, and every target you set kept inside the rules."""
import math
import unittest

from _support import Case
import common

FT, IN, LB, OZ = 0.3048, 0.0254, 0.45359237, 0.028349523125


class RuleConversions(Case):
    """Each SI value in rules.toml is the exact conversion of the rule's US value."""

    def test_exact(self):
        r = common.RULES
        cases = {
            "span 6 ft": (r["aircraft"]["span_max_m"], 6 * FT),
            "TOGW 55 lb": (r["aircraft"]["togw_max_kg"], 55 * LB),
            "arming plug 6 in": (r["aircraft"]["arming_plug_min_m"], 6 * IN),
            "markers 500 ft": (r["course"]["marker_offset_m"], 500 * FT),
            "straights 2 x 1,000 ft": (r["course"]["straights_per_lap_m"], 2000 * FT),
            "sensor 6 in": (r["sensor"]["length_min_m"], 6 * IN),
            "drop 60 in": (r["ground"]["drop_height_max_m"], 60 * IN),
            "drop step 1 in": (r["ground"]["drop_step_m"], IN),
            "ring to bottom 15 in": (r["ground"]["ring_to_bottom_max_m"], 15 * IN),
            "ring ID 1/2 in": (r["ground"]["ring_id_min_m"], IN / 2),
            "ring section 1/8 in": (r["ground"]["ring_section_max_m"], IN / 8),
            "pin 1/4 in": (r["ground"]["pin_diameter_m"], IN / 4),
            "simulator size 1/8 in": (r["simulators"]["size_tol_m"], IN / 8),
            "simulator mass 1 oz": (r["simulators"]["mass_tol_kg"], OZ),
        }
        for name, (value, exact) in cases.items():
            with self.subTest(name):
                self.assertClose(value, exact, rel=1e-12)

    def test_units_and_scoring(self):
        u = common.UNITS
        self.assertEqual((u["ft_m"], u["in_m"], u["lb_kg"], u["oz_kg"]), (FT, IN, LB, OZ))
        s = common.RULES["scoring"]
        ceilings = s["m1"] + (s["m2_base"] + 1) + (s["m3_base"] + 1) + (s["gm_base"] + 1)
        self.assertEqual(ceilings, s["mission_max"])   # 1 + 2 + 3 + 1.5 = 7.5
        self.assertClose(s["proposal_weight"] + s["design_report_weight"], 1.0)


class Competitor(Case):
    def test_aggressive_maxima(self):
        agg = common.field_maxima("aggressive")
        self.assertClose(agg["m2"], 18 * LB / 60 * 124 / 188)    # 0.08977 kg/s (ERAU 2025 basis)
        self.assertClose(agg["m3"], 27.0)                         # kg*laps
        self.assertClose(agg["gm"], 8.0 * 1.524)                  # 12.192 kg*m

    def test_scenarios_scale_every_mission(self):
        agg = common.field_maxima("aggressive")
        for scenario, factor in (("expected", 0.75), ("conservative", 0.50)):
            got = common.field_maxima(scenario)
            for mission in ("m2", "m3", "gm"):
                with self.subTest(scenario=scenario, mission=mission):
                    self.assertClose(got[mission], factor * agg[mission])

    def test_every_anchor_is_labelled(self):
        c = common.load("competitor")
        for mission in ("m2", "m3", "gm"):
            with self.subTest(mission=mission):
                self.assertIn(c[mission]["basis"], ("verified", "estimate"))
                self.assertTrue(c[mission]["note"].strip())


class TargetsInsideTheRules(Case):
    """Only the targets you have set (not nan) are checked."""

    def test_targets(self):
        rules = common.RULES
        step = rules["ground"]["drop_step_m"]
        for key in ("a01", "a02"):
            p = common.aircraft(key)
            given = lambda k: common.is_set(p.get(k))
            with self.subTest(aircraft=key):
                self.assertLessEqual(p["span_m"], rules["aircraft"]["span_max_m"])
                if given("h_drop_m"):
                    self.assertLessEqual(p["h_drop_m"], rules["ground"]["drop_height_max_m"] + 1e-12)
                if given("m_sensor_m3_kg") and given("m_sensor_max_kg"):
                    self.assertLessEqual(p["m_sensor_m3_kg"], p["m_sensor_max_kg"],
                                         "M3 may not exceed the declared maximum (Sec. 3.1.1)")
                if given("n_sim"):
                    self.assertTrue(float(p["n_sim"]).is_integer() and p["n_sim"] >= 0)
                if given("bank_deg"):
                    self.assertTrue(0 < p["bank_deg"] < 90)
                for v in ("v_race_mps", "v_tow_mps", "v_lof_mps", "a_ground_mps2", "a_air_mps2"):
                    if given(v):
                        self.assertGreater(p[v], 0, v)
        self.assertTrue(math.isclose(step, 0.0254))


if __name__ == "__main__":
    unittest.main()
