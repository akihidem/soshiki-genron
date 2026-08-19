"""Tests for the external-gold-suite heterogeneity re-test (deterministic)."""

import ast
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import experiments.market_external as MX  # noqa: E402
from experiments.market_external import EXT_TASKS, grade, run_ext  # noqa: E402

GOOD_ROMAN = (
    'def int_to_roman(n):\n'
    '    vals=[(1000,"M"),(900,"CM"),(500,"D"),(400,"CD"),(100,"C"),(90,"XC"),(50,"L"),'
    '(40,"XL"),(10,"X"),(9,"IX"),(5,"V"),(4,"IV"),(1,"I")]\n'
    '    out=""\n'
    '    for v,s in vals:\n'
    '        while n>=v:\n'
    '            out+=s; n-=v\n'
    '    return out\n'
    'def roman_to_int(s):\n'
    '    m={"I":1,"V":5,"X":10,"L":50,"C":100,"D":500,"M":1000}\n'
    '    t=0; prev=0\n'
    '    for ch in reversed(s):\n'
    '        v=m[ch]\n'
    '        t += -v if v<prev else v\n'
    '        prev=v\n'
    '    return t\n'
)
STUB_ROMAN = 'def int_to_roman(n):\n    return "X"\ndef roman_to_int(s):\n    return 0\n'


class MarketExternalTests(unittest.TestCase):
    def _sandbox_ok(self):
        return grade(GOOD_ROMAN, EXT_TASKS[0])["ran"]

    def test_gold_distinguishes_correct_from_broken(self):
        if not self._sandbox_ok():
            self.skipTest("sandbox unavailable in this environment")
        self.assertEqual(grade(GOOD_ROMAN, EXT_TASKS[0])["correctness"], 1.0)   # correct impl -> full gold
        self.assertLess(grade(STUB_ROMAN, EXT_TASKS[0])["correctness"], 0.5)    # stub -> fails most gold

    def test_crash_impl_scores_zero_not_none(self):
        # a non-running impl IS a failure against external truth (unlike self-test grading)
        if not self._sandbox_ok():
            self.skipTest("sandbox unavailable in this environment")
        g = grade("def int_to_roman(n): return undefined_name\n", EXT_TASKS[0])
        self.assertEqual(g["correctness"], 0.0)

    def test_calibrate_mock_zero_solve_no_domination(self):
        if not self._sandbox_ok():
            self.skipTest("sandbox unavailable in this environment")
        MX._CALL = MX._mock                              # mock -> None impls -> never solves gold
        r = MX.calibrate("gemma4:e2b", trials=2)
        self.assertEqual(r["p_weak"], 0.0)
        # 素の算術（p̂ > w/s）は False。ただしこれは*判定*ではない ── 判定は verdict（下の床テスト）。
        self.assertTrue(all(not pr["dominates_pointwise"] for pr in r["pairs"]))
        self.assertAlmostEqual(r["pairs"][0]["market_cost"], 0.2 + r["pairs"][0]["s"], places=3)

    def test_mock_all_fail_escalates_through_every_tier(self):
        if not self._sandbox_ok():
            self.skipTest("sandbox unavailable in this environment")
        MX._CALL = MX._mock                              # mock returns None -> all gold fail
        r = run_ext()
        for row in r["market"]["rows"]:
            self.assertEqual(len(row["ladder"]), 3)      # tried haiku->sonnet->opus
            self.assertEqual(row["cost"], 1.0 + 3.0 + 15.0)
        self.assertEqual(r["market"]["avg_correctness"], 0.0)
        self.assertEqual(r["baselines"]["opus"]["avg_cost"], 15.0)


class DominanceFloorTests(unittest.TestCase):
    """支配の主張に**標本誤差の床**を通す（model/gap.py）。fail-open の再発を止める床。

    旧実装は `p̂ > w/s` の点推定二値判定で ✓ を刻んでいた。真に境界上（利得ゼロ）のモデルにも
    n=6 では 34.5% の確率で立つ ── LLM を呼ばずに機械で再発を捕まえる。
    """

    def _pairs(self, p_weak, n=6):
        pairs = [{"strong": sm, "w": 0.2, "s": s, "w_over_s": round(0.2 / s, 4)}
                 for sm, s in MX._STRONG_TIERS]
        return {pr["strong"]: pr for pr in MX.gate_pairs(p_weak, n, pairs)}

    def test_gate_stamps_a_verdict_and_the_bar_on_every_pair(self):
        for pr in self._pairs(0.5).values():
            self.assertIn(pr["verdict"], ("DOMINATES", "UNDECIDED", "DOES_NOT_DOMINATE"))
            self.assertEqual(pr["n_tasks"], 6)
            self.assertGreater(pr["crit_upper"], pr["w_over_s"])   # 盲帯は必ず在る

    def test_point_estimate_alone_does_not_earn_a_dominance_verdict(self):
        """p̂=0.5 は w/s=0.2 を超えるが n=6 では帰無と両立 ⟹ UNDECIDED（旧実装は ✓ を立てた）。"""
        pairs = self._pairs(0.5)
        self.assertGreater(0.5, pairs["haiku"]["w_over_s"])        # 素の比較なら「支配」に見える
        self.assertEqual(pairs["haiku"]["verdict"], "UNDECIDED")   # 床を通すと判定不能
        self.assertEqual(pairs["sonnet"]["verdict"], "DOMINATES")  # 余裕が足りるティアは通る

    def test_zero_solve_is_undecided_not_refuted(self):
        """全問不正解でも「非支配」とは言えない（n=6 は下側の枝が空）。`dominates=False` とは別物。"""
        self.assertEqual(self._pairs(0.0)["haiku"]["verdict"], "UNDECIDED")

    def test_regate_is_idempotent_and_renames_the_raw_arithmetic(self):
        mp = {"trials": 2, "models": [{"weak": "w", "p_weak": 0.5,
                                       "per_task": {f"t{i}": 0.5 for i in range(6)},
                                       "pairs": [{"strong": "haiku", "w": 0.2, "s": 1.0,
                                                  "w_over_s": 0.2, "dominates": True}]}]}
        once = MX.regate(json.loads(json.dumps(mp)))
        twice = MX.regate(json.loads(json.dumps(once)))
        self.assertEqual(once, twice)                                  # 冪等
        pr = once["models"][0]["pairs"][0]
        self.assertEqual(pr["verdict"], "UNDECIDED")
        self.assertTrue(pr["dominates_pointwise"])   # 素の算術は監査履歴として残す（改名して）
        self.assertNotIn("dominates", pr)            # **旧キーは消える**（読めば KeyError で落ちる）

    def test_the_unsafe_key_cannot_be_read_at_all(self):
        """床を通さず支配を出力する経路は、silent fail-open でなく **KeyError で落ちる**。

        2026-07-15 codex: 床を calibrate()/_md_map() にだけ足し、_md_calib()・CLI 2経路・
        calib の JSON に足し忘れた。呼び出し箇所を1つずつ塞ぐ限り足し忘れた側から穴が開く
        ので、「素の値を読める名前」自体を消した ── これがその床。
        """
        pr = self._pairs(0.5)["haiku"]
        with self.assertRaises(KeyError):
            pr["dominates"]                          # noqa: B018 ── 読めないことが仕様


class PublishedArtifactsAreGatedTests(unittest.TestCase):
    """**公開されるものを全部**走査する（1ファイルだけ手で選ぶ床は、選ばれなかった側で嘘になる）。

    前版の床は `market_map_results.json` だけを見ており、`market_calib_results.json` が
    未 gate のまま緑だった（codex 指摘「テスト床にも偽装気味の穴」）。走査に変えて塞ぐ。
    """

    EXP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "experiments")

    def _pair_nodes(self, obj):
        return list(MX._gatable(obj))

    def test_every_published_results_json_with_pairs_is_gated(self):
        found_any = False
        for name in sorted(os.listdir(self.EXP)):
            if not name.endswith("_results.json"):
                continue
            with open(os.path.join(self.EXP, name), encoding="utf-8") as f:
                try:
                    doc = json.load(f)
                except ValueError:
                    continue
            for node in self._pair_nodes(doc):
                for pr in node["pairs"]:
                    found_any = True
                    with self.subTest(artifact=name, strong=pr.get("strong")):
                        self.assertIn("verdict", pr,
                                      f"{name} が床を通っていない: "
                                      "python3 -m experiments.market_external --regate")
                        self.assertNotIn("dominates", pr, f"{name} に旧 fail-open キーが残っている")
        self.assertTrue(found_any, "走査対象が0件＝床が何も見ていない（fail-open）")

    def test_no_published_markdown_renders_a_dominance_claim_for_an_undecided_pair(self):
        """**意味の床**: 判定不能なペアに「支配」と刻んだ md を公開していないか。"""
        for jname, mdname, render in (("market_map_results.json", "MARKET_MAP.md", MX._md_map),
                                      ("market_calib_results.json", "MARKET_CALIB.md", MX._md_calib)):
            with open(os.path.join(self.EXP, jname), encoding="utf-8") as f:
                doc = json.load(f)
            with open(os.path.join(self.EXP, mdname), encoding="utf-8") as f:
                published = f.read()
            with self.subTest(artifact=mdname):
                # ① 公開 md が生成元とずれていない（stale なら床をすり抜ける）
                self.assertEqual(published, render(doc) + "\n",
                                 f"{mdname} が stale: --regate を回すこと")
                # ② 判定不能なペアの行に「支配」が立っていない
                for node in self._pair_nodes(doc):
                    for pr in node["pairs"]:
                        if pr["verdict"] != "UNDECIDED":
                            continue
                        for line in published.splitlines():
                            if pr["strong"] in line and "判定不能" not in line and "|" in line:
                                self.assertNotIn(
                                    "**支配**", line,
                                    f"{mdname}: {pr['strong']} は判定不能なのに支配と刻まれている")

    def test_the_gated_map_still_retracts_exactly_three_of_nine(self):
        with open(os.path.join(self.EXP, "market_map_results.json"), encoding="utf-8") as f:
            mp = json.load(f)
        pairs = [pr for node in self._pair_nodes(mp) for pr in node["pairs"]]
        self.assertEqual(len(pairs), 9)
        self.assertEqual(sum(1 for pr in pairs if pr["verdict"] == "UNDECIDED"), 3)

    def test_the_headline_calibration_survives_the_floor(self):
        """主結論（大能力差 → market が Pareto 支配・p̂=0.889）は床を通しても立つ。"""
        with open(os.path.join(self.EXP, "market_calib_results.json"), encoding="utf-8") as f:
            cb = json.load(f)
        self.assertGreaterEqual(cb["p_weak"], 0.8)
        for pr in cb["pairs"]:
            with self.subTest(strong=pr["strong"]):
                self.assertEqual(pr["verdict"], "DOMINATES")


if __name__ == "__main__":
    unittest.main()
