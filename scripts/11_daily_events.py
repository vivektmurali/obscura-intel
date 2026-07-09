"""Phase 5 (ARCHITECTURE.md, override handover 2026-07-09): recompute the
event table over the full live store (recompute-over-append, same spike
definition as v0.1's scripts/02_events.py) and emit newly-detected events.

Writes data/live/events.csv (full cumulative table, internal) and
data/live_events.csv (just this run's new events, per ARCHITECTURE.md's
naming). Never touches v0.1's locked data/events.csv.
"""
import csv
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
UNIVERSE_CSV = ROOT / "data" / "universe.csv"
LIVE_DIR = ROOT / "data" / "live"
VOL_PARQUET = LIVE_DIR / "volume_daily.parquet"
TONE_PARQUET = LIVE_DIR / "tone_daily.parquet"
LIVE_EVENTS_CSV = LIVE_DIR / "events.csv"
NEW_EVENTS_CSV = ROOT / "data" / "live_events.csv"

VOL_Z_MIN = 3
V_MIN = 5


def zscore(series):
    roll_mean = series.rolling(90, min_periods=90).mean().shift(1)
    roll_std = series.rolling(90, min_periods=90).std().shift(1)
    return (series - roll_mean) / roll_std


def detect_events(ticker, vol_df, tone_df):
    df = vol_df.rename(columns={"value": "v"}).merge(
        tone_df.rename(columns={"value": "tone"}), on="date", how="inner"
    ).sort_values("date").reset_index(drop=True)
    df["vol_z"] = zscore(df["v"])
    df["tone_z"] = zscore(df["tone"])
    df["is_event_day"] = (df["vol_z"] >= VOL_Z_MIN) & (df["v"] >= V_MIN)
    df["run_start"] = df["is_event_day"] & ~df["is_event_day"].shift(1, fill_value=False)
    events = df[df["is_event_day"] & df["run_start"]].copy()
    events["direction"] = np.sign(events["tone_z"])
    events.insert(0, "ticker", ticker)
    return events[["ticker", "date", "v", "vol_z", "tone", "tone_z", "direction"]].rename(
        columns={"date": "event_date"})


def main():
    with open(UNIVERSE_CSV, encoding="utf-8") as f:
        universe = list(csv.DictReader(f))

    if not VOL_PARQUET.exists() or not TONE_PARQUET.exists():
        print("FATAL: live volume/tone store missing -- run 10_daily_ingest.py first")
        sys.exit(1)

    vol_all = pd.read_parquet(VOL_PARQUET)
    tone_all = pd.read_parquet(TONE_PARQUET)

    if LIVE_EVENTS_CSV.exists():
        previous_events = pd.read_csv(LIVE_EVENTS_CSV, parse_dates=["event_date"])
        previous_keys = set(zip(previous_events["ticker"], previous_events["event_date"].dt.date.astype(str)))
    else:
        previous_keys = set()

    all_events = []
    for row in universe:
        ticker = row["ticker"]
        vol_df = vol_all[vol_all["ticker"] == ticker][["date", "value"]]
        tone_df = tone_all[tone_all["ticker"] == ticker][["date", "value"]]
        if vol_df.empty or tone_df.empty:
            continue
        all_events.append(detect_events(ticker, vol_df, tone_df))

    events_df = pd.concat(all_events, ignore_index=True) if all_events else pd.DataFrame()
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    events_df.to_csv(LIVE_EVENTS_CSV, index=False)

    current_keys = set(zip(events_df["ticker"], events_df["event_date"].dt.date.astype(str)))
    new_keys = current_keys - previous_keys
    new_events = events_df[events_df.apply(
        lambda r: (r["ticker"], str(r["event_date"].date())) in new_keys, axis=1
    )]
    new_events.to_csv(NEW_EVENTS_CSV, index=False)

    print(f"Recomputed {len(events_df)} total events across {events_df['ticker'].nunique()} tickers "
          f"-> {LIVE_EVENTS_CSV}")
    print(f"New since last run: {len(new_events)} -> {NEW_EVENTS_CSV}")
    if len(new_events):
        for _, r in new_events.iterrows():
            print(f"  NEW: {r['ticker']} {r['event_date'].date()} "
                  f"vol_z={r['vol_z']:.2f} direction={'+' if r['direction'] > 0 else '-'}")


if __name__ == "__main__":
    main()
