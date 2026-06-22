"""Tests for the communication-cost calibration (grounds coordination.py on org_sim)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.calibrate_coord import run  # noqa: E402


class CalibrateCoordTests(unittest.TestCase):
    def setUp(self):
        self.r = run()

    def test_measured_manager_overhead_matches_model_default(self):
        # hierarchy(5) - flat(3) = 2 == coordination.py mgr_overhead default 2.0
        self.assertEqual(self.r["mgr_overhead"]["measured"], 2.0)
        self.assertTrue(self.r["mgr_overhead"]["match"])

    def test_flat_wins_at_zero_comm_cost(self):
        # c_comm in calls ~ 0 (shared-context coordination) -> flat regime (matches org_sim)
        self.assertEqual(self.r["winner_at_c_comm_0"], "flat")
        self.assertEqual(self.r["sweep"][0]["c_comm"], 0.0)
        self.assertEqual(self.r["sweep"][0]["winner"], "flat")

    def test_market_overhead_is_one_call(self):
        self.assertEqual(self.r["market_overhead_measured"], 1.0)

    def test_run_is_deterministic(self):
        self.assertEqual(run(), self.r)


if __name__ == "__main__":
    unittest.main()
