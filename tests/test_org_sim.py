"""Tests for the agent-organization simulator (deterministic mock agent + sandbox)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import experiments.org_sim as M  # noqa: E402
from experiments.org_sim import TASKS, correctness, quality, run, _mock  # noqa: E402


class OrgSimTests(unittest.TestCase):
    def setUp(self):
        M._CALL = _mock                                  # deterministic mock agent
        self.r = run("mock", TASKS[:2], measure_correctness=False)   # static only = hermetic/fast

    def test_overhead_ordering_flat_market_hierarchy(self):
        a = self.r["aggregate"]
        self.assertEqual(a["flat"]["avg_calls"], 3.0)
        self.assertEqual(a["market"]["avg_calls"], 4.0)
        self.assertEqual(a["hierarchy"]["avg_calls"], 5.0)   # manager overhead is largest

    def test_quality_rewards_coverage_and_consistency(self):
        t = TASKS[0]
        full = "\n".join(f"def {n}(x):\n    return x" for n in t["names"]) + \
               "\n" + "\n".join(f"def test_{n}():\n    {n}(1)" for n in t["names"])
        partial = f"def {t['names'][0]}(x):\n    return x\ndef test_x():\n    {t['names'][0]}(1)"
        self.assertEqual(quality(t, full)["quality"], 1.0)
        self.assertLess(quality(t, partial)["quality"], 1.0)

    def test_every_cell_measured(self):
        self.assertEqual(len(self.r["rows"]), 2 * 3)     # 2 tasks x 3 structures

    def test_sandbox_distinguishes_correct_from_incorrect(self):
        good = "def add(a,b):\n    return a+b\ndef test_g():\n    assert add(2,3)==5\n"
        bad = "def add(a,b):\n    return a-b\ndef test_b():\n    assert add(2,3)==5\n"
        gc = correctness(good)
        if not gc["ran"]:
            self.skipTest("sandbox unavailable in this environment")
        self.assertEqual(gc["correctness"], 1.0)
        self.assertEqual(correctness(bad)["correctness"], 0.0)

    def test_sandbox_runs_pytest_style_tests(self):
        # the manager-integrator emits pytest (import pytest, @parametrize) wrapped in
        # markdown — the shim must run it, else correctness measures test-format not truth
        art = ('**u.py**\n\n```python\nimport pytest\n'
               'def clamp(x,lo,hi): return max(lo,min(hi,x))\n'
               '@pytest.mark.parametrize("x,e",[(5,5),(-1,0),(99,10)])\n'
               'def test_c(x,e): assert clamp(x,0,10)==e\n```\n\nNo changes needed.')
        c = correctness(art)
        if not c["ran"]:
            self.skipTest("sandbox unavailable in this environment")
        self.assertTrue(c["ran"])
        self.assertEqual(c["correctness"], 1.0)        # markdown + pytest both handled

    def test_deterministic_on_mock(self):
        self.assertEqual(run("mock", TASKS[:2], measure_correctness=False), self.r)


if __name__ == "__main__":
    unittest.main()
