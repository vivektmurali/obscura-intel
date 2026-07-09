"""Phase 6: report figures. Null-vs-real distribution for the primary test,
observed CAR vs null spread at each horizon, and the tone-tercile spread.
Static PNGs only (matplotlib, per HANDOVER.md's allowed stack).
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
CAR_CSV = ROOT / "results" / "car_by_event.csv"
NULL_CSV = ROOT / "results" / "null_distributions.csv"
FIG_DIR = ROOT / "results" / "figures"

# palette (validated categorical/diverging set; see DECISIONS.md)
BLUE = "#2a78d6"
RED = "#e34948"
GRAY_MID = "#f0efec"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Segoe UI", "DejaVu Sans", "Arial"],
    "axes.edgecolor": GRID,
    "axes.labelcolor": INK_SECONDARY,
    "xtick.color": INK_MUTED,
    "ytick.color": INK_MUTED,
    "text.color": INK,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
})


def fig_primary_null(null_df, obs_t5, p_value):
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=150)
    ax.hist(null_df["T5"], bins=40, color=BLUE, alpha=0.75, edgecolor=SURFACE, linewidth=0.5,
            label="Permutation null (n=1,000)")
    ax.axvline(obs_t5, color=RED, linewidth=2, label=f"Observed = {obs_t5:.5f}")
    ax.axvline(0, color=INK_MUTED, linewidth=1, linestyle="--")
    ax.set_title("Primary test: observed vs. permutation null", color=INK, fontsize=13, loc="left")
    ax.set_xlabel("mean(sign(tone_z) x CAR_t5)")
    ax.set_ylabel("permutation draws")
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.legend(frameon=False, fontsize=9, loc="upper right")
    ax.text(0.02, 0.98, f"one-sided p = {p_value:.3f}", transform=ax.transAxes,
            fontsize=10, color=INK_SECONDARY, va="top")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "primary_null_vs_real.png")
    plt.close(fig)


def fig_car_by_horizon(car, null_df):
    horizons = [("CAR_t1", "T1", "t+1"), ("CAR_t5", "T5", "t+5"), ("CAR_t20", "T20", "t+20")]
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=150)
    x = np.arange(len(horizons))

    null_means, null_los, null_his, obs_vals = [], [], [], []
    for car_col, null_col, _ in horizons:
        sub = car.dropna(subset=[car_col])
        obs = (sub["direction"] * sub[car_col]).mean()
        obs_vals.append(obs)
        null_vals = null_df[null_col].dropna()
        null_means.append(null_vals.mean())
        null_los.append(np.percentile(null_vals, 2.5))
        null_his.append(np.percentile(null_vals, 97.5))

    null_los = np.array(null_los)
    null_his = np.array(null_his)
    null_means = np.array(null_means)

    ax.bar(x - 0.15, null_means, width=0.3, color=INK_MUTED, alpha=0.35, label="Null mean")
    ax.errorbar(x - 0.15, null_means, yerr=[null_means - null_los, null_his - null_means],
                fmt="none", ecolor=INK_MUTED, elinewidth=1.2, capsize=4,
                label="Null 95% interval")
    ax.bar(x + 0.15, obs_vals, width=0.3, color=BLUE, label="Observed")

    ax.axhline(0, color=INK_MUTED, linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([h[2] for h in horizons])
    ax.set_ylabel("mean(sign(tone_z) x CAR)")
    ax.set_title("Tone-signed CAR: observed vs. null, by horizon", color=INK, fontsize=13, loc="left")
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "car_by_horizon.png")
    plt.close(fig)


def fig_tone_tercile(car):
    valid = car.dropna(subset=["CAR_t5"]).copy()
    valid["tercile"] = pd.qcut(valid["tone_z"], 3, labels=["bottom", "mid", "top"])
    grouped = valid.groupby("tercile", observed=True)["CAR_t5"]
    means = grouped.mean()
    sems = grouped.sem()
    ns = grouped.size()

    colors = [RED, INK_MUTED, BLUE]
    fig, ax = plt.subplots(figsize=(6, 4.5), dpi=150)
    x = np.arange(3)
    ax.bar(x, means.reindex(["bottom", "mid", "top"]), yerr=sems.reindex(["bottom", "mid", "top"]),
           color=colors, capsize=4, ecolor=INK_SECONDARY)
    ax.axhline(0, color=INK_MUTED, linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([f"bottom\n(n={ns['bottom']})", f"mid\n(n={ns['mid']})", f"top\n(n={ns['top']})"])
    ax.set_ylabel("mean CAR_t5")
    ax.set_title("CAR_t5 by tone_z tercile (bottom = most negative tone)", color=INK, fontsize=12, loc="left")
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "tone_tercile.png")
    plt.close(fig)


def main():
    car = pd.read_csv(CAR_CSV, parse_dates=["event_date", "entry_date"])
    null_df = pd.read_csv(NULL_CSV)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    car_valid5 = car.dropna(subset=["CAR_t5"])
    obs_t5 = (car_valid5["direction"] * car_valid5["CAR_t5"]).mean()
    null_valid = null_df["T5"].dropna()
    p_value = (1 + (null_valid >= obs_t5).sum()) / (1 + len(null_valid))

    fig_primary_null(null_df, obs_t5, p_value)
    fig_car_by_horizon(car, null_df)
    fig_tone_tercile(car)

    print(f"Wrote 3 figures to {FIG_DIR}")


if __name__ == "__main__":
    main()
