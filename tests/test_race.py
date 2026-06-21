"""Tests for the race-externality model (competition thins the governance membrane)."""

import dataclasses
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.race import RaceParams, nash_equilibrium, social_optimum, gap, run  # noqa: E402


class RaceModelTests(unittest.TestCase):
    def setUp(self):
        self.p = RaceParams()

    def test_competition_thins_the_membrane_below_social_optimum(self):
        g = gap(self.p)
        self.assertLess(g["m_eq"], g["m_star_social"])   # race-to-the-bottom on safety
        self.assertGreater(g["gap"], 0.0)

    def test_higher_prize_widens_the_gap(self):
        gaps = [gap(dataclasses.replace(self.p, prize=v))["gap"]
                for v in (10.0, 50.0, 100.0, 200.0)]
        self.assertEqual(gaps, sorted(gaps))            # gap non-decreasing in race intensity

    def test_extreme_race_drives_membrane_to_zero(self):
        self.assertEqual(nash_equilibrium(dataclasses.replace(self.p, prize=400.0)), 0.0)

    def test_social_optimum_is_interior(self):
        m = social_optimum(self.p)
        self.assertGreater(m, 0.0)
        self.assertLess(m, 1.0)

    def test_run_is_deterministic(self):
        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
