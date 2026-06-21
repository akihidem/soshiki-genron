"""Tests for the agent-organization simulator (deterministic mock agent)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import experiments.org_sim as M  # noqa: E402
from experiments.org_sim import TASKS, quality, run, _mock  # noqa: E402


class OrgSimTests(unittest.TestCase):
    def setUp(self):
        M._CALL = _mock                      # use the deterministic mock agent
        self.r = run("mock", TASKS[:2])

    def test_hierarchy_costs_more_calls_than_flat(self):
        a = self.r["aggregate"]
        self.assertGreater(a["hierarchy"]["avg_calls"], a["flat"]["avg_calls"])  # manager overhead

    def test_quality_rewards_coverage_and_consistency(self):
        t = TASKS[0]
        full = "\n".join(f"def {n}(x):\n    return x" for n in t["names"]) + \
               "\n" + "\n".join(f"def test_{n}():\n    {n}(1)" for n in t["names"])
        partial = f"def {t['names'][0]}(x):\n    return x\ndef test_x():\n    {t['names'][0]}(1)"
        self.assertEqual(quality(t, full)["quality"], 1.0)
        self.assertLess(quality(t, partial)["quality"], 1.0)

    def test_every_cell_measured(self):
        self.assertEqual(len(self.r["rows"]), 2 * 2)   # 2 tasks x 2 structures
        self.assertTrue(all("quality" in row for row in self.r["rows"]))

    def test_deterministic_on_mock(self):
        self.assertEqual(run("mock", TASKS[:2]), self.r)


if __name__ == "__main__":
    unittest.main()
