"""Tests for the market-allocation threshold model (escalation dominates iff p > w/s)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.market import (MarketParams, dominates, escalation_cost,  # noqa: E402
                          ladder, p_star, run)


class MarketModelTests(unittest.TestCase):
    def test_escalation_cost_matches_measured_gap(self):
        # gemma w=0.2, haiku s=1.0, gemma solves 4/6 -> measured market cost 0.533
        self.assertAlmostEqual(escalation_cost(0.2, 1.0, 4 / 6), 0.533, places=2)

    def test_threshold_is_cost_ratio(self):
        self.assertEqual(p_star(0.2, 1.0), 0.2)
        self.assertEqual(p_star(1.0, 15.0), round(1 / 15, 4))

    def test_dominates_above_threshold_not_below(self):
        # cost ratio w/s = 0.2 -> dominates iff p > 0.2
        self.assertTrue(dominates(0.2, 1.0, 0.3))
        self.assertFalse(dominates(0.2, 1.0, 0.1))

    def test_homogeneous_never_dominates(self):
        # w == s -> p* = 1 -> needs p > 1 (impossible) -> market can't beat flat
        self.assertFalse(dominates(1.0, 1.0, 1.0))
        self.assertFalse(dominates(1.0, 1.0, 0.99))

    def test_ladder_reproduces_gap_experiment(self):
        g = ladder([(0.2, 4 / 6), (1.0, 1.0), (15.0, 1.0)])
        self.assertAlmostEqual(g["cost"], 0.533, places=2)
        self.assertEqual(g["correctness"], 1.0)             # haiku always solves -> full correctness

    def test_three_regimes_match_measurements(self):
        regimes = {rg["regime"][0]: rg for rg in run()["empirical_regimes"]}
        self.assertFalse(regimes["①"]["dominates"])         # homogeneous -> market loses
        self.assertFalse(regimes["②"]["dominates"])         # no gradient -> ties best single model
        self.assertTrue(regimes["③"]["dominates"])          # large gap -> market dominates

    def test_the_measured_regime_carries_the_sampling_floor(self):
        """③ の p は**実測の推定量 p̂** ── 定理の答えだけでなく床を通した判定も持つこと。

        `dominates` は「与えた p が真なら」の定理の答えであって*実測からの判定*ではない。
        実測レジームだけ床（GAP.md）を通す。①② は w=s/p=1 が構成上決まる解析点＝床の対象外。
        """
        regimes = {rg["regime"][0]: rg for rg in run()["empirical_regimes"]}
        self.assertEqual(regimes["①"]["verdict"], "ANALYTIC")
        self.assertEqual(regimes["②"]["verdict"], "ANALYTIC")
        third = regimes["③"]
        self.assertEqual(third["n_tasks"], 6)               # 実測は n=6 タスク
        self.assertEqual(third["crit_upper"], 0.6667)       # 支配に要る p̂
        self.assertEqual(third["verdict"], "DOMINATES")     # p̂=0.8888 は床を越える
        self.assertGreaterEqual(third["p"], third["crit_upper"])

    def test_run_is_deterministic(self):
        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
