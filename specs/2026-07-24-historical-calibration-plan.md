# Historical Calibration Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a non-predictive "historical calibration" block to every live event on a ticker page, showing the locked study's own tone-tercile CAR_t5 breakdown with a code-enforced disclaimer.

**Architecture:** `scripts/06_scoring.py` gains two pure functions (`compute_tercile_reference`, `classify_tercile`) and one scoring function (`score_calibration`) that recompute the locked study's tone-tercile stats fresh each run and attach them to live events; `score_null_mode`'s existing claims-audit assertion is widened to require the disclaimer alongside the new field. `scripts/12_build_site.py` passes the new fields into the existing per-ticker event table, and `site_src/templates/ticker.html` renders them.

**Tech Stack:** Python 3.11+, pandas, `unittest` (stdlib), Jinja2 — no new dependencies.

## Global Constraints

- Feature name is **"Historical calibration"** everywhere (code, copy, commits) — never "recommendation" or "watch."
- No change to any locked v0.1 artifact: `data/events.csv`, `results/stats.json`, `results/car_by_event.csv` are read-only inputs, never written.
- Tercile cutpoints/means are recomputed fresh from `results/car_by_event.csv` every run — no new locked reference file.
- Classification of a live event's `tone_z` uses the locked cutpoints directly; never re-run `qcut` on a combined live+locked pool.
- Every live event gets the calibration block — not just the most recent.
- The disclaimer string is defined once (`CALIBRATION_DISCLAIMER` in `scripts/06_scoring.py`) and rendered verbatim at the template layer — never re-derived or paraphrased elsewhere.
- New claims-audit checks use explicit `raise ValueError` (not a bare `assert`, per the 2026-07-16 lesson that `assert` is stripped under `python -O`). The pre-existing `assert` in `score_null_mode` is left as-is.
- Tests use real fixtures only (CLAUDE.md rule 3) — the tercile numbers below are the actual locked-data values, not invented.
- Every script change in this plan must actually be run in this session before the task is marked done (CLAUDE.md rule 1) — no code is written and left unexecuted.
- Each task ends with a commit; push happens at the end of the final task (CLAUDE.md rule 2).
- Test command for this project: `python -m unittest discover -s tests -v` (run from repo root). Currently: 38 tests, ~0.07s, all passing.

**Locked reference numbers** (from `results/car_by_event.csv`, `pd.qcut(tone_z, 3, labels=["bottom","mid","top"], retbins=True)`, verified against `06_figures.py`'s already-plotted `tone_tercile.png`):

| tercile | edge range | mean CAR_t5 | n |
|---|---|---|---|
| bottom | tone_z ≤ -0.060992862151788604 | 0.006125822605787347 | 81 |
| mid | -0.060992862151788604 < tone_z ≤ 0.4781734963545042 | -0.00048690668795241357 | 80 |
| top | tone_z > 0.4781734963545042 | 0.0031365360141517398 | 81 |

Full edge array: `[-12.440962071362412, -0.060992862151788604, 0.4781734963545042, 3.8686705437924407]` (first/last are the locked distribution's actual min/max, only used as the array's outer bounds — classification never checks against them directly, see Task 1).

---

### Task 1: Tercile reference + classification helpers

**Files:**
- Modify: `scripts/06_scoring.py` (add after `HISTORICAL_EVENTS_CSV`/`LIVE_EVENTS_CSV` constants around line 27-28, and after `score_intensity` around line 41)
- Test: `tests/test_06_scoring.py` (add new test classes)

**Interfaces:**
- Produces: `compute_tercile_reference() -> dict` with keys `"edges"` (list of 4 floats), `"mean"` (dict of `"bottom"|"mid"|"top"` → float), `"n"` (dict of `"bottom"|"mid"|"top"` → int)
- Produces: `classify_tercile(tone_z: float, edges: list[float]) -> str` returning `"bottom"|"mid"|"top"`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_06_scoring.py`, after the `ScoreIntensityTests` class:

```python
class ComputeTercileReferenceTests(unittest.TestCase):
    """Cross-checked against 06_figures.py's fig_tone_tercile, which already
    plots these exact numbers in results/figures/tone_tercile.png -- this
    proves the two independent qcut calls agree, not just that this one runs."""

    def test_matches_locked_figure_numbers(self):
        ref = scoring.compute_tercile_reference()
        self.assertAlmostEqual(ref["edges"][0], -12.440962071362412)
        self.assertAlmostEqual(ref["edges"][1], -0.060992862151788604)
        self.assertAlmostEqual(ref["edges"][2], 0.4781734963545042)
        self.assertAlmostEqual(ref["edges"][3], 3.8686705437924407)
        self.assertAlmostEqual(ref["mean"]["bottom"], 0.006125822605787347)
        self.assertAlmostEqual(ref["mean"]["mid"], -0.00048690668795241357)
        self.assertAlmostEqual(ref["mean"]["top"], 0.0031365360141517398)
        self.assertEqual(ref["n"]["bottom"], 81)
        self.assertEqual(ref["n"]["mid"], 80)
        self.assertEqual(ref["n"]["top"], 81)


class ClassifyTercileTests(unittest.TestCase):
    EDGES = [-12.440962071362412, -0.060992862151788604, 0.4781734963545042, 3.8686705437924407]

    def test_value_inside_bottom_tercile(self):
        self.assertEqual(scoring.classify_tercile(-1.0, self.EDGES), "bottom")

    def test_value_inside_mid_tercile(self):
        self.assertEqual(scoring.classify_tercile(0.1, self.EDGES), "mid")

    def test_value_inside_top_tercile(self):
        self.assertEqual(scoring.classify_tercile(1.0, self.EDGES), "top")

    def test_value_more_negative_than_locked_minimum_clips_to_bottom(self):
        self.assertEqual(scoring.classify_tercile(-50.0, self.EDGES), "bottom")

    def test_value_more_positive_than_locked_maximum_clips_to_top(self):
        self.assertEqual(scoring.classify_tercile(50.0, self.EDGES), "top")

    def test_exact_boundary_values(self):
        self.assertEqual(scoring.classify_tercile(-0.060992862151788604, self.EDGES), "bottom")
        self.assertEqual(scoring.classify_tercile(0.4781734963545042, self.EDGES), "mid")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_06_scoring -v`
Expected: `ComputeTercileReferenceTests` and `ClassifyTercileTests` FAIL with `AttributeError: module 'scoring' has no attribute 'compute_tercile_reference'` (and `classify_tercile`).

- [ ] **Step 3: Add the constant and both functions to `scripts/06_scoring.py`**

Add this constant next to the other path constants (after line 27 `LIVE_EVENTS_CSV = ROOT / "data" / "live" / "events.csv"`):

```python
CAR_BY_EVENT_CSV = ROOT / "results" / "car_by_event.csv"  # v0.1's locked event-level CAR table
```

Add both functions after `score_intensity` (after line 40, before `def score_novelty`):

```python
def compute_tercile_reference():
    """Locked tone_z tercile cutpoints + per-tercile mean CAR_t5, recomputed
    fresh from the locked results/car_by_event.csv every run (242 rows,
    sub-second) -- identical qcut call to 06_figures.py's fig_tone_tercile,
    so there is exactly one implementation of "what a tercile is"."""
    car = pd.read_csv(CAR_BY_EVENT_CSV)
    valid = car.dropna(subset=["CAR_t5"]).copy()
    tercile, edges = pd.qcut(valid["tone_z"], 3, labels=["bottom", "mid", "top"], retbins=True)
    valid["tercile"] = tercile
    grouped = valid.groupby("tercile", observed=True)["CAR_t5"]
    means = grouped.mean()
    ns = grouped.size()
    return {
        "edges": edges.tolist(),
        "mean": {label: float(means[label]) for label in ["bottom", "mid", "top"]},
        "n": {label: int(ns[label]) for label in ["bottom", "mid", "top"]},
    }


def classify_tercile(tone_z, edges):
    """Classify a tone_z value into the locked bottom/mid/top tercile. Values
    more extreme than the locked distribution's own min/max simply fall into
    the nearest tercile (bottom or top) rather than erroring -- there is no
    fourth bucket for "more extreme than anything seen historically"."""
    _, e1, e2, _ = edges
    if tone_z <= e1:
        return "bottom"
    if tone_z <= e2:
        return "mid"
    return "top"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_06_scoring -v`
Expected: all tests PASS, including the 6 new ones.

- [ ] **Step 5: Commit**

```bash
git add scripts/06_scoring.py tests/test_06_scoring.py
git commit -m "feat: add tercile reference + classification for historical calibration"
```

---

### Task 2: `score_calibration()` + disclaimer constant

**Files:**
- Modify: `scripts/06_scoring.py` (add after `classify_tercile`, before `def score_novelty`)
- Test: `tests/test_06_scoring.py`

**Interfaces:**
- Consumes: `classify_tercile(tone_z, edges)` from Task 1; a `tercile_ref` dict shaped like `compute_tercile_reference()`'s return value
- Produces: `score_calibration(df: pd.DataFrame, tercile_ref: dict) -> pd.DataFrame` — attaches columns `tercile_label`, `tercile_mean_car5`, `tercile_n`, `calibration_disclaimer` to a copy of `df` (requires a `tone_z` column already present)
- Produces: module-level constant `CALIBRATION_DISCLAIMER: str`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_06_scoring.py`:

```python
class ScoreCalibrationTests(unittest.TestCase):
    TERCILE_REF = {
        "edges": [-12.440962071362412, -0.060992862151788604, 0.4781734963545042, 3.8686705437924407],
        "mean": {"bottom": 0.006125822605787347, "mid": -0.00048690668795241357, "top": 0.0031365360141517398},
        "n": {"bottom": 81, "mid": 80, "top": 81},
    }

    def test_attaches_all_four_fields(self):
        df = pd.DataFrame({"tone_z": [-1.0, 0.1, 1.0]})
        result = scoring.score_calibration(df, self.TERCILE_REF)
        self.assertEqual(result["tercile_label"].tolist(), ["bottom", "mid", "top"])
        self.assertAlmostEqual(result["tercile_mean_car5"].iloc[0], 0.006125822605787347)
        self.assertEqual(result["tercile_n"].tolist(), [81, 80, 81])
        self.assertTrue((result["calibration_disclaimer"] == scoring.CALIBRATION_DISCLAIMER).all())

    def test_never_adds_a_forward_return_column(self):
        df = pd.DataFrame({"tone_z": [-1.0]})
        result = scoring.score_calibration(df, self.TERCILE_REF)
        self.assertFalse(scoring.FORBIDDEN_NULL_MODE_COLUMNS & set(result.columns))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_06_scoring -v`
Expected: `ScoreCalibrationTests` FAILS with `AttributeError: module 'scoring' has no attribute 'score_calibration'`.

- [ ] **Step 3: Add the constant and function to `scripts/06_scoring.py`**

Add after `classify_tercile`, before `def score_novelty`:

```python
CALIBRATION_DISCLAIMER = (
    "Historical average across similarly-toned events in the locked study "
    "-- not a prediction. The primary test found no statistically "
    "significant relationship between tone and forward returns "
    "(permutation p=0.763). Not a trading signal."
)


def score_calibration(df, tercile_ref):
    """Attach the historical-calibration fields (tercile_label,
    tercile_mean_car5, tercile_n, calibration_disclaimer) to every row.
    These are historical *group* averages from the locked study, never a
    per-event forward-return number -- score_null_mode's claims-audit
    assertion enforces the disclaimer travels with tercile_mean_car5."""
    df = df.copy()
    edges = tercile_ref["edges"]
    df["tercile_label"] = df["tone_z"].apply(lambda z: classify_tercile(z, edges))
    df["tercile_mean_car5"] = df["tercile_label"].map(tercile_ref["mean"])
    df["tercile_n"] = df["tercile_label"].map(tercile_ref["n"])
    df["calibration_disclaimer"] = CALIBRATION_DISCLAIMER
    return df
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_06_scoring -v`
Expected: all tests PASS, including the 2 new ones.

- [ ] **Step 5: Commit**

```bash
git add scripts/06_scoring.py tests/test_06_scoring.py
git commit -m "feat: add score_calibration and the historical-calibration disclaimer"
```

---

### Task 3: Widen the claims-audit assertion in `score_null_mode`

**Files:**
- Modify: `scripts/06_scoring.py:50-57` (`score_null_mode`)
- Test: `tests/test_06_scoring.py`

**Interfaces:**
- Consumes: `CALIBRATION_DISCLAIMER` constant from Task 2
- Produces: `score_null_mode` now also raises `ValueError` (not just the existing `AssertionError` for forbidden CAR columns) when `tercile_mean_car5` is present without a correct `calibration_disclaimer`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_06_scoring.py`, after `ScoreNullModeClaimsAuditTests`:

```python
class ScoreNullModeCalibrationAuditTests(unittest.TestCase):
    """Widens the same claims-audit guarantee: a historical-calibration
    number must never reach the site without its non-predictive disclaimer."""

    def _base_df(self):
        return pd.DataFrame({
            "ticker": ["DABUR"],
            "event_date": pd.to_datetime(["2023-05-04"]),
            "vol_z": [5.0],
        })

    def test_raises_when_tercile_mean_present_without_disclaimer(self):
        df = self._base_df()
        df["tercile_mean_car5"] = [0.006]
        with self.assertRaises(ValueError) as ctx:
            scoring.score_null_mode(df, [3.0, 5.0, 7.0])
        self.assertIn("disclaimer", str(ctx.exception).lower())

    def test_raises_when_disclaimer_text_is_wrong(self):
        df = self._base_df()
        df["tercile_mean_car5"] = [0.006]
        df["calibration_disclaimer"] = ["this text has been edited and no longer matches"]
        with self.assertRaises(ValueError):
            scoring.score_null_mode(df, [3.0, 5.0, 7.0])

    def test_succeeds_when_disclaimer_is_present_and_correct(self):
        df = self._base_df()
        df["tercile_mean_car5"] = [0.006]
        df["calibration_disclaimer"] = [scoring.CALIBRATION_DISCLAIMER]
        result = scoring.score_null_mode(df, [3.0, 5.0, 7.0])
        self.assertIn("intensity_percentile", result.columns)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_06_scoring -v`
Expected: `ScoreNullModeCalibrationAuditTests` FAILS — `test_raises_when_tercile_mean_present_without_disclaimer` and `test_raises_when_disclaimer_text_is_wrong` fail because no `ValueError` is currently raised (the function just proceeds); `test_succeeds_when_disclaimer_is_present_and_correct` should already pass incidentally.

- [ ] **Step 3: Modify `score_null_mode`**

Replace the current function body (`scripts/06_scoring.py:50-57`):

```python
def score_null_mode(df, reference_vol_z):
    assert not (FORBIDDEN_NULL_MODE_COLUMNS & set(df.columns)), (
        "NULL-mode claims audit failed: a forward-return column is present. "
        "Per ARCHITECTURE.md Sec 7, NULL verdict must never show or imply forward returns."
    )
    if "tercile_mean_car5" in df.columns:
        disclaimer_ok = (
            "calibration_disclaimer" in df.columns
            and (df["calibration_disclaimer"] == CALIBRATION_DISCLAIMER).all()
        )
        if not disclaimer_ok:
            raise ValueError(
                "Claims audit failed: tercile_mean_car5 is present without the exact "
                "required calibration disclaimer on every row. A historical-calibration "
                "number must never reach the site without its non-predictive disclaimer."
            )
    df = score_novelty(df)
    df["intensity_percentile"] = score_intensity(df["vol_z"].to_numpy(), reference_vol_z)
    return df
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_06_scoring -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/06_scoring.py tests/test_06_scoring.py
git commit -m "fix: widen NULL-mode claims audit to require the calibration disclaimer"
```

---

### Task 4: Wire into `main()` and run against real live data

**Files:**
- Modify: `scripts/06_scoring.py` (the `main()` function — originally at lines 60-95, but Tasks 1-3 insert code above it, so locate it by its `def main():` signature rather than by line number)

**Interfaces:**
- Consumes: `compute_tercile_reference`, `score_calibration`, `score_null_mode` (all now disclaimer-aware)
- Produces: `data/live/events.csv` and `data/live_events.csv` gain 4 new columns: `tercile_label`, `tercile_mean_car5`, `tercile_n`, `calibration_disclaimer`

- [ ] **Step 1: Replace `main()`**

Find the `def main():` function (it starts right after `score_null_mode` and runs to the end of the file, just before `if __name__ == "__main__":`) and replace its entire body with:

```python
def main():
    verdict = get_verdict()
    print(f"Verdict on record: {verdict}")
    if verdict != "NULL":
        print(f"FATAL: this script only implements NULL-mode scoring; verdict is {verdict}. "
              "SIGNAL-mode scoring (historical CAR(t+5) bucket stats) is not built -- "
              "would need its own review before implementing, per the claims-audit gate.")
        sys.exit(1)

    if not LIVE_EVENTS_CSV.exists():
        print("FATAL: data/live/events.csv missing -- run 11_daily_events.py first")
        sys.exit(1)

    reference = pd.read_csv(HISTORICAL_EVENTS_CSV)["vol_z"].to_numpy()
    tercile_ref = compute_tercile_reference()

    live_events = pd.read_csv(LIVE_EVENTS_CSV, parse_dates=["event_date"])
    live_events = score_calibration(live_events, tercile_ref)
    scored_live = score_null_mode(live_events, reference)
    scored_live.to_csv(LIVE_EVENTS_CSV, index=False)
    print(f"Scored {len(scored_live)} events in {LIVE_EVENTS_CSV} "
          f"(columns added: intensity_percentile, novelty_days, tercile_label, "
          f"tercile_mean_car5, tercile_n, calibration_disclaimer)")

    calibration_cols = ["tercile_label", "tercile_mean_car5", "tercile_n", "calibration_disclaimer"]
    if NEW_EVENTS_CSV.exists():
        new_events = pd.read_csv(NEW_EVENTS_CSV, parse_dates=["event_date"])
        if len(new_events):
            merged = new_events[["ticker", "event_date"]].merge(
                scored_live[["ticker", "event_date", "intensity_percentile", "novelty_days"] + calibration_cols],
                on=["ticker", "event_date"], how="left",
            )
            new_events["intensity_percentile"] = merged["intensity_percentile"].to_numpy()
            new_events["novelty_days"] = merged["novelty_days"].to_numpy()
            for col in calibration_cols:
                new_events[col] = merged[col].to_numpy()
        else:
            new_events["intensity_percentile"] = pd.Series(dtype=float)
            new_events["novelty_days"] = pd.Series(dtype=float)
            new_events["tercile_label"] = pd.Series(dtype=object)
            new_events["tercile_mean_car5"] = pd.Series(dtype=float)
            new_events["tercile_n"] = pd.Series(dtype="Int64")
            new_events["calibration_disclaimer"] = pd.Series(dtype=object)
        new_events.to_csv(NEW_EVENTS_CSV, index=False)
        print(f"Scored {len(new_events)} new-this-run events in {NEW_EVENTS_CSV}")
```

- [ ] **Step 2: Run the full test suite**

Run: `python -m unittest discover -s tests -v`
Expected: all tests PASS (38 pre-existing + new ones from Tasks 1-3).

- [ ] **Step 3: Run the script against the real live data**

Run: `python scripts/06_scoring.py`
Expected: prints `Verdict on record: NULL`, then `Scored <N> events in .../data/live/events.csv (columns added: intensity_percentile, novelty_days, tercile_label, tercile_mean_car5, tercile_n, calibration_disclaimer)`, then a `Scored <M> new-this-run events...` line. No traceback. `<N>` will be whatever `data/live/events.csv` currently holds (281 rows as of 2026-07-24; this will have grown by the time this runs).

- [ ] **Step 4: Inspect the real output**

Run: `python -c "import pandas as pd; df = pd.read_csv('data/live/events.csv'); print(df[['ticker','tone_z','tercile_label','tercile_mean_car5','tercile_n']].tail(10))"`
Expected: every row has a non-null `tercile_label` in `{bottom, mid, top}`, `tercile_mean_car5` matching the Global Constraints table above for that label, `tercile_n` in `{80, 81}`. Spot-check by hand: a row with `tone_z` around `-1.0` should show `tercile_label=bottom`.

- [ ] **Step 5: Commit the code change and the regenerated live data together**

```bash
git add scripts/06_scoring.py data/live/events.csv data/live_events.csv
git commit -m "feat: wire historical calibration into 06_scoring.py main()"
```

---

### Task 5: Render the calibration block on ticker pages

**Files:**
- Modify: `scripts/12_build_site.py:152-156` (ticker-page `ev_list` construction)
- Modify: `site_src/templates/ticker.html:29-43` (event history table)
- Modify: `site_src/static/style.css` (add `.calibration-note` rule after line 191)

**Interfaces:**
- Consumes: `tercile_label`, `tercile_mean_car5`, `tercile_n`, `calibration_disclaimer` columns now present in `data/live/events.csv` (Task 4)
- Produces: each per-ticker page (`docs/tickers/<TICKER>.html`) shows a calibration line under every event row

- [ ] **Step 1: Modify the `ev_list` construction in `scripts/12_build_site.py`**

Replace lines 152-156:

```python
        ev_list = [dict(
            event_date=r["event_date"].date(), direction=r["direction"],
            intensity_percentile=round(r["intensity_percentile"], 1),
            novelty_days=None if pd.isna(r["novelty_days"]) else int(r["novelty_days"]),
            tercile_label=r["tercile_label"],
            tercile_mean_car5_pct=round(r["tercile_mean_car5"] * 100, 2),
            tercile_n=int(r["tercile_n"]),
            calibration_disclaimer=r["calibration_disclaimer"],
        ) for _, r in ev_rows.iterrows()]
```

- [ ] **Step 2: Add the CSS rule**

Insert after `site_src/static/style.css:191` (`table.plain th { ... }`):

```css

.calibration-note { font-size: 0.76rem; color: var(--ink-faint); margin-top: 4px; max-width: 360px; }
```

- [ ] **Step 3: Modify the event table in `site_src/templates/ticker.html`**

Replace lines 29-43 (the `<thead>`/`<tbody>` block):

```html
<table class="plain">
  <thead>
    <tr><th>Date</th><th>Direction</th><th>Intensity</th><th>Novelty</th><th>Historical calibration</th></tr>
  </thead>
  <tbody>
    {% for ev in events %}
    <tr>
      <td class="mono">{{ ev.event_date }}</td>
      <td><span class="chip {{ 'up' if ev.direction > 0 else 'down' }}">{{ '+' if ev.direction > 0 else '−' }} tone</span></td>
      <td class="mono">{{ ev.intensity_percentile }}th pct</td>
      <td class="mono">{{ ev.novelty_days if ev.novelty_days is not none else "first seen" }}</td>
      <td>
        <span class="mono">{{ ev.tercile_label }} tone (n={{ ev.tercile_n }}): {{ '%+.2f'|format(ev.tercile_mean_car5_pct) }}%</span>
        <div class="calibration-note">{{ ev.calibration_disclaimer }} <a href="{{ root }}methodology.html">Methodology</a></div>
      </td>
    </tr>
    {% endfor %}
  </tbody>
</table>
```

- [ ] **Step 4: Run the site build against real data**

Run: `python scripts/12_build_site.py`
Expected: prints `Built site to .../docs: <N> ticker pages, <M> events, verdict=NULL`. No traceback.

- [ ] **Step 5: Inspect a real rendered ticker page**

Run: `python -c "
import re
html = open('docs/tickers/DABUR.html', encoding='utf-8').read()
print('Historical calibration' in html)
m = re.search(r'<td>\s*<span class=\"mono\">(bottom|mid|top) tone.*?</span>', html)
print(m.group(0) if m else 'NOT FOUND')
"`
Expected: `True` printed, followed by a matched span showing a real tercile label, n, and a percentage — confirming the block rendered with real data, not empty/broken markup. Manually open `docs/tickers/DABUR.html` in a browser (or view source) and confirm the disclaimer sentence and "Methodology" link appear under at least one event row and read correctly.

- [ ] **Step 6: Commit the code, template, and regenerated site together**

```bash
git add scripts/12_build_site.py site_src/templates/ticker.html site_src/static/style.css docs
git commit -m "feat: render historical calibration block on ticker pages"
```

---

### Task 6: Full verification, decisions log, push

**Files:**
- Modify: `DECISIONS.md` (append a dated entry)

- [ ] **Step 1: Run the complete test suite one more time**

Run: `python -m unittest discover -s tests -v`
Expected: all tests pass (38 + this plan's new tests).

- [ ] **Step 2: Append a DECISIONS.md entry**

Add a new section at the end of `DECISIONS.md`, following the file's existing style (one entry, dated, explaining any non-obvious choices — e.g. why tercile stats are recomputed fresh rather than cached, why the disclaimer is a single verbatim constant, real row counts observed when Task 4/5 were run).

- [ ] **Step 3: Commit and push**

```bash
git add DECISIONS.md
git commit -m "docs: log historical-calibration feature build in DECISIONS.md"
git push
```
