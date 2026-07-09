"""Phase 4 step 1: event study per HANDOVER.md Sec 4.5-4.6.

Entry rule: close of the first NSE trading day strictly after the event's
UTC date. Market model: OLS of stock return on ^NSEI return over a 120-
trading-day estimation window ending 21 trading days before entry (>=90
valid observations required, else market-adjusted beta=1 fallback, flagged).
AR_t = r_stock,t - (alpha + beta*r_mkt,t); CAR(h) = sum of AR over the first
h trading days after entry. Horizons: t+1, t+5, t+20.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
EVENTS_CSV = ROOT / "data" / "events.csv"
PRICES_PARQUET = ROOT / "data" / "prices.parquet"
OUT_CSV = ROOT / "results" / "car_by_event.csv"

BENCHMARK = "^NSEI"
EST_WINDOW = 120
EST_GAP = 21  # estimation window ends this many trading days before entry
MIN_EST_OBS = 90
HORIZONS = [1, 5, 20]
MAX_HORIZON = max(HORIZONS)


def build_return_matrix(prices):
    """Wide DataFrame indexed by canonical trading day (the benchmark's
    calendar), one log-return column per ticker (incl. benchmark)."""
    wide_close = prices.pivot(index="date", columns="ticker", values="close").sort_index()
    calendar = wide_close.index[wide_close[BENCHMARK].notna()]
    wide_close = wide_close.loc[calendar]
    returns = np.log(wide_close / wide_close.shift(1))
    return returns.reset_index(drop=True), calendar


def ols_alpha_beta(y, x):
    x_mat = np.column_stack([np.ones(len(x)), x])
    coef, *_ = np.linalg.lstsq(x_mat, y, rcond=None)
    return coef[0], coef[1]


def main():
    events = pd.read_csv(EVENTS_CSV, parse_dates=["event_date"])
    prices = pd.read_parquet(PRICES_PARQUET)
    returns, calendar = build_return_matrix(prices)
    n_days = len(calendar)
    calendar_pos = {d: i for i, d in enumerate(calendar)}

    rows = []
    nan_car_events = []

    for _, ev in events.iterrows():
        ticker = ev["ticker"]
        event_date = ev["event_date"]
        event_id = f"{ticker}_{event_date.date()}"

        after = calendar[calendar > event_date]
        if len(after) == 0:
            print(f"  SKIP {event_id}: no trading day after event_date in price range")
            continue
        entry_date = after[0]
        entry_idx = calendar_pos[entry_date]
        assert entry_date > event_date, "entry date must be strictly after event date"

        est_end_idx = entry_idx - EST_GAP
        est_start_idx = est_end_idx - EST_WINDOW + 1
        assert est_end_idx == entry_idx - EST_GAP, "estimation window must end EST_GAP days before entry"

        if est_start_idx < 0:
            print(f"  SKIP {event_id}: not enough history before entry for estimation window")
            continue

        stock_ret = returns[ticker].to_numpy()
        mkt_ret = returns[BENCHMARK].to_numpy()

        est_stock = stock_ret[est_start_idx:est_end_idx + 1]
        est_mkt = mkt_ret[est_start_idx:est_end_idx + 1]
        valid = ~np.isnan(est_stock) & ~np.isnan(est_mkt)
        n_valid = int(valid.sum())

        if n_valid >= MIN_EST_OBS:
            alpha, beta = ols_alpha_beta(est_stock[valid], est_mkt[valid])
            beta_source = "market_model"
        else:
            alpha, beta = 0.0, 1.0
            beta_source = "market_adjusted"

        fwd_end_idx = entry_idx + MAX_HORIZON
        ar = np.full(MAX_HORIZON, np.nan)
        avail = min(MAX_HORIZON, n_days - 1 - entry_idx)
        for d in range(1, avail + 1):
            idx = entry_idx + d
            r_s, r_m = stock_ret[idx], mkt_ret[idx]
            if not (np.isnan(r_s) or np.isnan(r_m)):
                ar[d - 1] = r_s - (alpha + beta * r_m)

        car = {}
        for h in HORIZONS:
            window = ar[:h]
            car[h] = np.nan if np.isnan(window).any() else window.sum()
            if np.isnan(car[h]):
                nan_car_events.append((event_id, h, "insufficient forward data" if avail < h else "NaN return within window"))

        row = {
            "event_id": event_id, "ticker": ticker, "event_date": event_date.date(),
            "entry_date": entry_date, "beta_source": beta_source, "alpha": alpha,
            "beta": beta, "n_est_obs": n_valid,
            "vol_z": ev["vol_z"], "tone_z": ev["tone_z"], "direction": ev["direction"],
            "CAR_t1": car[1], "CAR_t5": car[5], "CAR_t20": car[20],
        }
        for d in range(MAX_HORIZON):
            row[f"AR_d{d + 1}"] = ar[d]
        rows.append(row)

    out = pd.DataFrame(rows)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False)

    print(f"Wrote {len(out)} events to {OUT_CSV}")
    print(f"beta_source counts: {out['beta_source'].value_counts().to_dict()}")
    print(f"NaN CARs: {len(nan_car_events)} (event, horizon, reason) pairs")
    for eid, h, reason in nan_car_events:
        print(f"  {eid} CAR_t{h}: {reason}")


if __name__ == "__main__":
    main()
