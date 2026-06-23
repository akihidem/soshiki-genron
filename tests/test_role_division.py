"""Tests for role_division — 役割分業 coordinator の決定的ハーネスを検品する。

mock が砦：科学的結論は出さず、(1) 決定性 (2) コスト算術 (3) repair ループ制御 (4) de-confound 算術
(5) null→gain0 / positive→gain>0（rig されてない両方向の証拠） (6) gold-leak 遮断 (7) 実LLM seam の
配線/キャッシュ を確かめる。本体（market_external / meshflow）は読むだけで破壊しない。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.role_division import (  # noqa: E402
    Roles, _deconfound, _real_arms, _run_mock_demo, _cached_real_call,
    make_mock_call, make_mock_grade, run_groups, run_role_division, run_solo, main,
    _NULL_WORLD, _POSITIVE_WORLD, _MOCK_TASKS, _mock_arms, _TAGS,
)


def _calls_by_role(result, role):
    return [m for (r, m) in result["calls"] if r == role]


class RoleDivisionHarnessTests(unittest.TestCase):

    # (a) 決定性 — 同じ mock 入力で2回まったく同じ結果
    def test_deterministic(self):
        call, grade = make_mock_call(_POSITIVE_WORLD), make_mock_grade(_POSITIVE_WORLD)
        r1 = run_groups(_MOCK_TASKS, _mock_arms(), call, grade, n_iter=2, trials=1)
        r2 = run_groups(_MOCK_TASKS, _mock_arms(), call, grade, n_iter=2, trials=1)
        self.assertEqual(r1, r2)

    # (b) コスト = Σ(role 呼び出し × tier weight)・手計算と一致（positive world, hard task）
    def test_cost_accounting_matches_hand_count(self):
        call, grade = make_mock_call(_POSITIVE_WORLD), make_mock_grade(_POSITIVE_WORLD)
        hard = {"id": "hard", "names": ["g"], "spec": "hard"}
        solo = run_solo("opus", hard, call, grade)
        same = run_role_division(Roles("opus", "opus", "opus"), hard, call, grade, n_iter=2, group="role_same")
        cross = run_role_division(Roles("opus", "sonnet", "haiku"), hard, call, grade, n_iter=2, group="role_cross")
        self.assertEqual(solo["cost"], 15.0)                       # opus 単発
        self.assertEqual(cross["cost"], 22.0)                      # think15 + work3 + verify1 + work3（1 repair で解決）
        self.assertEqual(same["cost"], 90.0)                       # think15 + work15 + (verify15+work15)*2（解けず n_iter 使い切り）

    # (c) repair ループが n_iter を尊重・gold=1.0 / LGTM で早停止
    def test_repair_loop_respects_n_iter_and_early_stop(self):
        gp = make_mock_grade(_POSITIVE_WORLD)
        cp = make_mock_call(_POSITIVE_WORLD)
        hard = {"id": "hard", "names": ["g"], "spec": "hard"}
        # 解けない same: worker 呼びは 1(初期)+n_iter、verifier は n_iter
        same = run_role_division(Roles("opus", "opus", "opus"), hard, cp, gp, n_iter=2, group="role_same")
        self.assertEqual(len(_calls_by_role(same, "worker")), 3)   # 1 + 2 repairs
        self.assertEqual(len(_calls_by_role(same, "verifier")), 2)
        self.assertLess(same["score"], 1.0)
        # 解ける cross: gold=1.0 で repair を1回で打ち切る
        cross = run_role_division(Roles("opus", "sonnet", "haiku"), hard, cp, gp, n_iter=5, group="role_cross")
        self.assertEqual(cross["score"], 1.0)
        self.assertEqual(len(_calls_by_role(cross, "worker")), 2)  # 初期 + 1 repair のみ（n_iter=5 だが早停止）
        self.assertEqual(len(_calls_by_role(cross, "verifier")), 1)

    def test_lgtm_stops_loop_immediately(self):
        # verify_power<0 -> Verifier が LGTM -> 直さず即停止（repair なし）
        world = {"diff": {"hard": 3}, "cap": {"opus": 2}, "plan_boost": {}, "verify_power": {"opus": -1}}
        r = run_role_division(Roles("opus", "opus", "opus"),
                              {"id": "hard", "names": ["g"], "spec": "hard"},
                              make_mock_call(world), make_mock_grade(world), n_iter=3, group="role_same")
        self.assertEqual(len(_calls_by_role(r, "worker")), 1)      # 初期のみ・repair なし
        self.assertEqual(len(_calls_by_role(r, "verifier")), 1)
        self.assertEqual([i["stage"] for i in r["iters"]], ["initial", "lgtm"])

    # (d) de-confound 算術（純粋計算）
    def test_deconfound_arithmetic(self):
        cells = [{"task": "t", "group": "solo", "mean_score": 0.4, "mean_cost": 15},
                 {"task": "t", "group": "role_same", "mean_score": 0.6, "mean_cost": 90},
                 {"task": "t", "group": "role_cross", "mean_score": 0.9, "mean_cost": 22}]
        s = _deconfound(cells)
        self.assertEqual(s["structure_gain (role_same - solo)"], 0.2)     # 0.6 - 0.4
        self.assertEqual(s["diversity_gain (role_cross - role_same)"], 0.3)  # 0.9 - 0.6
        self.assertEqual(s["total_gain (role_cross - solo)"], 0.5)        # 0.9 - 0.4

    # (e) null world -> 全 gain ≈ 0（市場支配の再現＝harness が rig されてない）
    def test_null_world_no_ignition(self):
        call, grade = make_mock_call(_NULL_WORLD), make_mock_grade(_NULL_WORLD)
        s = run_groups(_MOCK_TASKS, _mock_arms(), call, grade, n_iter=2, trials=1)["summary"]
        self.assertEqual(s["structure_gain (role_same - solo)"], 0.0)
        self.assertEqual(s["diversity_gain (role_cross - role_same)"], 0.0)
        self.assertEqual(s["total_gain (role_cross - solo)"], 0.0)

    # (f) positive world -> diversity_gain > 0（haiku が有効な検証者の時だけ点火を検出）
    def test_positive_world_detects_diversity_gain(self):
        call, grade = make_mock_call(_POSITIVE_WORLD), make_mock_grade(_POSITIVE_WORLD)
        s = run_groups(_MOCK_TASKS, _mock_arms(), call, grade, n_iter=2, trials=1)["summary"]
        self.assertGreater(s["diversity_gain (role_cross - role_same)"], 0.0)
        self.assertEqual(s["structure_gain (role_same - solo)"], 0.0)     # plan 力0 で構造単独は効かない
        self.assertEqual(s["diversity_gain (role_cross - role_same)"], 0.166)  # 1.0 - mean([1.0,0.667])=0.834

    # (g) gold-leak ガード：どの role に渡る prompt にも task["gold"] が含まれない（特に VERIFIER）
    def test_no_gold_leak_to_any_role(self):
        sentinel = "GOLD_SECRET_ASSERT_XYZ"
        task = {"id": "hard", "names": ["g"], "spec": "do the thing", "gold": f"def gold_0(): assert {sentinel}"}
        seen = {"verifier": [], "all": []}

        def recording_call(model, prompt, seed=0):
            seen["all"].append(prompt)
            if prompt.startswith(_TAGS["verifier"]):
                seen["verifier"].append(prompt)
            # 解けないようにして verifier を必ず複数回踏ませる
            return make_mock_call(_NULL_WORLD)(model, prompt, seed)

        run_role_division(Roles("opus", "sonnet", "haiku"), task, recording_call,
                          make_mock_grade({"diff": {"hard": 99}}), n_iter=2, group="role_cross")
        self.assertTrue(seen["verifier"], "verifier should have been called")
        for p in seen["all"]:
            self.assertNotIn(sentinel, p)                          # gold は spec/names だけの prompt に絶対出ない

    # (h) 実LLM seam の配線とキャッシュ（metered 保護）
    def test_real_arms_assignment(self):
        arms = _real_arms()
        self.assertEqual(arms["solo"], "opus")
        self.assertEqual(arms["role_same"], Roles("opus", "opus", "opus"))
        self.assertEqual(arms["role_cross"], Roles("opus", "sonnet", "haiku"))  # §8: verifier=haiku

    def test_real_call_caches_by_model_prompt_seed(self):
        import experiments.market_external as MX
        calls = []
        orig = MX._route
        MX._route = lambda model, prompt, timeout=None: (calls.append((model, prompt)) or f"out:{model}")
        try:
            cache = {}
            call = _cached_real_call(cache, None)                  # cache_path=None -> ディスク書き込みなし
            a = call("opus", "PROMPT_A", 0)
            b = call("opus", "PROMPT_A", 0)                        # 同一 -> キャッシュ命中で _route 再呼びなし
            c = call("opus", "PROMPT_A", 1)                        # seed 違い -> 別サンプル
            self.assertEqual(a, b)
            self.assertEqual(len(calls), 2)                        # (seed0) + (seed1) の 2 回だけ
            self.assertEqual(a, "out:opus")
        finally:
            MX._route = orig

    # デモ全体が exit 0・両世界を返す
    def test_demo_runs_and_returns_both_worlds(self):
        res = _run_mock_demo()
        self.assertIn("null_world", res)
        self.assertIn("positive_world", res)
        self.assertEqual(main([]), 0)                              # role_division_demo.json を書いて 0


if __name__ == "__main__":
    unittest.main()
