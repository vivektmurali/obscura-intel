"""Phase 3: pull daily adjusted OHLCV for the universe + ^NSEI benchmark via
yfinance (2022-07-01 to 2026-01-31, per HANDOVER.md Sec 4.2), write the combined
store to data/prices.parquet, and report per-ticker integrity. Tickers with
insufficient history are dropped and logged, not silently kept or faked.
"""
import sys
import csv
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
UNIVERSE_CSV = ROOT / "data" / "universe.csv"
PRICES_PARQUET = ROOT / "data" / "prices.parquet"
INTEGRITY_CSV = ROOT / "data" / "price_integrity.csv"

START = "2022-07-01"
END = "2026-01-31"
BENCHMARK = "^NSEI"

# a ticker's series must start/end within this many calendar days of the
# requested range to count as covering the full study period
SLACK_DAYS = 21
MAX_MISSING_PCT = 5.0


def main():
    with open(UNIVERSE_CSV, encoding="utf-8") as f:
        universe = list(csv.DictReader(f))

    symbols = [row["yf_symbol"] for row in universe] + [BENCHMARK]
    print(f"Downloading {len(symbols)} symbols ({START} to {END})...")
    raw = yf.download(symbols, start=START, end=END, auto_adjust=True,
                       progress=False, group_by="ticker")

    if BENCHMARK not in raw.columns.get_level_values(0):
        print(f"FATAL: benchmark {BENCHMARK} missing from download")
        sys.exit(1)
    bench_dates = raw[BENCHMARK]["Close"].dropna().index
    n_bench_days = len(bench_dates)
    print(f"Benchmark {BENCHMARK}: {n_bench_days} trading days "
          f"({bench_dates.min().date()} to {bench_dates.max().date()})")

    long_frames = []
    integrity_rows = []
    dropped = []

    for row in universe + [{"ticker": BENCHMARK, "yf_symbol": BENCHMARK, "company_name": "Nifty 50 (benchmark)"}]:
        ticker = row["ticker"]
        symbol = row["yf_symbol"]
        if symbol not in raw.columns.get_level_values(0):
            print(f"  {ticker}: NOT RETURNED by yfinance at all")
            integrity_rows.append(dict(ticker=ticker, yf_symbol=symbol, rows=0,
                                        first_date="", last_date="", missing_pct=100.0,
                                        nonpositive_close=0, extreme_moves=0, status="DROPPED-no-data"))
            dropped.append(ticker)
            continue

        df = raw[symbol].dropna(subset=["Close"]).copy()
        n_rows = len(df)
        if n_rows == 0:
            print(f"  {ticker}: 0 rows returned")
            integrity_rows.append(dict(ticker=ticker, yf_symbol=symbol, rows=0,
                                        first_date="", last_date="", missing_pct=100.0,
                                        nonpositive_close=0, extreme_moves=0, status="DROPPED-no-data"))
            dropped.append(ticker)
            continue

        first_date, last_date = df.index.min(), df.index.max()
        missing_pct = 100.0 * (1 - n_rows / n_bench_days)
        nonpositive = int((df["Close"] <= 0).sum())
        log_ret = np.log(df["Close"] / df["Close"].shift(1))
        extreme_moves = int((log_ret.abs() > 0.5).sum())

        covers_start = first_date <= pd.Timestamp(START) + pd.Timedelta(days=SLACK_DAYS)
        covers_end = last_date >= pd.Timestamp(END) - pd.Timedelta(days=SLACK_DAYS)
        ok = covers_start and covers_end and missing_pct <= MAX_MISSING_PCT and nonpositive == 0

        status = "OK" if ok else "DROPPED-insufficient-coverage"
        if not ok:
            dropped.append(ticker)
            print(f"  {ticker}: DROPPED (first={first_date.date()} last={last_date.date()} "
                  f"missing={missing_pct:.1f}% nonpositive={nonpositive})")
        else:
            print(f"  {ticker}: OK ({n_rows} rows, {missing_pct:.1f}% missing, "
                  f"{extreme_moves} extreme-move days)")

        integrity_rows.append(dict(
            ticker=ticker, yf_symbol=symbol, rows=n_rows,
            first_date=first_date.date(), last_date=last_date.date(),
            missing_pct=round(missing_pct, 2), nonpositive_close=nonpositive,
            extreme_moves=extreme_moves, status=status,
        ))

        if ok:
            long_df = df[["Open", "High", "Low", "Close", "Volume"]].reset_index()
            long_df.columns = ["date", "open", "high", "low", "close", "volume"]
            long_df.insert(0, "ticker", ticker)
            long_frames.append(long_df)

    prices_df = pd.concat(long_frames, ignore_index=True)
    prices_df.to_parquet(PRICES_PARQUET, index=False)
    print(f"\nWrote {len(prices_df)} rows ({prices_df['ticker'].nunique()} symbols incl. benchmark) "
          f"to {PRICES_PARQUET}")

    pd.DataFrame(integrity_rows).to_csv(INTEGRITY_CSV, index=False)
    print(f"Wrote integrity report to {INTEGRITY_CSV}")

    non_benchmark_dropped = [t for t in dropped if t != BENCHMARK]
    if non_benchmark_dropped:
        print(f"\nDROPPED tickers ({len(non_benchmark_dropped)}): {non_benchmark_dropped}")
    else:
        print("\nNo tickers dropped.")


if __name__ == "__main__":
    main()
