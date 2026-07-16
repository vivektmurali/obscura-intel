# Decisions (synthesized from ADR-classified sources)

Precedence: ADR=0 (default), per-doc override may apply (see each entry). Two ADR
sources were classified in this ingest batch: `HANDOVER.md` (explicitly `locked: true`)
and `PREREGISTRATION.md` (`locked: false` in the classifier's structured field, but
flagged by the classifier's own note as a de facto locked-methodology commitment —
see "Classification caveat" under its entry below). Both carry `precedence: 0`
(highest, tied with each other).

---

## ADR-1: OBSCURA INTEL — v0.1 HANDOVER

- **source:** `HANDOVER.md`
- **status:** locked (`locked: true`, `precedence: 0`)
- **scope:** Obscura Intel v0.1 mission, NSE mid/small-cap ticker universe, GDELT DOC 2.0 event ingestion, event/spike-detection methodology, abnormal-returns market model, permutation-null inference + FDR correction, pre-registration and kill criteria, phase-by-phase execution plan, hard scope ban list, CLAUDE.md standing rules.

**Decision statement (locked, binding, changes require Vivek's explicit override):**

1. **Mission:** build v0.1 as a rigorous event study (not a predictor/trading system). Question under test: do news-volume spike events in NSE mid/small-cap names carry abnormal forward returns, in the direction of news tone, after the event is publicly observable? A well-executed NULL result is a full success.
2. **Universe (§4.1):** ~40 tickers from current Nifty Midcap 100 + Nifty Smallcap 100 constituents; filters: name distinctiveness as an English search string, spread across ≥6 sectors, usable Yahoo Finance `.NS` daily history. Survivorship bias from using current constituents is a disclosed, accepted limitation. Output: `data/universe.csv`.
3. **Study period (§4.2):** events 2023-01-01→2025-12-31; prices 2022-07-01→2026-01-31.
4. **Event data (§4.3):** GDELT DOC 2.0 API (`timelinevolraw`, `timelinetone`, `artlist`), no key required; ≥5s sleep between calls (later revised — see `DECISIONS.md` Phase 0/1 notes in context.md); every raw response cached to `data/raw/` (gitignored); JSON shapes verified empirically in Phase 0, never guessed.
5. **Event definition (§4.4):** `vol_z(t)` and `tone_z(t)` via trailing 90-day window (day t excluded); event day = `vol_z ≥ 3` AND `v_t ≥ 5`; consecutive event-day runs merged to first day; direction proxy = `sign(tone_z)`. Pre-registered fallback (usable at most once, only if total events < 150): `vol_z ≥ 2` AND `v_t ≥ 3`.
6. **Timestamp/lookahead rule (§4.5, "the single most important rule"):** entry point = close of the first NSE trading day strictly after the event's UTC date. Nothing from the event day itself is ever used as a tradeable price. No exceptions.
7. **Abnormal returns (§4.6):** daily log returns, adjusted prices (`yfinance`, `auto_adjust=True`); benchmark `^NSEI`; market model = OLS over 120-trading-day estimation window ending 21 trading days before entry, ≥90 valid observations required else fall back to market-adjusted (β=1) and flag the event; horizons t+1, t+5, t+20.
8. **Inference (§4.7):** permutation null, 1,000 draws per ticker (pseudo-events drawn from that ticker's trading days, excluding ±5 trading days around real events). Primary test (the one confirmatory number): one-sided permutation p<0.05 on mean(sign(tone_z) × CAR(t+5)). Secondary tests (BH-FDR q=0.10): tone-signed CAR at t+1/t+20; mean |CAR| vs null at each horizon; top-vs-bottom tone-tercile CAR(t+5) spread. Clustering caveat disclosed; one robustness pass drops calendar days with >3 simultaneous-ticker events. Sample-size gate: ≥150 events required for confirmatory status.
9. **Kill criteria (§4.8, pre-registered, binding):** primary fails (p≥0.05) AND no secondary survives FDR → verdict "no detectable edge under this specification," stated plainly in the README; v0.1 still ships and tags. No respecification after results are seen — exactly one pre-registered robustness pass permitted (fallback threshold / market-adjusted returns / clustering-drop); anything else is exploratory and separately labeled. `PREREGISTRATION.md` must be committed at end of Phase 2, before any price data is joined to event data.
10. **Hard scope ban list (§5, binding until v1.0 phase gates in ARCHITECTURE.md unban specific items post-Phase-4 — see constraints.md):** live prediction/alerting; Claude API or any LLM calls in the pipeline; Gemma fine-tuning; React or any web dashboard; FastAPI/servers/ngrok; Lightpanda or scraping beyond the GDELT API; Neo4j/FAISS/vector stores; databases (SQLite only if genuinely needed, flat files preferred); Docker; CI beyond a trivial lint; broker/trading integration; any synthetic or simulated data fallback. Override mechanism: Vivek must say the literal phrase "override handover"; any override is logged in `DECISIONS.md`.
11. **Allowed stack (§5, complete, locked):** Python 3.11+, `requests`, `pandas`, `numpy`, `scipy`, `statsmodels`, `yfinance`, `matplotlib`, `pyarrow`. CLI scripts + CSV/parquet + PNG figures. Nothing else without a `DECISIONS.md` entry.
12. **Standing rules (§8, written into `CLAUDE.md`):** execute everything (never mark done without running); commit+push every phase minimum; no synthetic data ever; scope police (§5 binding, "override handover" phrase required); decide autonomously and log non-obvious choices (interrupt Vivek only for: universe change after a failed coverage gate, any change to §4.7-4.8 kill criteria, scope overrides); prefer boring (flat scripts, no classes/config frameworks); honesty over momentum (null results stated as null); terse/direct/technical tone, one question at a time with a proposed default.
13. **Phase plan (§7):** Phase 0 repo+smoke test (gate) → Phase 1 universe+coverage → Phase 2 event extraction + preregistration commit → Phase 3 prices → Phase 4 event study → Phase 5 inference → Phase 6 report+tag `v0.1`. Every phase: run → inspect → commit → push; a phase without a pushed commit did not happen.

---

## ADR-2: Pre-registration — Obscura Intel v0.1 event study

- **source:** `PREREGISTRATION.md`
- **status:** `locked: false` per classifier's structured field, `precedence: 0` (per-doc override, tied with HANDOVER.md)
- **scope:** event study methodology instantiation — final universe, GDELT event detection thresholds, entry/return calculation, primary/secondary hypotheses, permutation test, robustness plan, kill criterion, sample-size gate, event-clustering caveat.

**Classification caveat (carried forward from the classifier, not resolved by the synthesizer — flagging for downstream awareness):** the classifier's `precedence`/`locked` fields were populated per strict ADR-taxonomy rules (no explicit "Status: Accepted" marker → `locked` conservatively left `false`), but the classifier explicitly notes this document's own language ("Committed before any join of event data to price data... Hash cited in README," gate-pass results already recorded as final) makes it function as a de facto locked commitment — structurally closer to a locked specification/pre-registered protocol than a conventional ADR. **This synthesizer treats `PREREGISTRATION.md` as a high-precedence, effectively-locked methodology source, on par with `HANDOVER.md` (both `precedence: 0`), for conflict-detection purposes** — i.e., a future document contradicting either is evaluated as contradicting a top-precedence, hard-to-override source. No LOCKED-vs-LOCKED contradiction was found between these two documents (see `INGEST-CONFLICTS.md` INFO-3).

**Decision statement (final, results-bearing instantiation of ADR-1's design):**

1. **Universe, final:** 38 NSE tickers (not ~40 — see `INGEST-CONFLICTS.md` INFO-2). Two originally-selected tickers (SAIL, BHEL) dropped after persistent GDELT fetch failures across three retry passes — a data-availability drop, not a universe redesign, occurring before any event detection ran. Full list: `data/universe.csv`; rationale/exclusions: `DECISIONS.md`.
2. **Event definition, as executed:** primary threshold (`vol_z ≥ 3`, `v ≥ 5`) applied to complete 2023-2025 volume/tone data for all 38 tickers produced **242 events across 28 tickers** (10 tickers had zero qualifying spike days). Comfortably above the 150-event gate. **Fallback threshold: NOT used.**
3. **Entry rule, returns, primary/secondary hypotheses, robustness list, kill criterion:** identical to ADR-1 §4.5-4.8 (restated verbatim in this document, not altered).
4. **Sample-size gate result:** 242 events ≥ 150 → **GATE PASS, confirmatory status** (this is a recorded outcome, not just a threshold restatement).
5. **Clustering caveat, empirically corroborated:** the Phase 2 qualitative spot-check of the 20 largest spikes found 2-3 of 20 events where sampled headlines were generic market-wide roundups rather than company-specific news (see `DECISIONS.md` Phase 2, and `context.md`) — the pre-registered robustness pass exists partly to address exactly this, now with direct evidence it's a real (not just theoretical) risk in this dataset.

---

**Note on downstream ADR-adjacent content:** `ARCHITECTURE.md` (classified `SPEC`, `precedence: 1`) contains its own binding "design principles" and a "claims policy" that function like decisions but are lower-precedence per this doc set's classification. They are recorded in `constraints.md`, not here, per the type-routing rule — but see `INGEST-CONFLICTS.md` for where SPEC-level content conflicts with the ADR decisions above and how it was resolved.
