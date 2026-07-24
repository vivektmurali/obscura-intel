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
CAR_BY_EVENT_CSV = ROOT / "results" / "car_by_event.csv"  # v0.1's locked event-level CAR table
NEW_EVENTS_CSV = ROOT / "data" / "live_events.csv"

FORBIDDEN_NULL_MODE_COLUMNS = {"CAR_t1", "CAR_t5", "CAR_t20", "car_t1", "car_t5", "car_t20"}


def get_verdict():
    with open(STATS_JSON, encoding="utf-8") as f:
        return json.load(f)["verdict"]


def score_intensity(vol_z_values, reference_vol_z):
    """Percentile rank of each vol_z against the locked historical distribution."""
    return np.array([stats.percentileofscore(reference_vol_z, v, kind="rank") for v in vol_z_values])


def compute_tercile_reference():
    """Locked tone_z tercile cutpoints + per-tercile mean CAR_t5, recomputed
    fresh from the locked results/car_by_event.csv every run (242 rows,
    sub-second) -- identical qcut call to 06_figures.py's fig_tone_tercile,
    so there is exactly one implementation of "what a tercile is"."""
    car = pd.read_csv(CAR_BY_EVENT_CSV)
    valid = car.dropna(subset=["CAR_t5"]).copy()
    tercile, edges = pd.qcut(valid["tone_z"], 3, labels=["bottom", "mid", "top"], retbins=True)
    valid["tercile"] = tercile
    grouped = valid.groupby("tercile", observed=True)["CAR_t5"]
    means = grouped.mean()
    ns = grouped.size()
    return {
        "edges": edges.tolist(),
        "mean": {label: float(means[label]) for label in ["bottom", "mid", "top"]},
        "n": {label: int(ns[label]) for label in ["bottom", "mid", "top"]},
    }


def classify_tercile(tone_z, edges):
    """Classify a tone_z value into the locked bottom/mid/top tercile. Values
    more extreme than the locked distribution's own min/max simply fall into
    the nearest tercile (bottom or top) rather than erroring -- there is no
    fourth bucket for "more extreme than anything seen historically"."""
    _, e1, e2, _ = edges
    if tone_z <= e1:
        return "bottom"
    if tone_z <= e2:
        return "mid"
    return "top"


CALIBRATION_DISCLAIMER = (
    "Historical average across similarly-toned events in the locked study "
    "-- not a prediction. The primary test found no statistically "
    "significant relationship between tone and forward returns "
    "(permutation p=0.763). Not a trading signal."
)


def score_calibration(df, tercile_ref):
    """Attach the historical-calibration fields (tercile_label,
    tercile_mean_car5, tercile_n, calibration_disclaimer) to every row.
    These are historical *group* averages from the locked study, never a
    per-event forward-return number -- score_null_mode's claims-audit
    assertion enforces the disclaimer travels with tercile_mean_car5."""
    df = df.copy()
    edges = tercile_ref["edges"]
    df["tercile_label"] = df["tone_z"].apply(lambda z: classify_tercile(z, edges))
    df["tercile_mean_car5"] = df["tercile_label"].map(tercile_ref["mean"])
    df["tercile_n"] = df["tercile_label"].map(tercile_ref["n"])
    df["calibration_disclaimer"] = CALIBRATION_DISCLAIMER
    return df


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
    if "tercile_mean_car5" in df.columns:
        disclaimer_ok = (
            "calibration_disclaimer" in df.columns
            and (df["calibration_disclaimer"] == CALIBRATION_DISCLAIMER).all()
        )
        if not disclaimer_ok:
            raise ValueError(
                "Claims audit failed: tercile_mean_car5 is present without the exact "
                "required calibration disclaimer on every row. A historical-calibration "
                "number must never reach the site without its non-predictive disclaimer."
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
    tercile_ref = compute_tercile_reference()

    live_events = pd.read_csv(LIVE_EVENTS_CSV, parse_dates=["event_date"])
    live_events = score_calibration(live_events, tercile_ref)
    scored_live = score_null_mode(live_events, reference)
    scored_live.to_csv(LIVE_EVENTS_CSV, index=False)
    print(f"Scored {len(scored_live)} events in {LIVE_EVENTS_CSV} "
          f"(columns added: intensity_percentile, novelty_days, tercile_label, "
          f"tercile_mean_car5, tercile_n, calibration_disclaimer)")

    calibration_cols = ["tercile_label", "tercile_mean_car5", "tercile_n", "calibration_disclaimer"]
    if NEW_EVENTS_CSV.exists():
        new_events = pd.read_csv(NEW_EVENTS_CSV, parse_dates=["event_date"])
        if len(new_events):
            merged = new_events[["ticker", "event_date"]].merge(
                scored_live[["ticker", "event_date", "intensity_percentile", "novelty_days"] + calibration_cols],
                on=["ticker", "event_date"], how="left",
            )
            new_events["intensity_percentile"] = merged["intensity_percentile"].to_numpy()
            new_events["novelty_days"] = merged["novelty_days"].to_numpy()
            for col in calibration_cols:
                new_events[col] = merged[col].to_numpy()
        else:
            new_events["intensity_percentile"] = pd.Series(dtype=float)
            new_events["novelty_days"] = pd.Series(dtype=float)
            new_events["tercile_label"] = pd.Series(dtype=object)
            new_events["tercile_mean_car5"] = pd.Series(dtype=float)
            new_events["tercile_n"] = pd.Series(dtype="Int64")
            new_events["calibration_disclaimer"] = pd.Series(dtype=object)
        new_events.to_csv(NEW_EVENTS_CSV, index=False)
        print(f"Scored {len(new_events)} new-this-run events in {NEW_EVENTS_CSV}")


if __name__ == "__main__":
    main()
