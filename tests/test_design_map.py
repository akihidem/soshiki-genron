"""Tests for the design-map synthesis (composition of the two measurements)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.design_map import run, recommend  # noqa: E402


class DesignMapTests(unittest.TestCase):
    def test_corner_sanity_human_low_is_hierarchy_no_membrane(self):
        rec = recommend(c_comm=3.0, stakes=0.8)
        self.assertEqual(rec["structure"], "hierarchy")
        self.assertEqual(rec["membrane_m_star"], 0.0)

    def test_corner_sanity_deep_ai_high_is_flat_full_membrane(self):
        rec = recommend(c_comm=0.03, stakes=40.0)
        self.assertEqual(rec["structure"], "flat")
        self.assertEqual(rec["membrane_m_star"], 1.0)

    def test_membrane_depends_only_on_stakes_separability(self):
        r = run()
        for row in r["grid"]:
            ms = {c["membrane_m_star"] for c in row["cells"].values()}
            self.assertEqual(len(ms), 1, "membrane should be constant across a stakes row")

    def test_run_is_deterministic(self):
        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
