"""replication.py の検定数学と、**複製深度の台帳が現物と一致すること**の床。

このファイルは2種類のテストを持つ:

  A. **数学の検品** ── 符号検定・最小到達 p・三値判定が閉形式と一致するか（純関数）。
  B. **床** ── リポジトリの現物に対する不変条件。以後、次をやると赤になる:
       ① 複製深度 trials=1 の実測ファイルを、理由を `replication.EXEMPT` に登録せずに足す
       ② 撤回済みの主張（mesh の +0.042 点火）を docs/ に生かしたまま残す

②が要るのは、**撤回がモデル層で完結して処方層へ伝播しない**事故を実際に踏んだからである
（`fcbfa5c` で mesh の点火を撤回し `fc13942` で mesh.py を回帰修正したのに、
`docs/deployment-architecture.md` は「実測 opus×codex で +0.042 点火」を配置則の根拠として
掲げ続けていた）。`test_generated_docs.py` が model/ の生成物に課した床の、docs/ 版である。
"""

import json
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model import replication as rp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# --------------------------------------------------------------------------- #
# A. 数学の検品
# --------------------------------------------------------------------------- #
class SignTestMathTests(unittest.TestCase):

    def test_concordant_pairs_carry_no_information(self):
        """全対一致 ⟹ 不一致対 0 ⟹ p=1。「n が大きいのに何も言えない」の正体。"""
        r = rp.sign_test([1, 1, 0, 0], [1, 1, 0, 0])
        self.assertEqual(r["discordant"], 0)
        self.assertEqual(r["p"], 1.0)

    def test_matches_closed_form_for_all_one_directional_outcomes(self):
        """全 m 対が一方向 ⟹ 両側 p = 2·2^{−m}（閉形式と逐一照合）。"""
        for m in range(1, 13):
            with self.subTest(m=m):
                r = rp.sign_test([1] * m, [0] * m)
                self.assertEqual(r["a_only"], m)
                self.assertEqual(r["b_only"], 0)
                self.assertAlmostEqual(r["p"], min(1.0, 2.0 * 2.0 ** -m), places=4)

    def test_is_symmetric_under_swapping_the_groups(self):
        va, vb = [1, 0, 1, 1, 0, 1], [0, 0, 1, 0, 1, 1]
        self.assertEqual(rp.sign_test(va, vb)["p"], rp.sign_test(vb, va)["p"])

    def test_p_value_is_a_valid_probability_over_an_exhaustive_enumeration(self):
        """n=6 の 2^6×2^6 全観測で 0≤p≤1 を確かめる（境界の取りこぼしを潰す）。"""
        n = 6
        for i in range(2 ** n):
            va = [(i >> k) & 1 for k in range(n)]
            for j in range(2 ** n):
                vb = [(j >> k) & 1 for k in range(n)]
                p = rp.sign_test(va, vb)["p"]
                self.assertGreaterEqual(p, 0.0)
                self.assertLessEqual(p, 1.0)

    def test_min_attainable_p_is_actually_attained_and_never_beaten(self):
        """`min_attainable_p(n)` が **達成可能かつ下界**であることを全観測で確かめる。

        これがこのモジュールの主張の要（「n だけで何が言えるかが決まる」）なので、
        公式を信じずに列挙で確かめる。
        """
        for n in range(1, 9):
            with self.subTest(n=n):
                lo = min(rp.sign_test([(i >> k) & 1 for k in range(n)],
                                      [(j >> k) & 1 for k in range(n)])["p"]
                         for i in range(2 ** n) for j in range(2 ** n))
                self.assertAlmostEqual(lo, rp.min_attainable_p(n), places=4)

    def test_min_n_for_significance_is_six_at_alpha_005(self):
        self.assertEqual(rp.min_n_for_significance(0.05), 6)
        self.assertGreater(rp.min_attainable_p(5), 0.05)
        self.assertLessEqual(rp.min_attainable_p(6), 0.05)

    def test_verdict_separates_not_significant_from_cannot_be_significant(self):
        """**「有意でない」と「有意になりようがない」を混ぜない**のが本モジュールの要点。"""
        self.assertEqual(rp.verdict(1.0, 3), rp.IMPOSSIBLE)     # n=3 は観測に依らず不可
        self.assertEqual(rp.verdict(0.02, 3), rp.IMPOSSIBLE)    # 小さい p でも n が足りなければ不可
        self.assertEqual(rp.verdict(0.5, 6), rp.UNDECIDED)
        self.assertEqual(rp.verdict(0.03, 6), rp.SIGNIFICANT)

    def test_declared_depth_prefers_the_declaration_and_never_guesses(self):
        self.assertEqual(rp.declared_depth({"trials": 3, "cells": [{"scores": [1.0]}]}), 3)
        self.assertEqual(rp.declared_depth({"cells": [{"scores": [1.0, 0.0]}]}), 2)
        self.assertIsNone(rp.declared_depth({"summary": {"gain": 0.4}}))   # 推測しない

    def test_declared_depth_takes_the_shallowest_cell(self):
        """深度は**最も浅いセル**で決まる（一部だけ複製して「trials=3」を名乗るのを防ぐ）。"""
        self.assertEqual(rp.declared_depth({"cells": [{"scores": [1.0, 0.0]}, {"scores": [1.0]}]}), 1)

    def test_run_is_deterministic(self):
        self.assertEqual(rp.run(), rp.run())


# --------------------------------------------------------------------------- #
# B. 床 ── リポジトリの現物に対する不変条件
# --------------------------------------------------------------------------- #
class ReplicationLedgerFloorTests(unittest.TestCase):

    def test_every_single_trial_artifact_is_registered_with_a_reason(self):
        """**①の床**: 理由なき trials=1 が黙って corpus に増えるのを止める。

        新しい実測を trials=1 で足したら、`EXEMPT` に理由を書くか、trials>1 で回し直すまで赤。
        """
        lg = rp.ledger()
        unregistered = [r["file"] for r in lg["debt"]]
        self.assertEqual(
            unregistered, ["role_division_repair_real.json"],
            "複製深度 1 の実測ファイルが replication.EXEMPT に未登録で在る（または既知の負債が"
            f"解消/変化した）: {unregistered}。trials>1 で回し直すか、理由を EXEMPT に登録すること。")

    def test_exempt_entries_all_exist_and_are_actually_single_trial(self):
        """免除リストが stale になる側も塞ぐ（消えたファイル・複製済みファイルの免除が残る）。"""
        by_file = {r["file"]: r for r in rp.ledger()["rows"]}
        for fname, reason in rp.EXEMPT.items():
            with self.subTest(file=fname):
                self.assertIn(fname, by_file, f"EXEMPT に在るが実在しない: {fname}")
                self.assertEqual(by_file[fname]["klass"], rp.SINGLE,
                                 f"{fname} はもう trials=1 ではない ── EXEMPT から外すこと")
                self.assertTrue(reason.strip(), "免除には理由が要る")

    def test_the_prescriptive_doc_claims_are_all_below_the_detection_floor(self):
        """本モジュールの中心的な観測を回帰として固定する（数字が動いたら気づく）。"""
        ra = rp.run()["reaudit"]
        self.assertEqual(ra["trials"], 1)
        self.assertEqual(ra["n"], 6)
        self.assertEqual(ra["n_significant"], 0,
                         "role_division_repair_real の主張が有意になった＝標本か検定が変わっている")
        for row in ra["rows"]:
            with self.subTest(contrast=row["contrast"]):
                self.assertGreater(row["p"], 0.05)
                self.assertEqual(row["verdict"], rp.UNDECIDED)

    def test_reaudit_vectors_match_the_committed_experiment_file(self):
        """台帳が読んでいるベクトルが現物と一致するか（畳み込みのバグを別経路で照合）。"""
        with open(os.path.join(ROOT, "experiments", "role_division_repair_real.json"),
                  encoding="utf-8") as f:
            obj = json.load(f)
        ra = rp.run()["reaudit"]
        for g, vec in ra["vectors"].items():
            cells = sorted((c for c in obj["cells"] if c["group"] == g), key=lambda c: c["task"])
            self.assertEqual(vec, [c["mean_score"] for c in cells])


class RetractedClaimsDoNotSurviveInDocsTests(unittest.TestCase):
    """**②の床**: 撤回がモデル層で完結して処方層へ伝播しない事故を止める。

    `model/mesh_results.json` の `retracted` に載っている主張の数値が、docs/ の散文に
    *生きた実測*として残っていないかを機械で見る。
    """

    # 撤回済みの主張 → docs/ に現れてはいけない数値表記。
    # mesh_results.json の retracted エントリと対応させる（片方だけ直すのを防ぐ）。
    _FORBIDDEN = ("+0.042", "+0.0417")

    def _docs(self):
        d = os.path.join(ROOT, "docs")
        return [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.endswith(".md")]

    def test_the_retraction_is_still_recorded_in_the_model_layer(self):
        """この床が何を守っているのかの前提。撤回記録が消えたらこのテスト自体が無意味になる。"""
        with open(os.path.join(ROOT, "model", "mesh_results.json"), encoding="utf-8") as f:
            mesh = json.load(f)
        retracted = mesh.get("retracted", {})
        self.assertTrue(retracted, "mesh_results.json の撤回記録が消えている")
        key = next(iter(retracted))
        self.assertIn("RETRACTED", key)
        self.assertEqual(retracted[key]["trials"], 1)
        # 撤回された値そのもの（0.0417）が retracted 側に在ることを確かめる
        self.assertAlmostEqual(retracted[key]["gain"], 0.0417, places=4)

    def test_no_doc_presents_the_retracted_ignition_as_a_live_measurement(self):
        offenders = []
        for path in self._docs():
            with open(path, encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    if any(tok in line for tok in self._FORBIDDEN) and "撤回" not in line:
                        offenders.append(f"{os.path.relpath(path, ROOT)}:{i}")
        self.assertEqual(
            offenders, [],
            "撤回済みの mesh 点火(+0.042)を、撤回と明示せずに載せている docs 行がある: "
            f"{offenders}。撤回はモデル層(mesh.py)だけでなく処方層(docs/)へも伝播させること。")


if __name__ == "__main__":
    unittest.main()
