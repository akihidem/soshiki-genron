"""Tests for the Goodhart / code-overfitting experiment (deterministic mock)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import experiments.goodhart as G  # noqa: E402
from experiments.goodhart import EXT_TASKS, _visible, grade, run_goodhart  # noqa: E402


class GoodhartTests(unittest.TestCase):
    def test_visible_extracts_proxy_cases(self):
        vis = _visible(EXT_TASKS[0])                     # roman gold
        self.assertEqual(len(vis), 3)
        self.assertTrue(any("int_to_roman" in v for v in vis))

    def test_mock_yields_zero_loss(self):
        if not grade("def int_to_roman(n): return 'I'\n", EXT_TASKS[0])["ran"]:
            self.skipTest("sandbox unavailable in this environment")
        G._CALL = G._mock                                # None impls -> both conditions score 0
        r = run_goodhart("mock")
        self.assertEqual(r["avg_gold_spec"], 0.0)
        self.assertEqual(r["avg_gold_proxy"], 0.0)
        self.assertEqual(r["goodhart_loss"], 0.0)

    def test_mock_is_deterministic(self):
        G._CALL = G._mock
        self.assertEqual(run_goodhart("mock"), run_goodhart("mock"))


if __name__ == "__main__":
    unittest.main()
