"""Phase 5 (ARCHITECTURE.md, override handover 2026-07-09): daily incremental
ingest for the live pipeline. Recompute-over-append: fetches only the gap
between each ticker's last stored day and the previous complete UTC day,
appends to the live parquet store, and never touches v0.1's locked
data/events.csv / data/prices.parquet (the validated study artifacts).

First run bootstraps the live store from the existing historical raw cache
(data/raw/*.json) rather than re-fetching years of GDELT history through the
same rate-limited API. Every subsequent run is a small top-up.
"""
import argparse
import csv
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yfinance as yf

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
UNIVERSE_CSV = ROOT / "data" / "universe.csv"
RAW_DIR = ROOT / "data" / "raw"
LIVE_DIR = ROOT / "data" / "live"
LIVE_RAW_DIR = LIVE_DIR / "raw"
VOL_PARQUET = LIVE_DIR / "volume_daily.parquet"
TONE_PARQUET = LIVE_DIR / "tone_daily.parquet"
PRICES_PARQUET = LIVE_DIR / "prices.parquet"
HISTORICAL_PRICES_PARQUET = ROOT / "data" / "prices.parquet"

BASE = "https://api.gdeltproject.org/api/v2/doc/doc"
BENCHMARK = "^NSEI"
HIST_YEARS = [2023, 2024, 2025]
SLEEP_BETWEEN_CALLS = 25
MAX_ATTEMPTS = 6
TIMEOUT = 90
PRICE_LOOKBACK_DAYS = 10  # re-fetch a small trailing window to catch corrections


def build_query(company_name, aliases):
    names = [company_name] + [a.strip() for a in aliases.split("|") if a.strip()]
    if len(names) == 1:
        return f'"{names[0]}" sourcecountry:IN'
    quoted = " OR ".join(f'"{n}"' for n in names)
    return f'({quoted}) sourcecountry:IN'


def call_with_retry(**params):
    for attempt in range(MAX_ATTEMPTS):
        wait = 30 * (attempt + 1)
        try:
            r = requests.get(BASE, params=params, timeout=TIMEOUT)
        except (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout,
                requests.exceptions.ConnectionError) as e:
            print(f"    connection issue ({type(e).__name__}), backing off {wait}s "
                  f"(attempt {attempt + 1}/{MAX_ATTEMPTS})")
            time.sleep(wait)
            continue
        if r.status_code == 429 or r.status_code >= 500:
            print(f"    {r.status_code}, backing off {wait}s (attempt {attempt + 1}/{MAX_ATTEMPTS})")
            time.sleep(wait)
            continue
        r.raise_for_status()
        try:
            return r.json()
        except requests.exceptions.JSONDecodeError:
            print(f"    invalid/empty JSON body, backing off {wait}s (attempt {attempt + 1}/{MAX_ATTEMPTS})")
            time.sleep(wait)
            continue
    return None


def parse_timeline(data, kind):
    """GDELT auto-selects bucket width by query span: daily buckets (T000000Z
    only) for the multi-year historical pulls, sub-daily (observed: 15-min)
    buckets for the live pipeline's short incremental-gap queries. Parse the
    full timestamp rather than assuming midnight, and collapse to one row per
    calendar day: sum raw article counts, average tone. Tone averaging is an
    unweighted mean of per-bucket averages -- GDELT doesn't expose per-bucket
    article counts to weight by -- so it's an approximation when buckets are
    sub-daily; exact for the always-daily historical bootstrap path.
    """
    if data is None:
        return pd.DataFrame(columns=["date", "value"])
    pts = (data.get("timeline") or [{}])[0].get("data", [])
    if not pts:
        return pd.DataFrame(columns=["date", "value"])
    df = pd.DataFrame(pts)
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%dT%H%M%SZ").dt.normalize()
    df["value"] = df["value"].astype(float)
    agg = "sum" if kind == "vol" else "mean"
    return df.groupby("date", as_index=False)["value"].agg(agg)


def bootstrap_gdelt_store(universe, kind, out_path):
    """Build the live daily store from the historical per-year raw cache."""
    frames = []
    for row in universe:
        ticker = row["ticker"]
        parts = []
        for year in HIST_YEARS:
            f = RAW_DIR / f"{ticker}_{year}_{kind}.json"
            if not f.exists():
                continue
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            parts.append(parse_timeline(data, kind))
        if not parts:
            continue
        df = pd.concat(parts, ignore_index=True).drop_duplicates("date").sort_values("date")
        df.insert(0, "ticker", ticker)
        frames.append(df)
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["ticker", "date", "value"])
    out.to_parquet(out_path, index=False)
    print(f"  bootstrapped {out_path.name}: {len(out)} rows from historical cache")
    return out


def load_or_bootstrap(universe, kind, out_path):
    if out_path.exists():
        return pd.read_parquet(out_path)
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    return bootstrap_gdelt_store(universe, kind, out_path)


def fetch_gap(ticker, query, kind, start_date, end_date):
    """start_date inclusive, end_date exclusive (both pandas Timestamps)."""
    start = start_date.strftime("%Y%m%d") + "000000"
    end = end_date.strftime("%Y%m%d") + "000000"
    mode = "timelinevolraw" if kind == "vol" else "timelinetone"
    print(f"  fetching {ticker} {kind} gap {start_date.date()} -> {end_date.date()}...")
    data = call_with_retry(query=query, mode=mode, format="json", startdatetime=start, enddatetime=end)
    if data is None:
        print(f"    FAILED: {ticker} {kind} gap exhausted retries")
        return None
    LIVE_RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = LIVE_RAW_DIR / f"{ticker}_{start_date.date()}_{end_date.date()}_{kind}.json"
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    time.sleep(SLEEP_BETWEEN_CALLS)
    return parse_timeline(data, kind)


def update_gdelt_series(universe, kind, store, target_date):
    updated_rows = []
    for row in universe:
        ticker = row["ticker"]
        existing = store[store["ticker"] == ticker]
        last_date = existing["date"].max() if len(existing) else None
        gap_start = (last_date + pd.Timedelta(days=1)) if last_date is not None else None
        if gap_start is None or gap_start > target_date:
            continue  # no gap (or ticker missing from bootstrap -- won't happen for universe tickers)
        query = build_query(row["company_name"], row["aliases"])
        new_df = fetch_gap(ticker, query, kind, gap_start, target_date + pd.Timedelta(days=1))
        if new_df is None or new_df.empty:
            continue
        new_df.insert(0, "ticker", ticker)
        updated_rows.append(new_df)

    if not updated_rows:
        print(f"  {kind}: nothing new for any ticker")
        return store

    new_data = pd.concat(updated_rows, ignore_index=True)
    combined = pd.concat([store, new_data], ignore_index=True)
    combined = combined.drop_duplicates(subset=["ticker", "date"], keep="last").sort_values(["ticker", "date"])
    print(f"  {kind}: added {len(new_data)} new rows")
    return combined


def update_prices(universe, target_date):
    symbols = [row["yf_symbol"] for row in universe] + [BENCHMARK]
    if PRICES_PARQUET.exists():
        store = pd.read_parquet(PRICES_PARQUET)
    else:
        LIVE_DIR.mkdir(parents=True, exist_ok=True)
        store = pd.read_parquet(HISTORICAL_PRICES_PARQUET)
        store.to_parquet(PRICES_PARQUET, index=False)
        print(f"  bootstrapped prices.parquet: {len(store)} rows from data/prices.parquet")

    start = (target_date - pd.Timedelta(days=PRICE_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    end = (target_date + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"  fetching prices {start} -> {end} for {len(symbols)} symbols...")
    raw = yf.download(symbols, start=start, end=end, auto_adjust=True, progress=False, group_by="ticker")

    frames = []
    for row in universe + [{"ticker": BENCHMARK, "yf_symbol": BENCHMARK}]:
        ticker, symbol = row["ticker"], row["yf_symbol"]
        if symbol not in raw.columns.get_level_values(0):
            continue
        df = raw[symbol].dropna(subset=["Close"]).reset_index()
        if df.empty:
            continue
        df = df.rename(columns={"Date": "date", "Open": "open", "High": "high",
                                 "Low": "low", "Close": "close", "Volume": "volume"})
        df.insert(0, "ticker", ticker)
        frames.append(df[["ticker", "date", "open", "high", "low", "close", "volume"]])

    if not frames:
        print("  prices: nothing new")
        return store

    new_data = pd.concat(frames, ignore_index=True)
    combined = pd.concat([store, new_data], ignore_index=True)
    combined = combined.drop_duplicates(subset=["ticker", "date"], keep="last").sort_values(["ticker", "date"])
    print(f"  prices: merged, store now {len(combined)} rows (was {len(store)})")
    return combined


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backfill", metavar="YYYY-MM-DD",
        help="Repair a gap by treating this date as the target instead of "
             "yesterday (UTC). Fetches through this date for every ticker "
             "whose store doesn't already reach it; safe to rerun.",
    )
    args = parser.parse_args()

    with open(UNIVERSE_CSV, encoding="utf-8") as f:
        universe = list(csv.DictReader(f))

    if args.backfill:
        target_date = pd.Timestamp(args.backfill)
        print(f"=== Backfill run: target date = {target_date.date()} ===")
    else:
        now_utc = datetime.now(timezone.utc)
        target_date = pd.Timestamp((now_utc - timedelta(days=1)).date())
        print(f"=== Daily ingest run: target date (previous complete UTC day) = {target_date.date()} ===")

    print("\n--- GDELT volume ---")
    vol_store = load_or_bootstrap(universe, "vol", VOL_PARQUET)
    vol_store = update_gdelt_series(universe, "vol", vol_store, target_date)
    vol_store.to_parquet(VOL_PARQUET, index=False)

    print("\n--- GDELT tone ---")
    tone_store = load_or_bootstrap(universe, "tone", TONE_PARQUET)
    tone_store = update_gdelt_series(universe, "tone", tone_store, target_date)
    tone_store.to_parquet(TONE_PARQUET, index=False)

    print("\n--- Prices ---")
    price_store = update_prices(universe, target_date)
    price_store.to_parquet(PRICES_PARQUET, index=False)

    print("\nDaily ingest done.")


if __name__ == "__main__":
    main()
