"""Tests for the real-SWE-bench repair harness — the PURE, deterministic parts.

The repo-dependent parts (_setup/_gold_validates/_fail_count) need a live pytest checkout at
/tmp/pytest_repo and are exercised by the experiment itself; here we lock down the fiddly bits
that silently caused the first all-zero artifact: SEARCH/REPLACE application and patch parsing."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.swebench_repair import _apply_edits, _edited_file, _unfence  # noqa: E402

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
