"""Phase 4 step 2: permutation inference per HANDOVER.md Sec 4.7-4.8.

Primary test: one-sided permutation test on mean(sign(tone_z) * CAR_t5),
1,000 seeded draws. Secondary tests (BH-FDR q=0.10): tone-signed CAR at
t+1/t+20, mean |CAR| at each horizon, top-vs-bottom tone-tercile spread
at t+5. Pre-registered robustness pass (one pass only): market-adjusted
returns instead of market-model; drop high-simultaneity calendar days.
(The third pre-registered robustness variant, the fallback spike
threshold, is not applicable -- the primary threshold already cleared
the event-count gate, so there was nothing to fall back from.)

Permutation CARs are computed with a rolling-window closed-form OLS
(validated against 04_event_study.py's per-event lstsq to floating-point
precision) so that 1,000 x ~242 recomputations stay fast.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
EVENTS_CSV = ROOT / "data" / "events.csv"
CAR_CSV = ROOT / "results" / "car_by_event.csv"
PRICES_PARQUET = ROOT / "data" / "prices.parquet"
STATS_JSON = ROOT / "results" / "stats.json"
NULL_DIST_CSV = ROOT / "results" / "null_distributions.csv"

BENCHMARK = "^NSEI"
EST_WINDOW = 120
EST_GAP = 21
HORIZONS = [1, 5, 20]
MAX_HORIZON = max(HORIZONS)
EXCLUSION_BUFFER = 5  # trading days around each real event, excluded from pseudo-date pool
N_PERM = 1000
SEED = 42
FDR_Q = 0.10
SIMULTANEITY_THRESHOLD = 3  # drop calendar days with MORE than this many simultaneous tickers


def build_return_matrix(prices):
    wide_close = prices.pivot(index="date", columns="ticker", values="close").sort_index()
    calendar = wide_close.index[wide_close[BENCHMARK].notna()]
    wide_close = wide_close.loc[calendar]
    returns = np.log(wide_close / wide_close.shift(1)).reset_index(drop=True)
    return returns, calendar


def rolling_alpha_beta(returns, ticker):
    stock = returns[ticker]
    mkt = returns[BENCHMARK]
    cov = stock.rolling(EST_WINDOW).cov(mkt)
    var = mkt.rolling(EST_WINDOW).var()
    beta = (cov / var).to_numpy()
    alpha = (stock.rolling(EST_WINDOW).mean() - (cov / var) * mkt.rolling(EST_WINDOW).mean()).to_numpy()
    return alpha, beta


def car_from_entry(entry_idx, stock_ret, mkt_ret, alpha, beta, n_days, market_adjusted=False):
    est_end_idx = entry_idx - EST_GAP
    if market_adjusted:
        a, b = 0.0, 1.0
    else:
        a, b = alpha[est_end_idx], beta[est_end_idx]
        if np.isnan(a) or np.isnan(b):
            return {h: np.nan for h in HORIZONS}

    avail = min(MAX_HORIZON, n_days - 1 - entry_idx)
    ar = np.full(MAX_HORIZON, np.nan)
    for d in range(1, avail + 1):
        idx = entry_idx + d
        r_s, r_m = stock_ret[idx], mkt_ret[idx]
        if not (np.isnan(r_s) or np.isnan(r_m)):
            ar[d - 1] = r_s - (a + b * r_m)

    out = {}
    for h in HORIZONS:
        window = ar[:h]
        out[h] = np.nan if np.isnan(window).any() else window.sum()
    return out


def one_sided_p(obs, null):
    null = np.asarray(null)
    valid = null[~np.isnan(null)]
    return (1 + np.sum(valid >= obs)) / (1 + len(valid))


def bh_fdr(pvals, q):
    pvals = np.asarray(pvals)
    n = len(pvals)
    order = np.argsort(pvals)
    ranked = pvals[order]
    thresh = (np.arange(1, n + 1) / n) * q
    passed = ranked <= thresh
    if not passed.any():
        return np.zeros(n, dtype=bool)
    max_rank = np.max(np.where(passed)[0])
    survives = np.zeros(n, dtype=bool)
    survives[order[:max_rank + 1]] = True
    return survives


def main():
    rng = np.random.default_rng(SEED)
    events = pd.read_csv(EVENTS_CSV, parse_dates=["event_date"])
    car = pd.read_csv(CAR_CSV, parse_dates=["event_date", "entry_date"])
    prices = pd.read_parquet(PRICES_PARQUET)
    returns, calendar = build_return_matrix(prices)
    calendar_pos = {d: i for i, d in enumerate(calendar)}
    n_days = len(calendar)

    # study-period bounds mirror where real events can occur
    period_start, period_end = pd.Timestamp("2023-01-01"), pd.Timestamp("2025-12-31")

    tickers_with_events = car["ticker"].unique().tolist()
    alpha_beta = {t: rolling_alpha_beta(returns, t) for t in tickers_with_events}
    stock_ret_arr = {t: returns[t].to_numpy() for t in tickers_with_events}
    mkt_ret_arr = returns[BENCHMARK].to_numpy()

    # candidate pseudo-event entry-index pool per ticker, excluding +/-EXCLUSION_BUFFER
    # trading days around each of that ticker's real event entry indices
    candidate_pool = {}
    for t in tickers_with_events:
        real_entries = car.loc[car["ticker"] == t, "entry_date"].map(calendar_pos).to_numpy()
        forbidden = set()
        for e in real_entries:
            forbidden.update(range(e - EXCLUSION_BUFFER, e + EXCLUSION_BUFFER + 1))
        lo = EST_WINDOW + EST_GAP  # enough history for a full estimation window
        hi = n_days - 1
        pool = [i for i in range(lo, hi) if i not in forbidden
                and period_start <= calendar[i] <= period_end]
        candidate_pool[t] = np.array(pool)

    per_ticker_counts = car.groupby("ticker").size().to_dict()
    n_events = len(car)
    # explicit row-position map so pseudo-event results land back in the exact
    # same row order as car_by_event.csv, regardless of groupby iteration order
    row_positions_by_ticker = {t: car.index[car["ticker"] == t].to_numpy() for t in tickers_with_events}
    car_reset = car.reset_index(drop=True)

    # fixed tercile membership (by real tone_z, among events with a valid observed
    # CAR_t5) -- computed once and reused for both the observed statistic and
    # every permutation's pseudo-CAR_t5, since tone_z never changes across draws
    valid5_mask = car_reset["CAR_t5"].notna()
    tone_terciles = pd.qcut(car_reset.loc[valid5_mask, "tone_z"], 3, labels=["bottom", "mid", "top"])
    tercile_top_mask = pd.Series(False, index=car_reset.index)
    tercile_bottom_mask = pd.Series(False, index=car_reset.index)
    tercile_top_mask.loc[tone_terciles[tone_terciles == "top"].index] = True
    tercile_bottom_mask.loc[tone_terciles[tone_terciles == "bottom"].index] = True

    print(f"Running {N_PERM} permutations over {n_events} events, "
          f"{len(tickers_with_events)} tickers...")

    null_rows = []  # per-permutation aggregate stats (market model)
    null_rows_adj = []  # per-permutation aggregate stats (market-adjusted robustness variant)
    tercile_null_vals = []

    for p in range(N_PERM):
        c1 = np.full(n_events, np.nan)
        c5 = np.full(n_events, np.nan)
        c20 = np.full(n_events, np.nan)
        c1a = np.full(n_events, np.nan)
        c5a = np.full(n_events, np.nan)
        c20a = np.full(n_events, np.nan)

        for t in tickers_with_events:
            k = per_ticker_counts[t]
            drawn = rng.choice(candidate_pool[t], size=k, replace=False)
            a_arr, b_arr = alpha_beta[t]
            s_arr = stock_ret_arr[t]
            positions = row_positions_by_ticker[t]
            for slot, entry_idx in enumerate(drawn):
                pos = positions[slot]
                res = car_from_entry(entry_idx, s_arr, mkt_ret_arr, a_arr, b_arr, n_days)
                res_adj = car_from_entry(entry_idx, s_arr, mkt_ret_arr, a_arr, b_arr, n_days, market_adjusted=True)
                c1[pos], c5[pos], c20[pos] = res[1], res[5], res[20]
                c1a[pos], c5a[pos], c20a[pos] = res_adj[1], res_adj[5], res_adj[20]

        dirs = car_reset["direction"].to_numpy()

        def safe_mean(x):
            v = x[~np.isnan(x)]
            return np.mean(v) if len(v) else np.nan

        null_rows.append(dict(
            T1=safe_mean(dirs * c1), T5=safe_mean(dirs * c5), T20=safe_mean(dirs * c20),
            M1=safe_mean(np.abs(c1)), M5=safe_mean(np.abs(c5)), M20=safe_mean(np.abs(c20)),
        ))
        null_rows_adj.append(dict(T5_adj=safe_mean(dirs * c5a)))

        # tercile null: same (fixed) tercile membership as the observed tone_z
        # terciles, applied to this permutation's pseudo CAR_t5, restricted to
        # the same rows used for the observed tercile statistic
        c5_series = pd.Series(c5, index=car_reset.index)
        top_p = c5_series[tercile_top_mask].mean()
        bottom_p = c5_series[tercile_bottom_mask].mean()
        tercile_null_vals.append(top_p - bottom_p)

        if (p + 1) % 100 == 0:
            print(f"  {p + 1}/{N_PERM} permutations done")

    null_df = pd.DataFrame(null_rows)
    null_df_adj = pd.DataFrame(null_rows_adj)
    tercile_null_vals = np.array(tercile_null_vals)

    null_export = null_df.copy()
    null_export["T5_adj"] = null_df_adj["T5_adj"]
    null_export["tercile_spread"] = tercile_null_vals
    null_export.to_csv(NULL_DIST_CSV, index=False)

    # observed statistics from the real (market-model) event study
    car_valid5 = car.dropna(subset=["CAR_t5"])
    car_valid1 = car.dropna(subset=["CAR_t1"])
    car_valid20 = car.dropna(subset=["CAR_t20"])

    T1_obs = (car_valid1["direction"] * car_valid1["CAR_t1"]).mean()
    T5_obs = (car_valid5["direction"] * car_valid5["CAR_t5"]).mean()
    T20_obs = (car_valid20["direction"] * car_valid20["CAR_t20"]).mean()
    M1_obs = car_valid1["CAR_t1"].abs().mean()
    M5_obs = car_valid5["CAR_t5"].abs().mean()
    M20_obs = car_valid20["CAR_t20"].abs().mean()

    top_mean = car_reset.loc[tercile_top_mask, "CAR_t5"].mean()
    bottom_mean = car_reset.loc[tercile_bottom_mask, "CAR_t5"].mean()
    tercile_obs = top_mean - bottom_mean
    p_tercile = one_sided_p(tercile_obs, tercile_null_vals)

    # --- primary test ---
    p_primary = one_sided_p(T5_obs, null_df["T5"])
    primary_pass = p_primary < 0.05

    # --- secondary tests + BH-FDR ---
    secondary_labels = ["tone_signed_CAR_t1", "tone_signed_CAR_t20",
                         "abs_CAR_t1_vs_null", "abs_CAR_t5_vs_null", "abs_CAR_t20_vs_null",
                         "tone_tercile_spread_CAR_t5"]
    secondary_obs = [T1_obs, T20_obs, M1_obs, M5_obs, M20_obs, tercile_obs]
    secondary_pvals = [
        one_sided_p(T1_obs, null_df["T1"]), one_sided_p(T20_obs, null_df["T20"]),
        one_sided_p(M1_obs, null_df["M1"]), one_sided_p(M5_obs, null_df["M5"]),
        one_sided_p(M20_obs, null_df["M20"]), p_tercile,
    ]

    secondary_survives = bh_fdr(np.array(secondary_pvals), FDR_Q)

    # --- robustness pass (one pass, after primary/secondary already recorded) ---
    # market-model observed T5 vs a market-adjusted-CAR null is not a like-for-like
    # comparison; reported for transparency only, not as a formal p-value claim
    p_market_adjusted = one_sided_p(T5_obs, null_df_adj["T5_adj"])

    car_dates = events.copy()
    car_dates["n_simultaneous"] = car_dates.groupby("event_date")["ticker"].transform("count")
    clustered_dates = sorted(car_dates.loc[car_dates["n_simultaneous"] > SIMULTANEITY_THRESHOLD,
                                            "event_date"].dt.date.astype(str).unique().tolist())
    declustered = car_valid5[~car_valid5["event_date"].astype(str).isin(clustered_dates)]
    T5_obs_declustered = (declustered["direction"] * declustered["CAR_t5"]).mean()
    p_declustered = one_sided_p(T5_obs_declustered, null_df["T5"])

    verdict = "SIGNAL" if (primary_pass or secondary_survives.any()) else "NULL"

    results = {
        "n_permutations": N_PERM, "seed": SEED, "n_events_total": len(car),
        "primary": {
            "statistic": "mean(sign(tone_z) x CAR_t5)", "observed": T5_obs,
            "p_value": p_primary, "pass": bool(primary_pass), "threshold": 0.05,
        },
        "secondary": [
            {"label": lbl, "observed": obs, "p_value": pv, "fdr_survives": bool(surv)}
            for lbl, obs, pv, surv in zip(secondary_labels, secondary_obs, secondary_pvals, secondary_survives)
        ],
        "robustness": {
            "fallback_spike_threshold": "not applicable -- primary threshold already cleared the >=150 event gate",
            "market_adjusted_returns": {
                "note": "market-model observed T5 vs a market-adjusted-CAR null is not a "
                        "like-for-like comparison; reported for transparency only",
                "p_value_vs_market_adjusted_null": p_market_adjusted,
            },
            "drop_high_simultaneity_days": {
                "threshold": f">{SIMULTANEITY_THRESHOLD} simultaneous tickers",
                "dropped_dates": clustered_dates,
                "n_events_dropped": len(car_valid5) - len(declustered),
                "observed_T5_declustered": T5_obs_declustered,
                "p_value": p_declustered,
            },
        },
        "verdict": verdict,
    }

    STATS_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(STATS_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=float)

    print("\n=== PRIMARY TEST ===")
    print(f"  mean(sign(tone_z) x CAR_t5) = {T5_obs:.5f}, p = {p_primary:.4f} "
          f"-> {'PASS' if primary_pass else 'FAIL'} (threshold p<0.05)")
    print("\n=== SECONDARY TESTS (BH-FDR q=0.10) ===")
    for lbl, obs, pv, surv in zip(secondary_labels, secondary_obs, secondary_pvals, secondary_survives):
        print(f"  {lbl}: obs={obs:.5f} p={pv:.4f} FDR-survives={surv}")
    print("\n=== ROBUSTNESS (exploratory) ===")
    print(f"  Market-adjusted-null comparison p={p_market_adjusted:.4f} (see note in stats.json)")
    print(f"  Dropped {len(clustered_dates)} high-simultaneity dates "
          f"({len(car_valid5) - len(declustered)} events removed)")
    print(f"  Declustered T5 obs={T5_obs_declustered:.5f}, p={p_declustered:.4f}")
    print(f"\nVERDICT: {verdict}")


if __name__ == "__main__":
    main()
