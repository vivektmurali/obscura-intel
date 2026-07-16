# Requirements: Obscura Intel

**Defined:** 2026-07-16 (reconstructed retrospectively from HANDOVER.md, PREREGISTRATION.md,
ARCHITECTURE.md, DECISIONS.md, PARKING.md — no PRD-type document exists for this project;
these requirements are derived from the locked ADRs/SPEC/decision log, not hand-authored from
scratch. Project is deep into execution: v0.1 shipped and tagged, v1.0 Phases 5-8 built and
tested. Only the final ship-gate work remains.)

**Core Value:** Success is defined by the pre-registered kill criterion (HANDOVER.md §4.7-4.8) —
a well-executed NULL result is a full success. The actual purpose is portfolio evidence of
methodological rigor for UK data/statistics hiring.

## v1 Requirements

Nearly all v1 requirements are already complete (checked). Only the SHIP category remains open.

### Setup

- [x] **SETUP-01**: Repo scaffolding + GDELT smoke test verifies API JSON shapes and rate-limit
      behavior empirically before any bulk pull

### Study (v0.1 — locked event study)

- [x] **STUDY-01**: 38-ticker NSE mid/small-cap universe constructed (≥6 sector spread, usable
      Yahoo Finance history); coverage gate passed (median 104.5 nonzero-volume days/year ≥ 30)
- [x] **STUDY-02**: News-volume-spike events detected from GDELT DOC 2.0 (`vol_z≥3`, `v≥5`);
      242 events across 28/38 tickers, sample-size gate passed (≥150, confirmatory);
      PREREGISTRATION.md committed before price data is joined to event data
- [x] **STUDY-03**: Price data ingested (yfinance, adjusted) and integrity-checked for all 38
      tickers + `^NSEI` benchmark; zero tickers dropped
- [x] **STUDY-04**: Abnormal returns computed via 120-trading-day OLS market model at t+1/t+5/t+20
      horizons, with lookahead-safe entry timing (close of first NSE trading day strictly after
      the event's UTC date)
- [x] **STUDY-05**: Permutation-null inference (1,000 draws/ticker) run for the primary hypothesis
      plus BH-FDR-corrected secondary tests and one pre-registered robustness pass; verdict
      recorded per the binding kill criterion
- [x] **STUDY-06**: Report figures (from persisted null distributions), README verdict statement,
      and `v0.1` git tag shipped
- [x] **STUDY-07**: Retroactive power/MDE analysis quantifies whether the locked NULL result is
      well-powered, without respecifying the locked test

### Pipeline (v1.0 — live daily ingestion, override)

- [x] **PIPE-01**: Daily unattended incremental ingestion (GDELT + yfinance) recomputes live
      events in a namespace (`data/live/`) separate from v0.1's locked artifacts
- [x] **PIPE-02**: Ingestion is idempotent and self-healing (retry/backoff, recompute-over-append,
      resumable across throttling and session boundaries)
- [x] **PIPE-03**: Both GDELT timeline bucket resolutions (daily and 15-minute sub-daily) parse
      correctly with no crash and no phantom/duplicate-day rows
- [x] **PIPE-04**: Automated regression test suite covers the live ingestion module's real
      production failure modes, using real captured fixtures (no synthetic data)

### Scoring (v1.0 — NULL-mode scoring layer, override)

- [x] **SCORE-01**: Scoring layer hard-exits if the locked verdict is ever not NULL; NULL-mode
      scoring asserts no `CAR_t*` (forward-return) column is present before running
- [x] **SCORE-02**: Live events scored by intensity percentile (anchored to the locked historical
      `vol_z` distribution) and per-ticker novelty (days-since-last-event, `NaN` when undefined)

### Site (v1.0 — public GitHub Pages site, override)

- [x] **SITE-01**: Public static site publishes a live event feed, per-ticker pages, and a
      methodology page; fully rebuilt from source on every run
- [x] **SITE-02**: Every displayed number is traceable to a cached raw API response; claims policy
      enforced in copy (a NULL verdict never implies forward returns)

### Hardening (v1.0 — release readiness, override)

- [x] **HARD-01**: Site build fails hard (non-zero exit) if live data is more than 4 calendar days
      stale; footer shows "data current through" separately from "built"
- [x] **HARD-02**: Optional Telegram alerting no-ops cleanly when secrets are absent, never fails
      the pipeline
- [x] **HARD-03**: `.github/workflows/daily.yml` verified end-to-end on real GitHub Actions
      infrastructure (manual `workflow_dispatch` runs and real scheduled runs)

### Ship (v1.0 — outstanding)

- [ ] **SHIP-01**: Pipeline completes 14 consecutive unattended scheduled cron runs with no hard
      reset (counter resets to zero on any scheduled failure, not a rolling window) — 4/14 as of
      2026-07-16
- [ ] **SHIP-02**: `v1.0` git tag cut once SHIP-01 passes
- [ ] **SHIP-03**: Repo/README sent to ≥3 real humans (≥1 technical) for outreach feedback —
      explicitly decoupled from SHIP-01/SHIP-02 (2026-07-16 decision), unblocked now

## v2 Requirements

None. This is a study + supporting live pipeline, not a platform with a growth roadmap. Anything
beyond the v1.0 ship gate is parked, not deferred-but-planned (see Out of Scope).

## Out of Scope

| Feature | Reason |
|---------|--------|
| LLM enrichment (Claude API / local Ollama headline scoring, ARCHITECTURE.md §8) | The one architecture-proposed item never granted an "override handover"; separately banned (Claude API/LLM calls in the pipeline); not requested, not built |
| Live prediction/alerting on trade signals | Banned outright (HANDOVER §5); live pipeline detects/displays events only, never predicts |
| Gemma fine-tuning | Banned, parked |
| React or any web dashboard | Banned; Phase 7's override authorized *a* public site, not specifically React — Jinja2 static HTML built instead |
| FastAPI/servers/ngrok | Banned; site is static GitHub Pages, compute is GitHub Actions only |
| Lightpanda or any scraping beyond the GDELT API (incl. NSE bhavcopy fallback) | Banned; bhavcopy fallback deliberately deferred — couldn't verify without scraping-adjacent behavior |
| Neo4j/FAISS/vector stores, server databases | Banned, never needed (flat files/parquet only) |
| Docker | Banned, not used |
| CI beyond a trivial lint (other than the overridden daily cron) | Daily cron is the one authorized exception (Phase 5 override); no additional CI added |
| Broker/trading integration | Banned, parked |
| Any synthetic/simulated data fallback | Banned outright, zero exceptions across the project |
| GKG themes/entity linking, additional markets beyond NSE, calendar-time portfolio clustering correction | Parked, unrequested |
| Mobile app, user accounts, paid infra | Parked (ARCHITECTURE §11 non-goals) |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SETUP-01 | Phase 1 | Complete |
| STUDY-01 | Phase 2 | Complete |
| STUDY-02 | Phase 3 | Complete |
| STUDY-03 | Phase 4 | Complete |
| STUDY-04 | Phase 5 | Complete |
| STUDY-05 | Phase 6 | Complete |
| STUDY-06 | Phase 7 | Complete |
| PIPE-01 | Phase 8 | Complete |
| PIPE-02 | Phase 8 | Complete |
| SCORE-01 | Phase 9 | Complete |
| SCORE-02 | Phase 9 | Complete |
| SITE-01 | Phase 10 | Complete |
| SITE-02 | Phase 10 | Complete |
| HARD-01 | Phase 11 | Complete |
| HARD-02 | Phase 11 | Complete |
| HARD-03 | Phase 11 | Complete |
| PIPE-03 | Phase 11 | Complete |
| PIPE-04 | Phase 11 | Complete |
| STUDY-07 | Phase 11 | Complete |
| SHIP-01 | Phase 12 | Pending |
| SHIP-02 | Phase 12 | Pending |
| SHIP-03 | Phase 12 | Pending |

**Coverage:**
- v1 requirements: 22 total
- Mapped to phases: 22
- Unmapped: 0 ✓
- Complete: 19 / Pending: 3 (all in Phase 12)

---
*Requirements defined: 2026-07-16*
*Last updated: 2026-07-16 after retrospective ingest of HANDOVER.md/PREREGISTRATION.md/ARCHITECTURE.md/DECISIONS.md/PARKING.md*
