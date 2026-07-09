# OBSCURA INTEL — SYSTEM ARCHITECTURE & SHIPPING ROADMAP (v1.0)

**Audience:** Vivek Murali + Claude Code.
**Relationship to HANDOVER.md:** This document is the master roadmap for the *full shipped system*. HANDOVER.md remains binding for (a) the statistical research design (§4), (b) standing execution rules (§8), (c) appendices (smoke test, pre-registration skeleton). Where phase numbering differs, the mapping table in §6.0 governs. HANDOVER.md's §5 ban list stays in force **until the validation gate (Phase 4) is passed**; after that, this document's phase gates govern what gets unbanned, and when.
**Date:** 2026-07-04.
**Codebase status at writing: still zero. Nothing in this file changes the next action, which is Phase 0.**

---

## 1. What "shipped" means (definition of done for v1.0)

v1.0 is shipped when every box is checked:

- [ ] Public URL (GitHub Pages) showing a **live event feed**, per-ticker pages, and a methodology page — updating daily with real data.
- [ ] Pipeline runs **fully unattended** on GitHub Actions cron: no laptop, no manual step. Proof: 14 consecutive unattended daily runs in the Actions log.
- [ ] Every number on the site is traceable to a cached raw API response (provenance rule, §3).
- [ ] Validation results published **whichever way they came out**, citing the pre-registration commit hash.
- [ ] Claims audit passed: no statement on the site exceeds what validation supports (§7).
- [ ] README is the flagship writeup; repo tagged `v1.0` and pinned on the GitHub profile.
- [ ] Sent to ≥3 real humans, at least one technical. Shipping includes an audience.

Not shipped: anything running in a notebook, behind a tunnel, on localhost, or requiring Vivek to remember to run it.

---

## 2. System overview

```
                 ┌────────────────────────────────────────────────┐
                 │           GitHub Actions (daily cron)          │
                 └────────────────────────────────────────────────┘
                        │                              │
              ┌─────────▼─────────┐          ┌─────────▼─────────┐
              │  GDELT DOC 2.0 API │          │  yfinance (.NS)   │
              │  vol / tone /      │          │  EOD prices       │
              │  artlist (events)  │          │  (fallback: NSE   │
              └─────────┬─────────┘          │   bhavcopy CSV)   │
                        │                     └─────────┬─────────┘
                        ▼                               ▼
              ┌──────────────────────────────────────────────────┐
              │        Data store: parquet in repo, raw JSON      │
              │        cached & compressed (provenance layer)     │
              └───────────────────────┬──────────────────────────┘
                                      ▼
              ┌──────────────────────────────────────────────────┐
              │   Event engine: z-score spike detection, tone,    │
              │   entity mapping  (recompute-over-append)         │
              └──────────┬───────────────────────────┬───────────┘
                         ▼                           ▼
        ┌────────────────────────────┐   ┌───────────────────────────┐
        │  VALIDATION CORE (batch,   │   │  LIVE PATH (daily):       │
        │  historical): event study, │   │  new events + scoring      │
        │  permutation null, FDR,    │   │  bounded by validation     │
        │  pre-registered verdict    │   │  verdict (§7)              │
        └──────────────┬─────────────┘   └─────────────┬─────────────┘
                       └──────────────┬────────────────┘
                                      ▼
              ┌──────────────────────────────────────────────────┐
              │  Static site build (daily) → GitHub Pages         │
              │  + Telegram alert on new event / pipeline failure │
              └──────────────────────────────────────────────────┘
```

### Design principles (binding)

1. **Zero-server.** Nothing must "stay up." Compute = GitHub Actions; storage = the repo; frontend = static files on Pages. Every previous Obscura incarnation died with its runtime; this one has no runtime to die.
2. **Real data only, everywhere.** No dummy, sample, placeholder, or synthetic data at any layer — including tests (§3).
3. **Validation-gated claims.** The system may detect and display events unconditionally; it may make forward-looking statements only to the extent the Phase 4 study supports them (§7).
4. **Recompute over append.** Ingestion is incremental (fetch only missing days); everything downstream (events, scores, site) is recomputed from the store each run. Idempotent by construction, self-healing after failures.
5. **Boring stack.** Flat scripts, parquet, cron. Complexity must buy its way in via `DECISIONS.md`.

---

## 3. Data reality and provenance

- **"Scraping millions of articles" is delegated to GDELT.** GDELT monitors global news at that scale and exposes aggregates (volume, tone) plus article lists. Obscura's edge is not re-crawling the web; it is entity mapping, event detection, and validation honesty on top of GDELT. Re-crawling is out of scope permanently (cost, legality, redundancy).
- **Provenance rule:** every API response is cached raw (compressed JSON) under `data/raw/` before any parsing. Every derived table carries source-file references. If a number on the site can't be traced to a raw file, it doesn't go on the site.
- **No-dummy-data rule extends to tests:** pytest fixtures are frozen slices of real cached responses (`tests/fixtures/`), never invented payloads. A test that needs data it doesn't have gets a real cached slice, or doesn't exist.
- **Zero-secret core:** GDELT and yfinance need no keys. Secrets enter only with optional Telegram/LLM (Actions secrets, never in repo).

---

## 4. Stack (final)

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.11+ | |
| Ingestion | `requests` (GDELT), `yfinance` | Fallback price source: NSE bhavcopy daily CSV (pre-agreed, Phase 8) |
| Data | `pandas`, `pyarrow` parquet, optional `duckdb` for queries | Parquet partitioned by month; raw JSON gzipped |
| Stats | `numpy`, `scipy`, `statsmodels` | Per HANDOVER.md §4 |
| Charts | `matplotlib` (PNG) or `plotly` static HTML | |
| Orchestration | GitHub Actions cron | Vivek has prior production experience with this pattern |
| Site | Static: Jinja2 → HTML **or** React static build reading committed JSON | Choice deferred to Phase 7; both are serverless |
| Hosting | GitHub Pages | |
| Alerts | Telegram bot (optional) | |
| LLM (optional, gated) | Claude API (Haiku-class, batched) or local Ollama | Phase 6 only; must earn its place (§10) |

Banned for v1.0: FastAPI/servers, ngrok, Docker, Neo4j/FAISS/vector stores, server databases, broker integration, intraday anything, user accounts, paid infra.

---

## 5. Repository layout (extends HANDOVER.md §6)

```
obscura-intel/
├── HANDOVER.md                 # binding annexes: research design, rules
├── ARCHITECTURE.md             # this file
├── README.md                   # becomes the flagship writeup
├── PREREGISTRATION.md          # locked end of Phase 3, pre-Phase-4
├── DECISIONS.md / PARKING.md
├── requirements.txt
├── .github/workflows/daily.yml # live pipeline (Phase 5)
├── scripts/
│   ├── 00_smoke_gdelt.py
│   ├── 01_universe.py          # build + audit universe
│   ├── 02_ingest_history.py    # bulk GDELT timelines + prices
│   ├── 03_events.py            # spike detection (historical + live reuse)
│   ├── 04_event_study.py       # CARs, market model
│   ├── 05_inference.py         # permutation null, FDR, verdict
│   ├── 06_scoring.py           # verdict-bounded live scoring
│   ├── 10_daily_ingest.py      # incremental fetch (live)
│   ├── 11_daily_events.py      # recompute events + scores (live)
│   ├── 12_build_site.py        # static site generation
│   └── 13_alert.py             # Telegram (optional)
├── site_src/                   # templates or React source
├── site/                       # built output → Pages
├── data/                       # parquet + small CSVs; raw/ cached
├── results/                    # validation outputs, figures
└── tests/                      # fixtures = frozen real responses
```

---

## 6. Phase roadmap

**Discipline (from HANDOVER.md §8, unchanged):** every phase ends run → inspected → committed → pushed. A phase without a pushed commit did not happen. Session size: 1–2 h.

### 6.0 Mapping to HANDOVER.md

| ARCHITECTURE phase | HANDOVER phase(s) | Scope |
|---|---|---|
| 0 | 0 | Repo + smoke test |
| 1 | 1 | Universe + coverage |
| 2 | 1 (data pull) + 3 | Historical ingestion: timelines + prices |
| 3 | 2 | Event engine + pre-registration lock |
| 4 | 4 + 5 + 6 | Validation core + verdict + report |
| 5–8 | — (new) | Live pipeline, scoring, surface, hardening |

HANDOVER.md §4 remains the authoritative statistical spec for Phases 1–4; steps below reference it rather than restate it.

---

### Phase 0 — Foundation (GATE) — ~1 session
**Objective:** a public repo with a passing real-data smoke test. The forcing function.
1. `git init`; create public GitHub repo `obscura-intel`; push.
2. Commit `HANDOVER.md`, `ARCHITECTURE.md`, generated `CLAUDE.md` (from HANDOVER §8), `.gitignore`, `requirements.txt`, 3-line README stub.
3. Write `scripts/00_smoke_gdelt.py` (HANDOVER Appendix A). **Run it.** Adapt parsing to the real JSON shapes; record shapes in `DECISIONS.md`.
4. Add a yfinance smoke line: fetch 10 days of `TATAMOTORS.NS`, print rows.
- **Gate:** smoke exits 0 with nonzero counts on artlist, timelinevolraw, timelinetone, and prices.
- **Commit:** `phase 0: smoke test passes (gdelt + yfinance)`.
- **Hard rule: no other code in the repo until this is pushed.**

### Phase 1 — Universe & entity layer — ~1–2 sessions
**Objective:** the 40-ticker universe with alias table and proven GDELT coverage.
1. `scripts/01_universe.py`: start from ~60 Nifty Midcap 100 / Smallcap 100 candidates; apply HANDOVER §4.1 filters (name distinctiveness, sector spread, price-history availability) → `data/universe.csv` (`ticker, yf_symbol, company_name, aliases, sector`).
2. Coverage audit: pull `timelinevolraw` per ticker for the study period (throttled ≥5s, cached raw) → `data/coverage_summary.csv`.
3. **Gate:** median ticker ≥30 nonzero-volume days/year. Fail → present table to Vivek, shift universe up-cap. (One of the three permitted interruptions.)
- **Commit:** `phase 1: universe + coverage audit`.

### Phase 2 — Historical ingestion — ~2 sessions
**Objective:** the complete historical data store, real data, integrity-checked.
1. `scripts/02_ingest_history.py`: for every ticker — GDELT `timelinevolraw` + `timelinetone` for 2023-01-01→2025-12-31; prices (universe + `^NSEI`) for 2022-07-01→2026-01-31 per HANDOVER §4.2. Cache raw; write monthly-partitioned parquet.
2. Integrity report → `data/integrity.csv`: per ticker — rows, date range, % missing, adjustment sanity. Drop broken tickers; log in `DECISIONS.md`; regenerate universe.
3. Idempotency check: rerun the script; it must fetch nothing new and change nothing.
- **Gate:** integrity report clean for ≥35 tickers; rerun is a no-op.
- **Commit:** `phase 2: historical store + integrity`.

### Phase 3 — Event engine + pre-registration lock — ~1–2 sessions
**Objective:** the events table, sanity-audited, and the analysis plan locked before results exist.
1. `scripts/03_events.py`: implement HANDOVER §4.4 spike detection (trailing-90d `vol_z`, thresholds, run-merging, `tone_z`) → `data/events.csv`. Write it to run identically on historical and future data (the live path reuses it).
2. Qualitative audit: `artlist` pulls for the 20 largest spikes → `data/event_samples.csv` (headlines + URLs). Inspect: do spikes correspond to real, correctly-attributed news? Drop poisoned tickers.
3. **Gate:** ≥150 events (one pre-registered fallback allowed, HANDOVER §4.4).
4. Write and commit `PREREGISTRATION.md` (HANDOVER Appendix B) **now** — before any event↔price join exists.
5. Unit tests (real fixtures): z-window math, run-merging, IST/UTC entry-date rule edge cases (HANDOVER §4.5).
- **Commit:** `phase 3: event engine + preregistration locked`.

### Phase 4 — VALIDATION CORE (THE GATE) — ~2–3 sessions
**Objective:** the pre-registered verdict.
1. `scripts/04_event_study.py`: entry rule, market model, CARs at t+1/t+5/t+20 per HANDOVER §4.5–4.6 → `results/car_by_event.csv`. In-script asserts: entry strictly after event date; estimation window placement; no unexplained NaNs.
2. `scripts/05_inference.py`: 1,000-draw seeded permutation null, primary test, secondaries with BH-FDR, the three pre-registered robustness variants only → `results/stats.json`, null-vs-real figures.
3. Record the verdict in `DECISIONS.md`: **SIGNAL** (primary passes, or secondaries survive FDR per prereg) or **NULL**.
4. Interim report: README gains a Results section stating the verdict plainly, citing the prereg hash.
- **Gate:** verdict recorded. **No respecification.** Exploratory extras go in a labeled section only.
- **Commit:** `phase 4: validation verdict — {SIGNAL|NULL}`.
- Everything after this phase is identical in structure for both verdicts; only §7's claim rules differ.

### Phase 5 — Live pipeline — ~2 sessions
**Objective:** the system runs itself daily, unattended.
1. `scripts/10_daily_ingest.py`: fetch only missing days — the **previous complete UTC day** of GDELT volume/tone per ticker, plus latest EOD prices. Append to parquet store; cache raw.
2. `scripts/11_daily_events.py`: recompute the events table over the full store (recompute-over-append); emit any new events → `data/live_events.csv`.
3. `.github/workflows/daily.yml` (skeleton below): cron `15 1 * * *` UTC (06:45 IST, pre-open; prior UTC day complete, prior close settled), plus `workflow_dispatch` for manual runs. Job: checkout → install → ingest → events → build site (Phase 7 adds it) → commit `data/` back with a bot identity → push.
4. Tolerances: GDELT/yfinance failure → fail loudly, skip day, next run self-heals via recompute; Actions cron delay is expected and harmless.

```yaml
name: daily-pipeline
on:
  schedule: [{ cron: "15 1 * * *" }]
  workflow_dispatch: {}
permissions: { contents: write }
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt
      - run: python scripts/10_daily_ingest.py
      - run: python scripts/11_daily_events.py
      - run: python scripts/12_build_site.py || true   # until Phase 7
      - run: |
          git config user.name obscura-bot
          git config user.email obscura-bot@users.noreply.github.com
          git add data/ site/ && git commit -m "data: $(date -u +%F)" || echo "no changes"
          git push
```

- **Gate:** 3 consecutive unattended green runs with real appended data.
- **Commit:** `phase 5: live pipeline unattended`.

### Phase 6 — Scoring layer (verdict-bounded) — ~1–2 sessions
**Objective:** what the system says about each new live event — no more than validation earned.
1. `scripts/06_scoring.py`, branch on the Phase 4 verdict:
   - **SIGNAL:** for a new event in tone-bucket *b*, report the *historical* CAR(t+5) distribution for bucket *b*: median, IQR, sign hit-rate, n. Always with uncertainty. Language: "historical association," never "will move," never advice.
   - **NULL:** intensity score = `vol_z` percentile; novelty = days since ticker's last event. **No forward-return numbers anywhere.**
2. Wire scoring into `11_daily_events.py` output.
3. Optional LLM enrichment: only per §10, and only after its earn-its-place test passes.
- **Gate:** claims audit — every emitted field is defensible from `results/stats.json`.
- **Commit:** `phase 6: scoring ({SIGNAL|NULL} mode)`.

### Phase 7 — Ship the surface — ~2–3 sessions
**Objective:** the public URL.
1. Choose implementation (log in `DECISIONS.md`):
   - **A. Jinja2 → static HTML.** Fastest to ship.
   - **B. React static build** consuming `data/site/*.json` emitted by the pipeline. More work; CV-shinier. Still serverless.
2. Pages: **Live feed** (recent events: ticker, date, headlines from cached artlist, score per §7); **Ticker pages** (price chart with event overlays, event history); **Methodology** (design summary, prereg hash, validation results either way, limitations verbatim from README); **About**.
3. `scripts/12_build_site.py` → `site/`; deploy via GitHub Pages (Actions deploy step or `gh-pages` branch). Add build to `daily.yml`.
4. Optional: `scripts/13_alert.py` — Telegram message on each new event (token in Actions secrets).
- **Gate:** public URL renders real data; updates on the next scheduled run without intervention.
- **Commit:** `phase 7: site live`.

### Phase 8 — Hardening & release — ~1–2 sessions
**Objective:** v1.0.
1. Failure alerting: pipeline failure → Telegram/email (Actions failure notification or a final always-run step).
2. Freshness guard: site header shows last-updated; build fails visibly if store is >3 days stale.
3. Data growth policy: monthly partition compaction; if repo >500 MB, move parquet to a data branch (log decision).
4. Price-source fallback: implement NSE bhavcopy ingestion behind a flag; document switch procedure.
5. Backfill tool: `10_daily_ingest.py --backfill YYYY-MM-DD` for gap repair.
6. README → flagship writeup: thesis, architecture diagram, validation verdict + prereg hash, case studies with headline links, limitations (survivorship, name-string entity matching, clustering, single market, GDELT coverage bias), roadmap.
7. **Gate = the §1 checklist, every box.** Then `git tag v1.0`, pin repo, send to ≥3 humans.
- **Commit:** `release: v1.0`.

---

## 7. Claims policy (binding on scoring, site copy, README, and any post about the project)

| | SIGNAL verdict | NULL verdict |
|---|---|---|
| Event detection | Display freely | Display freely |
| Direction/tone | Show tone + historical bucket stats with n and uncertainty | Show tone as description only |
| Forward returns | Historical distributions only; "historical association" phrasing | Not shown, not implied |
| Product framing | "Event-driven market intelligence with validated historical signal" | "Event-intelligence feed; predictive value tested and not found (see methodology)" |
| Never, either way | Trade advice, "will," "predicts," strategy-return marketing, certainty language | Same |

A NULL verdict does not reduce the project's value for its actual purpose (UK data/statistics roles): the pipeline engineering, the pre-registration discipline, and the honest write-up **are** the product.

---

## 8. LLM enrichment policy (optional module)

- Scope: classify event-day headlines (≤ ~50 articles/day) into a fixed taxonomy — earnings, order win, regulatory, accident, M&A, management change — and an LLM direction score.
- **Earn-its-place test (historical, before any live use):** LLM direction vs `tone_z` direction on CAR(t+5) sign across all historical events; enable live only if the bootstrap CI of the accuracy difference excludes zero.
- Cost: Haiku-class batched or local Ollama; hard cap £5/month; kill switch = one flag.
- If it doesn't beat the baseline, the result is documented and the module stays off. That sentence goes in the README either way — it demonstrates exactly the evaluation discipline the target employers hire for.

---

## 9. Risks (extends HANDOVER.md §9)

| Risk | Response |
|---|---|
| GDELT coverage sparse for small caps | Phase 1 gate → up-cap shift; sparse coverage is itself a documented finding |
| yfinance breaks/throttles | Pin version; caching; Phase 8 bhavcopy fallback |
| Actions cron delayed/skipped | Tolerated by design; recompute self-heals; manual `workflow_dispatch` |
| Repo data growth | Monthly compaction; data branch at 500 MB |
| Timezone/entry-rule bugs | Single tested implementation of HANDOVER §4.5 shared by historical + live paths |
| Cross-sectional event clustering | Disclosed + pre-registered robustness drop; calendar-time methods parked |
| Scope creep back to "platform v0" | §4 ban list; `PARKING.md`; "override handover" phrase required |
| Verdict-disappointment abandonment | §7 pre-commits the NULL branch as a full ship, not a failure |

---

## 10. Timeline vs the late-October deadline

| Weeks (2026) | Phases | Milestone |
|---|---|---|
| Jul 6 – Jul 12 | 0–1 | Repo live, universe locked |
| Jul 13 – Jul 26 | 2–3 | Historical store + events + prereg locked |
| Jul 27 – Aug 9 | 4 | **Validation verdict** |
| Aug 10 – Aug 23 | 5–6 | Unattended daily pipeline + scoring |
| Aug 24 – Sep 13 | 7 | Public site live |
| Sep 14 – Sep 18 | 8 | Hardening, v1.0 tag — **feature freeze Sep 18** |
| Sep 19 – Oct | — | Job applications *using* the artifact; no building |

Slack is deliberate: two jobs, 1–2 h sessions. If a phase slips a week, cut from Phase 7 option B (use Jinja2) and Phase 8 extras — never from Phase 4 rigor.

---

## 11. Non-goals for v1.0 (parked, not forgotten → PARKING.md)

Broker/trading execution; intraday latency; additional markets; user accounts; server databases; Docker/K8s; paid infrastructure; Gemma fine-tuning; full calendar-time portfolio statistics; mobile app; any claim of strategy returns.

---

*The next action is unchanged by this document: Phase 0. A repo URL with the smoke-test commit is the only evidence that this architecture has begun to exist.*
