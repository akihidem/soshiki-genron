"""Tests for the joint structure×membrane model (refuting separability)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.joint import compare, run, GOV_FACTOR  # noqa: E402


class JointModelTests(unittest.TestCase):
    def test_separability_breaks_somewhere(self):
        self.assertGreaterEqual(run()["separability_breaks"], 1)

    def test_high_stakes_flips_market_to_a_more_governable_structure(self):
        c = compare(c_comm=1.0, stakes=40.0)
        self.assertEqual(c["separable"]["structure"], "market")   # efficiency-optimal
        self.assertNotEqual(c["joint"]["structure"], "market")    # governance overrides it
        self.assertFalse(c["separability_holds"])

    def test_low_stakes_keeps_separability(self):
        # at low stakes the membrane is ~0, so governability cannot tip structure choice
        self.assertTrue(compare(c_comm=1.0, stakes=0.8)["separability_holds"])

    def test_governance_factor_penalizes_dispersed_structures(self):
        self.assertLess(GOV_FACTOR["hierarchy"], GOV_FACTOR["flat"])
        self.assertLess(GOV_FACTOR["flat"], GOV_FACTOR["market"])

    def test_run_is_deterministic(self):
        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
