"""Phase 0 smoke test: verify GDELT DOC 2.0 API access and response shapes.
Adapt parsing if actual JSON differs -- the gate is real, nonzero data,
printed honestly. Exit 0 only on full pass."""
import sys, time
import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://api.gdeltproject.org/api/v2/doc/doc"
Q = '"Tata Motors" sourcecountry:IN'

def call(**params):
    max_attempts = 6
    for attempt in range(max_attempts):
        r = requests.get(BASE, params=params, timeout=30)
        if r.status_code == 429:
            wait = 30 * (attempt + 1)
            print(f"  429 rate limited, backing off {wait}s (attempt {attempt + 1}/{max_attempts})")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("GDELT API: exhausted retries on 429")

art = call(query=Q, mode="artlist", maxrecords=10, format="json")
articles = art.get("articles", [])
print(f"artlist: {len(articles)} articles")
for a in articles[:3]:
    print("  ", a.get("seendate"), "|", (a.get("title") or "")[:80])

time.sleep(20)
vol = call(query=Q, mode="timelinevolraw", format="json",
           startdatetime="20250101000000", enddatetime="20250301000000")
vol_pts = (vol.get("timeline") or [{}])[0].get("data", [])
print(f"timelinevolraw: {len(vol_pts)} daily points")

time.sleep(20)
tone = call(query=Q, mode="timelinetone", format="json",
            startdatetime="20250101000000", enddatetime="20250301000000")
tone_pts = (tone.get("timeline") or [{}])[0].get("data", [])
print(f"timelinetone: {len(tone_pts)} daily points")

ok = bool(articles) and bool(vol_pts) and bool(tone_pts)
print("SMOKE TEST:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
