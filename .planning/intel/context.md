# Context (synthesized from DOC-classified sources)

Precedence: `DOC` = 3 (default, lowest) for both sources in this batch —
`precedence: 3` was also set explicitly per-doc for each, so no override tension.
Running notes below are appended per topic, each block attributed to its source.
Text is preserved close to verbatim (condensed only where the original is a long
narrative paragraph) so downstream provenance-tracing stays intact.

---

## Topic: Phase 0 — GDELT smoke test findings
**source:** `DECISIONS.md`
- GDELT rate limiting is aggressive from this network: the 5s inter-call sleep in
  HANDOVER.md's template was insufficient (hit 429 repeatedly). Changed to 20s
  sleep + retry loop on 429 (linear backoff, 30s×attempt, up to 6 attempts — later
  retuned, see "Runtime risk" below). Future bulk GDELT pulls must budget real
  wall-clock cost, not the nominal 5s/call.
- JSON shapes matched HANDOVER's template exactly: `artlist` → `{"articles":[...]}`
  (`seendate`/`title` keys); `timelinevolraw`/`timelinetone` → `{"timeline":[{"data":[...]}]}`.
- `sourcecountry:IN` returns mixed-language results (including Hindi-script
  headlines), not English-only — matters for later qualitative sampling.
- Windows console encoding fix: default stdout is cp1252, crashes on Hindi-script
  text; added `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`.

## Topic: Phase 1 — Universe construction & coverage gate
**source:** `DECISIONS.md`
- Universe source: full Nifty Midcap 100 + Smallcap 100 constituent lists pulled
  live (July 2026 vintage) via web search/fetch from smart-investing.in
  (niftyindices.com's own CSV endpoints timed out from this network).
- Selection: ~100-candidate pool narrowed to 40 by dropping (a) names too recently
  IPO'd/listed/demerged to have Yahoo Finance history back to 2022-07-01 (Groww,
  Waaree Energies, Premier Energies, Vishal Mega Mart, Lenskart, Meesho,
  PhysicsWallah, Urban Company, Pine Labs, Ola Electric, Jyoti CNC Automation,
  Sagility India, JSW Cement, Brainbees/FirstCry, Inventurus Knowledge Solutions);
  (b) names with unclear/discontinuous ticker history from recent corporate actions
  (GE Vernova T&D India, Piramal Finance, Cholamandalam Financial Holdings);
  (c) single-acronym/generic-word names too ambiguous for string matching (ITI Ltd,
  UPL Ltd, SRF Ltd, Anant Raj Ltd); (d) capping per-sector redundancy.
- Moderate-distinctiveness names kept anyway (CESC, NHPC, NMDC, Oil India, Lupin,
  Aarti Industries, Blue Star, Federal Bank) since the exact-quoted-legal-name +
  `sourcecountry:IN` query should filter most false-positive collisions; flagged
  for extra scrutiny at the Phase 2 qualitative spot-check rather than excluded.
- Final universe at this stage: 40 tickers, 12 sector buckets, well above the ≥6
  minimum. Written to `data/universe.csv`.
- Coverage pull throughput: GDELT rate-limits hard enough that `01_coverage.py`
  (25s/call + backoff) processes ~6-13 ticker-years/hour, not the ~144/hour a naive
  cadence implies — dominated by 429 backoff. Script caches every response
  immediately so it's resumable across session boundaries.
- Crash bug found+fixed mid-run: `call_with_retry` only retried HTTP 429 and
  connection errors; at ticker 27/40 (SAIL) a 200-with-invalid-body response raised
  an uncaught `JSONDecodeError` and killed the process (63/120 ticker-years already
  cached, no data lost, manual relaunch needed). Fixed by also retrying HTTP 5xx and
  JSON-decode failures.
- **SAIL and BHEL dropped from the universe**: both failed all fetch attempts
  across three separate runs (18 attempts each), including an isolated first-request
  run, ruling out queue-position rate pressure as the cause. Root cause not
  conclusively identified (likely IP-level throttle hardened over ~6h continuous
  querying). Per rule 3 (fail loudly, don't fabricate) and the same drop-and-log
  precedent as HANDOVER's Phase 3 price-integrity rule, both removed. **Final
  universe: 38 tickers** — sector spread unaffected (still >6 sectors; SAIL was the
  sole Steel & Iron entry, BHEL the sole Industrial-Equipment entry, 11 other
  buckets remain).
- Coverage gate result (38 tickers, complete 3-year data): median nonzero-volume
  days/year = 104.5, well above the ≥30 threshold. **GATE: PASS.** No universe-shift
  interruption needed (HANDOVER's escalation path only triggers on gate *failure*).
- Query construction: `("<company>" OR "<alias1>" OR ...) sourcecountry:IN` when
  aliases exist, else just `"<company>" sourcecountry:IN`; GDELT requires OR'd terms
  parenthesized (unparenthesized returns a plain-text 200 error, not JSON).

## Topic: Phase 2 — Event extraction
**source:** `DECISIONS.md`
- Event detection is all-or-nothing per ticker by design (`02_events.py::load_series`
  requires all 3 years of a series cached, else skips the ticker entirely rather than
  computing partial-year z-scores). First full run under-counted events (165, from
  only 19/38 tickers with complete tone data) before two gap-fill passes brought all
  38 to complete coverage, raising the count to 242. Rule: never treat an event count
  as final while any ticker shows "SKIP" in the run log.
- **Final event count: 242 events across 28 of 38 tickers** (10 tickers had zero
  qualifying spike days — expected, confirmed via zero SKIP lines and 114/114 tone
  files cached). Primary threshold used; pre-registered fallback NOT triggered. Gate
  (≥150): PASS, confirmatory. Direction split: 154 tone-positive, 88 tone-negative.
- Qualitative spot-check of the 20 largest spikes (`data/event_samples.csv`): large
  majority genuine, identifiable, company-specific news (earnings: PIIND, ICICIGI,
  COLPAL×2; corporate action: BHARATFORG/Rolls-Royce, MPHASIS/Blackstone; accident:
  COROMANDEL ammonia leak; crisis: CESC/Kolkata electrocution deaths; geopolitical:
  NHPC/Indus Waters Treaty; real estate: GODREJPROP/Noida). 5/20 returned no articles
  (sampling gap, not evidence of spurious event). **2-3/20 show market-wide-roundup
  contamination**: LICHSGFIN (generic "buy calls vanishing" story), M&MFIN (mixed
  relevance), OIL (about IOC/GAIL/ONGC, likely a multi-PSU roundup) — direct evidence
  the cross-sectional clustering risk HANDOVER §4.7 anticipated is real in this
  dataset, not just theoretical.
- Stray autonomous commit (`f2844ca`, non-conforming message style) appeared
  mid-Phase-2 from an overstepping background check-in, captured a stale draft;
  never pushed, undone via `git reset --soft HEAD~1`, redone properly once complete.

## Topic: Phase 3 — Prices
**source:** `DECISIONS.md`
- Price fetch clean on first pass — yfinance hit no rate limiting; batch-downloaded
  all 38 tickers + `^NSEI` in one `yf.download()` call. All 38 + benchmark passed
  integrity checks (full 2022-07-01→2026-01-31 coverage, 0 non-positive closes, 0
  extreme single-day moves >50% log-return) — **no tickers dropped**.
- Integrity criteria (`03_prices.py`): drop if first/last trading day not within 21
  days of window bounds, row count >5% below `^NSEI`'s, or any non-positive close.
  Extreme moves reported but don't auto-drop (could be a real shock).
- `missing_pct` small negative values (~-0.1%) are cosmetic (ticker had 1 extra
  trading day vs `^NSEI`'s own calendar), not missing data.

## Topic: Phase 4 — Event study
**source:** `DECISIONS.md`
- All 242 events got a full 120-observation estimation window, zero market-adjusted
  fallbacks needed. Only one NaN: NATIONALUM's 2025-12-31 event lacks 20 forward
  trading days within the fetched price range to compute CAR_t20 — flagged, not
  dropped or fabricated.
- Followed HANDOVER.md's phase numbering, not ARCHITECTURE.md's collapsed "Phase 4:
  VALIDATION CORE" label — `04_event_study.py`/`05_inference.py` committed as
  separate `phase 4`/`phase 5`. Momentary mislabeling in conversation, corrected
  before committing, no code impact. (See `INGEST-CONFLICTS.md` INFO-4.)
- Permutation engine uses closed-form rolling OLS (not per-event refit) for the
  ~242,000 pseudo-event recomputations; validated to floating-point precision
  against the per-event `lstsq` output. Runtime ~35s.
- Permutation null construction: per ticker, real events' tone_z/direction paired
  with freshly-drawn pseudo-event dates (same count, drawn without replacement,
  excluding ±5 trading days around real event entry dates) — holds tone-marginal
  fixed while randomizing timing.
- Tone-tercile spread secondary test reuses fixed tercile membership (from real
  tone_z) applied to each permutation's pseudo-CAR_t5.
- Robustness pass (pre-registered, one pass): (a) fallback threshold n/a (primary
  already cleared gate); (b) market-adjusted (β=1) reported for transparency
  (p=0.833) but not a like-for-like null comparison; (c) drop days with >3
  simultaneous tickers — 0 days met the threshold (max observed = exactly 3), so
  declustered and non-declustered results are identical.
- **VERDICT: NULL.** Primary test: mean(sign(tone_z)×CAR_t5) = -0.00151, one-sided
  permutation p=0.763 (wrong sign relative to thesis). No secondary survives
  BH-FDR at q=0.10 (best secondary p=0.238, abs_CAR_t1_vs_null). Robustness pass
  doesn't change the conclusion. Per HANDOVER §4.8: "no detectable edge under this
  specification." Full detail: `results/stats.json`.

## Topic: Phase 6 — Report figures
**source:** `DECISIONS.md`
- Raw null distributions persisted retroactively (`results/null_distributions.csv`)
  so figures plot actual null draws, not approximations; re-run reproduced
  `stats.json` byte-for-byte (seed=42, confirmed via `git diff`).
- Chart design: project dataviz skill invoked, adapted to static-PNG-only
  constraint; diverging palette (blue `#2a78d6`/red `#e34948`, gray midpoint) for
  polarity encodings. Three figures: primary null histogram w/ observed marker,
  tone-signed CAR observed-vs-null across horizons, CAR_t5 by tone tercile
  (clearest single visual of the "wrong sign" finding).

## Topic: Phase 5 (post-v0.1, override) — Live pipeline build
**source:** `DECISIONS.md`
- `11_daily_events.py` bug caught pre-commit: empty-DataFrame `.dt.date` access
  crashed on first-run-with-no-previous-file; fixed by skipping `.dt` access when
  no previous file exists.
- First live gap-fill was ~6 months (historical data ends 2025-12-31; "yesterday"
  relative to 2026-07-09 is mid-2026), hit the same GDELT throttling as the
  original historical pulls; took 3 passes to close. Expected, one-time.
- Live event count (275 across 29 tickers) differs from the locked study (242
  across 28) — expected: live store extends 6 months past the locked 2025-12-31
  cutoff. `data/live/events.csv` and `data/events.csv` are deliberately separate.
- Idempotency verified directly: re-running both live scripts back-to-back
  reports "nothing new"/"0 new events" correctly.
- `daily.yml` verified end-to-end via manual `workflow_dispatch` (run
  29013080177) on real Actions infrastructure, not just locally.

## Topic: Phase 6 (post-v0.1, override) — NULL-mode scoring
**source:** `DECISIONS.md`
- Verdict-branch guard is a hard `sys.exit`, not a comment: `06_scoring.py` refuses
  to run if `results/stats.json`'s verdict is ever anything other than NULL.
- Claims-audit gate enforced by assertion: `score_null_mode` asserts no `CAR_t*`
  column is present before scoring (code-level guarantee against regression).
- Intensity percentile anchored to v0.1's locked historical `vol_z` distribution
  (242 events), not the growing live table, to keep score meaning stable over time.
- Novelty = per-ticker days-since-last-event within the live cumulative table;
  `NaN` (not 0) for a ticker's first-ever recorded event.
- **Optional LLM enrichment (ARCHITECTURE §8) explicitly not built** — separately
  banned, needs its own override, not requested. (See `INGEST-CONFLICTS.md` INFO-1.)
- Updated `daily.yml` (with scoring step) re-verified via a second manual
  `workflow_dispatch` (run 29013524905).

## Topic: Phase 7 (post-v0.1, override) — Public site
**source:** `DECISIONS.md`
- Implementation choice: **Jinja2 + static HTML, not React** (ARCHITECTURE's
  option A, not B) — keeps the stack Python-only, no Node/npm toolchain for a
  site with no interactivity beyond nav + static charts. (See `INGEST-CONFLICTS.md`
  INFO-1.)
- GitHub Pages hosting: classic branch-based (`main`/`docs`), not Actions-based
  deployment — simpler, no separate Pages environment/permissions needed.
  Deviates from ARCHITECTURE's suggested `site/` path (GitHub's branch-based Pages
  only serves repo root or `/docs`) — logged rather than silently renamed.
- Charts: matplotlib PNGs embedded per ticker page, event days overlaid as thin
  vertical lines (green = positive tone, red = negative tone).
- Design treatment: editorial (portfolio-facing, meant to be shared), not a
  generic dashboard template — artifact-design skill invoked for process;
  typography Newsreader/IBM Plex Sans/IBM Plex Mono (avoiding "generic AI look"
  Inter/Space Grotesk); amber/ink color identity continued from report figures.
- Hero copy framing: since verdict is NULL, homepage explicitly frames the live
  feed as "an instrument that watches constantly and, so far, correctly reports
  nothing" rather than downplaying the null result.
- Live feed shows intensity + tone direction only, never a forward-return number —
  same claims-audit constraint restated in page copy itself.
- `docs/` committed to git (required for classic Pages) and rebuilt from scratch
  each run (`shutil.rmtree` + regenerate), matching "recompute over append."

## Topic: Phase 8 (post-v0.1, override) — Hardening
**source:** `DECISIONS.md`
- Freshness guard is a hard build failure (`sys.exit(1)`), not a banner:
  `12_build_site.py` checks max live-price date vs today (UTC), fails if >4
  calendar days stale (not ARCHITECTURE's literal 3 — 4 avoids a routine
  Friday→Monday weekend gap tripping the guard weekly). Footer shows "data
  current through {date}" separately from "built {time}."
- Data growth policy: documented, not implemented — live store ~2.5MB, growing
  ~115 rows/day; reaching ARCHITECTURE's 500MB compaction threshold would take
  decades at this rate. Revisit if `du -sh data/live/` approaches low hundreds of MB.
- NSE bhavcopy fallback: deliberately not implemented — couldn't confirm current
  URL/format with confidence (NSE changed format in 2024 per public reports;
  direct fetch timed out, consistent with known bot protection). Building it
  half-verified risks either silent breakage or scraping-evasion behavior that
  edges toward the "no scraping beyond GDELT" ban. yfinance has had zero failures
  across Phases 3, 5-8 — the practical case for this fallback is thin. Deferred.
- `daily.yml` with all Phase 8 additions verified via a third manual
  `workflow_dispatch` (run 29027636821); alert step correctly no-op'd on absent
  Telegram secrets rather than erroring.
- **v1.0 tag not cut yet**: requires (a) 14 consecutive unattended cron runs
  (cron only just started, needs ~2 weeks to accumulate honestly) and (b) outreach
  to ≥3 real humans (Vivek's task). All Phase 5-8 infrastructure built/tested/live
  as of this entry; tagging early would violate the project's own phase-gate
  discipline.

## Topic: Post-Phase-8 production bug — `parse_timeline` sub-daily buckets (2026-07-11)
**source:** `DECISIONS.md`
- Cron run 29139679607 failed (2026-07-11 04:29 UTC) — first cron run to hit a
  genuine 1-day incremental gap rather than the multi-month backfill Phases 5-8
  were tested against. Reset the 14-consecutive-run counter to zero (1 clean run,
  2026-07-10, before this).
- Root cause (confirmed empirically): GDELT's timeline modes auto-select bucket
  resolution by query span — multi-year queries return one daily bucket
  (`T000000Z` only); short-span queries return 15-minute buckets. `parse_timeline`
  hardcoded midnight-only parsing, crashed with `ValueError` on the first
  non-midnight bucket. Crash was pre-write (no bad data written) — "fail loudly,
  don't corrupt" worked as intended.
- Fix: parse full timestamp, group by calendar date, aggregate (`sum` for vol,
  `mean` for tone — an approximation for tone since GDELT doesn't expose per-bucket
  article counts to weight by; exact for the historical/daily-bucket path).
- Verified against the real gap locally, then on real scheduled cron runs: fix
  deployed ~10:16 UTC 2026-07-12 (that day's earlier scheduled run still failed,
  pre-fix); next two scheduled runs (07-13, 07-14) succeeded. Clean-run count
  toward the 14-run gate: 2 as of 2026-07-14.
- Runtime risk found+mitigated: GDELT throttling severity trending up sharply
  (38-40min pre-fix runs → 4-6h post-fix, all in retry backoff, not new bugs),
  approaching Actions' 6h job timeout. Reduced `MAX_ATTEMPTS` from 6 to 3
  (worst-case backoff chain 630s→180s, ~3.5x cut) — affects only the live
  incremental path, not the historical bulk-pull scripts.

## Topic: First regression test suite (2026-07-14, post-council review)
**source:** `DECISIONS.md`
- Zero automated tests existed anywhere before this — flagged by a local-council
  review as the single most actionable gap (both production bugs found that week
  live in `10_daily_ingest.py`, the untested subsystem).
- Framework: stdlib `unittest`+`unittest.mock`, not pytest — zero new dependencies,
  consistent with "prefer boring" and the allowed-stack discipline.
- Fixtures are real, not synthetic: a trimmed real historical-cache slice plus full
  copies of two real GDELT responses captured during that week's own incident
  investigation — no fabricated JSON anywhere.
- Negative-control validated: fixture reproducing the original crash confirmed to
  still fail against the pre-fix logic, then confirmed to pass against the fix.
- `call_with_retry` tests mock `requests.get`/`time.sleep` (standard network-fault
  simulation, not the kind of fabricated market/news data rule 3 bans). Covers all
  four of the project's real production failure modes. 11 tests, ~0.09s.
- Scope deliberately limited to `10_daily_ingest.py` (highest-leverage, twice-broken,
  touches a live external API) — pure-local-computation scripts are lower risk,
  candidate for a follow-up pass.

## Topic: Retroactive power/MDE analysis (2026-07-16, post-council review)
**source:** `DECISIONS.md`
- Added `07_power_analysis.py` as a retroactive addendum, not a respecification —
  computes the detectable effect size the already-run primary test *could* have
  found, using only already-locked data and the pre-registered alpha. Not gated by
  asking Vivek first (none of rule 5's three interrupt conditions apply).
- SE estimated two ways (empirical permutation-null std 0.002244; parametric
  cross-check 0.002407), agreeing within 7%.
- Result: a well-powered null, not an ambiguous one — MDE at 80% power = 0.56%
  tone-signed CAR_t5 at n=242; achieved power >99.8% for any true effect ≥1%,
  ~72% even at 0.5%. Added directly to the README's Results section.
- Caveated: assumes independence across events; disclosed cross-sectional
  clustering would inflate true SE, making this MDE optimistic, not pessimistic.
- Illustrative benchmark effect sizes (0.5%-3%) explicitly labeled as round-number
  benchmarks, not literature-sourced magnitudes (no citation available).

## Topic: Four cheap fixes from council review (2026-07-16)
**source:** `DECISIONS.md`
- `requirements.txt` pinned to exact versions taken from the most recent successful
  CI run's actual `pip install` output (not the local dev environment's versions,
  which differed: local pyarrow 24.0.0/yfinance 1.4.1 vs CI-proven 25.0.0/1.5.1).
- GDELT rate-limit story surfaced in the README's Live pipeline section, not just
  git history.
- 14-consecutive-run gate's reset semantics clarified in `ARCHITECTURE.md` §1:
  explicit hard reset to zero on any scheduled failure, not a rolling window.
- Data-provenance sentence added to README Limitations: acknowledges published
  tone/volume signals concern identifiable people/companies via GDELT aggregation
  of public coverage — nothing illegal/unusual, but worth stating for an
  ONS-style audience.

## Topic: Live pipeline scope decision + gate decoupling (2026-07-16, Vivek's call)
**source:** `DECISIONS.md`
- Live pipeline stays in scope, not frozen/dropped, despite a local-council
  "Simplicity Champion" argument that it's scope creep that doesn't strengthen
  the NULL finding. Decision: keep it — a DBT Python Developer role is
  specifically about production data-pipeline engineering, and the live pipeline
  (two real bugs found/fixed/regression-tested, retry logic tuned under real
  load, honestly logged) is the strongest evidence for that audience. Stays
  *secondary* to the study, per the README's existing framing.
- Outreach (≥3 real humans) explicitly decoupled from the 14-consecutive-run gate
  — the study/site have been complete and honest since the NULL verdict locked
  (2026-07-09); no reason outreach should wait on an unattended-cron reliability
  metric unrelated to analysis soundness. The `v1.0` git tag still waits for the
  14-run gate (that tag *is* the "pipeline proven unattended" milestone). Practical
  effect: outreach is unblocked now, independent of run count (4/14 as of the
  entry date).

## Topic: Third production bug — phantom-day rows (2026-07-16)
**source:** `DECISIONS.md`
- Found during an adversarial code review of the session's own work, not from a
  failed cron run. GDELT's `enddatetime` is inclusive, not exclusive as
  `fetch_gap`'s docstring assumed — a query for `[gap_start, target_date+1)`
  actually returns data through `target_date+1`'s exact midnight (one boundary
  bucket). After the `parse_timeline` fix started successfully grouping sub-daily
  buckets, that boundary instant became a full-but-near-meaningless row for
  `target_date+1`, advancing the store's `date.max()` past what was actually
  fetched — the next run's gap check then permanently skipped that day's real
  data (oscillating day-to-day, ~every other day for an affected ticker).
- New regression, not pre-existing: the old crashing `parse_timeline` never lived
  long enough to reach this code path; could only start corrupting data from
  2026-07-12 onward (first live post-fix run).
- Confirmed live in production before fixing: `volume_daily.parquet` showed
  BIOCON frozen at max-date 2026-07-14 (value 0.0); the 2026-07-15 cron log shows
  zero "fetching BIOCON vol" lines — silently skipped. 19 of 38 tickers affected.
- Fix: `fetch_gap` now filters to `df["date"] < end_date` before returning — fixed
  in `fetch_gap`, not `parse_timeline`, since the exclusivity contract belongs to
  the caller constructing the query range (parse_timeline is shared with the
  historical bootstrap path, which has no reason to know about it).
- Repair: truncated rows `date >= 2026-07-10` from both live parquet files
  (93+90 rows, 19 tickers), re-ran normal ingest; recompute-over-append naturally
  refetched the enlarged gap with fixed code. Verified: zero rows beyond the run's
  own target_date post-repair.
- Regression test added (`FetchGapBoundaryTests`), negative-control validated
  (pre-fix logic returns the phantom row; post-fix excludes it). 12 tests total.
- Process note: produced no exception, no failed run — degraded data quality
  silently, likely uncaught by monitoring alone; found only because Vivek asked
  for a general adversarial code-review pass.

---

## Topic: Parking lot (out-of-scope ideas, banned-item log, and override log)
**source:** `PARKING.md`
- Parked, untouched until v0.1 tags: LLM analysis cascade (Claude API pipeline for
  event scoring); Gemma fine-tune; React dashboard; Lightpanda/scraping beyond
  GDELT API; GKG themes/entity linking; additional markets beyond NSE;
  calendar-time portfolio methods (proper clustering correction); live
  alerting/prediction; FastAPI service.
- `ARCHITECTURE.md` v1.0 roadmap (2026-07-07, pasted by Vivek) logged here as
  re-proposing already-banned items (live alerting, LLM cascade, React dashboard,
  CI beyond trivial lint) via its Phases 5-8; its Phases 0-4 are noted as a
  "compatible restatement of HANDOVER.md's existing phases" needing no override.
- **OVERRIDE HANDOVER (2026-07-09), scope: Phase 5 only** — Vivek explicitly said
  "override handover" (via an AskUserQuestion option worded exactly that way) to
  proceed with the live pipeline (GitHub Actions cron, daily unattended ingest)
  despite it reintroducing the "CI beyond a trivial lint" and "live
  prediction/alerting" bans. Phases 6-8 remain parked, each needing its own
  override.
- **OVERRIDE HANDOVER (2026-07-09), scope: Phase 7 only** — same mechanism,
  specifically for the public GitHub Pages site, reintroducing the "React or any
  web dashboard" ban. LLM enrichment (Phase 6 optional) and Telegram alerts
  (Phase 8) remain un-overridden.
- **OVERRIDE HANDOVER (2026-07-09), scope: Phase 8 in full, including Telegram
  alerts** ("keep going override," confirmed via AskUserQuestion). LLM enrichment
  (Phase 6 optional) remains the one still-parked, un-overridden item — not
  requested, not built.
- Phase 5 (post-override) decisions: v0.1's locked artifacts (`data/events.csv`,
  `data/car_by_event.csv`, `results/stats.json`, etc.) are never touched by the
  live pipeline — it gets its own namespace (`data/live/`, `data/live_events.csv`).
  `.gitignore` narrowed (from a blanket `*.parquet`/`data/raw/` rule) to exclude
  only `data/prices.parquet` and `data/raw/`+`data/live/raw/` — `data/live/*.parquet`
  is now tracked, since Actions' ephemeral runners need it to survive between runs.
  Bootstrap strategy: seed the live parquet store from the local historical raw
  JSON cache once, rather than re-fetching 3 years through the rate-limited API.
  First real run has a ~6-month gap (historical data ends 2025-12-31, "yesterday"
  relative to 2026-07-09 is mid-2026) — expected, one-time, self-limiting.
