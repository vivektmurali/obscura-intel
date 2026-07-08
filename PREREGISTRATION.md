# Pre-registration — Obscura Intel v0.1 event study

Committed before any join of event data to price data. Hash cited in README.

## Universe

38 NSE mid/small-cap tickers drawn from current Nifty Midcap 100 + Nifty
Smallcap 100 constituents (vintage: July 2026). Selection filters: company
name distinctive as an English search string; spread across >=6 sectors;
Yahoo Finance `.NS` ticker judged likely to have usable daily history for
the full study period (2022-07-01 to 2026-01-31). Full list, aliases, and
sector labels: `data/universe.csv`. Selection rationale and exclusions
(recent IPOs, ambiguous names, corporate-action discontinuities): `DECISIONS.md`.

Two originally-selected tickers (SAIL, BHEL) were dropped after persistent
GDELT fetch failures across three retry passes — see `DECISIONS.md` for
detail. This is a data-availability drop, not a universe redesign, and
happened before any event detection ran.

**Known limitation:** using *current* index constituents introduces
survivorship bias. Acceptable for v0.1, disclosed, not fixed.

## Event definition

`vol_z(t) = (v_t - mean_90(t)) / std_90(t)`, trailing 90-day window (day t
excluded), computed identically for the tone series to get `tone_z(t)`.

Event day: `vol_z >= 3` AND `v_t >= 5` articles. Consecutive event-day runs
merged to the first day only. Direction proxy: `sign(tone_z)` on the event day.

Fallback (usable once, only if events < 150): `vol_z >= 2` AND `v_t >= 3`.
**Used: NO.** Primary threshold (`vol_z >= 3`, `v >= 5`) with complete
2023-2025 volume and tone data for all 38 universe tickers produced
**242 events** across 28 tickers (10 tickers had zero qualifying spike
days at this threshold) — comfortably above the 150-event gate. Full
detail: `data/events.csv`.

## Entry rule

Close of first NSE trading day strictly after the event's UTC date. No
event-day price is ever used as a tradeable price. No exceptions.

## Returns

Market model vs `^NSEI` (Nifty 50), 120-trading-day estimation window ending
21 trading days before entry. Fallback to market-adjusted (beta=1) if fewer
than 90 valid estimation-window observations; such events are flagged.
Horizons: CAR(t+1), CAR(t+5), CAR(t+20).

## Primary hypothesis (confirmatory)

`H1: mean over all events of sign(tone_z) x CAR(t+5) > 0`; one-sided
permutation test, p < 0.05; 1,000 permutations, seeded.

Permutation null: for each ticker with K real events, draw K pseudo-event
days uniformly from that ticker's trading days in the study period,
excluding +/-5 trading days around any real event. Recompute the full CAR
pipeline for each of 1,000 draws to build the null distribution.

## Secondary hypotheses (BH-FDR q=0.10, labeled secondary)

1. Tone-signed mean CAR at t+1 and t+20.
2. Mean |CAR| at each horizon vs null (reaction regardless of direction).
3. Top-vs-bottom tone-tercile spread in CAR(t+5).

## Robustness (pre-registered, exhaustive list — one pass only, after the
primary/secondary results are already recorded)

(a) fallback spike threshold (if not already triggered as primary)
(b) market-adjusted returns instead of market-model
(c) drop calendar days on which >3 universe tickers have simultaneous events

Anything beyond this exhaustive list is exploratory and labeled as such in
a separate README section. No respecification of the primary/secondary
tests themselves after results are seen.

## Kill criterion

Primary test fails (p >= 0.05) AND no secondary survives FDR -> verdict:
**"no detectable edge under this specification."** README states this
plainly if it occurs. v0.1 still ships and tags either way.

## Sample-size gate

>= 150 events required for the primary test to count as confirmatory.
Below that (after the one permitted fallback), results are reported as
exploratory/underpowered, not confirmatory. **Result: 242 events >= 150 —
GATE PASS, confirmatory status.**

## Clustering caveat

Cross-sectional event clustering (market-wide news days) inflates apparent
significance. Mitigation: disclosed as a limitation, plus the robustness
pass (c) above dropping high-simultaneity calendar days. Full calendar-time
portfolio methods are out of scope for v0.1 (parked).

**This is not just theoretical for this dataset:** the Phase 2 qualitative
spot-check of the 20 largest spikes found 2-3 events (of 20) where the
sampled headlines were generic market-wide roundups rather than
company-specific news — see `DECISIONS.md`. The robustness pass above
exists partly to address exactly this.
