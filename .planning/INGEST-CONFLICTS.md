## Conflict Detection Report

Mode: new. Docs classified: 5 (ADR: 2 — `HANDOVER.md`, `PREREGISTRATION.md`;
SPEC: 1 — `ARCHITECTURE.md`; DOC: 2 — `DECISIONS.md`, `PARKING.md`; PRD: 0).
Precedence in force: ADR(0) > SPEC(1) > PRD(3, n/a) > DOC(3), with per-doc
overrides applied exactly as declared in each classification file (`HANDOVER.md`
precedence 0 + locked; `PREREGISTRATION.md` precedence 0; `ARCHITECTURE.md`
precedence 1; `DECISIONS.md` and `PARKING.md` precedence 3).

Cycle detection: ran DFS over the `cross_refs` graph built from all 5
classifications. The graph is densely mutually connected (every doc references
every other doc — expected for a small, coherent project-handover corpus with no
formal `supersedes`/`depends-on` semantics declared by any classifier). No
supersession-type or precedence-order cycle was found; all 5 docs were fully
synthesized. Confidence: all 5 classifications are `high` confidence — no
`UNKNOWN`-low-confidence docs to surface as blockers.

### BLOCKERS (0)

None found. No LOCKED-vs-LOCKED ADR contradictions; mode is `new` so there is no
existing `CONTEXT.md` locked-decision set to check ingest content against; no
cycles; no low-confidence-UNKNOWN classifications.

### WARNINGS (0)

None found. No PRD-type documents were present in this batch, so no competing
acceptance-criteria variants exist to surface.

### INFO (5)

[INFO] Auto-resolved: HANDOVER.md ban list (locked ADR) vs ARCHITECTURE.md
Phases 5-8 (SPEC) — partially overridden, partially still banned
  Found: `ARCHITECTURE.md` (SPEC, precedence 1) proposes Phase 5 (GitHub Actions
  daily cron — reintroduces HANDOVER §5's "CI beyond a trivial lint" and "live
  prediction/alerting" bans), Phase 7 (public GitHub Pages site with a React
  static-build option — reintroduces "React or any web dashboard"), Phase 8
  (Telegram alerts), and an optional Phase 6 LLM enrichment module (reintroduces
  "Claude API or any LLM calls in the pipeline").
  Expected (per default precedence): `HANDOVER.md` (ADR, locked: true,
  precedence 0) bans all of the above outright — SPEC cannot lift an ADR ban by
  simply asserting a later phase gate.
  Resolution actually recorded in the project's own docs: `PARKING.md` shows
  Vivek explicitly invoked HANDOVER §5's own escape hatch — the literal phrase
  "override handover" — three separate times (2026-07-09), each scoped to one
  phase: Phase 5 only, then Phase 7 only, then Phase 8 in full including Telegram.
  `DECISIONS.md` confirms all three were subsequently built (live pipeline, Jinja2
  site not React — see next entry, hardening/alerts). **LLM enrichment (Phase 6
  optional) was never overridden** — `DECISIONS.md` (Phase 6 post-v0.1 entry)
  states explicitly: "Optional LLM enrichment ... is explicitly not built ...
  needing its own override before any of it ... gets touched." → Net resolution:
  ADR ban stands and wins by default synthesis rule for the one item with no
  logged override (LLM enrichment); for the three items with a logged, scoped
  "override handover," the override — not raw precedence — is what authorized
  the SPEC content, and downstream consumers (`gsd-roadmapper`) should treat
  Phase 5/7/8 as authorized-with-override rather than banned, and Phase 6 LLM
  enrichment as still banned/unbuilt.
  Sources: `HANDOVER.md` §5; `ARCHITECTURE.md` §4, §6 Phases 5-8, §8;
  `PARKING.md` (three "OVERRIDE HANDOVER" entries, 2026-07-09);
  `DECISIONS.md` Phase 5/6/7/8 (post-v0.1) entries.

[INFO] Auto-resolved: React-dashboard SPEC option vs locked ADR ban — SPEC's own
listed option never taken
  Found: `ARCHITECTURE.md` §4 and §7 list "React static build" as option B for
  the public site, alongside "Jinja2 → static HTML" as option A — the React
  option, if built, would reintroduce HANDOVER's locked "React or any web
  dashboard" ban even under the Phase 7 override (which authorizes *a* public
  site, not specifically a React one).
  Resolution: `DECISIONS.md` (Phase 7, post-v0.1) explicitly records the choice
  as "Jinja2 + static HTML, not React ... this project's stack is Python-only
  end to end; a React static build would add a whole separate Node/npm
  toolchain ... purely for a site with no interactivity requirements" — option A
  taken, option B never built. No conflict remains in the executed system; noted
  here only so downstream consumers don't mistake `ARCHITECTURE.md`'s SPEC-level
  "either A or B" language as still-open.
  Sources: `ARCHITECTURE.md` §4 (stack table), §7 (Phase 7, implementation
  choice); `DECISIONS.md` Phase 7 (post-v0.1) entry.

[INFO] Auto-resolved: universe size "~40" (ADR/SPEC) vs executed "38" (ADR/DOC)
  Found: `HANDOVER.md` §4.1 specifies "~40 tickers" (approximate) and
  `ARCHITECTURE.md` §6 Phase 1 restates "the 40-ticker universe" as its stated
  objective.
  Expected: `PREREGISTRATION.md` (precedence 0, treated as high-precedence
  locked-methodology per the classification note below) and `DECISIONS.md`
  (Phase 1) both record the final, executed universe as **38 tickers** — SAIL
  and BHEL were dropped after persistent GDELT fetch failures across three
  retry passes, logged as a data-availability drop, not a universe redesign.
  Resolution: not a genuine contradiction — "~40" was always approximate, and
  HANDOVER §8 rule 5's interrupt condition ("universe change after a failed
  coverage gate") does not apply here because the coverage gate itself passed
  (median 104.5 nonzero-volume days/year vs the ≥30 threshold); the drop
  happened for an unrelated reason (per-ticker fetch failure) and was logged
  autonomously per rule 5, not escalated. Flagging as INFO only so
  `gsd-roadmapper` reconciles any downstream "~40 tickers" language against the
  executed 38.
  Sources: `HANDOVER.md` §4.1; `ARCHITECTURE.md` §6 (Phase 1 objective);
  `PREREGISTRATION.md` "Universe" section; `DECISIONS.md` Phase 1 entry.

[INFO] Classification note carried forward, not a contradiction: PREREGISTRATION.md
locked-field ambiguity
  Found: `PREREGISTRATION.md` is classified `type: ADR`, `locked: false`,
  `precedence: 0`, but the classifier's own `notes` field flags that the
  document's language ("Committed before any join of event data to price
  data... Hash cited in README," gate-pass results already recorded as final)
  "suggests it functions as a de facto locked commitment," and recommends the
  synthesizer "treat this as a high-precedence locked-methodology source
  regardless of the strict ADR/locked field values."
  Resolution: this synthesis followed that recommendation — `decisions.md`
  records `PREREGISTRATION.md` as an effectively-locked methodology source on
  par with `HANDOVER.md` (both precedence 0) for conflict-detection purposes.
  No LOCKED-vs-LOCKED contradiction exists between the two (their content is
  consistent — `PREREGISTRATION.md` is a results-bearing instantiation of
  `HANDOVER.md`'s design, not a competing decision), so this did not escalate
  to a BLOCKER. Recorded as INFO so `gsd-roadmapper` is aware the strict
  `locked: false` field should not be read as "safely overridable."
  Sources: `PREREGISTRATION.md` (classification `notes` field, verbatim);
  `HANDOVER.md` (comparison ADR).

[INFO] Auto-resolved: ARCHITECTURE.md phase-numbering vs HANDOVER.md phase-numbering
  Found: `ARCHITECTURE.md` §6 collapses HANDOVER's separate Phase 4 (event
  study/CARs) and Phase 5 (permutation inference/verdict) into one label,
  "Phase 4 — VALIDATION CORE (THE GATE)."
  Resolution: `DECISIONS.md` (Phase 4 entry) states execution "followed
  HANDOVER.md's own phase numbering, not ARCHITECTURE.md's" — `04_event_study.py`
  and `05_inference.py` were committed as two separate phases (`phase 4`/
  `phase 5`), matching the higher-precedence ADR's original plan; the
  SPEC-level collapsed labeling caused a momentary mislabeling in conversation
  that was corrected before committing, with no code impact. ADR precedence
  won as the default rule would predict; recorded as INFO for traceability,
  not a live conflict.
  Sources: `ARCHITECTURE.md` §6.0 mapping table and Phase 4 heading;
  `HANDOVER.md` §7 (Phase 4, Phase 5); `DECISIONS.md` Phase 4 entry.

---

**Not flagged (checked, found consistent, no entry needed):** `ARCHITECTURE.md`
§4's optional `duckdb` stack addition has no corresponding `DECISIONS.md` entry
adopting it and does not appear in `HANDOVER.md`'s locked allowed-stack list (also
mirrored in `CLAUDE.md`) — per default precedence this SPEC-level optional
addition simply has not been authorized or used; not a contradiction requiring
resolution, just an unexercised SPEC option, consistent with the pattern of the
React-dashboard option above.
