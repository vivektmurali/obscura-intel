"""Phase 7 (ARCHITECTURE.md, override handover 2026-07-09): build the static
site. Reads the live pipeline's output (never v0.1's locked study files
directly, except for stats.json's verdict and the historical events.csv used
only as the scoring reference) and renders it via Jinja2 + matplotlib into
docs/, which GitHub Pages serves from the main branch.
"""
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from jinja2 import Environment, FileSystemLoader

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SITE_SRC = ROOT / "site_src"
OUT_DIR = ROOT / "docs"
UNIVERSE_CSV = ROOT / "data" / "universe.csv"
LIVE_EVENTS_CSV = ROOT / "data" / "live" / "events.csv"
NEW_EVENTS_CSV = ROOT / "data" / "live_events.csv"
LIVE_PRICES_PARQUET = ROOT / "data" / "live" / "prices.parquet"
STATS_JSON = ROOT / "results" / "stats.json"

BLUE = "#2a78d6"
RED = "#e34948"
INK = "#14181f"
INK_MUTED = "#7c8494"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"
ACCENT = "#c9822c"

RECENT_EVENTS_LIMIT = 30
# calendar days, not trading days -- 4 (not 3) so a routine Fri-close -> Mon-build
# gap over a weekend doesn't trip the guard; still catches a genuine multi-day outage
MAX_STALENESS_DAYS = 4


def render_ticker_chart(ticker, prices_df, events_df, out_path):
    df = prices_df[prices_df["ticker"] == ticker].sort_values("date")
    if df.empty:
        return
    fig, ax = plt.subplots(figsize=(8, 3.2), dpi=150)
    ax.plot(df["date"], df["close"], color=BLUE, linewidth=1.3)

    ev = events_df[events_df["ticker"] == ticker]
    for _, row in ev.iterrows():
        color = "#3f8f5f" if row["direction"] > 0 else RED
        ax.axvline(row["event_date"], color=color, alpha=0.35, linewidth=1)

    ax.set_facecolor(SURFACE)
    fig.patch.set_facecolor(SURFACE)
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK_MUTED, labelsize=8)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_ylabel("close (INR)", fontsize=8, color=INK_MUTED)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def main():
    with open(STATS_JSON, encoding="utf-8") as f:
        stats = json.load(f)
    verdict = stats["verdict"]
    primary_p = f"{stats['primary']['p_value']:.3f}"
    primary_observed = f"{stats['primary']['observed']:.5f}"
    best_secondary_p = f"{min(s['p_value'] for s in stats['secondary']):.3f}"

    universe = pd.read_csv(UNIVERSE_CSV)
    events = pd.read_csv(LIVE_EVENTS_CSV, parse_dates=["event_date"])
    new_events = pd.read_csv(NEW_EVENTS_CSV, parse_dates=["event_date"]) if NEW_EVENTS_CSV.exists() else pd.DataFrame()
    prices = pd.read_parquet(LIVE_PRICES_PARQUET)

    # freshness guard: fail the build (and therefore the commit/push step after it)
    # rather than publish a site that looks current but is running on stale data.
    # The prior successful build stays live on Pages until data catches up.
    data_current_through = prices["date"].max().date()
    staleness_days = (datetime.now(timezone.utc).date() - data_current_through).days
    if staleness_days > MAX_STALENESS_DAYS:
        print(f"FATAL: price data is {staleness_days} days stale (last: {data_current_through}, "
              f"threshold: {MAX_STALENESS_DAYS}). Refusing to build -- investigate scripts/10_daily_ingest.py "
              f"before publishing a site that looks current but isn't.")
        sys.exit(1)

    sector_by_ticker = dict(zip(universe["ticker"], universe["sector"]))
    company_by_ticker = dict(zip(universe["ticker"], universe["company_name"]))

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)
    (OUT_DIR / "static").mkdir()
    (OUT_DIR / "charts").mkdir()
    (OUT_DIR / "tickers").mkdir()
    shutil.copy(SITE_SRC / "static" / "style.css", OUT_DIR / "static" / "style.css")
    # GitHub Pages ignores dotfiles/underscored dirs by default via Jekyll; disable Jekyll processing
    (OUT_DIR / ".nojekyll").touch()

    env = Environment(loader=FileSystemLoader(str(SITE_SRC / "templates")), autoescape=True)
    build_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    common = dict(build_time=build_time, verdict=verdict, data_current_through=data_current_through)

    # --- index.html ---
    events_sorted = events.sort_values("event_date", ascending=False)
    recent = []
    for _, r in events_sorted.head(RECENT_EVENTS_LIMIT).iterrows():
        recent.append(dict(
            event_date=r["event_date"].date(), ticker=r["ticker"],
            sector=sector_by_ticker.get(r["ticker"], ""),
            direction=r["direction"],
            intensity_percentile=round(r["intensity_percentile"], 1),
        ))
    last_run_date = build_time.split(" ")[0]
    live_since = events["event_date"].min().date() if len(events) else "—"

    tpl = env.get_template("index.html")
    (OUT_DIR / "index.html").write_text(tpl.render(
        root="", page="feed", n_tickers=len(universe), n_events_total=len(events),
        n_new_events=len(new_events), last_run_date=last_run_date, recent_events=recent,
        live_since=live_since, primary_p=primary_p, **common,
    ), encoding="utf-8")

    # --- tickers.html ---
    counts = events.groupby("ticker").size().to_dict()
    tickers_ctx = []
    for _, row in universe.iterrows():
        tickers_ctx.append(dict(ticker=row["ticker"], sector=row["sector"], n_events=counts.get(row["ticker"], 0)))
    tpl = env.get_template("tickers.html")
    (OUT_DIR / "tickers.html").write_text(tpl.render(
        root="", page="tickers", n_tickers=len(universe), tickers=tickers_ctx, **common,
    ), encoding="utf-8")

    # --- per-ticker pages + charts ---
    tpl = env.get_template("ticker.html")
    for _, row in universe.iterrows():
        ticker = row["ticker"]
        render_ticker_chart(ticker, prices, events, OUT_DIR / "charts" / f"{ticker}.png")
        ev_rows = events[events["ticker"] == ticker].sort_values("event_date", ascending=False)
        ev_list = [dict(
            event_date=r["event_date"].date(), direction=r["direction"],
            intensity_percentile=round(r["intensity_percentile"], 1),
            novelty_days=None if pd.isna(r["novelty_days"]) else int(r["novelty_days"]),
            tercile_label=r["tercile_label"],
            tercile_mean_car5_pct=round(r["tercile_mean_car5"] * 100, 2),
            tercile_n=int(r["tercile_n"]),
            calibration_disclaimer=r["calibration_disclaimer"],
        ) for _, r in ev_rows.iterrows()]
        max_intensity = round(ev_rows["intensity_percentile"].max(), 1) if len(ev_rows) else "—"
        (OUT_DIR / "tickers" / f"{ticker}.html").write_text(tpl.render(
            root="../", page="tickers", ticker=ticker, sector=row["sector"],
            company_name=company_by_ticker.get(ticker, ticker), events=ev_list,
            max_intensity=max_intensity, **common,
        ), encoding="utf-8")

    # --- methodology.html ---
    tpl = env.get_template("methodology.html")
    (OUT_DIR / "methodology.html").write_text(tpl.render(
        root="", page="methodology", n_tickers=len(universe), primary_p=primary_p,
        primary_observed=primary_observed, best_secondary_p=best_secondary_p, **common,
    ), encoding="utf-8")

    # --- about.html ---
    tpl = env.get_template("about.html")
    (OUT_DIR / "about.html").write_text(tpl.render(root="", page="about", **common), encoding="utf-8")

    print(f"Built site to {OUT_DIR}: {len(universe)} ticker pages, {len(events)} events, verdict={verdict}")


if __name__ == "__main__":
    main()
