"""Tests for role_division_repair — sub-ceiling(実バグ修復)基盤の決定的検品。

実 pytest は走らせない（重い・非決定）。(1) repair prompt が role タグ付き・問題文/ファイルを含み
**テスト ID / gold patch / test_patch を一切漏らさない**(H3 Goodhart 遮断) と (2) grade closure が
差分適用→実テスト 0/1 採点→ファイル復元 を正しく行う（SR 原語を stub 化）ことを確かめる。
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import experiments.swebench_repair as SR  # noqa: E402
from experiments.role_division import _TAGS, LGTM  # noqa: E402
from experiments.role_division_repair import (  # noqa: E402
    _REPAIR_SUB, _r_thinker, _r_worker, _r_verifier, _r_solo, make_repair_grade, _arms,
)


def _fake_inst():
    # テスト ID・gold・test_patch にセンチネルを仕込む（プロンプトに漏れたら検出できる）
    return {
        "instance_id": "pytest-dev__pytest-9999",
        "problem_statement": "ISSUE_TEXT clamp returns wrong value on empty input",
        "_rd_path": "src/_pytest/buggy.py",
        "_rd_content": "def f():\n    return 1  # ORIGINAL_FILE_BODY\n",
        "FAIL_TO_PASS": json.dumps(["tests/test_x.py::test_LEAK_F2P"]),
        "PASS_TO_PASS": json.dumps(["tests/test_y.py::test_LEAK_P2P"]),
        "patch": "GOLD_PATCH_LEAK diff --git a/x b/x",
        "test_patch": "TEST_PATCH_LEAK diff --git a/t b/t",
    }


class RepairPromptTests(unittest.TestCase):
    def test_prompts_are_role_tagged(self):
        inst = _fake_inst()
        self.assertTrue(_r_thinker(inst).startswith(_TAGS["thinker"]))
        self.assertTrue(_r_worker(inst, "PLAN").startswith(_TAGS["worker"]))
        self.assertTrue(_r_verifier(inst, "DIFF").startswith(_TAGS["verifier"]))
        self.assertTrue(_r_solo(inst).startswith(_TAGS["solo"]))

    def test_prompts_include_issue_and_file(self):
        inst = _fake_inst()
        for p in (_r_thinker(inst), _r_worker(inst, "PLAN"), _r_solo(inst)):
            self.assertIn("ISSUE_TEXT", p)
            self.assertIn(inst["_rd_path"], p)
            self.assertIn("ORIGINAL_FILE_BODY", p)        # 元ファイル全文を渡している
        self.assertIn("PLAN", _r_worker(inst, "PLAN"))
        self.assertIn("DIFF", _r_verifier(inst, "DIFF"))  # verifier はレビュー対象の差分を見る

    def test_no_gold_or_test_leak_in_any_prompt(self):
        # H3: テスト ID / gold patch / test_patch は どの role prompt にも漏らさない
        inst = _fake_inst()
        prompts = [_r_thinker(inst), _r_worker(inst, "PLAN", "PREVDIFF", "CRITIQUE"),
                   _r_verifier(inst, "DIFF"), _r_solo(inst)]
        for sentinel in ("LEAK_F2P", "LEAK_P2P", "GOLD_PATCH_LEAK", "TEST_PATCH_LEAK"):
            for p in prompts:
                self.assertNotIn(sentinel, p, f"{sentinel} leaked into a prompt")

    def test_verifier_states_no_test_access(self):
        self.assertIn("NO access to the test suite", _r_verifier(_fake_inst(), "DIFF"))

    def test_worker_repair_includes_prev_and_critique(self):
        p = _r_worker(_fake_inst(), "PLAN", prev_code="PREVDIFF", critique="CRITIQUE_X")
        self.assertIn("PREVDIFF", p)
        self.assertIn("CRITIQUE_X", p)


class RepairGradeTests(unittest.TestCase):
    """grade closure を SR 原語の stub で検品（実 pytest 不要）。"""

    def setUp(self):
        self._orig = (SR._apply_edits, SR._fail_count, SR._git, SR._to_pytest_args, SR._REPO)
        self._tmp = tempfile.mkdtemp()
        SR._REPO = self._tmp
        os.makedirs(os.path.join(self._tmp, "src/_pytest"), exist_ok=True)
        open(os.path.join(self._tmp, "src/_pytest/buggy.py"), "w").write("buggy")
        self.git_calls = []
        SR._git = lambda *a, **k: self.git_calls.append(a)
        SR._to_pytest_args = lambda inst, ids: ids        # F2P/P2P をそのまま tag list に

    def tearDown(self):
        SR._apply_edits, SR._fail_count, SR._git, SR._to_pytest_args, SR._REPO = self._orig

    def _inst(self):
        return {"instance_id": "i", "_rd_path": "src/_pytest/buggy.py",
                "FAIL_TO_PASS": json.dumps(["F2P"]), "PASS_TO_PASS": json.dumps(["P2P"]),
                "patch": "", "test_patch": ""}

    def _grade_with(self, applied, f2p_fail, p2p_fail, base=0):
        SR._apply_edits = lambda content, code: applied
        SR._fail_count = lambda tests, timeout=300: {"F2P": f2p_fail, "P2P": p2p_fail}[tests[0]]
        inst = self._inst()
        return make_repair_grade(inst, inst["_rd_path"], "ORIGINAL", base)

    def test_resolved_when_f2p_pass_and_no_regression(self):
        g = self._grade_with(applied="NEWFILE", f2p_fail=0, p2p_fail=0, base=0)
        self.assertEqual(g("good diff", {}), 1.0)
        self.assertTrue(any(a[0] == "checkout" for a in self.git_calls))  # ファイルを戻している

    def test_zero_when_f2p_still_fails(self):
        g = self._grade_with(applied="NEWFILE", f2p_fail=2, p2p_fail=0, base=0)
        self.assertEqual(g("bad diff", {}), 0.0)

    def test_zero_on_new_regression(self):
        g = self._grade_with(applied="NEWFILE", f2p_fail=0, p2p_fail=3, base=0)  # P2P 新規 fail
        self.assertEqual(g("regressing diff", {}), 0.0)

    def test_baseline_p2p_not_punished(self):
        # 元から base=3 落ちる環境では p2p_fail<=base を regression と見なさない
        g = self._grade_with(applied="NEWFILE", f2p_fail=0, p2p_fail=3, base=3)
        self.assertEqual(g("diff", {}), 1.0)

    def test_zero_when_diff_unparseable(self):
        called = {"fc": 0}
        SR._apply_edits = lambda content, code: None
        SR._fail_count = lambda *a, **k: called.__setitem__("fc", called["fc"] + 1) or 0
        inst = self._inst()
        g = make_repair_grade(inst, inst["_rd_path"], "ORIGINAL", 0)
        self.assertEqual(g("garbage", {}), 0.0)
        self.assertEqual(called["fc"], 0)                 # 適用不能なら採点もしない


class RepairWiringTests(unittest.TestCase):
    def test_arms_assignment(self):
        from experiments.role_division import Roles
        arms = _arms()
        self.assertEqual(arms["solo"], "opus")
        self.assertEqual(arms["role_same"], Roles("opus", "opus", "opus"))
        self.assertEqual(arms["role_cross"], Roles("opus", "sonnet", "haiku"))

    def test_substrate_uses_repair_prompts(self):
        self.assertIs(_REPAIR_SUB.solo_prompt, _r_solo)
        self.assertIs(_REPAIR_SUB.verifier_prompt, _r_verifier)


if __name__ == "__main__":
    unittest.main()
