"""Regression tests for scripts/10_daily_ingest.py.

Covers the two subsystems that have already broken in production once each:
- parse_timeline's date parsing/aggregation (crashed on GDELT's sub-daily
  buckets, 2026-07-11 -- see DECISIONS.md).
- call_with_retry's backoff behavior (retuned 2026-07-14 after runtime grew
  to 4-6h under GDELT rate-limiting -- see DECISIONS.md).

Fixtures under tests/fixtures/ are trimmed slices or full copies of real,
previously-cached GDELT API responses (data/raw/, data/live/raw/) -- never
fabricated, per CLAUDE.md rule 3.
"""
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"

spec = importlib.util.spec_from_file_location(
    "daily_ingest", ROOT / "scripts" / "10_daily_ingest.py"
)
daily_ingest = importlib.util.module_from_spec(spec)
sys.modules["daily_ingest"] = daily_ingest
spec.loader.exec_module(daily_ingest)


def load_fixture(name):
    with open(FIXTURES / name, encoding="utf-8") as f:
        return json.load(f)


class ParseTimelineHistoricalDailyTests(unittest.TestCase):
    """Multi-year historical pulls: GDELT returns exactly one T000000Z bucket
    per day. Aggregation must be a no-op here (real regression: must not
    duplicate, drop, or shift these rows)."""

    def test_daily_buckets_pass_through_one_row_per_day(self):
        data = load_fixture("historical_daily_biocon_vol.json")
        df = daily_ingest.parse_timeline(data, "vol")
        self.assertEqual(len(df), 8)
        self.assertEqual(list(df["value"]), [0, 0, 0, 0, 0, 0, 3, 0])
        self.assertEqual(str(df["date"].iloc[6].date()), "2023-01-07")


class ParseTimelineSubdailyTests(unittest.TestCase):
    """Live incremental pulls: GDELT returns sub-daily buckets for short
    query spans. This is the exact shape that crashed the pipeline on
    2026-07-11 (ValueError on a non-midnight timestamp)."""

    def test_15min_tone_buckets_average_to_one_row_per_day(self):
        data = load_fixture("live_subdaily_1day_dabur_tone.json")
        df = daily_ingest.parse_timeline(data, "tone")
        self.assertEqual(len(df), 2)
        row0 = df[df["date"] == "2026-07-10"].iloc[0]
        row1 = df[df["date"] == "2026-07-11"].iloc[0]
        # ground truth: 80 buckets that day, one non-zero value of 2.7363
        self.assertAlmostEqual(row0["value"], 2.7363 / 80, places=8)
        self.assertEqual(row1["value"], 0)

    def test_hourly_vol_buckets_sum_per_calendar_day_across_multiday_gap(self):
        data = load_fixture("live_subdaily_multiday_biocon_vol.json")
        df = daily_ingest.parse_timeline(data, "vol")
        # 5 distinct calendar days must survive as 5 rows, not 1 (the bug
        # would have crashed before even reaching aggregation) and not
        # collapsed into fewer/more than the real number of days.
        self.assertEqual(len(df), 5)
        expected = {
            "2026-07-10": 0,
            "2026-07-11": 0,
            "2026-07-12": 0,
            "2026-07-13": 2,
            "2026-07-14": 0,
        }
        got = {str(r["date"].date()): r["value"] for _, r in df.iterrows()}
        self.assertEqual(got, expected)


class ParseTimelineEmptyResponseTests(unittest.TestCase):
    def test_none_response_returns_empty_frame_with_expected_columns(self):
        df = daily_ingest.parse_timeline(None, "vol")
        self.assertEqual(len(df), 0)
        self.assertEqual(list(df.columns), ["date", "value"])

    def test_empty_timeline_data_returns_empty_frame(self):
        df = daily_ingest.parse_timeline({"timeline": [{"data": []}]}, "tone")
        self.assertEqual(len(df), 0)
        self.assertEqual(list(df.columns), ["date", "value"])


def _resp(status_code=200, json_value=None, json_raises=None):
    r = Mock()
    r.status_code = status_code
    if json_raises is not None:
        r.json.side_effect = json_raises
    else:
        r.json.return_value = json_value
    r.raise_for_status = Mock()
    return r


class CallWithRetryTests(unittest.TestCase):
    """Locks in the retry/backoff contract, including the 2026-07-14 tuning
    (MAX_ATTEMPTS 6->3) that bounded worst-case runtime under GDELT
    rate-limiting. Uses the module's own MAX_ATTEMPTS so this stays correct
    if that constant is retuned again."""

    def setUp(self):
        self.sleep_patcher = patch("time.sleep")
        self.mock_sleep = self.sleep_patcher.start()
        self.addCleanup(self.sleep_patcher.stop)

    def test_succeeds_immediately_on_200(self):
        ok = _resp(200, {"timeline": []})
        with patch("requests.get", return_value=ok) as mock_get:
            result = daily_ingest.call_with_retry(query="x", mode="timelinevolraw")
        self.assertEqual(result, {"timeline": []})
        self.assertEqual(mock_get.call_count, 1)
        self.mock_sleep.assert_not_called()

    def test_retries_on_429_then_succeeds(self):
        responses = [_resp(429), _resp(429), _resp(200, {"ok": True})]
        with patch("requests.get", side_effect=responses) as mock_get:
            result = daily_ingest.call_with_retry(query="x", mode="timelinevolraw")
        self.assertEqual(result, {"ok": True})
        self.assertEqual(mock_get.call_count, 3)

    def test_exhausts_retries_and_returns_none(self):
        responses = [_resp(429) for _ in range(daily_ingest.MAX_ATTEMPTS)]
        with patch("requests.get", side_effect=responses) as mock_get:
            result = daily_ingest.call_with_retry(query="x", mode="timelinevolraw")
        self.assertIsNone(result)
        self.assertEqual(mock_get.call_count, daily_ingest.MAX_ATTEMPTS)

    def test_retries_on_connection_error_then_succeeds(self):
        responses = [requests.exceptions.ConnectTimeout(), _resp(200, {"ok": True})]
        with patch("requests.get", side_effect=responses) as mock_get:
            result = daily_ingest.call_with_retry(query="x", mode="timelinevolraw")
        self.assertEqual(result, {"ok": True})
        self.assertEqual(mock_get.call_count, 2)

    def test_retries_on_invalid_json_body_then_succeeds(self):
        """Regression for the Phase 1 SAIL/BHEL bug: a 200 response with an
        empty/invalid body must retry, not crash with an uncaught
        JSONDecodeError (DECISIONS.md, Phase 1)."""
        bad = _resp(200, json_raises=requests.exceptions.JSONDecodeError("x", "y", 0))
        good = _resp(200, {"ok": True})
        with patch("requests.get", side_effect=[bad, good]) as mock_get:
            result = daily_ingest.call_with_retry(query="x", mode="timelinevolraw")
        self.assertEqual(result, {"ok": True})
        self.assertEqual(mock_get.call_count, 2)

    def test_backoff_wait_grows_linearly_with_attempt(self):
        responses = [_resp(429) for _ in range(daily_ingest.MAX_ATTEMPTS)]
        with patch("requests.get", side_effect=responses):
            daily_ingest.call_with_retry(query="x", mode="timelinevolraw")
        waited = [call.args[0] for call in self.mock_sleep.call_args_list]
        self.assertEqual(waited, [30 * (i + 1) for i in range(daily_ingest.MAX_ATTEMPTS)])


if __name__ == "__main__":
    unittest.main()
