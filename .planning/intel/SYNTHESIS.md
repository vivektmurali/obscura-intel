# Synthesis Summary

Mode: `new`. Source: `.planning/intel/classifications/*.json` (5 classification
files, each pointing at one repo-root doc).

## Doc counts by type
- ADR: 2 — `HANDOVER.md` (locked, precedence 0), `PREREGISTRATION.md` (precedence 0;
  see classification-note caveat below)
- SPEC: 1 — `ARCHITECTURE.md` (precedence 1)
- PRD: 0
- DOC: 2 — `DECISIONS.md`, `PARKING.md` (both precedence 3)

All 5 classifications were `high` confidence. No `UNKNOWN`/low-confidence docs.

## Decisions locked
2 ADR sources, both `precedence: 0`:
- `HANDOVER.md` — `locked: true` in the classifier's structured field. Locks the
  v0.1 mission, research design (universe, event definition, timestamp/lookahead
  rule, market-model returns, permutation inference + kill criteria), the hard
  scope ban list (§5), the allowed stack, and the phase-by-phase execution
  discipline.
- `PREREGISTRATION.md` — `locked: false` in the structured field, but the
  classifier's own note flags this as a strict-taxonomy artifact (no explicit
  "Status: Accepted" marker) and recommends treating it as a de facto
  high-precedence locked-methodology source regardless. This synthesis followed
  that recommendation (see `decisions.md` and `INGEST-CONFLICTS.md` INFO-4).
  Records the final, results-bearing methodology: 38-ticker universe, 242 events
  across 28 tickers, sample-size gate PASS (confirmatory), NULL verdict inputs.

Full entries: `.planning/intel/decisions.md`.

## Requirements extracted
0. No PRD-type documents were present in this ingest batch. `requirements.md`
   is written but intentionally empty, with a note explaining why and how to
   populate it if a future ingest batch adds a PRD.

## Constraints
1 SPEC source (`ARCHITECTURE.md`), broken into 11 sub-constraint entries (C1-C11)
spanning: the v1.0 "shipped" gate checklist, zero-server/recompute-over-append
design principles, data-provenance rules, the final stack table, repo layout,
the 9-phase roadmap (0-8), the SIGNAL/NULL claims policy, the gated LLM-enrichment
policy, risk table, and the deadline timeline. Type breakdown: this SPEC spans
architecture/nfr/roadmap/protocol content in a single document — recorded as one
source with 11 labeled sub-entries rather than forced into a single taxonomy tag.

Full entries: `.planning/intel/constraints.md`.

## Context topics
2 DOC sources (`DECISIONS.md`, `PARKING.md`), organized into 23 topic blocks: 10
phase-by-phase implementation-decision topics (Phases 0-8, including two
post-v0.1-override sub-phases each for Phases 5-8), 4 named post-v0.1 incident/
review topics (parse_timeline bug, regression test suite, power/MDE analysis,
"four cheap fixes," scope-decision + gate-decoupling, phantom-day bug — see file
for exact list), plus 1 parking-lot/override-log topic from `PARKING.md`.

Full entries: `.planning/intel/context.md`.

## Conflicts
- **0 blockers.** No LOCKED-vs-LOCKED ADR contradictions (the two precedence-0
  ADRs are consistent — `PREREGISTRATION.md` instantiates `HANDOVER.md`'s design,
  doesn't compete with it); mode is `new` so no existing-CONTEXT.md check applied;
  cycle detection ran clean (dense mutual cross-referencing among the 5 docs, no
  supersession-type cycle); no low-confidence-UNKNOWN docs.
- **0 competing-variants (warnings).** No PRD documents in this batch.
- **5 auto-resolved (info).** All concern `ARCHITECTURE.md` (SPEC, precedence 1)
  content that either reintroduces or restates something already governed by the
  higher-precedence `HANDOVER.md`/`PREREGISTRATION.md` ADRs: (1) SPEC-proposed
  Phases 5-8 vs the locked ADR ban list — resolved via three explicit, scoped
  "override handover" invocations logged in `PARKING.md` (LLM enrichment remains
  the one un-overridden, unbuilt exception); (2) the SPEC's React-site option was
  never exercised (Jinja2 chosen instead); (3) "~40 tickers" (ADR/SPEC) vs the
  executed 38 (ADR/DOC) — a documented data-availability drop, not a contradiction;
  (4) `PREREGISTRATION.md`'s `locked: false` field is a classification-strictness
  artifact, not a signal it's safely overridable; (5) SPEC's collapsed phase
  numbering vs the ADR's original two-phase split — ADR numbering was what got
  built.

Full report, with `source:` citations for every claim: `.planning/INGEST-CONFLICTS.md`.

## Pointers
- Decisions: `.planning/intel/decisions.md`
- Requirements: `.planning/intel/requirements.md` (empty — no PRDs this batch)
- Constraints: `.planning/intel/constraints.md`
- Context: `.planning/intel/context.md`
- Conflicts report: `.planning/INGEST-CONFLICTS.md`
