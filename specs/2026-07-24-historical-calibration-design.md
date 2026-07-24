# Historical calibration feature — design

Status: proposed, awaiting user spec review (not yet built).
Origin: PARKING.md's 2026-07-16 "override handover" entry (brainstorming-only),
scoped here into an actual design per that entry's own follow-up requirement.

## 1. Premise

The original idea ("watch this stock, with reasoning") implied a forward-looking
recommendation. The v0.1 study already tested exactly that claim — tone-signed
news predicting forward returns — and found no detectable edge (primary test
p=0.763, wrong-signed point estimate, well-powered per the retroactive MDE
analysis). Building a recommendation feature on top of a locked NULL verdict
would contradict the project's own claims-audit gate.

This feature instead does the opposite: an explicit **anti-signal / calibration
tool**. For each live event, it surfaces what happened historically after
similarly-toned events in the locked study, framed unambiguously as "this is
the null result, not a signal."

## 2. Naming & framing

- Feature name: **"Historical calibration"** — not "recommendation," not "watch."
- Per-event copy pattern:

  > This event's tone was `{negative|mixed|positive}`. Historically, events in
  > this tone group (n={N}/242) averaged a `{X}%` 5-day return — but this
  > pattern showed no statistically detectable relationship to timing
  > (permutation p=0.763, see [Methodology](/methodology.html)). Not a trading
  > signal.

- Every instance links to the methodology/README null-result section rather
  than restating the full statistical case inline.

## 3. Data flow & components

```
results/car_by_event.csv (locked, 242 events — never touched by this feature)
        │
        ▼
06_scoring.py: compute_tercile_reference()
   - pd.qcut(tone_z, 3, labels=["bottom","mid","top"])   # identical to 06_figures.py's fig_tone_tercile
   - group by tercile → mean CAR_t5, n per tercile
        │
        ▼
06_scoring.py: score_calibration(live_events, tercile_ref)
   - classify each live event's tone_z into bottom/mid/top using the
     *locked* tercile cutpoints (values outside the historical tone_z
     range clip to the nearest tercile, not a new bucket)
   - attach: tercile_label, tercile_mean_car5, tercile_n, disclaimer
     (fixed string constant, defined once)
        │
        ▼
12_build_site.py: render a calibration block on every live event row
   on that ticker's page, using only the attached fields (never
   re-derives or paraphrases the disclaimer at render time)
```

- `compute_tercile_reference()` reads only the locked `results/car_by_event.csv`
  — same locked/live boundary `06_scoring.py` already enforces for the
  intensity percentile (anchored to the locked `vol_z` distribution, never the
  growing live table, so scores don't drift as new events accumulate).
- Tercile cutpoints come from re-running the same `pd.qcut` call already used
  in `06_figures.py`'s `fig_tone_tercile` — one test asserts this matches
  byte-for-byte, so there are not two independent implementations of "what a
  tercile is."
- A live event's tone_z is classified against those fixed boundaries directly
  (not by re-running qcut on a combined live+locked pool), so the reference
  distribution is stable regardless of how many live events accumulate.

## 4. Claims-audit enforcement

Same discipline as the existing NULL-mode guard in `06_scoring.py`, widened by
one field:

- `score_calibration()` must attach the fixed disclaimer string alongside
  `tercile_mean_car5`, enforced by an explicit `raise ValueError` (not a bare
  `assert` — already flagged as fragile under `python -O` in the power-analysis
  script fix) if the disclaimer is missing or doesn't match the approved
  constant exactly.
- The existing `score_null_mode` assertion (no `CAR_t*`/`car_t*` column reaches
  the site build) is extended: a `tercile_mean_car5` column is only permitted
  when its disclaimer sibling field is also present and correct. This widens
  the claims-audit contract; it does not loosen it.
- `12_build_site.py` renders the disclaimer text verbatim from the scored
  field — one source of truth for the exact wording.

## 5. Testing

Following this project's existing pattern (real fixtures, negative-control
validation, no synthetic data):

- `compute_tercile_reference()`: tested against a real slice of
  `results/car_by_event.csv`, cross-checked against `06_figures.py`'s existing
  tercile means (already-plotted, known-good numbers) to prove agreement, not
  just that the new code executes.
- `score_calibration()`: tested both ways — disclaimer present (succeeds),
  disclaimer stripped (raises `ValueError`) — mirroring the existing
  `06_scoring.py` NULL-mode negative-control tests.
- One test confirms a live event with tone_z outside the historical
  [min, max] range still clips into a valid tercile rather than crashing the
  build.

## 6. Process note

- PARKING.md's 2026-07-16 entry authorized brainstorming only and explicitly
  deferred "the actual scoped design" to a follow-up entry. This spec is that
  follow-up; a new PARKING.md entry will log it once approved.
- Building this still reintroduces HANDOVER.md §5's "live prediction/alerting"
  ban in code, not just in discussion. Per rule 4, that requires Vivek to say
  "override handover" again, specifically for the build step, before this
  spec is handed to `writing-plans`/execution — the brainstorming override
  does not carry forward automatically.

## Out of scope

- No change to `data/events.csv`, `results/stats.json`, `results/car_by_event.csv`,
  or any other locked v0.1 artifact.
- No per-ticker-only historical stats (rejected during brainstorming — n too
  small per ticker, risk of reading as a personal track record).
- No new locked reference file — tercile stats are cheap to recompute fresh
  every run (242 rows) and doing so avoids a second place encoding the same
  logic.
