"""Tests for the empirical race-game harness (deterministic mock)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.race_game import _parse_S, build_players, run  # noqa: E402


class RaceGameHarnessTests(unittest.TestCase):
    def setUp(self):
        self.r = run(build_players("mock"))

    def test_parse_S_reads_and_clamps(self):
        self.assertEqual(_parse_S("S=0.3 because ..."), 0.3)
        self.assertEqual(_parse_S("S=1.5"), 1.0)
        self.assertIsNone(_parse_S("no number here"))

    def test_mock_shows_race_then_recovery_shape(self):
        a = self.r["avg_safety_by_condition"]
        self.assertLess(a["baseline"], a["liability"])     # race-to-bottom, then internalized
        self.assertGreaterEqual(a["mandate"], 0.7)         # the regulated floor binds

    def test_every_cell_parsed(self):
        self.assertTrue(all(row["S"] is not None for row in self.r["rows"]))

    def test_deterministic(self):
        self.assertEqual(run(build_players("mock")), self.r)


if __name__ == "__main__":
    unittest.main()
