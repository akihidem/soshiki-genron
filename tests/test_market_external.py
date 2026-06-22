"""Tests for the external-gold-suite heterogeneity re-test (deterministic)."""

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
        self.assertTrue(all(not pr["dominates"] for pr in r["pairs"]))   # p=0 -> below every w/s
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


if __name__ == "__main__":
    unittest.main()
