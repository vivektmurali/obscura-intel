"""Regression tests for scripts/07_power_analysis.py.

Covers the two things a 2026-07-16 code review flagged as fragile:
- the staleness cross-check was a bare `assert` (stripped under `python -O`)
  -- now an explicit `raise ValueError`, tested here in both the match and
  mismatch case.
- the MDE/achieved-power math lived only inline in main() -- extracted to
  `compute_mde`/`compute_achieved_power` so it's independently testable.

Fixtures under tests/fixtures/power_analysis_*.{csv,json} are small real
slices of this project's actual results/car_by_event.csv,
results/null_distributions.csv, and results/stats.json (the "observed" value
in the match fixture is the real mean(direction * CAR_t5) computed from the
5-row car subset, not invented) -- never fabricated, per CLAUDE.md rule 3.
"""
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from scipy import stats as scipy_stats

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"

spec = importlib.util.spec_from_file_location(
    "power_analysis", ROOT / "scripts" / "07_power_analysis.py"
)
power_analysis = importlib.util.module_from_spec(spec)
sys.modules["power_analysis"] = power_analysis
spec.loader.exec_module(power_analysis)


class ComputeMdeTests(unittest.TestCase):
    def test_mde_matches_hand_computed_z_score_formula(self):
        se = 0.002244
        z_alpha = scipy_stats.norm.ppf(0.95)
        result = power_analysis.compute_mde(se, z_alpha, [0.5, 0.8, 0.9])
        self.assertEqual(set(result.keys()), {"50pct", "80pct", "90pct"})
        for power, key in [(0.5, "50pct"), (0.8, "80pct"), (0.9, "90pct")]:
            expected = (z_alpha + scipy_stats.norm.ppf(power)) * se
            self.assertAlmostEqual(result[key], expected, places=10)

    def test_mde_at_50pct_power_equals_z_alpha_times_se(self):
        # norm.ppf(0.5) == 0, so the 50%-power MDE collapses to z_alpha * se
        se = 0.01
        z_alpha = scipy_stats.norm.ppf(0.95)
        result = power_analysis.compute_mde(se, z_alpha, [0.5])
        self.assertAlmostEqual(result["50pct"], z_alpha * se, places=10)

    def test_mde_scales_linearly_with_se(self):
        z_alpha = scipy_stats.norm.ppf(0.95)
        low = power_analysis.compute_mde(0.001, z_alpha, [0.8])["80pct"]
        high = power_analysis.compute_mde(0.002, z_alpha, [0.8])["80pct"]
        self.assertAlmostEqual(high, 2 * low, places=10)


class ComputeAchievedPowerTests(unittest.TestCase):
    def test_achieved_power_matches_hand_computed_formula(self):
        se = 0.002244
        z_alpha = scipy_stats.norm.ppf(0.95)
        result = power_analysis.compute_achieved_power(se, z_alpha, [0.005, 0.01])
        expected_05 = scipy_stats.norm.cdf(0.005 / se - z_alpha)
        expected_10 = scipy_stats.norm.cdf(0.01 / se - z_alpha)
        self.assertAlmostEqual(result["0.5pct"], expected_05, places=10)
        self.assertAlmostEqual(result["1.0pct"], expected_10, places=10)

    def test_achieved_power_at_zero_effect_is_alpha(self):
        # a "true effect" of exactly 0 reduces to P(Z > z_alpha) == alpha
        se = 0.002244
        z_alpha = scipy_stats.norm.ppf(0.95)
        result = power_analysis.compute_achieved_power(se, z_alpha, [0.0])
        self.assertAlmostEqual(result["0.0pct"], 0.05, places=6)

    def test_achieved_power_increases_with_effect_size(self):
        se = 0.002244
        z_alpha = scipy_stats.norm.ppf(0.95)
        result = power_analysis.compute_achieved_power(se, z_alpha, [0.005, 0.01, 0.02])
        powers = [result["0.5pct"], result["1.0pct"], result["2.0pct"]]
        self.assertEqual(powers, sorted(powers))


class MainStalenessGuardTests(unittest.TestCase):
    """Exercises main() end-to-end against real (trimmed) fixture data."""

    def setUp(self):
        self.tmp_out = FIXTURES / "_tmp_power_analysis_output.json"
        self.addCleanup(lambda: self.tmp_out.unlink(missing_ok=True))
        patches = {
            "CAR_CSV": FIXTURES / "power_analysis_car_subset.csv",
            "NULL_CSV": FIXTURES / "power_analysis_null_subset.csv",
            "OUT_JSON": self.tmp_out,
        }
        self.patchers = [patch.object(power_analysis, k, v) for k, v in patches.items()]
        for p in self.patchers:
            p.start()
            self.addCleanup(p.stop)

    def test_main_succeeds_when_car_matches_locked_stats(self):
        with patch.object(power_analysis, "STATS_JSON",
                           FIXTURES / "power_analysis_stats_match.json"):
            power_analysis.main()
        self.assertTrue(self.tmp_out.exists())
        import json
        with open(self.tmp_out, encoding="utf-8") as f:
            written = json.load(f)
        self.assertEqual(written["n_events"], 5)
        self.assertAlmostEqual(written["observed_primary_statistic"], 0.0174155745450577, places=10)

    def test_main_raises_when_car_is_stale_relative_to_locked_stats(self):
        with patch.object(power_analysis, "STATS_JSON",
                           FIXTURES / "power_analysis_stats_mismatch.json"):
            with self.assertRaises(ValueError) as ctx:
                power_analysis.main()
        self.assertIn("stale", str(ctx.exception))
        # the guard must fire before any output is written
        self.assertFalse(self.tmp_out.exists())


if __name__ == "__main__":
    unittest.main()
