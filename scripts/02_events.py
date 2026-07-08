"""Phase 2: fetch GDELT tone timelines (cached), compute vol_z/tone_z per
HANDOVER.md Sec 4.4, detect spike events, and write data/events.csv.
No synthetic fallback: a ticker-year that can't be fetched after retries is
left out of that ticker's series, not filled in.
"""
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
UNIVERSE_CSV = ROOT / "data" / "universe.csv"
RAW_DIR = ROOT / "data" / "raw"
EVENTS_CSV = ROOT / "data" / "events.csv"
EVENT_SAMPLES_CSV = ROOT / "data" / "event_samples.csv"
N_SAMPLES = 20
HEADLINES_PER_EVENT = 5

BASE = "https://api.gdeltproject.org/api/v2/doc/doc"
YEARS = [2023, 2024, 2025]
SLEEP_BETWEEN_CALLS = 25
MAX_ATTEMPTS = 6
TIMEOUT = 90

VOL_THRESHOLD = dict(vol_z=3, v=5)
FALLBACK_THRESHOLD = dict(vol_z=2, v=3)
EVENT_GATE = 150


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
        if r.status_code == 429:
            print(f"    429 rate limited, backing off {wait}s (attempt {attempt + 1}/{MAX_ATTEMPTS})")
            time.sleep(wait)
            continue
        if r.status_code >= 500:
            print(f"    {r.status_code} server error, backing off {wait}s (attempt {attempt + 1}/{MAX_ATTEMPTS})")
            time.sleep(wait)
            continue
        r.raise_for_status()
        try:
            return r.json()
        except requests.exceptions.JSONDecodeError:
            print(f"    invalid/empty JSON body (HTTP {r.status_code}, {len(r.content)} bytes), "
                  f"backing off {wait}s (attempt {attempt + 1}/{MAX_ATTEMPTS})")
            time.sleep(wait)
            continue
    return None


def fetch_ticker_year_tone(ticker, query, year):
    cache_path = RAW_DIR / f"{ticker}_{year}_tone.json"
    if cache_path.exists():
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)

    start = f"{year}0101000000"
    end = f"{year + 1}0101000000"
    print(f"  fetching {ticker} {year} tone...")
    data = call_with_retry(query=query, mode="timelinetone", format="json",
                            startdatetime=start, enddatetime=end)
    if data is None:
        return None
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    time.sleep(SLEEP_BETWEEN_CALLS)
    return data


def load_series(ticker, kind):
    """kind: 'vol' or 'tone'. Returns a DataFrame indexed by date, or None if
    any year is missing (caller decides whether that's fatal)."""
    all_pts = []
    for year in YEARS:
        f = RAW_DIR / f"{ticker}_{year}_{kind}.json"
        if not f.exists():
            return None
        d = json.load(open(f, encoding="utf-8"))
        pts = d["timeline"][0]["data"]
        all_pts.extend(pts)
    df = pd.DataFrame(all_pts)
    df["date"] = pd.to_datetime(df["date"].str.replace("T000000Z", ""), format="%Y%m%d")
    df = df.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    df["value"] = df["value"].astype(float)
    return df[["date", "value"]]


def zscore(series):
    roll_mean = series.rolling(90, min_periods=90).mean().shift(1)
    roll_std = series.rolling(90, min_periods=90).std().shift(1)
    return (series - roll_mean) / roll_std


def detect_events(vol_df, tone_df, vol_z_min, v_min):
    df = vol_df.rename(columns={"value": "v"}).merge(
        tone_df.rename(columns={"value": "tone"}), on="date", how="inner"
    )
    df["vol_z"] = zscore(df["v"])
    df["tone_z"] = zscore(df["tone"])
    df["is_event_day"] = (df["vol_z"] >= vol_z_min) & (df["v"] >= v_min)

    # merge runs of consecutive event days: keep first day only
    df["run_start"] = df["is_event_day"] & ~df["is_event_day"].shift(1, fill_value=False)
    events = df[df["is_event_day"] & df["run_start"]].copy()
    events["direction"] = np.sign(events["tone_z"])
    return events[["date", "v", "vol_z", "tone", "tone_z", "direction"]]


def fetch_artlist(ticker, query, event_date):
    """event_date: pandas Timestamp. Caches per ticker+date so reruns don't re-fetch."""
    date_str = event_date.strftime("%Y%m%d")
    cache_path = RAW_DIR / f"{ticker}_{date_str}_artlist.json"
    if cache_path.exists():
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)

    start = event_date.strftime("%Y%m%d") + "000000"
    end = (event_date + pd.Timedelta(days=1)).strftime("%Y%m%d") + "000000"
    print(f"  fetching artlist {ticker} {date_str}...")
    data = call_with_retry(query=query, mode="artlist", maxrecords=HEADLINES_PER_EVENT,
                            format="json", startdatetime=start, enddatetime=end)
    if data is None:
        return None
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    time.sleep(SLEEP_BETWEEN_CALLS)
    return data


def sample_top_spikes(events_df, universe_by_ticker):
    top = events_df.reindex(events_df["vol_z"].abs().sort_values(ascending=False).index).head(N_SAMPLES)
    rows = []
    for _, ev in top.iterrows():
        ticker = ev["ticker"]
        row = universe_by_ticker[ticker]
        query = build_query(row["company_name"], row["aliases"])
        data = fetch_artlist(ticker, query, ev["event_date"])
        articles = (data or {}).get("articles", [])
        if not articles:
            rows.append({
                "event_date": ev["event_date"].date(), "ticker": ticker, "vol_z": ev["vol_z"],
                "tone_z": ev["tone_z"], "headline": "(no articles retrieved)", "url": "", "seendate": "",
            })
            continue
        for a in articles:
            rows.append({
                "event_date": ev["event_date"].date(), "ticker": ticker, "vol_z": ev["vol_z"],
                "tone_z": ev["tone_z"], "headline": a.get("title", ""),
                "url": a.get("url", ""), "seendate": a.get("seendate", ""),
            })
    pd.DataFrame(rows).to_csv(EVENT_SAMPLES_CSV, index=False)
    print(f"\nWrote {len(rows)} sample headline rows ({len(top)} events) to {EVENT_SAMPLES_CSV}")


def main():
    with open(UNIVERSE_CSV, encoding="utf-8") as f:
        universe = list(csv.DictReader(f))

    print("=== Fetching tone timelines ===")
    for i, row in enumerate(universe, 1):
        ticker = row["ticker"]
        query = build_query(row["company_name"], row["aliases"])
        print(f"[{i}/{len(universe)}] {ticker}")
        for year in YEARS:
            data = fetch_ticker_year_tone(ticker, query, year)
            if data is None:
                print(f"  FAILED: {ticker} {year} tone exhausted retries")

    print("\n=== Detecting events (primary threshold: vol_z>=3, v>=5) ===")
    all_events = []
    skipped_tickers = []
    for row in universe:
        ticker = row["ticker"]
        vol_df = load_series(ticker, "vol")
        tone_df = load_series(ticker, "tone")
        if vol_df is None or tone_df is None:
            print(f"  SKIP {ticker}: missing vol or tone data")
            skipped_tickers.append(ticker)
            continue
        events = detect_events(vol_df, tone_df, VOL_THRESHOLD["vol_z"], VOL_THRESHOLD["v"])
        events.insert(0, "ticker", ticker)
        all_events.append(events)

    events_df = pd.concat(all_events, ignore_index=True) if all_events else pd.DataFrame()
    n_events = len(events_df)
    print(f"\nPrimary threshold event count: {n_events}")

    used_fallback = False
    if n_events < EVENT_GATE:
        print(f"Below gate ({EVENT_GATE}) — applying pre-registered fallback threshold "
              f"(vol_z>={FALLBACK_THRESHOLD['vol_z']}, v>={FALLBACK_THRESHOLD['v']})")
        used_fallback = True
        all_events = []
        for row in universe:
            ticker = row["ticker"]
            vol_df = load_series(ticker, "vol")
            tone_df = load_series(ticker, "tone")
            if vol_df is None or tone_df is None:
                continue
            events = detect_events(vol_df, tone_df, FALLBACK_THRESHOLD["vol_z"], FALLBACK_THRESHOLD["v"])
            events.insert(0, "ticker", ticker)
            all_events.append(events)
        events_df = pd.concat(all_events, ignore_index=True) if all_events else pd.DataFrame()
        n_events = len(events_df)
        print(f"Fallback threshold event count: {n_events}")

    events_df = events_df.rename(columns={"date": "event_date"})
    events_df.to_csv(EVENTS_CSV, index=False)
    print(f"\nWrote {n_events} events to {EVENTS_CSV}")
    if skipped_tickers:
        print(f"Skipped tickers (missing data): {skipped_tickers}")
    print("USED_FALLBACK:", used_fallback)
    print("GATE:", "PASS (confirmatory)" if n_events >= EVENT_GATE else "FAIL (exploratory/underpowered)")

    if n_events > 0:
        print(f"\n=== Sampling artlist for the {N_SAMPLES} largest spikes ===")
        universe_by_ticker = {row["ticker"]: row for row in universe}
        sample_top_spikes(events_df, universe_by_ticker)


if __name__ == "__main__":
    main()
