"""Phase 6 (ARCHITECTURE.md, override handover scope): verdict-bounded
scoring for live events. Branches on the Phase 4/5 verdict recorded in
results/stats.json -- currently NULL, so this emits only intensity
(vol_z percentile against the locked historical reference distribution)
and novelty (days since the ticker's previous live event). No forward-
return numbers anywhere in NULL mode -- enforced by an assertion, not
just convention, per ARCHITECTURE.md's claims-audit gate.

Optional LLM enrichment (ARCHITECTURE.md Sec 8) is a separate, still-
banned module requiring its own override -- not implemented here.

Run after scripts/11_daily_events.py; adds score columns to its output.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
STATS_JSON = ROOT / "results" / "stats.json"
HISTORICAL_EVENTS_CSV = ROOT / "data" / "events.csv"  # v0.1's locked reference distribution
LIVE_EVENTS_CSV = ROOT / "data" / "live" / "events.csv"
NEW_EVENTS_CSV = ROOT / "data" / "live_events.csv"

FORBIDDEN_NULL_MODE_COLUMNS = {"CAR_t1", "CAR_t5", "CAR_t20", "car_t1", "car_t5", "car_t20"}


def get_verdict():
    with open(STATS_JSON, encoding="utf-8") as f:
        return json.load(f)["verdict"]


def score_intensity(vol_z_values, reference_vol_z):
    """Percentile rank of each vol_z against the locked historical distribution."""
    return np.array([stats.percentileofscore(reference_vol_z, v, kind="rank") for v in vol_z_values])


def score_novelty(df):
    """Days since this ticker's previous event, within the same (sorted) table."""
    df = df.sort_values(["ticker", "event_date"]).copy()
    df["novelty_days"] = df.groupby("ticker")["event_date"].diff().dt.days
    return df


def score_null_mode(df, reference_vol_z):
    assert not (FORBIDDEN_NULL_MODE_COLUMNS & set(df.columns)), (
        "NULL-mode claims audit failed: a forward-return column is present. "
        "Per ARCHITECTURE.md Sec 7, NULL verdict must never show or imply forward returns."
    )
    df = score_novelty(df)
    df["intensity_percentile"] = score_intensity(df["vol_z"].to_numpy(), reference_vol_z)
    return df


def main():
    verdict = get_verdict()
    print(f"Verdict on record: {verdict}")
    if verdict != "NULL":
        print(f"FATAL: this script only implements NULL-mode scoring; verdict is {verdict}. "
              "SIGNAL-mode scoring (historical CAR(t+5) bucket stats) is not built -- "
              "would need its own review before implementing, per the claims-audit gate.")
        sys.exit(1)

    if not LIVE_EVENTS_CSV.exists():
        print("FATAL: data/live/events.csv missing -- run 11_daily_events.py first")
        sys.exit(1)

    reference = pd.read_csv(HISTORICAL_EVENTS_CSV)["vol_z"].to_numpy()

    live_events = pd.read_csv(LIVE_EVENTS_CSV, parse_dates=["event_date"])
    scored_live = score_null_mode(live_events, reference)
    scored_live.to_csv(LIVE_EVENTS_CSV, index=False)
    print(f"Scored {len(scored_live)} events in {LIVE_EVENTS_CSV} "
          f"(columns added: intensity_percentile, novelty_days)")

    if NEW_EVENTS_CSV.exists():
        new_events = pd.read_csv(NEW_EVENTS_CSV, parse_dates=["event_date"])
        if len(new_events):
            # pull the already-computed scores for these specific (ticker, event_date) rows
            merged = new_events[["ticker", "event_date"]].merge(
                scored_live[["ticker", "event_date", "intensity_percentile", "novelty_days"]],
                on=["ticker", "event_date"], how="left",
            )
            new_events["intensity_percentile"] = merged["intensity_percentile"].to_numpy()
            new_events["novelty_days"] = merged["novelty_days"].to_numpy()
        else:
            new_events["intensity_percentile"] = pd.Series(dtype=float)
            new_events["novelty_days"] = pd.Series(dtype=float)
        new_events.to_csv(NEW_EVENTS_CSV, index=False)
        print(f"Scored {len(new_events)} new-this-run events in {NEW_EVENTS_CSV}")


if __name__ == "__main__":
    main()
