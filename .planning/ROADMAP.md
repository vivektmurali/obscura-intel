# Roadmap: Obscura Intel

## Overview

This roadmap is reconstructed retrospectively (2026-07-16), not written from scratch — the project
is deep into execution. v0.1 (Phases 1-7 below) is the locked, tagged event study: verdict NULL,
shipped honestly per the pre-registered kill criterion. v1.0 (Phases 8-11) is a live daily pipeline
+ public site, built entirely under three separately-logged "override handover" authorizations
(2026-07-09) that individually lifted specific HANDOVER.md §5 bans (cron/CI, public site, alerts) —
each phase built, tested on real GitHub Actions infrastructure, and hardened through two real
post-Phase-8 production bugs (found, root-caused, fixed, regression-tested — no synthetic data used
anywhere). Only Phase 12 remains: accumulating the 14-consecutive-unattended-cron-run streak that
gates the `v1.0` tag, and outreach to real humans (decoupled from that streak per a 2026-07-16
decision, so it can proceed in parallel).

## Phases

**Phase Numbering:**
- Integer phases (1-11): completed, in execution order (v0.1 study, then v1.0 override phases)
- Phase 12: outstanding — ship gate (cron streak) + outreach, no further build work required

- [x] **Phase 1: Foundation & Smoke Test** - Repo scaffolding + GDELT API smoke test verifies JSON shapes and real rate-limit behavior
- [x] **Phase 2: Universe Construction & Coverage Gate** - 38-ticker NSE universe built and coverage-gated
- [x] **Phase 3: Event Extraction & Pre-Registration Lock** - 242 events detected, PREREGISTRATION.md locked before any price join
- [x] **Phase 4: Price Data & Integrity** - Adjusted prices + benchmark ingested, integrity-checked, zero drops
- [x] **Phase 5: Event Study (Abnormal Returns)** - CARs computed via market model at t+1/t+5/t+20
- [x] **Phase 6: Permutation Inference & Verdict** - Permutation-null test + BH-FDR secondaries + robustness pass; verdict recorded (NULL)
- [x] **Phase 7: Report, Figures & v0.1 Tag** - Figures, README verdict statement, `v0.1` tagged and shipped
- [x] **Phase 8: Live Daily Pipeline (override)** - Unattended daily GDELT+yfinance ingestion, idempotent and self-healing
- [x] **Phase 9: NULL-Mode Scoring Layer (override)** - Verdict-bounded scoring, hard-gated against ever showing forward returns
- [x] **Phase 10: Public Site (override)** - Static Jinja2 GitHub Pages site: live feed, per-ticker pages, methodology page
- [x] **Phase 11: Hardening, Testing & Production Fixes (override)** - Freshness guard, alerting, real-infra verification, two production bugs fixed + regression-tested, first test suite, retroactive power analysis
- [ ] **Phase 12: v1.0 Ship Gate** - 14 consecutive unattended cron runs (currently 4/14) + outreach to ≥3 real humans (decoupled, unblocked now)

## Phase Details

### Phase 1: Foundation & Smoke Test
**Goal**: Repo exists and GDELT's real API behavior (JSON shapes, rate limits, encoding quirks) is verified empirically before any bulk pull is built against assumptions
**Depends on**: Nothing (first phase)
**Requirements**: SETUP-01
**Success Criteria** (what must be TRUE):
  1. A smoke-test script successfully calls all three GDELT endpoints (`artlist`, `timelinevolraw`, `timelinetone`) and confirms the JSON shapes match the handover template
  2. Real rate-limit behavior (429s) is observed and handled (20s sleep + backoff), not just assumed from documentation
  3. Non-English/mixed-script GDELT output (e.g. Hindi headlines) prints without crashing the console
**Plans**: Complete (implemented pre-GSD; `scripts/00_smoke_gdelt.py`, see DECISIONS.md Phase 0)

### Phase 2: Universe Construction & Coverage Gate
**Goal**: A defensible, sector-diverse ticker universe exists with confirmed GDELT news coverage
**Depends on**: Phase 1
**Requirements**: STUDY-01
**Success Criteria** (what must be TRUE):
  1. `data/universe.csv` lists 38 NSE tickers spanning ≥6 sectors, each with usable Yahoo Finance history back to 2022-07-01
  2. Every universe ticker has a documented, non-fabricated reason for inclusion or exclusion (IPO recency, ticker discontinuity, name ambiguity, fetch failure)
  3. The coverage gate (median nonzero-volume days/year ≥ 30) passes and is recorded in `data/coverage_summary.csv`
**Plans**: Complete (implemented pre-GSD; `scripts/01_coverage.py`, see DECISIONS.md Phase 1)

### Phase 3: Event Extraction & Pre-Registration Lock
**Goal**: News-volume-spike events are detected under a pre-registered, unpeeked-at definition, and the methodology is locked before any price data is joined
**Depends on**: Phase 2
**Requirements**: STUDY-02
**Success Criteria** (what must be TRUE):
  1. Every one of the 38 universe tickers shows complete (non-SKIP) 2023-2025 volume and tone coverage before any event count is treated as final
  2. `data/events.csv` contains 242 events across 28 tickers under the primary threshold (`vol_z≥3`, `v≥5`), clearing the ≥150-event confirmatory gate
  3. `PREREGISTRATION.md` is committed, describing the final universe, event definition, and test plan, before `03_prices.py` ever runs
  4. A qualitative spot-check of the 20 largest spikes confirms the large majority are genuine, identifiable, company-specific news events
**Plans**: Complete (implemented pre-GSD; `scripts/02_events.py`, `PREREGISTRATION.md`, see DECISIONS.md Phase 2)

### Phase 4: Price Data & Integrity
**Goal**: Clean, adjusted daily price data exists for every universe ticker and the benchmark, with no fabricated substitutes for any gap
**Depends on**: Phase 3
**Requirements**: STUDY-03
**Success Criteria** (what must be TRUE):
  1. All 38 tickers + `^NSEI` have full 2022-07-01→2026-01-31 daily price coverage
  2. Every ticker passes integrity checks (no non-positive closes, no coverage gap >21 days from window bounds, row count within 5% of the benchmark's)
  3. Any ticker that fails integrity is dropped and logged, never patched with fabricated values (none were dropped this run)
**Plans**: Complete (implemented pre-GSD; `scripts/03_prices.py`, see DECISIONS.md Phase 3)

### Phase 5: Event Study (Abnormal Returns)
**Goal**: Every locked event has a computed abnormal return under the pre-registered market model, with no lookahead
**Depends on**: Phase 4
**Requirements**: STUDY-04
**Success Criteria** (what must be TRUE):
  1. Every event's entry point is the close of the first NSE trading day strictly after the event's UTC date — never the event day itself
  2. CAR is computed at t+1/t+5/t+20 via a 120-trading-day OLS market model (≥90 valid observations), with market-adjusted (β=1) fallback used and flagged only when the window is short
  3. Any event lacking sufficient forward trading days to compute a horizon (e.g. CAR_t20 near the study-period boundary) is flagged as NaN, never dropped silently or fabricated
**Plans**: Complete (implemented pre-GSD; `scripts/04_event_study.py`, see DECISIONS.md Phase 4)

### Phase 6: Permutation Inference & Verdict
**Goal**: The pre-registered primary and secondary hypotheses are tested against a real permutation null, and a binding SIGNAL/NULL verdict is recorded exactly as it comes out
**Depends on**: Phase 5
**Requirements**: STUDY-05
**Success Criteria** (what must be TRUE):
  1. A 1,000-draw-per-ticker permutation null is constructed (pseudo-events excluding ±5 trading days around real events) and used for the one-sided primary test
  2. Secondary tests are BH-FDR corrected at q=0.10; the single pre-registered robustness pass (clustering-drop) is run and does not change the conclusion
  3. The verdict (NULL: primary p=0.763, wrong sign; no secondary survives FDR) is recorded in `results/stats.json` with no respecification after results were seen
**Plans**: Complete (implemented pre-GSD; `scripts/05_inference.py`, see DECISIONS.md Phase 4)

### Phase 7: Report, Figures & v0.1 Tag
**Goal**: The NULL result is reported honestly and completely, and v0.1 ships as a full, tagged success
**Depends on**: Phase 6
**Requirements**: STUDY-06
**Success Criteria** (what must be TRUE):
  1. Report figures plot the actual persisted null distributions (not approximations), reproducible byte-for-byte at seed=42
  2. README states the NULL verdict plainly, with no softening, per "honesty over momentum"
  3. `v0.1` is tagged and pushed, closing the locked study
**Plans**: Complete (implemented pre-GSD; `scripts/06_report_figures.py` equivalent, README.md Results section, see DECISIONS.md Phase 6)

### Phase 8: Live Daily Pipeline (override)
**Goal**: The system keeps detecting the same kind of events every day, unattended, without ever touching v0.1's locked artifacts
**Depends on**: Phase 7 (and the 2026-07-09 "override handover" authorizing this phase specifically)
**Requirements**: PIPE-01, PIPE-02
**Success Criteria** (what must be TRUE):
  1. `scripts/10_daily_ingest.py` and `scripts/11_daily_events.py` write only to `data/live/` and `data/live_events.csv`, never to `data/events.csv`/`data/car_by_event.csv`/`results/stats.json`
  2. Re-running the live scripts back-to-back with no new gap correctly reports "0 new events" / "nothing new" (idempotency verified directly)
  3. `daily.yml` runs successfully end-to-end on real GitHub Actions infrastructure via manual `workflow_dispatch`, not just locally
**Plans**: Complete (implemented pre-GSD; `.github/workflows/daily.yml`, `scripts/10_daily_ingest.py`, `scripts/11_daily_events.py`, see DECISIONS.md Phase 5 post-v0.1 + PARKING.md override log)

### Phase 9: NULL-Mode Scoring Layer (override)
**Goal**: Live events are scored for intensity and novelty without ever implying a forward-return edge the locked study didn't find
**Depends on**: Phase 8 (same override scope)
**Requirements**: SCORE-01, SCORE-02
**Success Criteria** (what must be TRUE):
  1. `scripts/06_scoring.py` hard-exits (`sys.exit`) if `results/stats.json`'s verdict is ever anything other than NULL
  2. NULL-mode scoring asserts no `CAR_t*` column is present before running — a code-level guarantee, not just a comment
  3. Every scored live event has an intensity percentile (anchored to the locked 242-event historical distribution) and a novelty value (days-since-last-event, `NaN` for a ticker's first-ever event)
**Plans**: Complete (implemented pre-GSD; `scripts/06_scoring.py`, see DECISIONS.md Phase 6 post-v0.1)

### Phase 10: Public Site (override)
**Goal**: A shareable, honest public site exists that reports the NULL verdict and shows the live feed without overclaiming
**Depends on**: Phase 9 (and a separate 2026-07-09 "override handover" scoped to this phase)
**Requirements**: SITE-01, SITE-02
**Success Criteria** (what must be TRUE):
  1. The public GitHub Pages site (Jinja2 → static HTML, classic branch-based hosting) shows a live event feed, per-ticker pages, and a methodology page
  2. `docs/` is fully rebuilt from scratch (`shutil.rmtree` + regenerate) on every run, never incrementally patched
  3. The site never shows a forward-return number; hero copy explicitly frames the live feed as "an instrument that watches constantly and, so far, correctly reports nothing"
**Plans**: Complete (implemented pre-GSD; `scripts/12_build_site.py`, `site_src/`, `docs/`, see DECISIONS.md Phase 7 post-v0.1)

### Phase 11: Hardening, Testing & Production Fixes (override)
**Goal**: The live pipeline survives real unattended operation — including the failure modes actually encountered — with automated regression coverage and an honest account of the study's statistical power
**Depends on**: Phase 10 (same override scope, extended by two post-Phase-8 incident-response passes)
**Requirements**: HARD-01, HARD-02, HARD-03, PIPE-03, PIPE-04, STUDY-07
**Success Criteria** (what must be TRUE):
  1. `scripts/12_build_site.py` fails the build hard if live data is >4 calendar days stale; the footer separately shows "data current through" vs "built"
  2. Optional Telegram alerting no-ops cleanly (confirmed on real Actions infra) when secrets are absent, never failing the pipeline
  3. `daily.yml` is verified via 3+ manual `workflow_dispatch` runs plus real scheduled runs, including recovery from two real production bugs (`parse_timeline` sub-daily-bucket crash, `fetch_gap` inclusive-boundary phantom-day rows) — both root-caused, fixed, and regression-tested with real fixtures, no synthetic data
  4. A first automated regression test suite (stdlib `unittest`, 12 tests) covers `10_daily_ingest.py`'s real production failure modes, with a validated negative control (pre-fix logic still fails the reproducing fixture)
  5. A retroactive power/MDE analysis is added to the README, confirming the locked NULL result is well-powered (MDE 0.56% at 80% power, n=242) without respecifying the locked test
**Plans**: Complete (implemented pre-GSD; `scripts/10_daily_ingest.py` fixes, `scripts/07_power_analysis.py`, `tests/test_10_daily_ingest.py`, `requirements.txt` pin, README additions — see DECISIONS.md Phase 8 post-v0.1, "Post-Phase-8 bug" section, regression-test-suite section, power-analysis section, "four cheap fixes" section, and the 2026-07-16 phantom-day-bug section)

### Phase 12: v1.0 Ship Gate
**Goal**: The live pipeline's unattended reliability is proven honestly over time, and the project reaches real humans — without faking either milestone to hit a date
**Depends on**: Phase 11
**Requirements**: SHIP-01, SHIP-02, SHIP-03
**Success Criteria** (what must be TRUE):
  1. The pipeline completes 14 consecutive unattended scheduled cron runs with zero hard resets (currently 4/14 as of 2026-07-16; any scheduled failure resets the counter to zero, not a rolling window)
  2. `v1.0` is tagged and pushed only once criterion 1 is genuinely met — no backdating, no batch-triggering to fake the streak
  3. The repo/README has been sent to ≥3 real humans (≥1 technical) for feedback — this proceeds independently of criterion 1/2 per the 2026-07-16 decoupling decision, since the study and site have been complete and honest since the verdict locked (2026-07-09)
**Plans**: TBD — this phase is monitoring (cron streak accumulates passively via the existing schedule) plus an outreach task for Vivek, not new engineering work; no further build plans are anticipated unless a future scheduled run fails and resets the counter

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Smoke Test | Complete | Complete | 2026 (v0.1 Phase 0) |
| 2. Universe Construction & Coverage Gate | Complete | Complete | 2026 (v0.1 Phase 1) |
| 3. Event Extraction & Pre-Registration Lock | Complete | Complete | 2026 (v0.1 Phase 2) |
| 4. Price Data & Integrity | Complete | Complete | 2026 (v0.1 Phase 3) |
| 5. Event Study (Abnormal Returns) | Complete | Complete | 2026 (v0.1 Phase 4) |
| 6. Permutation Inference & Verdict | Complete | Complete | 2026 (v0.1 Phase 5) |
| 7. Report, Figures & v0.1 Tag | Complete | Complete | 2026 (v0.1 tagged) |
| 8. Live Daily Pipeline (override) | Complete | Complete | 2026-07-09 |
| 9. NULL-Mode Scoring Layer (override) | Complete | Complete | 2026-07-09 |
| 10. Public Site (override) | Complete | Complete | 2026-07-09 |
| 11. Hardening, Testing & Production Fixes (override) | Complete | Complete | 2026-07-16 |
| 12. v1.0 Ship Gate | 0/TBD | In progress (4/14 cron runs; outreach unblocked) | - |
