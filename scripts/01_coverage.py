"""Phase 1: pull GDELT article-volume timelines for every universe ticker
over the study period (2023-01-01 to 2025-12-31), cache raw responses, and
summarize coverage per ticker. No synthetic fallback: a ticker that can't be
fetched after retries is logged as failed, not filled in.
"""
import csv
import json
import sys
import time
from pathlib import Path
from statistics import median

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
UNIVERSE_CSV = ROOT / "data" / "universe.csv"
RAW_DIR = ROOT / "data" / "raw"
OUT_CSV = ROOT / "data" / "coverage_summary.csv"

BASE = "https://api.gdeltproject.org/api/v2/doc/doc"
YEARS = [2023, 2024, 2025]
SLEEP_BETWEEN_CALLS = 25
MAX_ATTEMPTS = 6
TIMEOUT = 90


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


def fetch_ticker_year(ticker, query, year):
    cache_path = RAW_DIR / f"{ticker}_{year}_vol.json"
    if cache_path.exists():
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)

    start = f"{year}0101000000"
    end = f"{year + 1}0101000000"
    print(f"  fetching {ticker} {year}...")
    data = call_with_retry(query=query, mode="timelinevolraw", format="json",
                            startdatetime=start, enddatetime=end)
    if data is None:
        return None
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    time.sleep(SLEEP_BETWEEN_CALLS)
    return data


def main():
    with open(UNIVERSE_CSV, encoding="utf-8") as f:
        universe = list(csv.DictReader(f))

    rows = []
    failed = []

    for i, row in enumerate(universe, 1):
        ticker = row["ticker"]
        company_name = row["company_name"]
        aliases = row["aliases"]
        query = build_query(company_name, aliases)
        print(f"[{i}/{len(universe)}] {ticker} ({company_name})")

        all_points = []
        ticker_failed = False
        for year in YEARS:
            data = fetch_ticker_year(ticker, query, year)
            if data is None:
                print(f"  FAILED: {ticker} {year} exhausted retries")
                ticker_failed = True
                continue
            pts = (data.get("timeline") or [{}])[0].get("data", [])
            all_points.extend(pts)

        if ticker_failed and not all_points:
            failed.append(ticker)
            continue

        values = [p["value"] for p in all_points]
        total_articles = sum(values)
        nonzero_days = sum(1 for v in values if v > 0)
        max_daily = max(values) if values else 0
        nonzero_days_per_year = nonzero_days / 3.0

        rows.append({
            "ticker": ticker,
            "company_name": company_name,
            "total_articles": total_articles,
            "nonzero_days": nonzero_days,
            "nonzero_days_per_year": round(nonzero_days_per_year, 1),
            "max_daily_count": max_daily,
            "partial": ticker_failed,
        })

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "ticker", "company_name", "total_articles", "nonzero_days",
            "nonzero_days_per_year", "max_daily_count", "partial",
        ])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote {len(rows)} rows to {OUT_CSV}")
    if failed:
        print(f"FAILED entirely (no data at all): {failed}")

    if rows:
        med = median(r["nonzero_days_per_year"] for r in rows)
        print(f"\nMedian nonzero-volume days/year: {med:.1f}")
        print("GATE:", "PASS" if med >= 30 else "FAIL", "(threshold: >= 30)")
    else:
        print("GATE: FAIL (no data at all)")


if __name__ == "__main__":
    main()
