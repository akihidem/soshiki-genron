"""Tests for the empirical calibration (measured oversight -> model optima)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.oversight.calibrate import calibrate  # noqa: E402


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.r = calibrate()

    def test_large_gap_oversight_thins_the_membrane(self):
        g = self.r["governance"]
        self.assertLess(g["m_star_calibrated_large_gap"], g["m_star_calibrated_capable"])

    def test_measured_overflag_collapses_the_membrane(self):
        self.assertEqual(self.r["governance"]["m_star_with_measured_overflag"], 0.0)

    def test_degraded_oversight_lowers_safe_optimization_pressure(self):
        a = self.r["alignment"]
        self.assertLess(a["p_star_calibrated_large_gap"], a["p_star_calibrated_capable"])

    def test_deterministic(self):
        self.assertEqual(calibrate(), self.r)


if __name__ == "__main__":
    unittest.main()
