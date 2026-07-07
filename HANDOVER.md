# OBSCURA INTEL — v0.1 HANDOVER

**Audience:** Claude Code, operating with full repo + execution access.
**Owner:** Vivek Murali (Newcastle upon Tyne, UK).
**Date:** 2026-07-04.
**Status of codebase at handover: ZERO. No repo, no commits, no runnable code exists. Everything before this document was chat-generated and never executed. Treat all prior "Obscura code" as if it does not exist.**

---

## 0. How to use this file

1. Vivek creates an empty directory, drops this file in it, opens Claude Code, and says: *"Read HANDOVER.md. Execute Phase 0."*
2. You (Claude Code) work strictly phase-by-phase. Each phase ends with code **executed**, output **inspected**, and a **commit pushed**. No phase is entered until the previous phase's acceptance check passes.
3. In Phase 0 you generate `CLAUDE.md` from §8 of this document so the standing rules persist across your sessions.

---

## 1. Mission

Build **v0.1 of Obscura Intel: a rigorous event study**, not a predictor.

Question under test: **do news-volume spike events in NSE mid/small-cap names carry abnormal forward returns, in the direction of news tone, after the event is publicly observable?**

The deliverable is a public GitHub repo that answers this question honestly — **a well-executed null result is a full success**. The repo is portfolio evidence for UK data/statistics roles (ONS Statistical Methodologist, DBT Python Developer). The audience cares about method quality: pre-registration, null controls, multiple-testing correction, honest limitations. They do not care about Sharpe ratios.

What v0.1 is **not**: a trading system, a live signal feed, a dashboard, an LLM pipeline, or a product. See the ban list in §5.

---

## 2. Context you need about the owner and the project

- **History:** ~9 months of chat sessions produced elaborate Obscura architecture (GDELT ingestion, NLP scoring, Claude API cascade, React dashboard, backtest engine, adversarial pressure-test prompts). None of it was ever run or committed. The failure mode is **code generation substituting for execution**. Your job is to be the antidote: small steps, everything run, everything committed.
- **A previous chat-generated pipeline included a synthetic-data fallback that silently activated when GDELT was unreachable.** This produced fake green checkmarks and false confidence. Synthetic fallbacks are permanently banned (§8).
- **Deadline pressure:** Vivek has a UK work-authorisation deadline in late October 2026. v0.1 must tag by ~20 July 2026. He works two jobs (night shifts + retail mornings); assume sessions are 1–2 hours. Phases are sized accordingly.
- **Communication style:** terse, direct, technical. No cheerleading, no hedging. When you must ask him something, ask one precise question with a default.

---

## 3. The thesis, corrected

The original framing — "every stock move has an event behind it" — is retrodictive and untestable (post-hoc narrative matching is free and worthless; a large share of major price moves have no identifiable news driver at all). The only falsifiable, forward-running claim is:

> **Given an observable news event now, the stock exhibits abnormal returns afterwards, with direction predicted by tone.**

Why NSE mid/small caps: obvious news on large liquid names is priced in milliseconds by HFT and vendor NLP; GDELT updates in 15-minute batches with lag, so any residual edge must live where information diffuses slowly — low-attention, less-covered names. That hypothesis is what v0.1 tests. If the effect doesn't exist there, it doesn't exist anywhere reachable by this pipeline, and the README says so.

---

## 4. Research design (fixed — changes require Vivek's explicit override)

### 4.1 Universe
- **~40 tickers** drawn from current Nifty Midcap 100 + Nifty Smallcap 100 constituents.
- Selection filters (you apply, document in `DECISIONS.md`):
  1. Company name is **distinctive as an English search string** (reject ambiguous names — e.g. one-word generic terms, common surnames — because event mapping is name-string matching).
  2. Spread across ≥6 sectors.
  3. Yahoo Finance `.NS` ticker has usable daily history for the full study period.
- Output: `data/universe.csv` with columns `ticker, yf_symbol, company_name, aliases (pipe-separated), sector`.
- **Known limitation (must appear in README):** using *current* constituents introduces survivorship bias. Acceptable for v0.1, disclosed, not fixed.

### 4.2 Study period
- Events: **2023-01-01 → 2025-12-31** (3 years).
- Prices: fetch **2022-07-01 → 2026-01-31** (extra tail for estimation windows and t+20 horizons).

### 4.3 Event data — GDELT DOC 2.0 API
- Base: `https://api.gdeltproject.org/api/v2/doc/doc`. Free, no key.
- Per ticker, per query = `"<company name>" sourcecountry:IN` (plus aliases OR'd where needed):
  - `mode=timelinevolraw` → daily raw article counts.
  - `mode=timelinetone` → daily average tone.
  - `mode=artlist&maxrecords=250` → only for sampled event days (qualitative inspection), not bulk.
- Chunk long date ranges if the API requires it; `startdatetime`/`enddatetime` format `YYYYMMDDHHMMSS`. **Sleep ≥5s between calls.** Cache every raw response to `data/raw/` (gitignored) so no query is ever re-run.
- Exact parameter names and JSON shapes must be **verified empirically in the Phase 0 smoke test** — adapt parsing to what the API actually returns, and record the verified shapes in `DECISIONS.md`. Never guess silently.

### 4.4 Event definition (spike detection)
For each ticker's daily volume series `v_t`:
- `vol_z(t) = (v_t − mean_90(t)) / std_90(t)` using a trailing 90-day window (exclude day t).
- **Event day:** `vol_z ≥ 3` AND `v_t ≥ 5` articles.
- Merge runs of consecutive event days: keep the first day only.
- `tone_z(t)` computed identically from the tone series. Event direction proxy: `sign(tone_z)` on the event day.
- **Pre-registered fallback (may be used at most once, only if total events < 150):** loosen to `vol_z ≥ 2` AND `v_t ≥ 3`. Record use in `PREREGISTRATION.md` addendum.

### 4.5 Timestamp / lookahead rule (the single most important rule in this document)
GDELT timelines are UTC calendar days; NSE closes 15:30 IST (10:00 UTC), so an article-day partially post-dates the close.
- **Entry point = close of the first NSE trading day strictly after the event's UTC date.**
- All forward returns are measured from that entry close. Nothing from the event day itself is ever used as a tradeable price. No exceptions, no "open of event day," ever.

### 4.6 Abnormal returns
- Daily log returns, adjusted prices (`yfinance`, `auto_adjust=True`).
- Benchmark: **^NSEI (Nifty 50)** — chosen for reliable availability; beta mismatch vs mid/small caps is a disclosed limitation.
- **Market model:** OLS of stock return on benchmark over a 120-trading-day estimation window ending 21 trading days before entry. Require ≥90 valid observations; otherwise fall back to market-adjusted (β=1), flag the event.
- `AR_t = r_stock,t − (α + β·r_mkt,t)`; `CAR(h) = Σ AR` over `h` trading days after entry.
- Horizons: **t+1, t+5, t+20**.

### 4.7 Inference — null control and multiple testing
- **Permutation null:** for each ticker with K real events, draw K pseudo-event days uniformly from that ticker's trading days in the study period, excluding ±5 trading days around any real event. Recompute the full CAR pipeline. **1,000 permutations** → null distribution of each test statistic.
- **Primary test (THE test, one number):**
  `H1: mean over all events of sign(tone_z) × CAR(t+5) > 0`, one-sided permutation p < 0.05.
- **Secondary tests** (Benjamini–Hochberg FDR, q = 0.10, labeled secondary):
  1. Tone-signed mean CAR at t+1 and t+20.
  2. Mean |CAR| at each horizon vs null (reaction regardless of direction).
  3. Top-vs-bottom tone-tercile spread in CAR(t+5).
- **Clustering caveat:** cross-sectional event clustering (market-wide news days) inflates significance. v0.1 mitigation: (a) disclose it, (b) robustness pass dropping calendar days on which >3 universe tickers have simultaneous events. Full calendar-time portfolio methods are parked for v0.2.
- **Sample-size gate:** ≥150 events required for the primary test to count as confirmatory. Below that (after the one fallback), report as underpowered/exploratory.

### 4.8 Kill criteria (pre-registered, binding)
- If the primary test fails (p ≥ 0.05) **and** no secondary survives FDR → verdict: **"no detectable edge under this specification."** README states it plainly. v0.1 still ships and tags.
- **No respecification after results are seen.** One pre-registered robustness pass only: (a) fallback spike threshold, (b) market-adjusted instead of market-model, (c) the clustering-drop above. Anything else is labeled exploratory in a separate README section.
- `PREREGISTRATION.md` (skeleton in §11) must be **committed at the end of Phase 2 — before any price data is joined to event data**. Its commit hash is cited in the README.

---

## 5. Hard scope

**Banned in v0.1 (do not build, do not scaffold, do not "just stub out"):**
live prediction/alerting; Claude API or any LLM calls in the pipeline; Gemma fine-tuning; React or any web dashboard; FastAPI/servers/ngrok; Lightpanda or any scraping beyond the GDELT API; Neo4j/FAISS/vector stores; databases (SQLite acceptable only if genuinely needed — flat files preferred); Docker; CI beyond a trivial lint; broker/trading integration; **any synthetic or simulated data fallback**.

If Vivek asks for a banned item mid-project, respond: *"Banned by HANDOVER.md §5. Say 'override handover' to proceed."* Log any override in `DECISIONS.md`.

**Allowed stack (complete):** Python 3.11+, `requests`, `pandas`, `numpy`, `scipy`, `statsmodels`, `yfinance`, `matplotlib`, `pyarrow`. CLI scripts + CSV/parquet + PNG figures. Nothing else without a `DECISIONS.md` entry.

---

## 6. Repository layout

```
obscura-intel/
├── HANDOVER.md            # this file, committed verbatim in Phase 0
├── CLAUDE.md              # generated from §8 in Phase 0
├── README.md              # stub in Phase 0; full report in Phase 6
├── PREREGISTRATION.md     # committed end of Phase 2, before Phase 4
├── DECISIONS.md           # running log of autonomous decisions
├── PARKING.md             # every out-of-scope idea goes here, one line each
├── requirements.txt
├── .gitignore             # data/raw/, *.parquet, __pycache__/, .venv/
├── scripts/
│   ├── 00_smoke_gdelt.py
│   ├── 01_coverage.py
│   ├── 02_events.py
│   ├── 03_prices.py
│   ├── 04_event_study.py
│   ├── 05_inference.py
│   └── 06_figures.py
├── data/                  # small committed CSVs; raw/ gitignored
└── results/               # car_by_event.csv, stats.json, figures/
```

---

## 7. Phase plan

Every phase ends: **run → inspect output → commit → push.** A phase without a pushed commit did not happen.

### Phase 0 — Repo + smoke test (GATE; ~30 min)
1. `git init`; create **public** GitHub repo `obscura-intel`; add remote.
2. Commit `HANDOVER.md`, generated `CLAUDE.md` (§8), `.gitignore`, `requirements.txt`, README stub (3 lines: what this is, status line "Phase 0", owner).
3. Write `scripts/00_smoke_gdelt.py` (template §10). **Run it.** It must hit `artlist`, `timelinevolraw`, and `timelinetone` for one ticker and print real counts. If JSON shapes differ from the template's assumptions, adapt the parsing and note the true shapes in `DECISIONS.md`.
4. Acceptance: script exits 0 with nonzero counts on all three modes. Commit `phase 0: gdelt smoke test passes`, push.
- **Hard rule: no other code exists in the repo until this commit is pushed.** This gate is the project's forcing function; it is not optional.

### Phase 1 — Universe + coverage (1 session)
1. Build `data/universe.csv` (§4.1). Start from ~60 candidates, apply filters, land on ~40.
2. `scripts/01_coverage.py`: pull `timelinevolraw` for every ticker over the study period (cached, throttled). Write `data/coverage_summary.csv`: per ticker — total articles, nonzero days/year, max daily count.
3. **Acceptance gate:** median ticker has ≥30 nonzero-volume days/year. If failed → stop, show Vivek the table, propose shifting universe up-cap (e.g., Nifty 100 names). This is one of the three questions worth interrupting him for.
4. Commit `phase 1: universe + coverage`, push.

### Phase 2 — Event extraction (1 session)
1. `scripts/02_events.py`: pull tone timelines, compute `vol_z`/`tone_z`, apply §4.4 → `data/events.csv` (`ticker, event_date, v, vol_z, tone, tone_z, direction`).
2. Sample `artlist` for the 20 largest spikes → `data/event_samples.csv` (date, ticker, top headlines + URLs) for qualitative sanity: do the spikes correspond to real identifiable news?
3. Gate: ≥150 events (one fallback allowed, §4.4). Report the count.
4. Write and commit `PREREGISTRATION.md` (§11) **now**. Commit `phase 2: events + preregistration`, push.

### Phase 3 — Prices (1 session)
1. `scripts/03_prices.py`: `yfinance` daily adjusted OHLCV for universe + `^NSEI` over §4.2 range → `data/prices.parquet` (gitignored) + committed `data/price_integrity.csv` (per ticker: rows, first/last date, % missing, split/adjustment sanity checks).
2. Any ticker with broken data: drop it, log in `DECISIONS.md`, regenerate universe file.
3. Commit `phase 3: prices + integrity`, push.

### Phase 4 — Event study (1 session)
1. `scripts/04_event_study.py`: implement §4.5–4.6 exactly. Output `results/car_by_event.csv` (event id, ticker, entry date, β source, AR series, CAR at each horizon).
2. Unit-style asserts inside the script: entry date strictly after event date; estimation window ends 21 trading days before entry; no NaN CARs unaccounted.
3. Commit `phase 4: event study`, push. **Do not peek at aggregate results yet beyond mechanical validation** (the prereg is already locked, but discipline matters).

### Phase 5 — Inference (1 session)
1. `scripts/05_inference.py`: permutation null (1,000 draws, seeded), primary + secondaries, BH-FDR → `results/stats.json` + printed verdict block.
2. Robustness pass (the three pre-registered variants only).
3. Commit `phase 5: inference — verdict {SIGNAL|NULL}`, push.

### Phase 6 — Report + tag (1 session)
1. `scripts/06_figures.py`: null-vs-real distribution plots, CAR-by-horizon chart, tone-tercile chart → `results/figures/*.png`.
2. Rewrite `README.md` as the report: thesis → design → prereg hash → results (either way) → 2–3 case-study events with headline links → limitations (survivorship, name-string entity matching, clustering, single market, GDELT coverage bias) → what v0.2 would test.
3. Commit, push, `git tag v0.1`. Done.

---

## 8. Standing rules → write these into `CLAUDE.md` in Phase 0

1. **Execute everything.** Never write a script and move on without running it in this session. Never mark anything done that hasn't run.
2. **Commit + push every phase, minimum.** Conventional messages (`phase N: ...`). A session that ends without a push must end with an explicit warning to Vivek.
3. **No synthetic data, ever.** If an API fails, fail loudly, cache what you have, and stop. Fabricated/simulated fallback data is the project's historical failure mode and is banned.
4. **Scope police.** §5 ban list is binding. Out-of-scope ideas (Vivek's or yours) get one line in `PARKING.md`, nothing more. If Vivek insists: require the phrase "override handover."
5. **Decide autonomously, log it.** Implementation details (parsing, chunk sizes, plotting) are yours — record non-obvious choices in `DECISIONS.md`. Interrupt Vivek only for: (a) universe change after a failed coverage gate, (b) any change to §4.7–4.8 kill criteria, (c) scope overrides. Everything else: pick a sensible default and log it.
6. **Prefer boring.** Flat scripts over abstractions. No classes where a function does. No config frameworks. This is a study, not a platform.
7. **Honesty over momentum.** If results are null, the README says null. If data quality undermines the test, the README says that. Never soften a finding to make the project look better.
8. **Tone with Vivek:** terse, direct, technical. One question at a time, always with a proposed default.

---

## 9. Known risks and pre-agreed responses

| Risk | Likelihood | Pre-agreed response |
|---|---|---|
| GDELT coverage of Indian mid/small caps too sparse | High | Phase 1 gate → escalate with data, shift universe up-cap. Sparse coverage is itself a documented finding. |
| Ambiguous company names poison event mapping | Medium | Name-distinctiveness filter in §4.1; spot-check via Phase 2 `event_samples.csv`; drop poisoned tickers, log it. |
| `yfinance` throttling / bad `.NS` data | Medium | Cache aggressively, retry with backoff, drop broken tickers via Phase 3 integrity report. |
| Too few events (<150) | Medium | One pre-registered threshold fallback; else report underpowered — still ship. |
| Event clustering inflates significance | Certain (partially) | Disclose; run the >3-simultaneous-tickers drop; park calendar-time methods for v0.2. |
| GDELT API shape/limits differ from assumptions | Medium | Phase 0 smoke test verifies empirically; adapt and record in `DECISIONS.md`. |
| Scope creep back toward "the platform" | High | §5 + `PARKING.md` + override phrase. |

---

## 10. Appendix A — `scripts/00_smoke_gdelt.py` template

```python
"""Phase 0 smoke test: verify GDELT DOC 2.0 API access and response shapes.
Adapt parsing if actual JSON differs — the gate is real, nonzero data,
printed honestly. Exit 0 only on full pass."""
import sys, time
import requests

BASE = "https://api.gdeltproject.org/api/v2/doc/doc"
Q = '"Tata Motors" sourcecountry:IN'

def call(**params):
    r = requests.get(BASE, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

art = call(query=Q, mode="artlist", maxrecords=10, format="json")
articles = art.get("articles", [])
print(f"artlist: {len(articles)} articles")
for a in articles[:3]:
    print("  ", a.get("seendate"), "|", (a.get("title") or "")[:80])

time.sleep(5)
vol = call(query=Q, mode="timelinevolraw", format="json",
           startdatetime="20250101000000", enddatetime="20250301000000")
vol_pts = (vol.get("timeline") or [{}])[0].get("data", [])
print(f"timelinevolraw: {len(vol_pts)} daily points")

time.sleep(5)
tone = call(query=Q, mode="timelinetone", format="json",
            startdatetime="20250101000000", enddatetime="20250301000000")
tone_pts = (tone.get("timeline") or [{}])[0].get("data", [])
print(f"timelinetone: {len(tone_pts)} daily points")

ok = bool(articles) and bool(vol_pts) and bool(tone_pts)
print("SMOKE TEST:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
```

## 11. Appendix B — `PREREGISTRATION.md` skeleton

```markdown
# Pre-registration — Obscura Intel v0.1 event study
Committed before any join of event data to price data. Hash cited in README.

## Universe
[paste final ticker list + selection rules]

## Event definition
vol_z ≥ 3 AND v ≥ 5 (trailing-90d z-scores); consecutive days merged to first.
Fallback (usable once, only if events < 150): vol_z ≥ 2 AND v ≥ 3. Used: [YES/NO]

## Entry rule
Close of first NSE trading day strictly after event UTC date. No event-day prices used.

## Returns
Market model vs ^NSEI, 120d estimation ending t−21; fallback β=1 if <90 obs.
Horizons: CAR(t+1), CAR(t+5), CAR(t+20).

## Primary hypothesis (confirmatory)
mean[ sign(tone_z) × CAR(t+5) ] > 0; one-sided permutation p < 0.05; 1,000 permutations.

## Secondary hypotheses (BH-FDR q=0.10)
1. Tone-signed CAR at t+1, t+20
2. |CAR| at all horizons vs null
3. Top-minus-bottom tone-tercile CAR(t+5)

## Robustness (pre-registered, exhaustive list)
(a) fallback spike threshold (b) market-adjusted returns (c) drop days with >3 simultaneous ticker events

## Kill criterion
Primary fails AND no secondary survives FDR → report "no detectable edge under
this specification." No respecification. Exploratory analyses labeled as such.

## Sample-size gate
≥150 events for confirmatory status; below → exploratory/underpowered.
```

## 12. Parking lot seed (`PARKING.md`)

Everything from the old architecture goes here, untouched until v0.1 tags: LLM analysis cascade, Gemma fine-tune, React dashboard, Lightpanda scraping, GKG themes/entity linking, additional markets, calendar-time portfolio methods, live alerting, FastAPI service.

---

*End of handover. Phase 0 is the only next action.*
