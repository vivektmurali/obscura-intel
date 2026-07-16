# Obscura Intel

## What This Is

A rigorous, pre-registered event study testing whether GDELT news-volume spikes in NSE mid/small-cap
stocks carry abnormal forward returns in the direction of news tone — plus a live daily pipeline
(GitHub Actions cron, static GitHub Pages site) that keeps detecting and displaying the same kind of
events going forward, without ever claiming a forward-return edge the locked study didn't find. It is
portfolio evidence of methodological rigor (pre-registration, null controls, multiple-testing
correction, honest limitations, production pipeline engineering) for UK data/statistics hiring (ONS
Statistical Methodologist, DBT Python Developer roles) — not a trading system.

## Core Value

Success is defined by the pre-registered kill criterion (HANDOVER.md §4.7-4.8): primary permutation
test p<0.05 OR a secondary test survives BH-FDR q=0.10. **A well-executed NULL result is a full
success** — the deliverable is evaluation rigor (pre-registration discipline, null controls, honest
reporting, and now a real production pipeline with real bugs found/fixed/tested), not a profitable
signal.

## Requirements

### Validated

<!-- Shipped, locked, and confirmed — v0.1 study + v1.0 post-override infrastructure. -->

- ✓ SETUP-01: Repo scaffolding + GDELT smoke test verifies API JSON shapes/rate-limit behavior — v0.1 Phase 0
- ✓ STUDY-01: 38-ticker NSE universe constructed, coverage gate passed (median 104.5 nonzero-vol days/yr ≥ 30) — v0.1 Phase 1
- ✓ STUDY-02: 242 events across 28/38 tickers detected (vol_z≥3, v≥5), sample-size gate passed (≥150, confirmatory), PREREGISTRATION.md committed before price join — v0.1 Phase 2
- ✓ STUDY-03: Price data ingested and integrity-checked for all 38 tickers + ^NSEI benchmark, zero drops — v0.1 Phase 3
- ✓ STUDY-04: Abnormal returns computed via 120-day OLS market model at t+1/t+5/t+20, lookahead-safe entry timing — v0.1 Phase 4
- ✓ STUDY-05: Permutation-null inference (1,000 draws/ticker) + BH-FDR secondary tests + one pre-registered robustness pass run; verdict recorded — v0.1 Phase 5
- ✓ STUDY-06: Report figures (from persisted null distributions) + README verdict statement + `v0.1` tag shipped — v0.1 Phase 6
- ✓ PIPE-01: Daily unattended incremental ingestion (GDELT + yfinance) recomputes live events in a separate namespace from locked v0.1 artifacts — v1.0 Phase 5 (override)
- ✓ PIPE-02: Ingestion is idempotent and self-healing (retry/backoff, recompute-over-append, resumable) — v1.0 Phase 5 (override)
- ✓ SCORE-01: Scoring layer hard-exits if verdict is ever not NULL; NULL-mode asserts no CAR_t* column present — v1.0 Phase 6 (override)
- ✓ SCORE-02: Live events scored by intensity percentile (anchored to locked historical distribution) and per-ticker novelty (days-since-last-event, NaN when undefined) — v1.0 Phase 6 (override)
- ✓ SITE-01: Public static site (GitHub Pages, Jinja2) publishes live feed + per-ticker pages + methodology page, full rebuild every run — v1.0 Phase 7 (override)
- ✓ SITE-02: Every site number traceable to a cached raw API response; claims policy enforced in copy (NULL verdict never implies forward returns) — v1.0 Phase 7 (override)
- ✓ HARD-01: Site build fails hard if live data >4 calendar days stale; footer shows "data current through" vs "built" separately — v1.0 Phase 8 (override)
- ✓ HARD-02: Optional Telegram alerting no-ops cleanly when secrets absent, never fails the pipeline — v1.0 Phase 8 (override)
- ✓ HARD-03: `.github/workflows/daily.yml` verified end-to-end on real GitHub Actions infra (3 manual `workflow_dispatch` runs + real scheduled runs) — v1.0 Phase 8 (override)
- ✓ PIPE-03: Both GDELT timeline bucket resolutions (daily and sub-daily/15-min) parse correctly with no crash and no phantom/duplicate-day rows — fixed post-Phase-8 (2026-07-11 `parse_timeline` crash, 2026-07-16 `fetch_gap` inclusive-boundary phantom-day bug), both regression-tested
- ✓ PIPE-04: Automated regression test suite (stdlib `unittest`) covers `10_daily_ingest.py`'s real production failure modes using real captured fixtures — added 2026-07-14, extended 2026-07-16 (12 tests total)
- ✓ STUDY-07: Retroactive power/MDE analysis quantifies the study is a well-powered null (MDE 0.56% at 80% power, n=242), added to README without respecifying the locked test — 2026-07-16

### Active

<!-- Only the v1.0 "shipped" gate remains. Everything else is built, tested, and running in production. -->

- [ ] SHIP-01: Pipeline completes 14 consecutive unattended scheduled cron runs with no hard reset (counter resets to zero on any scheduled failure — not a rolling window)
- [ ] SHIP-02: `v1.0` git tag cut once SHIP-01 passes
- [ ] SHIP-03: Repo/README sent to ≥3 real humans (≥1 technical) for outreach feedback — explicitly decoupled from SHIP-01/SHIP-02 (2026-07-16 decision), unblocked now

### Out of Scope

<!-- HANDOVER.md §5 ban list, binding. Three items lifted via logged "override handover"; one remains banned. -->

- Live prediction/alerting on trade signals — banned outright (HANDOVER §5); the live pipeline detects/displays events only, never predicts
- LLM enrichment (Claude API / local Ollama headline scoring, ARCHITECTURE.md §8) — the one architecture-proposed item never overridden; explicitly not built, needs its own "override handover" before any of it is touched
- Gemma fine-tuning — banned, parked
- React or any web dashboard — banned; Phase 7's override authorized *a* public site, not specifically React; Jinja2 static HTML was built instead (logged choice, not a ban violation)
- FastAPI/servers/ngrok — banned; site is static GitHub Pages, compute is GitHub Actions only
- Lightpanda or any scraping beyond the GDELT API — banned; NSE bhavcopy fallback (ARCHITECTURE §4/§8) deliberately not built for the same reason (couldn't verify without scraping-adjacent behavior)
- Neo4j/FAISS/vector stores, server databases (SQLite only if genuinely needed) — banned, never needed
- Docker — banned, not used
- CI beyond a trivial lint (other than the overridden daily cron itself) — the daily cron is the one authorized exception (Phase 5 override); no additional CI added
- Broker/trading integration — banned, parked
- Any synthetic/simulated data fallback — banned outright, zero exceptions across the entire project; every bug (SAIL/BHEL fetch failures, parse_timeline crash, phantom-day rows) was fixed by fixing the fetch/parse logic or dropping the affected data, never by fabricating substitutes
- GKG themes/entity linking, additional markets beyond NSE, calendar-time portfolio clustering correction — parked, unrequested
- Mobile app, user accounts, paid infra, additional markets — parked (ARCHITECTURE §11 non-goals)

## Context

- **Two-track locked precedent:** `HANDOVER.md` (v0.1 mission, research design, kill criteria, ban list — locked, precedence 0) and `PREREGISTRATION.md` (results-bearing instantiation: 38 tickers, 242 events, gate PASS — treated as de facto locked, precedence 0 despite a `locked:false` classifier field) are both immutable. `ARCHITECTURE.md` (v1.0 system spec, precedence 1) self-declares subordinate to both and only *lifts* specific ADR bans after a named gate, via Vivek's explicit "override handover" phrase — never on its own authority.
- **GDELT is far more rate-limit-aggressive than HANDOVER's template assumed** — recurring theme across the whole project (Phase 0 smoke test, Phase 1 bulk coverage pull, live daily ingest). Every GDELT-touching script budgets real wall-clock cost (throttling/backoff), not nominal per-call sleep.
- **Universe drifted from "~40" (approximate, per HANDOVER §4.1) to 38 executed** — SAIL and BHEL dropped after persistent fetch failures across three retry passes, an unrelated-to-coverage-gate data-availability drop (gate itself passed), logged autonomously per CLAUDE.md rule 5, not escalated to Vivek.
- **v0.1 verdict: NULL.** Primary permutation test p=0.763 (wrong sign vs thesis); no secondary survives BH-FDR q=0.10 (best p=0.238). One pre-registered robustness pass doesn't change the conclusion. This is a full, honest, ship-worthy result per the pre-registration — not a failure to fix.
- **Two production bugs found in the live pipeline post-Phase-8**, both in `scripts/10_daily_ingest.py`: (1) `parse_timeline` hardcoded midnight-only bucket parsing, crashed on GDELT's 15-minute sub-daily buckets on the first true 1-day incremental gap (2026-07-11 cron failure, reset the 14-run counter to zero); (2) `fetch_gap` assumed GDELT's `enddatetime` was exclusive when it's actually inclusive, producing phantom near-zero boundary-day rows that silently stalled 19/38 tickers' gap detection — found via adversarial code review, not a crash, on 2026-07-16. Both fixed, regression-tested, no synthetic data used in either fix or its tests (fixtures are real captured API responses).
- **A local-council code review (2026-07-14/16) drove four more improvements**: a first regression test suite (11→12 tests, stdlib `unittest`, real fixtures), a retroactive power/MDE analysis (well-powered null, not ambiguous), pinned `requirements.txt` to CI-proven versions, and README additions (GDELT throttling story, 14-run gate reset semantics, data-provenance/privacy sentence for an ONS-style audience).
- **Live pipeline scope decision (2026-07-16, Vivek's call):** stays in scope despite a "Simplicity Champion" council argument that it's creep diluting the NULL finding — kept because it's the strongest evidence for the DBT Python Developer audience specifically (real bugs found/fixed/tested under real load). Stays secondary to the study per the README's framing.
- **Outreach explicitly decoupled from the 14-run gate (2026-07-16, Vivek's call):** the study and site have been complete and honest since the verdict locked (2026-07-09); no reason outreach should wait on an unrelated cron-reliability metric. Outreach unblocked now (4/14 runs as of 2026-07-16); the `v1.0` tag still waits for the full 14-run streak.
- **Repository:** `vivektmurali/obscura-intel` on GitHub Actions (cron `15 1 * * *` UTC) + classic branch-based GitHub Pages (`docs/`, committed, rebuilt from scratch every run).

## Constraints

- **Locked research design**: HANDOVER.md §4.1-4.8 (universe, event definition, timestamp/lookahead rule, market-model returns, permutation inference, kill criteria) and PREREGISTRATION.md's results-bearing instantiation — immutable, no respecification after results were seen (exactly one pre-registered robustness pass permitted, already used).
- **Hard scope ban list**: HANDOVER.md §5 — binding except where lifted by a logged "override handover" (Phases 5, 7, 8 in full; Phase 6 LLM enrichment remains banned/un-overridden).
- **Allowed stack**: Python 3.11+, `requests`, `pandas`, `numpy`, `scipy`, `statsmodels`, `yfinance`, `matplotlib`, `pyarrow`, plus `jinja2` (added, logged) for the site. CLI scripts + CSV/parquet + PNG figures + static HTML. Nothing else without a `DECISIONS.md` entry.
- **Zero-server architecture**: compute = GitHub Actions, storage = repo (parquet/CSV), frontend = static GitHub Pages. No databases, no Docker, no servers.
- **No synthetic data, ever**: if an API fails, fail loudly, cache what's there, stop — banned as the project's historical failure mode; upheld across every incident this project has had.
- **v1.0 shipped gate (ARCHITECTURE.md §1)**: 14 consecutive unattended cron runs (hard reset to zero on any scheduled failure) gates the `v1.0` tag; outreach to ≥3 real humans is decoupled from that gate (2026-07-16 decision) and can proceed independently.
- **Timeline**: feature freeze 2026-09-18, deadline late October 2026 (ARCHITECTURE.md §10). Slack budgeted; if anything slips, cut from Phase 7 (already resolved — Jinja2 chosen) or Phase 8 extras first, never Phase 4 rigor.
- **Claims policy (ARCHITECTURE.md §7)**: event detection always free to display; forward-return language only to the extent Phase 4's validation supports — under the locked NULL verdict, no forward-return numbers appear anywhere on the site or in scoring, enforced at the code level (hard `sys.exit` + assertion).

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Universe: 38 tickers, not ~40 | SAIL/BHEL failed all GDELT fetch attempts across 3 retry passes; coverage gate itself passed | ✓ Good |
| Verdict: NULL, no respecification | Primary p=0.763 (wrong sign), no secondary survives BH-FDR; one pre-registered robustness pass doesn't change it | ✓ Good — full honest result per pre-registration |
| "Override handover" x3 (2026-07-09): Phases 5, 7, 8 | Vivek explicitly invoked the escape hatch to reintroduce cron/CI, public site, and Telegram alerts, each scoped individually | ✓ Good — each built, tested, logged |
| Phase 6 LLM enrichment left un-overridden | Not requested; separately banned (Claude API in pipeline) | — Pending (parked, not built) |
| Public site: Jinja2 static HTML, not React | Keeps Python-only stack, no Node/npm toolchain for a site with no interactivity needs | ✓ Good |
| GitHub Pages: classic branch-based, not Actions deploy | Simpler, no separate Pages environment/permissions | ✓ Good |
| Freshness guard threshold: 4 days, not literal 3 | Avoids tripping on every routine Friday→Monday weekend gap | ✓ Good |
| Live pipeline stays in scope (2026-07-16) | Strongest evidence for DBT Python Developer audience despite "scope creep" argument; stays secondary to the study | ✓ Good |
| Outreach decoupled from 14-run gate (2026-07-16) | Study/site have been honest and complete since 2026-07-09; unattended-cron reliability is orthogonal to analysis soundness | ✓ Good — outreach unblocked now |
| `parse_timeline` fix: parse full timestamp, group by date | GDELT auto-selects daily vs 15-min buckets by query span; hardcoded midnight parsing crashed on real 1-day gaps | ✓ Good — regression tested |
| `fetch_gap` boundary fix: filter `date < end_date` | GDELT's `enddatetime` is inclusive, not exclusive as originally assumed; caused silent phantom-day rows and stalled gap detection for 19/38 tickers | ✓ Good — regression tested, repaired in production |
| MAX_ATTEMPTS reduced 6→3 in live ingest | GDELT throttling severity trending up (4-6h runs), approaching Actions' 6h job timeout | ✓ Good |
| First regression test suite added (stdlib `unittest`) | Zero tests existed; both production bugs that week lived in the one untested subsystem | ✓ Good |
| Retroactive power/MDE analysis added | Distinguishes a well-powered null from an ambiguous one; doesn't touch the locked test | ✓ Good |
| NSE bhavcopy fallback deferred | Couldn't confirm current URL/format without scraping-adjacent behavior edging toward the ban; yfinance has had zero failures | — Pending (documented, not built) |

---
*Last updated: 2026-07-16 after reconstructing project state via HANDOVER.md/ARCHITECTURE.md/DECISIONS.md/PARKING.md ingest (v0.1 shipped + v1.0 Phases 5-8 built/tested; only the 14-run gate and outreach remain outstanding).*
