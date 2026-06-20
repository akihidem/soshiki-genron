"""Tests for the capacity / decomposition-granularity model (F1)."""

import dataclasses
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.capacity import CapParams, optimal_granularity, total_cost, run  # noqa: E402


class CapacityModelTests(unittest.TestCase):
    def setUp(self):
        self.p = CapParams()

    def test_higher_capacity_gives_coarser_decomposition(self):
        gs = [optimal_granularity(dataclasses.replace(self.p, kappa=k))["g_star"]
              for k in (2.0, 5.0, 10.0, 20.0, 50.0, 100.0)]
        self.assertEqual(gs, sorted(gs, reverse=True))   # monotonically non-increasing
        self.assertGreater(gs[0], gs[-1])

    def test_cheap_comm_just_clears_capacity(self):
        opt = optimal_granularity(self.p)   # default c_comm cheap
        self.assertEqual(opt["g_star"], math.ceil(self.p.work / self.p.kappa))
        self.assertTrue(opt["covers_capacity"])

    def test_expensive_comm_does_not_increase_granularity(self):
        cheap = optimal_granularity(dataclasses.replace(self.p, c_comm=0.05))["g_star"]
        pricey = optimal_granularity(dataclasses.replace(self.p, c_comm=8.0))["g_star"]
        self.assertLessEqual(pricey, cheap)   # accept overload rather than over-coordinate

    def test_total_cost_breakdown_sums(self):
        tc = total_cost(self.p, 7)
        self.assertAlmostEqual(tc["total"], tc["overload"] + tc["coordination"], places=4)

    def test_run_is_deterministic(self):
        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
