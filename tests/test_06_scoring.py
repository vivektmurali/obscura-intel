"""Regression tests for scripts/06_scoring.py.

The highest-stakes untested code in the pipeline before this: score_null_mode's
assertion is the code-level guarantee (not just convention) that the live site
never shows a forward-return number while the locked verdict is NULL
(ARCHITECTURE.md Sec 7's claims-audit gate). Tested directly here, both the
refuse-to-score and the normal-scoring paths.

Fixtures are real data: a 20-value slice of the actual data/events.csv vol_z
column (the locked historical reference distribution), and three real DABUR
events from data/live/events.csv for the novelty-days test -- never
fabricated, per CLAUDE.md rule 3.
"""
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import mock_open, patch

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

spec = importlib.util.spec_from_file_location(
    "scoring", ROOT / "scripts" / "06_scoring.py"
)
scoring = importlib.util.module_from_spec(spec)
sys.modules["scoring"] = scoring
spec.loader.exec_module(scoring)

# A 20-value slice of the real data/events.csv vol_z column (first 20 rows),
# frozen here so the test doesn't depend on that file's current contents.
REFERENCE_VOL_Z = [
    15.441960919907627, 5.483911210417497, 6.728557597935446, 5.632380183453387,
    11.270112508530522, 7.739735363919328, 6.482883446258912, 5.074140642357904,
    5.790739170690222, 3.915790409504024, 3.7653577745675135, 5.243759617428421,
    3.5821289443898325, 4.137022092507982, 11.88170467239295, 4.023561192466761,
    3.033330650834319, 4.100135499115986, 3.871462794162285, 4.164735629212857,
]


class ScoreIntensityTests(unittest.TestCase):
    def test_percentile_matches_hand_computed_values(self):
        import numpy as np
        result = scoring.score_intensity(
            np.array([3.033330650834319, 15.441960919907627, 9.237645785370972]),
            np.array(REFERENCE_VOL_Z),
        )
        self.assertAlmostEqual(result[0], 5.0)   # the reference's minimum
        self.assertAlmostEqual(result[1], 100.0)  # the reference's maximum
        self.assertAlmostEqual(result[2], 85.0)   # a real midpoint value


class ScoreNoveltyTests(unittest.TestCase):
    def test_first_event_per_ticker_has_nan_novelty(self):
        df = pd.DataFrame({
            "ticker": ["DABUR", "DABUR", "DABUR"],
            "event_date": pd.to_datetime(["2023-05-04", "2023-07-07", "2023-08-03"]),
        })
        result = scoring.score_novelty(df)
        days = result["novelty_days"].tolist()
        self.assertTrue(pd.isna(days[0]))
        self.assertEqual(days[1], 64.0)
        self.assertEqual(days[2], 27.0)

    def test_tickers_are_independent(self):
        # interleaved input order must not let one ticker's dates leak into
        # another's novelty calculation
        df = pd.DataFrame({
            "ticker": ["DABUR", "HAVELLS", "DABUR"],
            "event_date": pd.to_datetime(["2023-05-04", "2023-07-18", "2023-07-07"]),
        })
        result = scoring.score_novelty(df)
        havells_row = result[result["ticker"] == "HAVELLS"].iloc[0]
        self.assertTrue(pd.isna(havells_row["novelty_days"]))


class ScoreNullModeClaimsAuditTests(unittest.TestCase):
    """The core safety property: NULL mode must never carry a forward-return
    column, enforced at the code level."""

    def _base_df(self):
        return pd.DataFrame({
            "ticker": ["DABUR"],
            "event_date": pd.to_datetime(["2023-05-04"]),
            "vol_z": [5.0],
        })

    def test_raises_when_car_t5_column_present(self):
        df = self._base_df()
        df["CAR_t5"] = [0.01]
        with self.assertRaises(AssertionError) as ctx:
            scoring.score_null_mode(df, [3.0, 5.0, 7.0])
        self.assertIn("claims audit", str(ctx.exception).lower())

    def test_raises_for_lowercase_variant_too(self):
        df = self._base_df()
        df["car_t1"] = [0.02]
        with self.assertRaises(AssertionError):
            scoring.score_null_mode(df, [3.0, 5.0, 7.0])

    def test_succeeds_and_adds_score_columns_when_no_forbidden_column(self):
        df = self._base_df()
        result = scoring.score_null_mode(df, REFERENCE_VOL_Z)
        self.assertIn("intensity_percentile", result.columns)
        self.assertIn("novelty_days", result.columns)
        self.assertNotIn("CAR_t5", result.columns)


class MainVerdictGuardTests(unittest.TestCase):
    """main() must refuse to run in any non-NULL verdict, before touching
    any live-events file -- SIGNAL-mode scoring isn't implemented."""

    def test_exits_before_touching_live_events_file_when_verdict_is_signal(self):
        signal_stats = {"verdict": "SIGNAL"}
        with patch("builtins.open", mock_open(read_data=json.dumps(signal_stats))):
            with patch.object(scoring, "LIVE_EVENTS_CSV") as mock_path:
                # if main() ever reaches the file-existence check, this
                # would be exercised -- assert it never is
                mock_path.exists.side_effect = AssertionError(
                    "main() touched LIVE_EVENTS_CSV before the verdict guard fired"
                )
                with self.assertRaises(SystemExit) as ctx:
                    scoring.main()
                self.assertEqual(ctx.exception.code, 1)


class ComputeTercileReferenceTests(unittest.TestCase):
    """Cross-checked against 06_figures.py's fig_tone_tercile, which already
    plots these exact numbers in results/figures/tone_tercile.png -- this
    proves the two independent qcut calls agree, not just that this one runs."""

    def test_matches_locked_figure_numbers(self):
        ref = scoring.compute_tercile_reference()
        self.assertAlmostEqual(ref["edges"][0], -12.440962071362412)
        self.assertAlmostEqual(ref["edges"][1], -0.060992862151788604)
        self.assertAlmostEqual(ref["edges"][2], 0.4781734963545042)
        self.assertAlmostEqual(ref["edges"][3], 3.8686705437924407)
        self.assertAlmostEqual(ref["mean"]["bottom"], 0.006125822605787347)
        self.assertAlmostEqual(ref["mean"]["mid"], -0.00048690668795241357)
        self.assertAlmostEqual(ref["mean"]["top"], 0.0031365360141517398)
        self.assertEqual(ref["n"]["bottom"], 81)
        self.assertEqual(ref["n"]["mid"], 80)
        self.assertEqual(ref["n"]["top"], 81)


class ClassifyTercileTests(unittest.TestCase):
    EDGES = [-12.440962071362412, -0.060992862151788604, 0.4781734963545042, 3.8686705437924407]

    def test_value_inside_bottom_tercile(self):
        self.assertEqual(scoring.classify_tercile(-1.0, self.EDGES), "bottom")

    def test_value_inside_mid_tercile(self):
        self.assertEqual(scoring.classify_tercile(0.1, self.EDGES), "mid")

    def test_value_inside_top_tercile(self):
        self.assertEqual(scoring.classify_tercile(1.0, self.EDGES), "top")

    def test_value_more_negative_than_locked_minimum_clips_to_bottom(self):
        self.assertEqual(scoring.classify_tercile(-50.0, self.EDGES), "bottom")

    def test_value_more_positive_than_locked_maximum_clips_to_top(self):
        self.assertEqual(scoring.classify_tercile(50.0, self.EDGES), "top")

    def test_exact_boundary_values(self):
        self.assertEqual(scoring.classify_tercile(-0.060992862151788604, self.EDGES), "bottom")
        self.assertEqual(scoring.classify_tercile(0.4781734963545042, self.EDGES), "mid")


class ScoreCalibrationTests(unittest.TestCase):
    TERCILE_REF = {
        "edges": [-12.440962071362412, -0.060992862151788604, 0.4781734963545042, 3.8686705437924407],
        "mean": {"bottom": 0.006125822605787347, "mid": -0.00048690668795241357, "top": 0.0031365360141517398},
        "n": {"bottom": 81, "mid": 80, "top": 81},
    }

    def test_attaches_all_four_fields(self):
        df = pd.DataFrame({"tone_z": [-1.0, 0.1, 1.0]})
        result = scoring.score_calibration(df, self.TERCILE_REF)
        self.assertEqual(result["tercile_label"].tolist(), ["bottom", "mid", "top"])
        self.assertAlmostEqual(result["tercile_mean_car5"].iloc[0], 0.006125822605787347)
        self.assertEqual(result["tercile_n"].tolist(), [81, 80, 81])
        self.assertTrue((result["calibration_disclaimer"] == scoring.CALIBRATION_DISCLAIMER).all())

    def test_never_adds_a_forward_return_column(self):
        df = pd.DataFrame({"tone_z": [-1.0]})
        result = scoring.score_calibration(df, self.TERCILE_REF)
        self.assertFalse(scoring.FORBIDDEN_NULL_MODE_COLUMNS & set(result.columns))


if __name__ == "__main__":
    unittest.main()
