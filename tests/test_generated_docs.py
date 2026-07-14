"""生成物（model/*.md, model/*_results.json）が生成元コードと一致していることを機械で保証する。

## なぜ要るか（実際に踏んだ穴）

2026-07-15 の codex レビューが `model/NOISE.md` の stale を検出した。感度表は `f=0.05 → 床 2` を
出しているのに、直後の本文が「trials=1 の床は 3 タスクで動かない」と断言していた ── `noise.py` の
`_md()` を直したのに `python3 -m model.noise` を再実行しなかったため。

これは **研究結果の要約としての正しさのバグ**である（読者が本文を信じると、コードが計算する値と
違うことを信じる）。しかも厄介なことに:

- `noise_results.json` は **OK だった**（データは正しかった）。ずれていたのは `_md()` の*散文*だけ。
  ⟹ JSON だけを検品するテストでは**構造的に捕まらない**。
- 「再生成すればよい」は人の記憶に依存する ⟹ **必ずまた忘れる**。

よって stale を**テストで落とす**。以後、生成元を直して再生成し忘れたコミットは赤になる。

## 何を検品するか

各生成モジュールについて `_md(run())` / `json.dumps(run())` を**その場で**作り直し、
リポジトリにコミットされているファイルと**逐語一致**することを要求する。
（`run()` はすべて決定的・引数デフォルトのみ。main() の書き出しと同じ引数で比較する）
"""

import importlib
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "model")

# (module, json ファイル, md ファイル, md レンダラ名) ── main() の書き出しと対応
GENERATORS = [
    ("sweep",      "results.json",            "RESULTS.md",     "_results_md"),
    ("governance", "governance_results.json", "GOVERNANCE.md",  "_md"),
    ("capacity",   "capacity_results.json",   "CAPACITY.md",    "_md"),
    ("design_map", "design_map_results.json", "DESIGN_MAP.md",  "_md"),
    ("joint",      "joint_results.json",      "JOINT.md",       "_md"),
    ("race",       "race_results.json",       "RACE.md",        "_md"),
    ("alignment",  "alignment_results.json",  "ALIGNMENT.md",   "_md"),
    ("market",     "market_results.json",     "MARKET.md",      "_md"),
    ("mesh",       "mesh_results.json",       "MESH.md",        "_md"),
    ("noise",      "noise_results.json",      "NOISE.md",       "_md"),
]

_REGEN_HINT = "再生成: python3 -m model.{name}"


class GeneratedArtifactsAreFreshTests(unittest.TestCase):
    """コミット済みの生成物が、いま生成元を走らせた結果と一致するか。"""

    def test_markdown_is_not_stale(self):
        """**本丸**: 散文が数値とずれていないか（JSON では捕まらない層）。"""
        for name, _json_file, md_file, renderer in GENERATORS:
            with self.subTest(module=name, artifact=md_file):
                mod = importlib.import_module(f"model.{name}")
                expected = getattr(mod, renderer)(mod.run()) + "\n"
                path = os.path.join(MODEL_DIR, md_file)
                self.assertTrue(os.path.exists(path), f"{md_file} が無い")
                with open(path, encoding="utf-8") as f:
                    actual = f.read()
                self.assertEqual(actual, expected,
                                 f"model/{md_file} が生成元 model/{name}.py より stale。"
                                 + _REGEN_HINT.format(name=name))

    def test_results_json_is_not_stale(self):
        for name, json_file, _md_file, _renderer in GENERATORS:
            with self.subTest(module=name, artifact=json_file):
                mod = importlib.import_module(f"model.{name}")
                expected = json.dumps(mod.run(), ensure_ascii=False, indent=2, sort_keys=True)
                path = os.path.join(MODEL_DIR, json_file)
                self.assertTrue(os.path.exists(path), f"{json_file} が無い")
                with open(path, encoding="utf-8") as f:
                    actual = f.read()
                self.assertEqual(actual, expected,
                                 f"model/{json_file} が生成元 model/{name}.py より stale。"
                                 + _REGEN_HINT.format(name=name))

    def test_run_is_deterministic_for_every_generator(self):
        """生成物の比較が意味を持つ前提（run() が決定的）を、比較の*前*に確かめる。"""
        for name, _j, _m, _r in GENERATORS:
            with self.subTest(module=name):
                mod = importlib.import_module(f"model.{name}")
                self.assertEqual(mod.run(), mod.run())

    def test_every_generator_module_is_covered(self):
        """model/ に新しい生成モジュールが増えたのに、この床から漏れていないか。"""
        covered = {name for name, _j, _m, _r in GENERATORS}
        found = set()
        for fname in os.listdir(MODEL_DIR):
            if not fname.endswith(".py") or fname.startswith("_"):
                continue
            with open(os.path.join(MODEL_DIR, fname), encoding="utf-8") as f:
                src = f.read()
            # main() が .md を書き出すモジュール＝生成モジュール
            if '.md"' in src and "def main(" in src:
                found.add(fname[:-3])
        self.assertEqual(found - covered, set(),
                         "生成モジュールが GENERATORS に登録されていない（stale 検品から漏れる）")


if __name__ == "__main__":
    unittest.main()
