"""Tests for the F7 alignment formalization (spec+verification bound capability)."""

import dataclasses
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.alignment import AlignParams, optimal_pressure, true_value, run  # noqa: E402


class AlignmentModelTests(unittest.TestCase):
    def setUp(self):
        self.p = AlignParams()

    def test_interior_optimal_pressure_exists(self):
        opt = optimal_pressure(self.p)
        self.assertTrue(opt["interior"])
        self.assertGreater(opt["p_star"], 0.0)

    def test_over_optimization_hurts_true_value(self):
        ps = optimal_pressure(self.p)["p_star"]
        self.assertGreater(true_value(self.p, ps), true_value(self.p, ps + 1.5))  # Goodhart

    def test_p_star_rises_with_spec_quality(self):
        ps = [optimal_pressure(dataclasses.replace(self.p, spec_quality=s))["p_star"]
              for s in (0.3, 0.5, 0.7, 0.9, 0.99)]
        self.assertEqual(ps, sorted(ps))
        self.assertLess(ps[0], ps[-1])

    def test_p_star_rises_with_verification(self):
        ps = [optimal_pressure(dataclasses.replace(self.p, verification=v))["p_star"]
              for v in (0.0, 0.3, 0.6, 0.9)]
        self.assertEqual(ps, sorted(ps))

    def test_p_star_falls_with_oversight_error(self):
        ps = [optimal_pressure(dataclasses.replace(self.p, oversight_error=oe))["p_star"]
              for oe in (0.0, 0.2, 0.5, 0.9)]
        self.assertEqual(ps, sorted(ps, reverse=True))   # worse oversight -> lower safe capability

    def test_race_overshoot_collapses_true_value(self):
        r = run()["race_overshoot"]
        self.assertLess(r["value_when_raced"], r["value_at_p_star"])

    def test_run_is_deterministic(self):
        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
