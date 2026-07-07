# Obscura Intel — standing rules

This project follows `HANDOVER.md` exactly. Read it in full before doing anything. Phase-by-phase; do not skip ahead.

## Rules

1. **Execute everything.** Never write a script and move on without running it in this session. Never mark anything done that hasn't run.
2. **Commit + push every phase, minimum.** Conventional messages (`phase N: ...`). A session that ends without a push must end with an explicit warning to Vivek.
3. **No synthetic data, ever.** If an API fails, fail loudly, cache what you have, and stop. Fabricated/simulated fallback data is the project's historical failure mode and is banned.
4. **Scope police.** HANDOVER.md §5 ban list is binding. Out-of-scope ideas (Vivek's or Claude's) get one line in `PARKING.md`, nothing more. If Vivek insists on a banned item: require the phrase "override handover."
5. **Decide autonomously, log it.** Implementation details (parsing, chunk sizes, plotting) are Claude's call — record non-obvious choices in `DECISIONS.md`. Interrupt Vivek only for: (a) universe change after a failed coverage gate, (b) any change to §4.7–4.8 kill criteria, (c) scope overrides. Everything else: pick a sensible default and log it.
6. **Prefer boring.** Flat scripts over abstractions. No classes where a function does. No config frameworks. This is a study, not a platform.
7. **Honesty over momentum.** If results are null, the README says null. If data quality undermines the test, the README says that. Never soften a finding to make the project look better.
8. **Tone with Vivek:** terse, direct, technical. One question at a time, always with a proposed default.

## Banned (HANDOVER.md §5)

Live prediction/alerting; Claude API or any LLM calls in the pipeline; Gemma fine-tuning; React or any web dashboard; FastAPI/servers/ngrok; Lightpanda or any scraping beyond the GDELT API; Neo4j/FAISS/vector stores; databases (SQLite acceptable only if genuinely needed); Docker; CI beyond a trivial lint; broker/trading integration; any synthetic or simulated data fallback.

## Allowed stack

Python 3.11+, `requests`, `pandas`, `numpy`, `scipy`, `statsmodels`, `yfinance`, `matplotlib`, `pyarrow`. CLI scripts + CSV/parquet + PNG figures. Nothing else without a `DECISIONS.md` entry.

## Phase gate discipline

A phase is not done until: code ran, output was inspected, and a commit was pushed. No other code exists in the repo until the Phase 0 smoke-test commit is pushed.
