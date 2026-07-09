# Parking lot

Out-of-scope ideas. One line each. Untouched until v0.1 tags.

- LLM analysis cascade (Claude API pipeline for event scoring)
- Gemma fine-tune
- React dashboard
- Lightpanda / scraping beyond GDELT API
- GKG themes / entity linking
- Additional markets beyond NSE
- Calendar-time portfolio methods (proper clustering correction)
- Live alerting / prediction
- FastAPI service
- ARCHITECTURE.md v1.0 roadmap (2026-07-07, pasted by Vivek): Phases 5-8 — GitHub Actions daily live pipeline, LLM enrichment scoring, GitHub Pages site (React option), Telegram alerts. Re-proposes items already banned above (live alerting, LLM cascade, React dashboard, CI beyond trivial lint). Phases 0-4 of that doc are a compatible restatement of HANDOVER.md's existing phases and don't need an override.
- **OVERRIDE HANDOVER (2026-07-09):** Vivek explicitly confirmed "override handover" (via an AskUserQuestion option worded exactly that way) to proceed with ARCHITECTURE.md Phase 5 (live pipeline: GitHub Actions cron, daily unattended ingestion) despite it reintroducing HANDOVER.md §5's "CI beyond a trivial lint" and "live prediction/alerting" bans. Scope: Phase 5 only (daily ingest + event recompute + cron). Phases 6-8 (LLM scoring, public site, Telegram alerts) remain parked and each need their own override before being built, per rule 4 — this override does not blanket-approve them.

## Phase 5 (post-override) decisions

- **v0.1's locked artifacts are never touched by the live pipeline.** `data/events.csv`, `data/car_by_event.csv`, `results/stats.json` etc. are the validated study the published verdict depends on. The live pipeline gets its own namespace: `data/live/` (growing parquet store) and `data/live_events.csv` (new-events-this-run, per ARCHITECTURE.md's literal naming). `scripts/10_daily_ingest.py` and `scripts/11_daily_events.py` never write to any v0.1 path.
- **`.gitignore` fix required**: the original blanket `*.parquet` rule (and `data/raw/`) would leave GitHub Actions' ephemeral runners with an empty store on every checkout — there's no other persistent storage for a "zero-server" pipeline, so the live parquet store *must* be committed to survive between runs. Narrowed the rule to exclude only `data/prices.parquet` (v0.1's original, still locally-regenerable) and `data/raw/` + `data/live/raw/` (raw JSON caches, regenerable, not needed once parsed into the parquet store). `data/live/*.parquet` is now tracked.
- **Bootstrap strategy**: `10_daily_ingest.py` seeds `data/live/volume_daily.parquet` / `tone_daily.parquet` from the local historical raw JSON cache (`data/raw/*.json`) the *first* time it's run (locally, once, by me) rather than re-fetching 3 years of GDELT history through the same rate-limited API. That bootstrapped parquet then gets committed, so every future CI run — including the very first one on GitHub Actions — starts from an already-populated store and only fetches the true daily gap.
- **First real run has a ~6-month gap, not a 1-day one**: the historical study data ends 2025-12-31, but "yesterday" relative to today (2026-07-09) is mid-2026 — so the very first incremental fetch has to pull ~6 months per ticker per series, hitting the same GDELT throttling as the original historical pulls. This is expected, one-time, and self-limiting (every subsequent daily run is a true 1-day top-up).
