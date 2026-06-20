"""Tests for the governance-membrane model (the optimality-vs-legibility tension)."""

import dataclasses
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.governance import (  # noqa: E402
    GovParams, optimal_membrane, total_loss, stakes_thresholds, run,
)


class GovernanceModelTests(unittest.TestCase):
    def setUp(self):
        self.p = GovParams()

    def test_interior_optimum_at_moderate_stakes(self):
        opt = optimal_membrane(self.p)
        self.assertEqual(opt["regime"], "partial_membrane")
        self.assertGreater(opt["m_star"], 0.0)
        self.assertLess(opt["m_star"], 1.0)

    def test_no_membrane_when_stakes_tiny(self):
        opt = optimal_membrane(dataclasses.replace(self.p, stakes=0.3))
        self.assertEqual(opt["m_star"], 0.0)
        self.assertEqual(opt["regime"], "no_membrane")

    def test_full_membrane_when_stakes_huge(self):
        opt = optimal_membrane(dataclasses.replace(self.p, stakes=1000.0))
        self.assertEqual(opt["m_star"], 1.0)

    def test_m_star_nondecreasing_in_stakes(self):
        ms = [optimal_membrane(dataclasses.replace(self.p, stakes=s))["m_star"]
              for s in (0.5, 1.5, 5.0, 15.0, 50.0)]
        self.assertEqual(ms, sorted(ms))

    def test_m_star_is_the_minimizer(self):
        opt = optimal_membrane(self.p)
        loss_star = total_loss(self.p, opt["m_star"])["total"]
        self.assertLessEqual(loss_star, total_loss(self.p, 0.0)["total"])
        self.assertLessEqual(loss_star, total_loss(self.p, 1.0)["total"])
        # also beats nearby points
        self.assertLessEqual(loss_star, total_loss(self.p, opt["m_star"] + 0.1)["total"] + 1e-9)

    def test_better_oversight_makes_membrane_pay_sooner(self):
        lo_weak = stakes_thresholds(dataclasses.replace(self.p, beta=1.0))["membrane_starts_paying_at_stakes"]
        lo_strong = stakes_thresholds(dataclasses.replace(self.p, beta=5.0))["membrane_starts_paying_at_stakes"]
        self.assertLess(lo_strong, lo_weak)

    def test_falsifier_does_not_trigger(self):
        # the thesis "governance is load-bearing" survives: some stakes -> m*>0
        self.assertGreater(optimal_membrane(dataclasses.replace(self.p, stakes=10.0))["m_star"], 0.0)

    def test_run_is_deterministic(self):
        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
