# Copyright © 2026 the members of the AUM AIAA DBF team. All rights reserved.
"""Hand-checked expected values for Script 1 (s1_course.py). TOOLING.

Every expected value was derived independently on 12 Oct 2026, from the closed
forms in 00_START_HERE_RnD.md Sec. 4 (Script 1), and cross-checked against the
3-figure table there. g = 9.80665 m/s^2 is passed explicitly.

Run:  python -m unittest discover -s analysis/tests -v
"""
import unittest

from _support import G, Case
import s1_course as s1

STRAIGHTS = 609.6                      # m per lap (rules Sec. 3.3.3)
R_FLOOR = 48.5104266544097             # m: turn radius at V* for EVERY bank angle

# bank (deg): (load factor, V* m/s, t_min s)
FLOOR = {
    60.0: (2.0,                28.705042791689213, 42.47337336675169),
    63.0: (2.2026892645852665, 30.55589046688749,  39.900653568620776),
    65.0: (2.3662015831524985, 31.940492692283765, 38.1709828882676),
    70.0: (2.9238044001630863, 36.15305075232276,  33.72329511975331),
    75.0: (3.8637033051562737, 42.13584024050835,  28.934987246982473),
}


class TurnGeometry(Case):
    def test_turn_radius(self):
        """24.4 m/s at 60 deg. R&D Sec. 4 rounds it to 35.0 m."""
        self.assertClose(self.call(s1.turn_radius, 24.4, 60.0, G), 35.0508334920422)

    def test_load_factor(self):
        """60 deg gives 1.9999999999999996 in floating point: never test it with ==."""
        for bank, (n, _, _) in FLOOR.items():
            with self.subTest(bank=bank):
                self.assertClose(self.call(s1.load_factor, bank), n)


class LapLength(Case):
    def test_base_case(self):
        """R&D Sec. 4 says 1,049 m because it rounded r to 35.0 m first; the
        unrounded value is 1,050.06 m."""
        self.assertClose(self.call(s1.lap_length, 35.0508334920422, STRAIGHTS), 1050.0617640031955)

    def test_no_turn_radius_leaves_the_straights(self):
        self.assertClose(self.call(s1.lap_length, 0.0, STRAIGHTS), STRAIGHTS)

    def test_overshoot(self):
        """5 m straight and level past each marker adds 20 m per lap."""
        base = self.call(s1.lap_length, 35.0508334920422, STRAIGHTS)
        longer = self.call(s1.lap_length, 35.0508334920422, STRAIGHTS, 5.0)
        self.assertClose(longer - base, 20.0)


class LapTime(Case):
    def test_base_case(self):
        """24.4 m/s at 60 deg. R&D Sec. 4: 43.0 s."""
        self.assertClose(self.call(s1.lap_time, 24.4, 60.0, G), 43.03531819685228)

    def test_overshoot_costs_its_distance_at_speed(self):
        base = self.call(s1.lap_time, 24.4, 60.0, G)
        longer = self.call(s1.lap_time, 24.4, 60.0, G, STRAIGHTS, 5.0)
        self.assertClose(longer - base, 20.0 / 24.4)

    def test_best_speed(self):
        for bank, (_, v_star, _) in FLOOR.items():
            with self.subTest(bank=bank):
                self.assertClose(self.call(s1.best_speed, bank, G), v_star)

    def test_min_lap_time(self):
        for bank, (_, _, t_min) in FLOOR.items():
            with self.subTest(bank=bank):
                self.assertClose(self.call(s1.min_lap_time, bank, G), t_min)

    def test_floor_radius_is_the_same_at_every_bank(self):
        """At V* the turns take exactly half the lap distance, so r(V*) is
        609.6 m / (4 pi) = 48.51 m whatever the bank angle."""
        for bank in FLOOR:
            with self.subTest(bank=bank):
                v_star = self.call(s1.best_speed, bank, G)
                self.assertClose(self.call(s1.turn_radius, v_star, bank, G), R_FLOOR)

    def test_the_floor_is_a_minimum(self):
        for bank, (_, v_star, t_min) in FLOOR.items():
            with self.subTest(bank=bank):
                self.assertClose(self.call(s1.lap_time, v_star, bank, G), t_min)
                for v in (0.99 * v_star, 1.01 * v_star):
                    self.assertGreater(self.call(s1.lap_time, v, bank, G), t_min)


class TakeOff(Case):
    def test_segments(self):
        """Ground roll to 15 m/s at 5 m/s^2 (3 s, 22.5 m), then 2.5 m/s^2 to race speed."""
        cases = {(15.0, 5.0, 30.0, 2.5): (9.0, 157.5),
                 (15.0, 5.0, 35.0, 2.5): (11.0, 222.5)}
        for args, (t, x) in cases.items():
            with self.subTest(args=args):
                got = self.call(s1.takeoff_segment, *args)
                self.assertEqual(len(got), 2, "return (time, distance)")
                self.assertClose(got[0], t)
                self.assertClose(got[1], x)


class MissionTime(Case):
    LAP = 1180.9354151591708   # m: lap length at 35 m/s, 70 deg

    def test_five_laps(self):
        self.assertClose(self.call(s1.mission_time, 11.0, 222.5, self.LAP, 35.0, 5), 173.3479164513101)

    def test_first_lap(self):
        self.assertClose(self.call(s1.mission_time, 11.0, 222.5, self.LAP, 35.0, 1), 38.38386900454773)

    def test_no_take_off_is_whole_laps_at_speed(self):
        self.assertClose(self.call(s1.mission_time, 0.0, 0.0, self.LAP, 35.0, 3), 3 * self.LAP / 35.0)

    def test_the_pieces_together(self):
        """Your functions chained: the five-lap M2 time at 35 m/s, 70 deg."""
        lap = self.call(s1.lap_length, self.call(s1.turn_radius, 35.0, 70.0, G), STRAIGHTS)
        t_to, x_to = self.call(s1.takeoff_segment, 15.0, 5.0, 35.0, 2.5)
        self.assertClose(self.call(s1.mission_time, t_to, x_to, lap, 35.0, 5), 173.3479164513101)


class LapsInWindow(Case):
    def test_counts(self):
        cases = [
            ((45.0, 31.875), {}, 9),     # lap 9 ends at exactly 300.000 s: it counts
            ((45.0, 31.876), {}, 8),     # 8 ms per lap slower loses the 9th lap
            ((45.0, 31.875), {"t_stow": 10.0, "stow_counts": True}, 8),
            ((45.0, 31.875), {"t_stow": 10.0, "stow_counts": False}, 9),
            ((300.0, 30.0), {}, 1),      # lap 1 ends exactly at the limit
            ((301.0, 30.0), {}, 0),      # lap 1 never finishes in time
        ]
        for args, kwargs, laps in cases:
            with self.subTest(args=args, **kwargs):
                self.assertWhole(self.call(s1.laps_in_window, *args, 300.0, **kwargs), laps)


class Wind(Case):
    """Optional: a steady wind down the course, 35 m/s at 70 deg."""

    def test_wind(self):
        for wind, t in ((0.0, 33.741011861690595), (5.0, 33.25366749389421),
                        (10.0, 34.20094440424455)):
            with self.subTest(wind=wind):
                self.assertClose(self.call(s1.lap_time_wind, 35.0, 70.0, wind, G, optional=True), t)


if __name__ == "__main__":
    unittest.main()
