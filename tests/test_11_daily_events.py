"""Regression tests for scripts/11_daily_events.py.

zscore/detect_events are pure numerical functions -- tested here with
engineered numeric sequences chosen to exercise specific properties (the
trailing-90-day window, the no-lookahead shift(1), run-merging on consecutive
event days), not real market/news data. This is standard practice for testing
a statistical formula's implementation, distinct from CLAUDE.md rule 3's ban
on fabricated data standing in for real GDELT/price signals in the pipeline
itself or its outputs.
"""
import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

spec = importlib.util.spec_from_file_location(
    "daily_events", ROOT / "scripts" / "11_daily_events.py"
)
daily_events = importlib.util.module_from_spec(spec)
sys.modules["daily_events"] = daily_events
spec.loader.exec_module(daily_events)


class ZscoreTests(unittest.TestCase):
    def test_nan_before_full_90_day_window(self):
        series = pd.Series(np.full(89, 1.0))
        result = daily_events.zscore(series)
        self.assertTrue(result.isna().all())

    def test_excludes_current_day_no_lookahead(self):
        # 90 quiet days (value=1.0, std=0 causes div-by-zero -> NaN/inf, so
        # use a tiny alternating pattern instead for a well-defined std),
        # then a huge spike on day 91. If the spike leaked into its own
        # window's mean/std (i.e. no shift(1)), the z-score would be
        # dramatically smaller than if the window is computed purely from
        # the 90 prior (quiet) days.
        quiet = [1.0, 3.0] * 45  # 90 days, alternating -> defined nonzero std
        spike = 1000.0
        series = pd.Series(quiet + [spike])
        result = daily_events.zscore(series)
        prior_mean = pd.Series(quiet).mean()
        prior_std = pd.Series(quiet).std()
        expected = (spike - prior_mean) / prior_std
        self.assertAlmostEqual(result.iloc[90], expected, places=10)

    def test_matches_manual_rolling_computation_on_a_later_window(self):
        # once past the first 90 days, verify against an independently
        # computed trailing rolling mean/std for an arbitrary later day
        values = list(range(1, 200))  # simple increasing sequence
        series = pd.Series(values, dtype=float)
        result = daily_events.zscore(series)
        day = 150  # 0-indexed
        window = series.iloc[day - 90:day]  # the 90 days strictly before `day`
        expected = (series.iloc[day] - window.mean()) / window.std()
        self.assertAlmostEqual(result.iloc[day], expected, places=10)


class DetectEventsTests(unittest.TestCase):
    def _build_frames(self, vol_values, tone_values, start="2023-01-01"):
        dates = pd.date_range(start, periods=len(vol_values), freq="D")
        vol_df = pd.DataFrame({"date": dates, "value": vol_values})
        tone_df = pd.DataFrame({"date": dates, "value": tone_values})
        return vol_df, tone_df

    def test_no_events_when_below_threshold(self):
        # 95 quiet days, volume never exceeds V_MIN -- must yield zero events
        vol_df, tone_df = self._build_frames([1.0] * 95, [0.0] * 95)
        result = daily_events.detect_events("TEST", vol_df, tone_df)
        self.assertEqual(len(result), 0)

    def test_consecutive_event_days_collapse_to_one_event(self):
        # 90 quiet days (alternating, nonzero std), then a 3-day-long spike
        # well above VOL_Z_MIN and V_MIN -- must emit exactly ONE event (the
        # first spike day), not three.
        quiet = [1.0, 3.0] * 45
        spike_days = [50.0, 50.0, 50.0]
        vol = quiet + spike_days + [1.0, 3.0] * 5
        tone = [0.0] * 90 + [2.0, 2.0, 2.0] + [0.0] * 10
        vol_df, tone_df = self._build_frames(vol, tone)
        result = daily_events.detect_events("TEST", vol_df, tone_df)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["event_date"], vol_df["date"].iloc[90])

    def test_direction_matches_sign_of_tone_z(self):
        quiet = [1.0, 3.0] * 45
        vol = quiet + [50.0] * 2 + [1.0, 3.0] * 5
        # negative tone during the spike -> direction must be -1
        tone = [0.0] * 90 + [-5.0] * 2 + [0.0] * 10
        vol_df, tone_df = self._build_frames(vol, tone)
        result = daily_events.detect_events("TEST", vol_df, tone_df)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["direction"], -1.0)

    def test_output_schema(self):
        vol_df, tone_df = self._build_frames(
            [1.0, 3.0] * 45 + [50.0] * 2, [0.0] * 90 + [1.0] * 2,
        )
        result = daily_events.detect_events("TEST", vol_df, tone_df)
        self.assertEqual(
            list(result.columns),
            ["ticker", "event_date", "v", "vol_z", "tone", "tone_z", "direction"],
        )
        self.assertTrue((result["ticker"] == "TEST").all())


if __name__ == "__main__":
    unittest.main()
