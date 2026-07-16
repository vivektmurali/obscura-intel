# Constraints (synthesized from SPEC-classified sources)

Precedence: `SPEC` = 1 (default), overridden per-doc to `precedence: 1` explicitly
for the one SPEC in this batch. Ranks below ADR (0), above PRD (3 default, n/a here)
and DOC (3, per-doc override applied to `DECISIONS.md`/`PARKING.md` in this batch).

**Relationship to ADR sources (stated in the SPEC itself, `source: ARCHITECTURE.md` line 4):**
"HANDOVER.md remains binding for (a) the statistical research design, (b) standing
execution rules, (c) appendices. ... HANDOVER.md's §5 ban list stays in force until
the validation gate (Phase 4) is passed; after that, this document's phase gates
govern what gets unbanned, and when." This is a self-declared subordination to the
ADR set (`decisions.md`) — the SPEC does not claim to override the ADRs, it claims
staged authority to *lift* specific ADR-level bans after a named gate. See
`INGEST-CONFLICTS.md` for how this staged-unban claim interacts with what was
actually built (per `DECISIONS.md`).

---

## SPEC-1: OBSCURA INTEL — SYSTEM ARCHITECTURE & SHIPPING ROADMAP (v1.0)

- **source:** `ARCHITECTURE.md`
- **type:** nfr / protocol / roadmap (mixed — this SPEC spans architecture, ops policy, and phased roadmap; no single constraint-type tag from the taxonomy fits cleanly, recorded here as a set of sub-constraints by section)

### C1 — Definition of "shipped" (v1.0 gate checklist), §1
Public GitHub Pages live event feed + per-ticker pages + methodology page, updating
daily with real data; pipeline fully unattended on GitHub Actions cron (proof: 14
consecutive unattended daily runs — hard reset to zero on any scheduled failure,
not a rolling window; the counter's reset semantics were clarified directly in this
section per `DECISIONS.md`'s "Four cheap fixes" entry); every site number traceable
to a cached raw API response; validation results published either way, citing the
pre-registration commit hash; claims audit passed (§7); README as flagship writeup,
tag `v1.0` gated on the 14-run streak; sent to ≥3 real humans (≥1 technical) —
**explicitly decoupled from the 14-run gate** (decision dated 2026-07-16, cross-
referenced to `DECISIONS.md`).

### C2 — Design principles (binding), §2
Zero-server (compute = GitHub Actions, storage = repo, frontend = static Pages);
real data only everywhere including tests; validation-gated claims (system may
detect/display events unconditionally, but forward-looking statements only to the
extent Phase 4 study supports, §7); recompute-over-append (incremental ingest,
full recompute downstream, idempotent, self-healing); boring stack (flat scripts,
parquet, cron — complexity must earn a `DECISIONS.md` entry).

### C3 — Data reality and provenance, §3
GDELT is the sole delegated web-scale news source (re-crawling permanently out of
scope: cost, legality, redundancy); provenance rule — every API response cached
raw (compressed JSON) under `data/raw/` before parsing, every derived table carries
source-file references, no untraceable number on the site; no-dummy-data rule
extends to tests (`tests/fixtures/` = frozen real cached responses only); zero-secret
core (GDELT/yfinance keyless; secrets only for optional Telegram/LLM, via Actions
secrets, never in repo).

### C4 — Stack (final), §4
Python 3.11+; `requests` + `yfinance` ingestion (fallback: NSE bhavcopy CSV,
pre-agreed for Phase 8); `pandas`/`pyarrow` parquet (monthly-partitioned) + optional
`duckdb` for queries; `numpy`/`scipy`/`statsmodels` per HANDOVER §4; `matplotlib`
PNG or `plotly` static HTML for charts; GitHub Actions cron orchestration; site =
static Jinja2→HTML **or** React static build reading committed JSON (choice
deferred to Phase 7 — see `decisions.md`'s note on this and `INGEST-CONFLICTS.md`
for the resolution actually taken); GitHub Pages hosting; optional Telegram bot
alerts; optional gated LLM enrichment (Claude API Haiku-class batched, or local
Ollama — Phase 6 only, must earn its place per §10). Explicitly banned for v1.0:
FastAPI/servers, ngrok, Docker, Neo4j/FAISS/vector stores, server databases, broker
integration, intraday anything, user accounts, paid infra.

### C5 — Repository layout (extends HANDOVER §6), §5
Adds `.github/workflows/daily.yml`, `scripts/01_universe.py` through `13_alert.py`
(renumbered/expanded vs HANDOVER's `00`-`06`), `site_src/`, `site/`, `tests/`
(fixtures = frozen real responses).

### C6 — Phase roadmap, §6 (phases 0-4 map onto HANDOVER's phases per the §6.0
mapping table; phases 5-8 are new, not present in HANDOVER)
Phase 0 foundation/smoke gate; Phase 1 universe+entity layer; Phase 2 historical
ingestion (integrity report, idempotency check); Phase 3 event engine +
pre-registration lock; Phase 4 VALIDATION CORE (the gate — event study,
inference, verdict recorded as SIGNAL or NULL, no respecification); Phase 5 live
pipeline (daily cron, `.github/workflows/daily.yml` skeleton, 3-consecutive-green-run
gate); Phase 6 scoring layer, verdict-bounded (SIGNAL: historical CAR(t+5) bucket
stats with uncertainty, never "will move"; NULL: intensity/novelty score only, no
forward-return numbers anywhere — enforced as a code-level claims-audit gate);
Phase 7 ship the surface (public URL, live feed / ticker pages / methodology page,
implementation choice A-Jinja2 vs B-React logged in `DECISIONS.md`); Phase 8
hardening & release (failure alerting, freshness guard >3 days stale = build fails,
data growth/compaction policy, NSE bhavcopy fallback behind a flag, backfill tool,
README → flagship writeup, then `git tag v1.0`).

### C7 — Claims policy (binding on scoring, site copy, README, any public post), §7
Table of what may be shown under SIGNAL vs NULL verdicts. Event detection always
free to display. Forward returns: SIGNAL = historical distributions only
("historical association" phrasing); NULL = not shown, not implied. Never, either
way: trade advice, "will," "predicts," strategy-return marketing, certainty
language. Explicit statement: a NULL verdict does not reduce the project's value
for its actual purpose (UK data/statistics job-market portfolio) — pipeline
engineering + pre-registration discipline + honest write-up **are** the product.

### C8 — LLM enrichment policy (optional module, gated), §8
Scope: classify event-day headlines into a fixed taxonomy + an LLM direction score.
Earn-its-place test required before any live use (bootstrap CI of accuracy
difference vs `tone_z` baseline must exclude zero). Hard cost cap £5/month; kill
switch = one flag. If it doesn't beat baseline: documented, module stays off,
stated in README either way.

### C9 — Risks (extends HANDOVER §9), §9
GDELT coverage sparsity; yfinance breakage/throttling; Actions cron delay/skip
(tolerated by design); repo data growth; timezone/entry-rule bugs (single shared
implementation across historical+live paths); cross-sectional event clustering;
scope creep back to "platform v0" (§4 ban list + PARKING.md + override phrase);
verdict-disappointment abandonment (§7 pre-commits NULL as a full ship).

### C10 — Timeline vs. late-October deadline, §10
Weekly phase-to-milestone table, Jul 6 2026 → Oct 2026; feature freeze 2026-09-18;
slack built in; if a phase slips, cut from Phase 7 (use Jinja2, not React) and
Phase 8 extras first — never from Phase 4 rigor.

### C11 — Non-goals for v1.0 (parked, not forgotten → PARKING.md), §11
Broker/trading execution; intraday latency; additional markets; user accounts;
server databases; Docker/K8s; paid infrastructure; Gemma fine-tuning; full
calendar-time portfolio statistics; mobile app; any claim of strategy returns.
