"""Tests for the bug-repair decorrelation harness (deterministic mock + verified bugs)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import experiments.repair as R  # noqa: E402
from experiments.repair import _BUGGY, grade, run_repair  # noqa: E402


class RepairTests(unittest.TestCase):
    def test_injected_bugs_are_real(self):
        # every buggy version must actually FAIL its gold (else it's not a repair task)
        if not grade("def edit_distance(a, b): return 0\n", _BUGGY[0])["ran"]:
            self.skipTest("sandbox unavailable")
        for t in _BUGGY:
            c = grade(t["buggy"], t)
            self.assertLess(c["correctness"], 1.0, f"{t['id']} bug does not fail gold")
            self.assertGreater(c["correctness"], 0.0, f"{t['id']} bug too broken (not subtle)")

    def test_mock_yields_structure(self):
        if not grade("def edit_distance(a, b): return 0\n", _BUGGY[0])["ran"]:
            self.skipTest("sandbox unavailable")
        R._CALL = R._mock
        r = run_repair(models=("opus", "codex"))
        self.assertEqual(set(r["per_model"]), {"opus", "codex"})
        self.assertEqual(len(r["pairs"]), 1)              # one opus+codex pair
        self.assertIn("union", r["pairs"][0])


if __name__ == "__main__":
    unittest.main()
