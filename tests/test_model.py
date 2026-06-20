"""Tests for the coordination-cost model + sweep.

Asserts the *robust qualitative* claims (not exact numbers, which move with
parameters): the crossover exists and points the right way, hierarchy's domain
shrinks as its overhead grows, the verification axis helps flat, costs are affine
in c_comm, and the sweep is deterministic.
"""

import dataclasses
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.coordination import Params, cost_flat, cost_hierarchy, winner  # noqa: E402
from model import sweep as S  # noqa: E402


class CoordinationModelTests(unittest.TestCase):
    def setUp(self):
        self.p = Params()

    def test_hierarchy_wins_when_communication_is_expensive(self):
        self.assertEqual(winner(self.p, 5.0)[0], "hierarchy")

    def test_flat_wins_when_communication_is_cheap_and_sparse(self):
        sparse = dataclasses.replace(self.p, density=0.2)
        self.assertEqual(winner(sparse, 0.02)[0], "flat")

    def test_flat_hierarchy_crossover_exists_and_is_positive(self):
        c = S.crossover(self.p, "flat", "hierarchy")
        self.assertIsNotNone(c)
        self.assertGreater(c, 0.0)

    def test_hierarchy_domain_shrinks_as_manager_overhead_grows(self):
        # higher crossover c_comm* == hierarchy wins only above a higher bar == smaller domain
        cs = [S.crossover(dataclasses.replace(self.p, mgr_overhead=o), "flat", "hierarchy")
              for o in (0.0, 1.0, 2.0, 4.0, 8.0)]
        self.assertEqual(cs, sorted(cs))
        self.assertLess(cs[0], cs[-1])

    def test_verification_axis_helps_flat(self):
        # neutralizing the blind-spot/escape penalty lowers flat's crossover (helps it less)
        base = S.crossover(self.p, "flat", "hierarchy")
        neutral = S.crossover(dataclasses.replace(self.p, same_error=True), "flat", "hierarchy")
        self.assertLess(neutral, base)

    def test_total_cost_is_affine_in_c_comm(self):
        const = cost_flat(self.p, 0.0)["total"]
        slope = cost_flat(self.p, 1.0)["total"] - const
        self.assertAlmostEqual(cost_flat(self.p, 3.0)["total"], slope * 3.0 + const, places=6)

    def test_zero_overhead_still_has_a_crossover_from_verification(self):
        # even with free managers, self-review blind spots keep hierarchy from always winning
        c = S.crossover(dataclasses.replace(self.p, mgr_overhead=0.0), "flat", "hierarchy")
        self.assertIsNotNone(c)
        self.assertGreater(c, 0.0)

    def test_sweep_is_deterministic(self):
        self.assertEqual(S.run(), S.run())

    def test_sweep_reports_all_expected_sections(self):
        r = S.run()
        for key in ("headline", "regime_sequence_as_c_comm_falls", "phase_2d",
                    "sensitivity_mgr_overhead", "isolate_coordination_only"):
            self.assertIn(key, r)


if __name__ == "__main__":
    unittest.main()
