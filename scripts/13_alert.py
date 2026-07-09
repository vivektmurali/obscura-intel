"""Phase 8 (ARCHITECTURE.md, override handover 2026-07-09): optional Telegram
alerting. Two modes:

  python scripts/13_alert.py             -- notify on each new live event
  python scripts/13_alert.py --failure "message"  -- notify on pipeline failure

Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID as environment variables
(GitHub Actions secrets, never committed). If either is missing, this prints
a note and exits 0 -- alerting is optional and its absence must never fail
the pipeline.
"""
import argparse
import os
import sys
from pathlib import Path

import pandas as pd
import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
NEW_EVENTS_CSV = ROOT / "data" / "live_events.csv"
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def send(token, chat_id, text):
    r = requests.post(
        TELEGRAM_API.format(token=token),
        json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
        timeout=30,
    )
    if r.status_code != 200:
        print(f"  Telegram API error {r.status_code}: {r.text[:200]}")
        return False
    return True


def format_event_message(row):
    direction = "positive" if row["direction"] > 0 else "negative"
    return (
        f"Obscura Intel: new event\n"
        f"{row['ticker']} — {row['event_date'].date()}\n"
        f"Tone: {direction} | Intensity: {row['intensity_percentile']:.0f}th pct\n"
        f"(NULL verdict on record — no forward-return implication)\n"
        f"https://vivektmurali.github.io/obscura-intel/tickers/{row['ticker']}.html"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--failure", metavar="MESSAGE", help="Send a pipeline-failure alert instead")
    args = parser.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram not configured (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing) -- skipping alert.")
        sys.exit(0)

    if args.failure:
        ok = send(token, chat_id, f"Obscura Intel: pipeline run FAILED\n{args.failure}")
        print("Sent failure alert." if ok else "Failed to send failure alert.")
        return

    if not NEW_EVENTS_CSV.exists():
        print("No live_events.csv yet -- nothing to alert on.")
        return

    new_events = pd.read_csv(NEW_EVENTS_CSV, parse_dates=["event_date"])
    if new_events.empty:
        print("No new events this run -- nothing to alert on.")
        return

    sent = 0
    for _, row in new_events.iterrows():
        if send(token, chat_id, format_event_message(row)):
            sent += 1
    print(f"Sent {sent}/{len(new_events)} event alerts.")


if __name__ == "__main__":
    main()
