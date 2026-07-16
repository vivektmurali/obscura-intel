"""Regression tests for scripts/04_event_study.py.

Scoped deliberately narrow: this script produced the locked, tagged v0.1
verdict, so only its already-standalone pure functions (build_return_matrix,
ols_alpha_beta) are tested here -- not a refactor of main()'s CAR/entry-date
logic, which is locked study code, not the live pipeline.

Fixture values are a real 6-day slice of data/prices.parquet for BIOCON and
^NSEI (2022-07-01 through 2022-07-08) -- never fabricated, per CLAUDE.md
rule 3.
"""
import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

spec = importlib.util.spec_from_file_location(
    "event_study", ROOT / "scripts" / "04_event_study.py"
)
event_study = importlib.util.module_from_spec(spec)
sys.modules["event_study"] = event_study
spec.loader.exec_module(event_study)

# Real 6-day slice of data/prices.parquet (BIOCON, ^NSEI close prices).
REAL_PRICES_LONG = pd.DataFrame({
    "ticker": ["BIOCON"] * 6 + ["^NSEI"] * 6,
    "date": pd.to_datetime([
        "2022-07-01", "2022-07-04", "2022-07-05", "2022-07-06", "2022-07-07", "2022-07-08",
    ] * 2),
    "close": [
        308.538483, 308.290894, 310.519104, 317.897125, 318.293274, 319.679688,
        15752.049805, 15835.349609, 15810.849609, 15989.799805, 16132.900391, 16220.599609,
    ],
})


class BuildReturnMatrixTests(unittest.TestCase):
    def test_log_returns_match_hand_computed_values(self):
        returns, calendar = event_study.build_return_matrix(REAL_PRICES_LONG)
        self.assertEqual(len(calendar), 6)
        # first row is always NaN (no prior day to diff against)
        self.assertTrue(np.isnan(returns["BIOCON"].iloc[0]))
        self.assertTrue(np.isnan(returns["^NSEI"].iloc[0]))
        # real log-return values, computed independently from the same prices
        self.assertAlmostEqual(returns["BIOCON"].iloc[1], np.log(308.290894 / 308.538483), places=10)
        self.assertAlmostEqual(returns["^NSEI"].iloc[3], np.log(15989.799805 / 15810.849609), places=10)

    def test_calendar_excludes_days_where_benchmark_is_missing(self):
        # a day BIOCON has a price for but the benchmark doesn't must be
        # dropped from the canonical trading-day calendar
        prices_with_gap = pd.concat([
            REAL_PRICES_LONG,
            pd.DataFrame({"ticker": ["BIOCON"], "date": pd.to_datetime(["2022-07-11"]), "close": [325.720734]}),
        ], ignore_index=True)
        returns, calendar = event_study.build_return_matrix(prices_with_gap)
        self.assertNotIn(pd.Timestamp("2022-07-11"), calendar)
        self.assertEqual(len(calendar), 6)


class OlsAlphaBetaTests(unittest.TestCase):
    def test_matches_numpy_lstsq_ground_truth(self):
        y = np.array([-0.000803, 0.007202, 0.023482, 0.001245, 0.004346])
        x = np.array([0.005274, -0.001548, 0.011255, 0.008910, 0.005421])
        alpha, beta = event_study.ols_alpha_beta(y, x)
        x_mat = np.column_stack([np.ones(len(x)), x])
        expected_alpha, expected_beta = np.linalg.lstsq(x_mat, y, rcond=None)[0]
        self.assertAlmostEqual(alpha, expected_alpha, places=12)
        self.assertAlmostEqual(beta, expected_beta, places=12)

    def test_perfect_linear_relationship_recovers_exact_beta(self):
        # y = 2 + 3*x exactly -> OLS must recover alpha=2, beta=3 to float precision
        x = np.array([0.01, 0.02, -0.01, 0.03, -0.02])
        y = 2.0 + 3.0 * x
        alpha, beta = event_study.ols_alpha_beta(y, x)
        self.assertAlmostEqual(alpha, 2.0, places=10)
        self.assertAlmostEqual(beta, 3.0, places=10)


if __name__ == "__main__":
    unittest.main()
