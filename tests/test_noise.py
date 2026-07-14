"""Tests for model/noise.py — 非決定な採点ハーネスの検出床（trials=1 の偽点火を弾く床）。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.mesh import empirical_mesh  # noqa: E402
from model.noise import (  # noqa: E402
    SWE6_FABLE_T1, SWE6_FABLE_T2,
    SWE24_CODEX_T1, SWE24_CODEX_T2, SWE24_OPUS_T1, SWE24_OPUS_T2,
    TrueStructure, detection_floor, disagreement_rate, effective_flip, flip_from_disagreement,
    gain_from_counts, min_trials_for, null_joint, p_gain_ge, reportable, robust_counts, run,
    split_counts, stable_vector, swebench_case,
)


def _brute_force_joint(st: TrueStructure, fa: float, fb: float) -> dict:
    """DP(null_joint) と**独立に**、セルごとの (A観測, B観測) を全列挙して (a,b) の同時分布を作る。

    null_joint は種別ごとの (pa, pb) を先に畳んだ実装。こちらは「真値が確率 f で反転する」という
    生の意味論からだけ組み立てる ⟹ _observed_probs の導出そのものを検品できる。
    """
    cells = ([(1, 1)] * st.common + [(1, 0)] * st.a_only +
             [(0, 1)] * st.b_only + [(0, 0)] * st.neither)
    dist = {(0, 0): 1.0}
    for ta, tb in cells:
        nxt: dict = {}
        for oa in (0, 1):
            pa = (1 - fa) if oa == ta else fa       # 真値 ta が oa と観測される確率
            for ob in (0, 1):
                pb = (1 - fb) if ob == tb else fb
                p = pa * pb
                da = 1 if (oa == 1 and ob == 0) else 0
                db = 1 if (ob == 1 and oa == 0) else 0
                for (a, b), q in dist.items():
                    nxt[(a + da, b + db)] = nxt.get((a + da, b + db), 0.0) + q * p
        dist = nxt
    return dist


class GainIdentityTests(unittest.TestCase):
    """① gain = min(a,b)/n ── 「点火には*相互*相補が要る」を定理として検品する。"""

    def test_split_counts(self):
        c = split_counts([1, 1, 0, 0], [1, 0, 1, 0])
        self.assertEqual((c["common"], c["a_only"], c["b_only"], c["neither"]), (1, 1, 1, 1))
        self.assertEqual(c["n"], 4)

    def test_identity_agrees_with_independent_mesh_implementation(self):
        # mesh.empirical_mesh は union/best から gain を出す別実装。恒等式と一致するはず。
        cases = [
            ([1, 1, 0], [0, 1, 1]),          # 相互相補
            ([0, 1, 0], [0, 1, 1]),          # 入れ子
            ([1, 0, 1, 0], [1, 0, 1, 0]),    # 一致
            ([1, 1, 1], [0, 0, 0]),          # 片方が全部
            (SWE24_OPUS_T1, SWE24_CODEX_T1),
            (SWE24_OPUS_T2, SWE24_CODEX_T2),
        ]
        for va, vb in cases:
            c = split_counts(va, vb)
            identity = gain_from_counts(c["a_only"], c["b_only"], c["n"])
            via_union = empirical_mesh([va, vb])["gain"]
            self.assertAlmostEqual(identity, via_union, places=4, msg=f"{va} vs {vb}")

    def test_gain_zero_unless_mutual(self):
        # 入れ子（B ⊇ A）は a=0 → gain 0（脱相関していても点火しない）
        self.assertEqual(gain_from_counts(0, 5, 10), 0.0)
        self.assertEqual(gain_from_counts(5, 0, 10), 0.0)
        self.assertGreater(gain_from_counts(1, 3, 24), 0.0)     # 相互 → >0
        self.assertAlmostEqual(gain_from_counts(1, 3, 24), 1 / 24, places=6)   # min(1,3)=1

    def test_gain_degenerate_n(self):
        self.assertEqual(gain_from_counts(1, 1, 0), 0.0)


class NoiseEstimationTests(unittest.TestCase):
    """② 実測ノイズ: 不一致率 d → 反転率 f → 多数決後の f_eff。"""

    def test_measured_disagreement_matches_swebench_trials_md(self):
        # SWEBENCH_TRIALS.md: opus は ~3/24 = 12% の run-to-run variance、codex は完全再現。
        self.assertAlmostEqual(disagreement_rate([SWE24_OPUS_T1, SWE24_OPUS_T2]), 3 / 24, places=6)
        self.assertEqual(disagreement_rate([SWE24_CODEX_T1, SWE24_CODEX_T2]), 0.0)
        # fable は 3/6 flip（SWEBENCH_FABLE_PT6.md）
        self.assertAlmostEqual(disagreement_rate([SWE6_FABLE_T1, SWE6_FABLE_T2]), 0.5, places=6)

    def test_disagreement_rate_rejects_ragged_input(self):
        with self.assertRaises(ValueError):
            disagreement_rate([[1, 0, 1], [1, 0]])

    def test_flip_from_disagreement_is_inverse_of_2f_1_minus_f(self):
        for f in (0.0, 0.01, 0.067, 0.1, 0.2, 0.4, 0.49):
            d = 2 * f * (1 - f)
            self.assertAlmostEqual(flip_from_disagreement(d), f, places=9)

    def test_flip_from_disagreement_saturates_outside_model(self):
        self.assertEqual(flip_from_disagreement(0.0), 0.0)
        self.assertEqual(flip_from_disagreement(0.5), 0.5)      # fable: 対称モデルの縁
        self.assertEqual(flip_from_disagreement(0.9), 0.5)      # 表現域外 → 0.5 に飽和

    def test_effective_flip_trials1_is_identity(self):
        for f in (0.0, 0.067, 0.3, 0.5):
            self.assertAlmostEqual(effective_flip(f, 1), f, places=9)

    def test_effective_flip_trials3_closed_form(self):
        for f in (0.05, 0.067, 0.125, 0.3):
            expect = 3 * f * f * (1 - f) + f ** 3
            self.assertAlmostEqual(effective_flip(f, 3), expect, places=9)

    def test_effective_flip_monotone_decreasing_in_trials(self):
        f = 0.125
        vals = [effective_flip(f, t) for t in (1, 3, 5, 7, 9)]
        self.assertTrue(all(vals[i] > vals[i + 1] for i in range(len(vals) - 1)))

    def test_effective_flip_coinflip_never_improves(self):
        # f=0.5 は情報ゼロ → 何回重ねても 0.5（fable のケース）
        for t in (1, 3, 5, 9, 21):
            self.assertAlmostEqual(effective_flip(0.5, t), 0.5, places=9)

    def test_effective_flip_even_trials_tie_broken_pessimistically(self):
        # trials=2: 1勝1敗の同数を 1/2 で誤りに倒す → f_eff = f²+ f(1−f) = f
        for f in (0.1, 0.25):
            self.assertAlmostEqual(effective_flip(f, 2), f, places=9)


class RobustEstimatorTests(unittest.TestCase):
    """③ 割れたセルは相補性の証拠に使えない（SWEBENCH_TRIALS.md の手作業を機械化）。"""

    def test_stable_vector_marks_disagreements_none(self):
        self.assertEqual(stable_vector([[1, 0, 1], [1, 1, 1]]), [1, None, 1])

    def test_robust_counts_reproduces_swebench_trials_md(self):
        rb = robust_counts([SWE24_OPUS_T1, SWE24_OPUS_T2], [SWE24_CODEX_T1, SWE24_CODEX_T2])
        # SWEBENCH_TRIALS.md の結論をベクトルから機械で再現する:
        #   安定 opus-only は sympy-24443 の 1 件のみ / 安定 codex-only は 0 件 / robust gain = 0
        self.assertEqual(rb["a_only"], 1)
        self.assertEqual(rb["b_only"], 0)
        self.assertEqual(rb["unstable"], 3)       # 11148 / 24325 / 24661
        self.assertEqual(rb["gain"], 0.0)
        self.assertEqual(rb["n"], 24)
        self.assertEqual(rb["common"] + rb["a_only"] + rb["b_only"] + rb["neither"]
                         + rb["unstable"], 24)

    def test_trials1_robust_degenerates_to_naive(self):
        # trials=1 では「安定」が意味を持たない ⟹ 頑健推定は naive に退化する＝床を持てない
        rb = robust_counts([SWE24_OPUS_T1], [SWE24_CODEX_T1])
        nv = split_counts(SWE24_OPUS_T1, SWE24_CODEX_T1)
        self.assertEqual((rb["a_only"], rb["b_only"]), (nv["a_only"], nv["b_only"]))
        self.assertEqual(rb["unstable"], 0)
        self.assertAlmostEqual(rb["gain"], 1 / 24, places=4)   # ＝当時報告した +0.042


class NullDistributionTests(unittest.TestCase):
    """④ 帰無分布と検出床（厳密 DP）。"""

    def test_joint_is_a_probability_distribution(self):
        st = TrueStructure(common=5, a_only=2, b_only=1, neither=3)
        for fa, fb in ((0.0, 0.0), (0.1, 0.0), (0.1, 0.2), (0.5, 0.5)):
            total = sum(null_joint(st, fa, fb, trials=1).values())
            self.assertAlmostEqual(total, 1.0, places=9)

    def test_dp_matches_independent_brute_force(self):
        """DP を、生の反転意味論から組んだ別実装と突き合わせる（_observed_probs の検品）。"""
        for st in (TrueStructure(3, 1, 1, 2), TrueStructure(4, 2, 0, 1), TrueStructure(0, 0, 0, 3)):
            for fa, fb in ((0.0, 0.0), (0.067, 0.0), (0.2, 0.15), (0.5, 0.3)):
                dp = null_joint(st, fa, fb, trials=1)
                bf = _brute_force_joint(st, fa, fb)
                keys = set(dp) | set(bf)
                for k in keys:
                    self.assertAlmostEqual(dp.get(k, 0.0), bf.get(k, 0.0), places=9,
                                           msg=f"st={st} fa={fa} fb={fb} key={k}")

    def test_dp_matches_closed_form_when_grader_b_is_deterministic(self):
        """fb=0 なら a と b は素なタスク集合から来る ⟹ P(min≥m) = P(a≥m)·P(b≥m)。"""
        st = TrueStructure(common=18, a_only=1, b_only=0, neither=5)
        fa, fb, trials = 0.067, 0.0, 1

        def _tail(counts_probs, m):
            """独立ベルヌーイ和の裾 P(X ≥ m)（counts_probs = [(n, p), ...]）。"""
            dist = {0: 1.0}
            for n_, p_ in counts_probs:
                for _ in range(n_):
                    nxt: dict = {}
                    for k, q in dist.items():
                        nxt[k + 1] = nxt.get(k + 1, 0.0) + q * p_
                        nxt[k] = nxt.get(k, 0.0) + q * (1 - p_)
                    dist = nxt
            return sum(q for k, q in dist.items() if k >= m)

        # a は a_only(真に解く→(1−fa) で 1) と neither(真に落とす→fa で 1) から
        # b は common(真に解く→fa で 0 と誤観測) と b_only から
        for m in (1, 2, 3, 4):
            expect = (_tail([(st.a_only, 1 - fa), (st.neither, fa)], m)
                      * _tail([(st.common, fa), (st.b_only, 1 - fa)], m))
            self.assertAlmostEqual(p_gain_ge(st, fa, fb, trials, m), expect, places=9, msg=f"m={m}")

    def test_p_gain_ge_zero_is_one(self):
        st = TrueStructure(3, 1, 0, 2)
        self.assertEqual(p_gain_ge(st, 0.1, 0.1, 1, 0), 1.0)

    def test_deterministic_grader_needs_only_one_task(self):
        # ノイズゼロなら H0 の下で min(a,b)≥1 は確率 0 ⟹ 床は 1 タスク（1件でも相互相補なら本物）
        st = TrueStructure(common=18, a_only=1, b_only=0, neither=5)
        fl = detection_floor(st, 0.0, 0.0, trials=1)
        self.assertEqual(fl["m"], 1)
        self.assertEqual(fl["p_at_m"], 0.0)

    def test_floor_is_nonincreasing_in_trials(self):
        st = TrueStructure(common=18, a_only=1, b_only=0, neither=5)
        floors = [detection_floor(st, 0.067, 0.0, trials=t)["m"] for t in (1, 3, 5, 7)]
        self.assertTrue(all(floors[i] >= floors[i + 1] for i in range(len(floors) - 1)), floors)

    def test_floor_rises_with_noise(self):
        st = TrueStructure(common=18, a_only=1, b_only=0, neither=5)
        low = detection_floor(st, 0.02, 0.0, trials=1)["m"]
        high = detection_floor(st, 0.20, 0.0, trials=1)["m"]
        self.assertLess(low, high)

    def test_floor_requires_null_structure(self):
        with self.assertRaises(ValueError):
            detection_floor(TrueStructure(10, 2, 3, 5), 0.1, 0.0)   # 相互相補あり = H0 でない

    def test_p_at_m_actually_meets_alpha(self):
        st = TrueStructure(common=18, a_only=1, b_only=0, neither=5)
        fl = detection_floor(st, 0.067, 0.0, trials=1, alpha=0.05)
        self.assertLessEqual(fl["p_at_m"], 0.05)
        # 一段下（m-1）は α を超えている＝「最小の m」であることの検品
        self.assertGreater(p_gain_ge(st, 0.067, 0.0, 1, fl["m"] - 1), 0.05)


class RetractionWasPredictableTests(unittest.TestCase):
    """⑤ 本丸: 撤回された +0.042 は、trial-2 を回す*前に*床未満と判定できた。"""

    def test_retracted_gain_was_below_the_trials1_floor(self):
        s = swebench_case()
        self.assertEqual(s["trial1_naive"]["a_only"], 1)
        self.assertEqual(s["trial1_naive"]["b_only"], 3)
        self.assertAlmostEqual(s["trial1_naive"]["gain"], 0.0417, places=4)   # 当時の「点火」
        floor1 = next(f for f in s["floor_by_trials"] if f["trials"] == 1)
        self.assertEqual(floor1["floor_m_A"], 3)                              # 床は 3 タスク
        self.assertAlmostEqual(floor1["floor_gain_A"], 0.125, places=4)
        self.assertFalse(floor1["reportable_A"])                              # 観測 1 タスクは報告不可
        self.assertEqual(s["observed_gain_tasks"], 1)

    def test_noise_alone_explains_the_observation(self):
        # H0（相互相補ゼロ）＋opus の実測ノイズだけで、あの観測は過半の確率で出る
        s = swebench_case()
        self.assertGreater(s["p_trial1_gain_under_h0"], 0.5)
        self.assertAlmostEqual(s["p_trial1_gain_under_h0"], 0.6792, places=3)

    def test_conclusion_is_insensitive_to_how_f_is_estimated(self):
        """f の推定法を変えても『観測 1 タスクは床未満』という*結論*は動かない（床の値自体は動く）。"""
        s = swebench_case()
        observed = s["observed_gain_tasks"]                       # = 1
        for sv in s["f_sensitivity"]:                             # f = 0.05 / 0.067 / 0.10 / 0.125
            self.assertGreater(sv["floor_m_trials1"], observed, msg=f"f={sv['f_opus']}")
            self.assertGreater(sv["floor_m_trials3"], observed, msg=f"f={sv['f_opus']}")
            # ノイズだけで「点火」が出る確率は、どの f でも過半
            self.assertGreater(sv["p_false_ignition_trials1"], 0.5, msg=f"f={sv['f_opus']}")

    def test_floor_value_over_the_measured_f_range(self):
        """実測レンジ（対称モデル 0.067 〜 保守読み 0.125）では trials=1 の床は 3 タスクで一定。

        f=0.05（実測より楽観・データに裏付けなし）まで下げると床は 2 に落ちる ── 床の*値*は f に依存する。
        依存しないのは「観測 1 タスクは床未満」という結論の方（上のテスト）。
        """
        s = swebench_case()
        in_range = [sv for sv in s["f_sensitivity"] if sv["f_opus"] >= 0.067]
        self.assertTrue(in_range)
        for sv in in_range:
            self.assertEqual(sv["floor_m_trials1"], 3, msg=f"f={sv['f_opus']}")
        below_range = [sv for sv in s["f_sensitivity"] if sv["f_opus"] < 0.067]
        for sv in below_range:
            self.assertEqual(sv["floor_m_trials1"], 2, msg=f"f={sv['f_opus']}")
        # trials=3 の床はレンジ全域で 2
        for sv in s["f_sensitivity"]:
            self.assertEqual(sv["floor_m_trials3"], 2, msg=f"f={sv['f_opus']}")

    def test_h0_structure_choice_does_not_change_the_floor(self):
        # 割れた 3 セルを common に寄せても neither に寄せても床は同じ
        s = swebench_case()
        for fl in s["floor_by_trials"]:
            self.assertEqual(fl["floor_m_A"], fl["floor_m_B"], msg=f"trials={fl['trials']}")

    def test_min_trials_to_have_reported_that_gain(self):
        s = swebench_case()
        self.assertEqual(s["min_trials_for_1_task"], 5)      # trials=1 は必要標本の 1/5 だった

    def test_reportable_gate(self):
        st = TrueStructure(common=18, a_only=1, b_only=0, neither=5)
        self.assertFalse(reportable(1, st, 0.067, 0.0, trials=1))   # 観測 1 タスク < 床 3
        self.assertTrue(reportable(3, st, 0.067, 0.0, trials=1))    # 3 タスクなら報告可
        self.assertTrue(reportable(5, st, 0.067, 0.0, trials=1))

    def test_min_trials_for_returns_none_when_unreachable(self):
        # f=0.5（fable）は多数決で改善しない ⟹ どれだけ trials を積んでも床に届かない
        st = TrueStructure(common=18, a_only=1, b_only=0, neither=5)
        self.assertIsNone(min_trials_for(st, 0.5, 0.0, 1, t_max=25))


class RunTests(unittest.TestCase):
    def test_run_is_deterministic(self):
        self.assertEqual(run(), run())

    def test_fable_case_flags_broken_grader(self):
        f = run()["fable_pt6"]
        self.assertAlmostEqual(f["disagreement_d"], 0.5, places=4)
        self.assertAlmostEqual(f["flip_f"], 0.5, places=4)
        # 多数決を何回重ねても 0.5 のまま＝trials では救えない（先に harness を直す）
        for t, fe in f["f_eff_by_trials"].items():
            self.assertAlmostEqual(fe, 0.5, places=4, msg=f"trials={t}")

    def test_pytest6_has_no_detection_power_for_small_gains(self):
        p = run()["pytest6"]
        self.assertEqual(p["robust"]["gain"], 0.0)
        # n=6 の床は 2 タスク = gain 0.333 ⟹ それ未満の相補は原理的に見えない
        self.assertEqual(p["floor_trials1"]["m"], 2)
        self.assertAlmostEqual(p["floor_trials1"]["gain"], round(2 / 6, 4), places=4)


if __name__ == "__main__":
    unittest.main()
