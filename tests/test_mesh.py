"""Tests for model/mesh.py — 合議 mesh が単体最強を超える臨界（脱相関）の解析モデル。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.mesh import (  # noqa: E402
    mesh_correctness, mesh_gain, ignites, mesh_cost,
    dominates_strong, min_agents_to_match_strong, p_all_fail, run,
    failure_correlation, union_solve, empirical_mesh,
)


class MeshModelTests(unittest.TestCase):
    def test_gain_matches_closed_form(self):
        for p in (0.2, 0.5, 0.8):
            for rho in (0.0, 0.3, 1.0):
                for n in (2, 3, 5):
                    expect = (1 - rho) * (1 - p) * (1 - (1 - p) ** (n - 1))
                    self.assertAlmostEqual(mesh_gain(p, rho, n), round(expect, 6), places=6)

    def test_union_equals_single_plus_gain(self):
        for p in (0.3, 0.6):
            for rho in (0.0, 0.5):
                for n in (2, 4):
                    self.assertAlmostEqual(mesh_correctness(p, rho, n), p + mesh_gain(p, rho, n), places=6)

    def test_critical_point_rho_one_kills_gain(self):
        # ρ=1（完全相関＝入れ子/hard core）→ 利得 0 ＝ 市場支配
        for p in (0.2, 0.5, 0.9):
            for n in (2, 4, 8):
                self.assertEqual(mesh_gain(p, 1.0, n), 0.0)
                self.assertFalse(ignites(p, 1.0, n))

    def test_no_gain_at_degenerate_p_or_single_agent(self):
        self.assertEqual(mesh_gain(0.0, 0.0, 4), 0.0)     # 誰も解けない
        self.assertEqual(mesh_gain(1.0, 0.0, 4), 0.0)     # 全員必ず解く（縁なし）
        self.assertEqual(mesh_gain(0.5, 0.0, 1), 0.0)     # 1 エージェント＝mesh でない

    def test_gain_monotonic_decreasing_in_rho(self):
        gains = [mesh_gain(0.5, r / 10, 3) for r in range(0, 11)]   # rho 0.0..1.0
        self.assertTrue(all(gains[i] >= gains[i + 1] for i in range(len(gains) - 1)))
        self.assertGreater(gains[0], gains[-1])           # 脱相関で利得が立つ

    def test_gain_increasing_in_n_when_decorrelated(self):
        gains = [mesh_gain(0.5, 0.0, n) for n in range(1, 7)]
        self.assertTrue(all(gains[i] <= gains[i + 1] for i in range(len(gains) - 1)))

    def test_gain_capped_by_one_minus_p_as_n_grows(self):
        # n→∞ で利得 → (1−ρ)(1−p)（相関と素の難度が天井）
        cap = (1 - 0.3) * (1 - 0.4)                       # rho=0.3, p=0.4
        self.assertLess(mesh_gain(0.4, 0.3, 50), round(cap, 6) + 1e-9)
        self.assertAlmostEqual(mesh_gain(0.4, 0.3, 200), round(cap, 6), places=4)

    def test_p_all_fail_endpoints(self):
        self.assertAlmostEqual(p_all_fail(0.5, 0.0, 2), 0.25, places=6)   # independent: q^2
        self.assertAlmostEqual(p_all_fail(0.5, 1.0, 2), 0.5, places=6)    # comonotone: q

    def test_cost_and_strong_domination(self):
        self.assertAlmostEqual(mesh_cost(3, 0.2, 0.1), 0.9, places=6)     # 3*(0.2+0.1)
        # weak mesh reaching correctness 1 at low n+cost can dominate a pricey strong model
        self.assertTrue(dominates_strong(p=1.0, rho=0.0, n=2, w=0.2, s=1.0, verify=0.1))  # union=1, cost0.6<1
        # but if it can't reach correctness 1, it does not dominate
        self.assertFalse(dominates_strong(p=0.5, rho=0.5, n=2, w=0.2, s=1.0, verify=0.1))

    def test_min_agents_to_match_strong(self):
        r = min_agents_to_match_strong(p=0.5, rho=0.0, w=0.2, s=1.0, verify=0.1, target=0.99)
        self.assertIsNotNone(r["n"])                      # independent weak agents can reach 0.99
        self.assertEqual(r["cost_dominates_strong"], r["cost"] < 1.0)
        # fully correlated -> union capped at p=0.5 -> never reaches 0.99
        rc = min_agents_to_match_strong(p=0.5, rho=1.0, w=0.2, s=1.0, verify=0.1, target=0.99)
        self.assertIsNone(rc["n"])

    def test_failure_correlation_endpoints(self):
        # 同一の解パターン → 失敗 comonotone → ρ=1
        self.assertAlmostEqual(failure_correlation([[1, 0, 1, 0], [1, 0, 1, 0]]), 1.0, places=4)
        # 反相関（片方解く＝他方落とす） → ρ=-1
        self.assertAlmostEqual(failure_correlation([[1, 0, 1, 0], [0, 1, 0, 1]]), -1.0, places=4)

    def test_union_solve(self):
        self.assertEqual(union_solve([[1, 0, 0], [0, 1, 0]]), round(2 / 3, 4))   # どちらか解けた=2/3

    def test_empirical_mesh_ignites_only_with_mutual_complementarity(self):
        # 相互相補（各自が相手の落とす所を拾う）→ union>best → 点火
        e = empirical_mesh([[1, 1, 0], [0, 1, 1]])
        self.assertEqual(e["union"], 1.0)
        self.assertGreater(e["gain"], 0.0)
        self.assertTrue(e["ignites"])
        # 入れ子（B が A を包む・非対称）→ union=best → 利得 0（ρ<1 でも点火しない）
        e2 = empirical_mesh([[0, 1, 0], [0, 1, 1]])
        self.assertEqual(e2["gain"], 0.0)
        self.assertFalse(e2["ignites"])
        self.assertLess(e2["failure_rho"], 1.0)              # 脱相関はしている

    def test_real_swebench_is_reported_from_trials2_not_trials1(self):
        """実測点は **trials=2 の頑健値のみ**。単一試行の +0.042 は撤回済みで、点火として載せない。

        この repo は 2026-06-23 に trials=2 で「mesh 点火」を撤回した(SWEBENCH_TRIALS.md)のに、
        翌日 model/mesh.py に trial-1 のベクトルを入れて「初の点火」を*再*公開してしまい、
        旧テストが `assertTrue(ignites)` でそれを固定していた。本テストはその再発を防ぐ。
        """
        er = run()["empirical_real"]
        full = er["opus×codex full-24 (trials=2, robust)"]
        self.assertEqual(full["trials"], 2)
        self.assertEqual(full["gain"], 0.0)                  # 安定な相互相補ゼロ
        self.assertEqual((full["a_only"], full["b_only"]), (1, 0))   # 一方向（sympy-24443 のみ）
        self.assertEqual(full["unstable_cells"], 3)          # opus の run noise 3/24
        self.assertFalse(full["ignites"])                    # ← 旧テストはここが True だった

    def test_no_empirical_point_claims_ignition(self):
        # 実測の点はどれも検出床を超えていない＝「real frontier で mesh が点火した」実測は*無い*
        for name, e in run()["empirical_real"].items():
            self.assertFalse(e["ignites"], msg=name)
            self.assertGreaterEqual(e["trials"], 2, msg=f"{name}: 単一試行の値を載せてはいけない")

    def test_ignition_is_gated_by_the_detection_floor_not_by_gain_gt_zero(self):
        # 「点火」の判定は gain>0 でなく gain(タスク数) ≥ 検出床。床は noise.py が計算する。
        for name, e in run()["empirical_real"].items():
            self.assertIsNotNone(e["floor_tasks"], msg=name)
            self.assertEqual(e["ignites"], e["gain_tasks"] >= e["floor_tasks"], msg=name)

    def test_retracted_point_is_kept_visible_and_below_floor(self):
        # 撤回済みの点は消さずに残す（本リポの作法）。ただし点火としては数えない。
        ret = run()["retracted"]
        key = "opus×codex full-24 (trial-1 のみ) — RETRACTED"
        self.assertIn(key, ret)
        self.assertEqual(ret[key]["trials"], 1)
        self.assertAlmostEqual(ret[key]["gain"], 0.0417, places=3)   # 当時「初の点火」と報告した値
        self.assertEqual(ret[key]["gain_tasks"], 1)                  # 1 タスク分（床は 3 タスク）

    def test_rho_itself_is_unstable_across_trials(self):
        # 解析モデルが依存する ρ すら、単一試行では決まらない（0.61 → 0.89 に振れる）
        full = run()["empirical_real"]["opus×codex full-24 (trials=2, robust)"]
        rhos = full["failure_rho_by_trial"]
        self.assertEqual(len(rhos), 2)
        self.assertGreater(abs(rhos[0] - rhos[1]), 0.2)
        self.assertTrue(all(r < 1.0 for r in rhos))          # ρ<1（脱相関）なのに gain 0
        self.assertEqual(full["gain"], 0.0)                  # ＝解析の「ρ<1 ⟹ 点火」の実測反証

    def test_empirical_regimes_and_determinism(self):
        r1 = run()
        r2 = run()
        self.assertEqual(r1, r2)                          # 決定的
        regimes = {rg["regime"]: rg for rg in r1["empirical_regimes"]}
        # 冗長 mesh（ρ≈1）は不点火、edge demo（ρ=0）は点火
        self.assertFalse(any(rg["ignites"] for rg in regimes.values() if rg["rho"] == 1.0))
        self.assertTrue(any(rg["ignites"] for rg in regimes.values() if rg["rho"] == 0.0))


if __name__ == "__main__":
    unittest.main()
