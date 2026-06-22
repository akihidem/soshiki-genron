"""Tests for the real-SWE-bench repair harness — the PURE, deterministic parts.

The repo-dependent parts (_setup/_gold_validates/_fail_count) need a live pytest checkout at
/tmp/pytest_repo and are exercised by the experiment itself; here we lock down the fiddly bits
that silently caused the first all-zero artifact: SEARCH/REPLACE application and patch parsing."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json as _json  # noqa: E402
import tempfile  # noqa: E402

import experiments.swebench_repair as SR  # noqa: E402
from experiments.swebench_repair import _apply_edits, _edited_file, _to_pytest_args, _unfence  # noqa: E402

_CONTENT = "import os\n\ndef f(x):\n    return x + 1\n\ndef g(y):\n    return y\n"


class EditedFileTests(unittest.TestCase):
    def test_single_src_file(self):
        patch = "--- a/src/_pytest/pathlib.py\n+++ b/src/_pytest/pathlib.py\n@@ -1 +1 @@\n-x\n+y\n"
        self.assertEqual(_edited_file(patch), "src/_pytest/pathlib.py")

    def test_multi_src_file_returns_none(self):
        patch = ("+++ b/src/_pytest/a.py\n@@ @@\n-x\n+y\n"
                 "+++ b/src/_pytest/b.py\n@@ @@\n-x\n+y\n")
        self.assertIsNone(_edited_file(patch))

    def test_non_src_ignored(self):
        patch = "+++ b/testing/test_x.py\n@@ @@\n-x\n+y\n"
        self.assertIsNone(_edited_file(patch))

    def test_sympy_layout_no_src_prefix(self):
        # sympy edits sympy/<module>/foo.py (no src/ prefix); the test file is excluded
        patch = ("--- a/sympy/physics/units/unitsystem.py\n+++ b/sympy/physics/units/unitsystem.py\n@@ @@\n-x\n+y\n"
                 "--- a/sympy/physics/units/tests/test_quantities.py\n+++ b/sympy/physics/units/tests/test_quantities.py\n@@ @@\n-a\n+b\n")
        self.assertEqual(_edited_file(patch), "sympy/physics/units/unitsystem.py")


class PytestArgsTests(unittest.TestCase):
    def test_node_ids_pass_through(self):
        ids = ["testing/test_mark.py::TestX::test_a", "testing/x.py::test_b"]
        self.assertEqual(_to_pytest_args({"test_patch": ""}, ids), ids)

    def test_bare_names_become_dir_plus_dash_k(self):
        # sympy bare function names -> scope to the test-patch dirs + `-k "a or b"`
        inst = {"test_patch": "+++ b/sympy/physics/units/tests/test_quantities.py\n@@ @@\n+def test_issue_24211(): pass\n"}
        args = _to_pytest_args(inst, ["test_issue_24211", "test_other"])
        self.assertEqual(args[0], "sympy/physics/units/tests")
        self.assertIn("-k", args)
        self.assertEqual(args[-1], "test_issue_24211 or test_other")

    def test_empty(self):
        self.assertEqual(_to_pytest_args({"test_patch": ""}, []), [])


class ApplyEditsTests(unittest.TestCase):
    def test_exact_search_replace(self):
        sr = "<<<<<<< SEARCH\n    return x + 1\n=======\n    return x - 1\n>>>>>>> REPLACE"
        out = _apply_edits(_CONTENT, "prose\n" + sr + "\nmore")
        self.assertIn("return x - 1", out)
        self.assertNotIn("return x + 1", out)

    def test_whitespace_tolerant(self):
        sr = "<<<<<<< SEARCH\n    return x + 1   \n=======\n    return x * 2\n>>>>>>> REPLACE"
        out = _apply_edits(_CONTENT, sr)
        self.assertIn("return x * 2", out)

    def test_multiple_blocks_all_apply(self):
        sr = ("<<<<<<< SEARCH\n    return x + 1\n=======\n    return x - 1\n>>>>>>> REPLACE\n"
              "<<<<<<< SEARCH\n    return y\n=======\n    return y * 2\n>>>>>>> REPLACE")
        out = _apply_edits(_CONTENT, sr)
        self.assertIn("return x - 1", out)
        self.assertIn("return y * 2", out)

    def test_full_file_fallback(self):
        full = "```python\n" + _CONTENT.replace("+ 1", "+ 2") + "```"
        out = _apply_edits(_CONTENT, full)
        self.assertIn("+ 2", out)

    def test_unmatched_search_rejects_attempt(self):
        sr = "<<<<<<< SEARCH\nNOT IN THE FILE AT ALL\n=======\nz\n>>>>>>> REPLACE"
        self.assertIsNone(_apply_edits(_CONTENT, sr))

    def test_garbage_returns_none(self):
        self.assertIsNone(_apply_edits(_CONTENT, "just prose, no fix here"))

    def test_noop_edit_returns_none(self):
        # a block whose replacement equals the search makes no change -> None (nothing to grade)
        sr = "<<<<<<< SEARCH\n    return y\n=======\n    return y\n>>>>>>> REPLACE"
        self.assertIsNone(_apply_edits(_CONTENT, sr))


class IterativeLoopTests(unittest.TestCase):
    """The agentic loop: fail -> feed the test output back -> revise -> succeed. Stubs the live repo
    (real tmpfile I/O, no-op git, fake test verdict) so the orchestration is checked deterministically."""

    def setUp(self):
        self._save = (SR._REPO, SR._git, SR._run_capture, SR._CALL)
        self._dir = tempfile.mkdtemp()
        SR._REPO = self._dir
        SR._git = lambda *a, **k: type("R", (), {"returncode": 0})()
        # tests pass only once the file on disk contains the FIXED marker
        SR._run_capture = lambda tests, timeout=300: (
            (0, "") if "FIXED" in open(os.path.join(self._dir, "f.py")).read() else (1, "boom"))

    def tearDown(self):
        SR._REPO, SR._git, SR._run_capture, SR._CALL = self._save

    def _inst(self):
        return {"problem_statement": "bug", "FAIL_TO_PASS": _json.dumps(["t::a"]),
                "PASS_TO_PASS": _json.dumps([])}

    def test_feedback_then_success(self):
        open(os.path.join(self._dir, "f.py"), "w").write(_CONTENT)
        calls = {"n": 0}

        def call(m, p):
            calls["n"] += 1
            if calls["n"] == 1:
                return "no usable edit yet"                  # -> None -> feedback, loop again
            self.assertIn("did NOT resolve", p)              # round 2 sees the failure feedback
            return "```python\n" + _CONTENT.replace("return y", "return y  # FIXED") + "```"
        SR._CALL = call
        self.assertEqual(SR._repair_iterative("m", self._inst(), "f.py", _CONTENT, 0, rounds=3), 1)
        self.assertEqual(calls["n"], 2)                      # early-exit on success, not all 3 rounds

    def test_never_fixes_hits_round_cap(self):
        open(os.path.join(self._dir, "f.py"), "w").write(_CONTENT)
        calls = {"n": 0}

        def call(m, p):
            calls["n"] += 1
            return "still no fix"                            # never produces a usable edit
        SR._CALL = call
        self.assertEqual(SR._repair_iterative("m", self._inst(), "f.py", _CONTENT, 0, rounds=3), 0)
        self.assertEqual(calls["n"], 3)                      # exhausts exactly `rounds` attempts


class UnfenceTests(unittest.TestCase):
    def test_longest_block_wins(self):
        text = "```\nsmall\n```\nmid\n```python\n" + _CONTENT + "```"
        self.assertIn("def g(y)", _unfence(text))

    def test_keeps_imports_verbatim(self):
        # the whole point: unlike _extract_code, _unfence must NOT drop non-stdlib imports
        code = "from _pytest.config import Config\nimport attr\n\ndef h():\n    return 1\n"
        self.assertEqual(_unfence("```python\n" + code + "```"), code)


if __name__ == "__main__":
    unittest.main()
