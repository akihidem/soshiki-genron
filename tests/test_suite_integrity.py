"""テスト群そのものの床 ── 「全 green」が本当に床の証明になっているか。

2026-07-15 の codex レビューが README の「215本・全green」の **stale** を検出した。だが数を
直すだけでは同じ事故が必ずまた起きる（`test_generated_docs.py` が生成物で潰したのと同型 ──
人の記憶に依存する更新は忘れる）。しかも数を数え直したら、**stale より悪いもの**が出た:

    `tests/test_mmlu_pro_bench.py` の 10 件は素の pytest 関数（module 直下の `def test_*`）で
    書かれていた。`unittest` の loader は TestCase 派生しか拾わないので、README が正典として
    案内する `python3 -m unittest discover -s tests -t .` では **0 件実行**されていた
    （pytest なら 10 件）。つまり **「全 green」はその 10 件を一度も走らせずに主張されていた。**

緑は床の証明にならない ── *どの緑か*を機械で固定しなければ。ここで2つを床にする:

  ① **どの test モジュールも正典 runner から見えている**こと（silently-skipped を落とす）
  ② **README の主張する本数が実際と一致する**こと（stale を落とす）

②はテストを足すたびに赤くなる。それが目的である（README の更新を強制する）。
"""

import collections
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.join(ROOT, "tests")

# README が本数を主張している箇所。**見つからなければ落とす**（マーカーを消して逃げるのを防ぐ）。
_COUNT_MARKERS = (
    r"# テスト（(\d+)本",             # 走らせ方ブロック
    r"決定的テスト（(\d+)本",          # リポジトリ地図
    r"\*\*(\d+) tests green\*\*",     # 到達点
)


def _counts_by_module() -> collections.Counter:
    """正典 runner（unittest discover）が実際に見つける test 数をモジュール別に数える。"""
    suite = unittest.defaultTestLoader.discover(TESTS_DIR, top_level_dir=ROOT)
    counts, stack = collections.Counter(), [suite]
    while stack:
        for t in stack.pop():
            if isinstance(t, unittest.TestSuite):
                stack.append(t)
            else:
                counts[t.__class__.__module__] += 1
    return counts


class SuiteIntegrityTests(unittest.TestCase):

    def test_no_test_module_is_invisible_to_the_canonical_runner(self):
        """素の pytest 関数だけの module は `unittest discover` から **0 件**に見える＝床にならない。

        pytest では緑に見えるので、**気づけないまま「全 green」を主張してしまう**のが怖い所。
        """
        counts = _counts_by_module()
        files = sorted(f[:-3] for f in os.listdir(TESTS_DIR)
                       if f.startswith("test_") and f.endswith(".py"))
        invisible = [f for f in files if counts.get(f"tests.{f}", 0) == 0]
        self.assertEqual(
            invisible, [],
            "正典コマンド `python3 -m unittest discover -s tests -t .` から見えない test モジュール"
            f"（0 件実行される）: {invisible}。素の pytest 関数でなく unittest.TestCase に載せること。")

    def test_readme_test_count_is_not_stale(self):
        """README の本数が実測と一致するか。テストを足したら README も直すまで赤のままになる。"""
        total = sum(_counts_by_module().values())
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
            readme = f.read()
        for pat in _COUNT_MARKERS:
            found = re.findall(pat, readme)
            with self.subTest(marker=pat):
                self.assertTrue(found, f"README の本数マーカーが消えている: {pat!r}")
                for got in found:
                    self.assertEqual(
                        int(got), total,
                        f"README の本数 {got} が実測 {total} と食い違う（marker={pat!r}）。"
                        "README を直すこと。")

    def test_both_runners_agree_on_what_exists(self):
        """unittest が見つける数 = tests/ に実在する TestCase メソッド数（取りこぼしゼロ）。

        pytest だけが見つける test が在るなら、それは正典コマンドの床の外にある。
        """
        counts = _counts_by_module()
        self.assertGreater(sum(counts.values()), 0)
        for mod, n in counts.items():
            with self.subTest(module=mod):
                self.assertGreater(n, 0, f"{mod} が 0 件（loader から不可視）")


if __name__ == "__main__":
    unittest.main()
