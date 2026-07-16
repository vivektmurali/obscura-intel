"""Phase 7 (post-v0.1, retroactive addendum -- see DECISIONS.md): post-hoc
power / minimum-detectable-effect (MDE) analysis for the primary test.

This does NOT reopen the verdict, respecify the test, or touch any kill
criterion (HANDOVER.md Sec 4.7-4.8) -- it answers a different question the
locked result doesn't by itself: given this design's actual sampling
variability (the permutation null's spread), what effect size could the
primary test have detected? A NULL result from an underpowered design and a
NULL result from a well-powered one are different findings; this makes which
one this is explicit and citable, using only data already locked
(results/car_by_event.csv, results/null_distributions.csv) and the primary
test's own alpha (HANDOVER.md Sec 4.7: one-sided, 0.05).
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
CAR_CSV = ROOT / "results" / "car_by_event.csv"
NULL_CSV = ROOT / "results" / "null_distributions.csv"
STATS_JSON = ROOT / "results" / "stats.json"
OUT_JSON = ROOT / "results" / "power_analysis.json"

ALPHA = 0.05  # HANDOVER.md Sec 4.7: one-sided primary test threshold
POWER_LEVELS = [0.5, 0.8, 0.9]
# Illustrative benchmarks only, not literature-sourced effect sizes (rule 7:
# don't assert a claim -- e.g. "typical PEAD magnitude is X%" -- without a
# citable source). Round numbers spanning "small" to "large" for a 5-day
# tone-signed CAR, so a reader can place this study's MDE on that scale.
BENCHMARK_EFFECTS = [0.005, 0.01, 0.015, 0.02, 0.03]


def compute_mde(se, z_alpha, power_levels):
    """Minimum detectable effect at each power level, given a standard error."""
    return {
        f"{int(p * 100)}pct": (z_alpha + stats.norm.ppf(p)) * se
        for p in power_levels
    }


def compute_achieved_power(se, z_alpha, benchmark_effects):
    """Achieved power to detect each benchmark effect size, given a standard error."""
    return {
        f"{effect * 100:.1f}pct": float(stats.norm.cdf(effect / se - z_alpha))
        for effect in benchmark_effects
    }


def main():
    car = pd.read_csv(CAR_CSV, parse_dates=["event_date", "entry_date"])
    null_df = pd.read_csv(NULL_CSV)
    with open(STATS_JSON, encoding="utf-8") as f:
        stats_json = json.load(f)

    car5 = car.dropna(subset=["CAR_t5"])
    x = car5["direction"] * car5["CAR_t5"]
    n = len(x)

    # cross-check against the locked primary result -- this script must never
    # silently diverge from what 05_inference.py already found and recorded.
    # An explicit check, not a bare `assert`: assertions are stripped entirely
    # under `python -O`/PYTHONOPTIMIZE, which would silently disable this
    # staleness guard (found in code review, 2026-07-16).
    observed = x.mean()
    if abs(observed - stats_json["primary"]["observed"]) >= 1e-9:
        raise ValueError(
            "observed T5 statistic recomputed here does not match the locked stats.json -- "
            "do not proceed, results/car_by_event.csv may be stale relative to stats.json"
        )

    se_empirical = null_df["T5"].std(ddof=1)
    se_parametric = x.std(ddof=1) / np.sqrt(n)
    z_alpha = stats.norm.ppf(1 - ALPHA)

    mde = {
        "empirical_permutation_null": {
            "se": se_empirical,
            "mde_by_power": compute_mde(se_empirical, z_alpha, POWER_LEVELS),
        },
        "parametric_sample_se": {
            "se": se_parametric,
            "mde_by_power": compute_mde(se_parametric, z_alpha, POWER_LEVELS),
        },
    }

    achieved_power = compute_achieved_power(se_empirical, z_alpha, BENCHMARK_EFFECTS)

    results = {
        "n_events": n,
        "observed_primary_statistic": observed,
        "p_value_primary": stats_json["primary"]["p_value"],
        "alpha_one_sided": ALPHA,
        "mde": mde,
        "achieved_power_at_benchmark_effects": achieved_power,
        "note": (
            "MDE/power computed for the primary test only (mean(sign(tone_z) x CAR_t5), "
            "one-sided alpha=0.05), using the permutation null's own empirical standard "
            "deviation as the primary SE estimate (matches the test actually run) and a "
            "parametric std/sqrt(n) estimate as a cross-check. Both assume independence "
            "across events; cross-sectional event clustering (HANDOVER.md Sec 4.7) would "
            "inflate the true SE and so make this MDE optimistic, not pessimistic -- "
            "consistent with the rest of this project's honesty-over-momentum stance."
        ),
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=float)

    print(f"n = {n} events, observed T5 = {observed:.5f} (p={stats_json['primary']['p_value']:.4f})")
    print(f"\nSE estimates: empirical permutation-null = {se_empirical:.6f}, "
          f"parametric = {se_parametric:.6f} (agree within "
          f"{abs(se_empirical - se_parametric) / se_parametric:.1%})")
    print("\n=== Minimum detectable effect (one-sided alpha=0.05), using empirical null SE ===")
    for p in POWER_LEVELS:
        m = mde["empirical_permutation_null"]["mde_by_power"][f"{int(p * 100)}pct"]
        print(f"  {int(p * 100)}% power: MDE = {m:.5f} ({m * 100:.3f}% tone-signed CAR_t5)")
    print("\n=== Achieved power at illustrative benchmark effect sizes ===")
    for k, v in achieved_power.items():
        print(f"  true effect={k}: achieved power={v:.1%}")
    print(f"\nWritten to {OUT_JSON}")


if __name__ == "__main__":
    main()
