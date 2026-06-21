"""Tests for the oversight-scaling harness (deterministic mock backend).

The real measurement runs against ollama and is non-deterministic; these tests
pin the harness logic and the expected shape using the mock overseers.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.oversight.run import build_overseers, run_matrix, summarize  # noqa: E402
from experiments.oversight.overseer import MockOverseer, review  # noqa: E402
from experiments.oversight.dataset import flawed_items, clean_items, ITEMS  # noqa: E402


class OversightHarnessTests(unittest.TestCase):
    def setUp(self):
        self.summary = summarize(run_matrix(build_overseers("mock", [], "")))

    def test_strong_overseer_catches_everything(self):
        s = self.summary["strong(cap3)"]
        self.assertEqual(s["catch_rate"], 1.0)
        self.assertEqual(s["oversight_error"], 0.0)

    def test_weak_overseer_only_catches_obvious_flaws(self):
        bs = self.summary["weak(cap1)"]["catch_rate_by_subtlety"]
        self.assertEqual(bs[1], 1.0)
        self.assertEqual(bs[2], 0.0)
        self.assertEqual(bs[3], 0.0)

    def test_oversight_error_rises_as_overseer_weakens(self):
        errs = [self.summary[k]["oversight_error"]
                for k in ("strong(cap3)", "mid(cap2)", "weak(cap1)")]
        self.assertEqual(errs, sorted(errs))
        self.assertLess(errs[0], errs[-1])

    def test_catch_rate_nonincreasing_with_subtlety_for_weak(self):
        bs = self.summary["weak(cap1)"]["catch_rate_by_subtlety"]
        self.assertGreaterEqual(bs[1], bs[2])
        self.assertGreaterEqual(bs[2], bs[3])

    def test_no_false_positives_from_mock(self):
        for s in self.summary.values():
            self.assertEqual(s["false_positive_rate"], 0.0)

    def test_dataset_has_graded_flaws_and_clean_controls(self):
        self.assertTrue(clean_items())
        self.assertEqual({i.subtlety for i in flawed_items()}, {1, 2, 3})

    def test_review_marks_caught_only_on_flagged_flaw(self):
        flawed = next(i for i in ITEMS if i.flawed and i.subtlety == 3)
        self.assertTrue(review(MockOverseer(3), flawed)["caught"])
        self.assertFalse(review(MockOverseer(1), flawed)["caught"])

    def test_harness_is_deterministic(self):
        self.assertEqual(summarize(run_matrix(build_overseers("mock", [], ""))), self.summary)


if __name__ == "__main__":
    unittest.main()
