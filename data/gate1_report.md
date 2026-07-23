# STOP GATE 1 — Consolidated Report

Phase 1 diagnostics against run #1 (`data/backtest_results.csv`, 1076 raw
signals -> 797 episodes via `backtesting/episode_builder.py`). Every number
below is episode-level and net of `ROUND_TRIP_COST_PCT` unless stated
otherwise. This phase changed no engine behavior — Phase 2 does not start
until the human has read this and made the decisions below.

## G1-a — Does capped-≥65 still beat/match EXECUTE at episode level? Which sub-buckets?

| population | n | win rate | expectancy |
|---|---|---|---|
| capped (score ≥65, blocked by ceiling) | 88 | 60.2% | 2.64% |
| genuine (score 40–64) | 689 | 54.9% | 0.97% |
| EXECUTE (actual) | 20 | 65.0% | 2.74% |

**Framing, per the human's own correction at the checkpoint:** with n=20 for
EXECUTE, "2.74% vs 2.64%" is not a meaningful ordering either way. The
finding is **capped is clearly not worse than EXECUTE, on a sample
~4.4x larger** (88 vs 20) — not "capped beats EXECUTE." Genuine (n=689,
0.97%) is a real, distinct, and clearly weaker population — the ceiling is
correctly separating two different things, it's just also catching a large
population of episodes indistinguishable from EXECUTE along with the
genuinely weak one.

**Sub-buckets** (capped, by ceiling cause):

| cause | n | win rate | expectancy |
|---|---|---|---|
| CAUTION + NEUTRAL sector | 49 | 65.3% | 2.87% |
| UNFAVORABLE market | 25 | 56.0% | 3.09% |
| CAUTION + WEAK sector | 14 | 50.0% | 1.05% (small sample) |

CAUTION+WEAK is the one sub-bucket that looks meaningfully different —
addressed in G1-c below via the sector-aware policy.

## G1-b — Which regime-cause dominates CAUTION: distribution days vs CHOPPY?

Daily regime timeline reconstructed across the full run #1 window
(2024-07-22 → 2026-07-14, 490 trading days; see `backtesting/regime_timeline.py`
and `data/regime_timeline.csv`):

| verdict | days | % of window |
|---|---|---|
| CAUTION | 344 | 70.2% |
| UNFAVORABLE | 133 | 27.1% |
| FAVORABLE | 13 | 2.7% |

**The market spent 97.3% of the last two years in CAUTION or UNFAVORABLE.**
FAVORABLE occurred on only 13 days total, across two short windows
(2024-07-22→07-29, 6 days; 2025-10-01→10-10, 7 days). This alone explains
most of EXECUTE's scarcity: the ceiling is almost never even partially open
by design, not merely strict when it is. It also means "just wait for
FAVORABLE markets" is not a viable strategy — the strategy would sit in
cash for all but ~11 days of the sampled two years under the current
ceiling.

Within CAUTION's 344 days: **250 (72.7%) involve a CHOPPY trend** (with or
without concurrent distribution days), vs **94 (27.3%) driven by
distribution-day accumulation alone** on an otherwise-uptrending market.
CHOPPY trend is the dominant CAUTION driver, distribution days a real but
secondary contributor — largely consistent with `get_market_regime_verdict()`'s
own docstring noting distribution days "doesn't work alone."

## The UNFAVORABLE-capped result — clustering check (the human flagged this specifically)

8 contiguous UNFAVORABLE periods exist across the window (3–28 days each,
full list in `data/regime_timeline.csv` / `tests/run_regime_timeline.py`
output). The 25 UNFAVORABLE-capped episodes touch **6 of these 8 distinct
periods**, not 1–2:

| period | dates | n days | n episodes |
|---|---|---|---|
| 1 | 2024-11-13 → 2024-12-11 | 19 | 3 |
| 2 | 2024-12-20 → 2024-12-27 | 5 | 2 |
| 3 | 2025-01-07 → 2025-02-11 | 27 | 9 |
| 4 | 2025-07-31 → 2025-09-04 | 24 | 5 |
| 5 | 2026-04-10 → 2026-05-07 | 18 | 1 |
| 6 | 2026-05-20 → 2026-06-30 | 28 | 5 |

No single period drives more than 9/25 (36%) of the episodes. This is
genuinely reassuring — the 3.09% UNFAVORABLE-capped expectancy isn't one
lucky window's artifact — but n=25 total is still thin, spread across 6
periods means most periods contribute only 1–5 episodes each. **Treat as a
real, repeatable phenomenon worth testing further (e.g. in run #2 with more
history), not yet as strong enough evidence on its own to justify
"UNFAVORABLE at 1/4 risk" as a standing policy.**

## G1-c — Which regime policy wins on drawdown-adjusted return?

Portfolio simulation (`backtesting/portfolio_simulator.py`): 5 concurrent
slots, 1% risk per full-size trade, sized by each policy's risk_fraction.

| policy | n taken | n missed (slots full) | slot util. | final equity | max DD | CAGR | Calmar (CAGR/\|DD\|) |
|---|---|---|---|---|---|---|---|
| (a) hard cap — current | 20 | 0 | 100.0% | 105.91 | -1.17% | 4.30% | 3.68 |
| (b/d) CAUTION 1/2, UNFAVORABLE blocked | 78 | 5 | 94.0% | 117.73 | -4.29% | 9.35% | 2.18 |
| (c) CAUTION 1/2, UNFAVORABLE 1/4 | 103 | 5 | 95.4% | 119.37 | -4.99% | 9.96% | 2.00 |
| (e) sector-aware CAUTION (NEUTRAL/STRONG 1/2, WEAK 1/4) | 78 | 5 | 94.0% | 117.20 | -4.08% | 9.08% | 2.23 |

(b) and (d) from the master execution spec's original list are the same
rule once UNFAVORABLE's fate is made explicit for (b) too — implemented as
one policy, not duplicated.

**On raw CAGR, (a) hard cap has the best Calmar ratio (3.68) — but this is
an artifact of taking so few trades (20 over 9 of 24 months) that variance
is tiny, not evidence the current system is "better."** Among the three
scaled variants, **(e) sector-aware has the best risk-adjusted result**
(Calmar 2.23), narrowly ahead of (b/d) at 2.18, both ahead of (c) at 2.00 —
consistent with (c)'s inclusion of the thin, uncertain UNFAVORABLE-1/4
exposure adding drawdown without a commensurate CAGR gain over (b/d).
Note (e) and (b/d) select the *same* 78 episodes (sector-aware only
resizes the CAUTION+WEAK subset, it doesn't exclude it) — (e)'s slightly
lower CAGR (9.08% vs 9.35%) alongside its better max drawdown (-4.08% vs
-4.29%) is exactly what down-weighting a real-but-weaker-edge bucket
should look like in a simple fixed-fractional model that doesn't reallocate
freed risk budget elsewhere.

All three scaled variants stay comfortably inside the 20% max-drawdown
success criterion.

## G1-d — Do EXECUTE-grade episodes beat all three baselines, net of costs?

| baseline | result |
|---|---|
| NIFTY buy-and-hold | -2.17% net over the window |
| Random-entry control (K=100, same target/stop distances as real signals) | mean -0.45%, median -1.01%, p95 +7.12%, win rate 44.0% |
| Naive momentum (best trailing-return ticker, no pattern/score/regime logic) | n=98, mean +2.67%, win rate 58.2% |
| **EXECUTE (actual)** | **n=20, mean +2.74%, win rate 65.0%** |

- **vs NIFTY buy-hold:** beats decisively (2.74% vs -2.17%).
- **vs random control's mean/median:** beats decisively (2.74% vs -0.45%/-1.01%).
- **vs random control's 95th percentile (docs/backtest_success_criteria.md
  criterion 4, as literally written):** does **not** clear it (2.74% <
  7.12%). Flagging rather than silently failing: comparing an *average*
  return to a *95th-percentile* draw from unconditioned random entries is
  an unusually strict, arguably mismatched bar — the 95th percentile of
  pure luck will frequently exceed any strategy's mean by construction.
  Per standing rule 6, this criterion is not being loosened retroactively;
  it is reported as a genuine FAIL against the criterion as written, with
  a note that the human may want to revisit the criterion's construction
  (e.g. compare distributions, or EXECUTE's own 95th percentile against
  random's) for run #2's success-criteria review.
- **vs naive momentum — the humbling one:** EXECUTE's 2.74% (n=20) and
  naive momentum's 2.67% (n=98) are statistically indistinguishable. A
  rule with zero pattern detection, zero scoring, zero regime/sector
  gating achieves nearly the same average return and a comparable win
  rate (58.2% vs 65.0%) as the full decision engine. This is the most
  important baseline result in this report and deserves direct attention
  before Phase 4 calibration work: on this run, the case that the
  strategy's machinery adds value *beyond simple momentum* is not yet
  demonstrated.

## G1-e — Does the triangle > VCP > C&H inversion survive deduplication?

**Yes.** Episode level (`backtesting/component_diagnostics.py`):

| pattern | weight | n | win rate | expectancy |
|---|---|---|---|---|
| Ascending Triangle | 20 | 126 | 77.0% | **4.63%** |
| VCP | 30 (highest) | 20 | 60.0% | 2.22% |
| Flat Base | 18 | 7 | 57.1% | 2.05% |
| Cup & Handle | 25 | 21 | 47.6% | **0.36%** |
| Bull Flag | 15 | 1 | 100.0% | 0.14% (n=1, ignore) |

`PATTERN_WEIGHTS`' assumed ordering (VCP highest, then Cup & Handle, then
Ascending Triangle) is inverted from actual realized performance: the
lowest-of-the-four-meaningful-samples-weighted pattern (Ascending Triangle,
weight 20) outperforms the highest-weighted pattern (VCP, weight 30) by
more than 2x, and the second-highest-weighted pattern (Cup & Handle,
weight 25) is the single worst performer of the group. This is not a
raw-signal artifact — it survives at episode level with a reasonably
sized Ascending Triangle sample (n=126).

## G1-f — No-pattern vs pattern episodes: net expectancy gap?

Corrected after fixing a real bug this diagnostic surfaced: `aggregate_by()`'s
groupby silently dropped the entire no-pattern population (NaN
`pattern_used`) under pandas' default `dropna=True` — the pattern
breakdown above originally only covered the 175 pattern-confirmed
episodes, missing 622 of 797 (78%) entirely. Fixed in
`backtest_runner.py`/`component_diagnostics.py`.

| group | n | win rate | expectancy |
|---|---|---|---|
| Pattern-confirmed (weighted avg, all 5 patterns) | 175 | — | ~3.71% |
| **No pattern fired** | **622 (78% of all episodes)** | 51.4% | **0.50%** |

A large, consequential gap: **the majority of the system's signal volume
(78%) comes from setups with no confirmed breakout pattern at all**, and
that majority underperforms the pattern-confirmed population by roughly
3.2 percentage points of expectancy. This is exactly what the roadmap's
B-8 "no-pattern path decision" (Phase 4.6) exists to resolve — the two
options being either a monitor-tier demotion for no-pattern signals or a
raised emission threshold for them specifically. This report does not
choose between them; that's a Gate decision.

## Gate 1 extension tests (2026-07-23, per decision #5 below)

Two cheap post-processing tests requested before accepting or rejecting
the "EXECUTE ~ naive momentum" tie as meaningful — both run against
existing logs, no re-runs (`tests/run_gate1_extension.py`).

### (a) Momentum through the same portfolio simulator as Falcon

Momentum's own trades (n=98) run through `portfolio_simulator.py` —
identical 5 slots, identical 1% base risk, identical
`ROUND_TRIP_COST_PCT`. Momentum has no natural stop distance, so its
r_multiple uses the same reference risk unit already used for the
random-entry control (run #1's real median stop_pct, 5.93%), and every
momentum trade is taken at full size (1.0) — no downsizing, unlike
Falcon-(e), which does downsize some of its own trades. This is the more
generous assumption for momentum, not a thumb on the scale for Falcon.

| system | n taken | final equity | max DD | CAGR | Calmar |
|---|---|---|---|---|---|
| momentum_baseline | 98 | 146.26 | **-28.33%** | 21.91% | **0.77** |
| falcon_e_sector_aware | 78 | 117.20 | -4.08% | 9.08% | **2.23** |

**Falcon-(e) wins decisively on both Calmar (2.23 vs 0.77) and max
drawdown (-4.08% vs -28.33%).** Momentum's higher raw CAGR is bought with
nearly 7x the drawdown — the same volatility difference test (b) below
quantifies directly. At the portfolio level, where risk is actually
priced, momentum is not a substitute for Falcon's machinery.

### (b) score≥65 population (n=108) vs momentum (n=98)

| | n | mean | std |
|---|---|---|---|
| Falcon score≥65 (EXECUTE + capped) | 108 | 2.66% | **8.61%** |
| Naive momentum | 98 | 2.67% | **20.64%** |

Mean difference: -0.01pp, 95% CI [-4.45, 4.43]. Welch's t: t=-0.005,
p=0.9956. Mann-Whitney U: p=0.7299. Cohen's d: -0.001 (~zero).

**The mean-return tie is confirmed, precisely — not a fluke of the
smaller n=88 sample.** But momentum's standard deviation is 2.4x
Falcon's (20.64% vs 8.61%). The two systems produce statistically
identical *average* returns from populations with very different
*variance* — which is exactly why (a)'s portfolio-level Calmar comparison
is so lopsided. **The machinery's value doesn't show up in raw per-trade
mean return; it shows up in consistency/risk, which only a portfolio-level
test (not a per-trade mean comparison) can see.**

**Resolution of decision #5's kill criterion:** Falcon wins clearly on
Calmar (test a). Per the human's own framing, this demonstrates the
machinery's value "where it actually lives" — this does *not* raise the
kill-criterion's odds; if anything it's a stronger vindication than a
raw-mean win would have been, since it shows exactly *how* the value is
created (risk reduction, not edge inflation).

### (c) NIFTY buy-and-hold's own Calmar, same window

Requested before treating (a)'s Calmar win as the headline: does
Falcon-(e) beat the *index itself* on risk-adjusted terms, not just
momentum-chasing? (`backtesting/baselines.py::nifty_buy_hold`, now also
reporting `max_drawdown_pct`/`calmar`.)

| system | CAGR | max DD | Calmar |
|---|---|---|---|
| NIFTY buy-and-hold | **-0.95%** | -15.77% | **-0.06** |
| falcon_e_sector_aware | 9.08% | -4.08% | 2.23 |

**This is not the ~12-15% CAGR / ~10-12% drawdown scenario hypothesized
going in.** NIFTY was essentially flat-to-slightly-down over the full
window, with a real -15.77% drawdown along the way — Falcon-(e) beats it
even more decisively than expected (Calmar 2.23 vs -0.06, not ~1.0-1.2),
but for a different reason than "beats a strong index": here it beats a
weak one, on both return *and* risk.

**One nuance worth surfacing rather than leaving implicit:** the window
wasn't uniformly weak. NIFTY fell from 24509 (2024-07-22) to a trough of
22083 (2025-03-04, -9.9%), then rallied to a new all-time high of 26329
on 2026-01-02 (+19.2% off the trough) — a genuine ~10-month recovery to
new highs — before declining again to end the window at 24052
(2026-07-14, roughly flat vs. the start, -8.6% off the January peak).
**The full-window buy-hold number nets out flat/negative because of the
final ~6-month decline, not because the window lacked a real recovery
leg.** This actually strengthens rather than weakens the B-7
justification below: a ~10-month rally to new highs occurring somewhere
inside a window that produced only 13 FAVORABLE days total is hard to
explain as "the market was genuinely never favorable" — it looks more
like the classifier under-firing FAVORABLE during a real uptrend, exactly
what B-7's sanity check (new-high months should mostly read FAVORABLE)
is designed to catch.

## Summary of what does NOT change (no engine edits made this phase)

Every number above comes from post-processing run #1's existing CSV plus a
benchmark-only regime reconstruction (`backtesting/regime_timeline.py`,
which never touches per-ticker replay). No threshold, weight, or
`categorize()` behavior was changed.

---

## Decisions (recorded 2026-07-23)

1. **Exposure-scaling adoption: ADOPTED.** Variant (e), sector-aware
   (CAUTION+NEUTRAL/STRONG at 1/2, CAUTION+WEAK excluded), for run #2.
   Best Calmar among scaled options; reinforced by the extension test
   (a) above.
2. **UNFAVORABLE risk: KEEP BLOCKED for real entries; shadow-log
   would-be entries in run #2.** n=25 across 6 of 8 periods is
   encouraging but too thin to size real risk on. Shadow-logging grows
   the sample for free and turns this into a data-driven Gate 2 decision
   instead of a hunch now.
3. **Cup & Handle: PROBATION (weight -> 0, detection stays on),
   CONDITIONAL on the underperformance holding on the tuning split alone**
   (2024-07-22 -> 2025-09-21, `docs/backtest_success_criteria.md`). Full-
   window numbers have already been seen by everyone in this
   conversation, so enactment is gated on a tuning-split-only re-check to
   keep validation-period data out of the decision. Triangle/VCP ordering
   stays untouched — reordering integers now is exactly the one-window
   reaction Phase 4's calibrated scorer exists to replace wholesale.
4. **No-pattern path (B-8): MONITOR-TIER DEMOTION.** Pattern presence
   required for ALERT_WATCHLIST and above; no-pattern signals recorded in
   the backtest log but not surfaced as live signals. Preserves the data
   for Phase 4's continuous features to potentially rescue an
   unnamed-tight-base subset later; does not raise the global score
   threshold (which would also punish pattern-confirmed 40-64 signals as
   collateral damage).
5. **Naive-momentum tie: RESOLVED, does not raise the kill criterion.**
   See "Gate 1 extension tests" above — Falcon-(e) wins decisively on
   Calmar (2.23 vs 0.77) and max drawdown (-4.08% vs -28.33%) when
   momentum's own trades are run through the identical portfolio
   simulator, and the mean-tie is confirmed precisely (not a small-sample
   fluke) but explained by a 2.4x variance difference, not equal edge.
6. **Success criterion 4: AMENDED, loudly** (see
   `docs/backtest_success_criteria.md`'s dated amendment note). The
   original construction (EXECUTE's mean vs the 95th percentile of
   *individual* random-trade outcomes) is mis-specified — the top 5% of
   individual random trades is always large by construction. Replaced
   with a permutation test: EXECUTE's mean vs the 95th percentile of the
   distribution of random-resample *means*, each resample matched to
   n=20 (or whatever EXECUTE's actual n is in the run being judged).

## Phase 2 scope addition (recorded 2026-07-23)

**Regime recalibration (B-7) is now in scope for Phase 2**, beyond what
was originally listed: 13 FAVORABLE days in a two-year window that
included a sustained recovery is a classifier defect in practice,
independent of the CHOPPY-vs-distribution-days attribution split in G1-b.
Recalibrate on the tuning split only; sanity-check the result against
known market history — months where NIFTY was making new highs should
mostly classify FAVORABLE, or the classifier is still wrong.

**Per standing rule 5, and per the human's explicit instruction: the
extension-test numbers above are reported back before Phase 2 begins.
Not starting Phase 2 implementation in this same turn.**

## B-7 regime recalibration — result (2026-07-23)

Root cause identified: NIFTY's own trend classification
(`technical_analysis/pattern_system/market_structure.py`'s
`MarketStructureEngine.analyze_structure()`, shared with per-stock pattern
gating and sector-breadth Pct_Uptrend) calls UPTREND only when the SINGLE
most recently confirmed HIGH pivot AND the single most recently confirmed
LOW pivot are BOTH individually higher than their own predecessor. A real,
sustained recovery routinely produces one "back-and-fill" pivot pair (a
higher high followed by a slightly lower low before continuing up) that
flips this rule to CHOPPY. Verified directly on the tuning split: the
2025-03-04 trough-to-recovery leg (entirely inside the tuning split) read
CHOPPY on 99 of 136 days (72.8%) under the original rule.

**Recalibration implemented as a market-level-only fix**
(`backtesting/replay_engine.py::_regime_trend_state_of_truncated()`),
deliberately NOT touching the shared `market_structure_engine`/
`_trend_state_of_truncated()` used for per-stock pattern gating and
sector-breadth — that would silently loosen pattern-detection eligibility
system-wide, a much bigger blast radius than "regime recalibration" calls
for. Asymmetric design, tuning-split-only: DOWNTREND keeps the original
strict single-pivot-pair rule (a false negative there is costlier than
one on the upside); UPTREND uses a majority vote over the last 3 confirmed
HIGH pivots and the last 3 confirmed LOW pivots independently, tolerating
one back-and-fill pivot without flipping to CHOPPY.

**Tuning-split verification** (2024-07-22 → 2025-09-21, 292 days):

| | CAUTION | UNFAVORABLE | FAVORABLE |
|---|---|---|---|
| Original | 211 | 75 | 6 |
| Symmetric majority-vote (both sides loosened, tried and rejected) | 197 | 86 | 9 |
| **Asymmetric (adopted)** | 208 | **75 (unchanged)** | **9** |

The symmetric variant (loosening both UPTREND and DOWNTREND) was tried
first and rejected: it also raised FAVORABLE to 9, but raised UNFAVORABLE
too (75→86) — a worse false-negative rate on the side that matters most.
The asymmetric design is a clean improvement over the original: FAVORABLE
+50% (6→9), UNFAVORABLE unchanged, CAUTION down by 3.

**Honest framing for Gate 2:** this is a real, verified improvement, not
a full fix — FAVORABLE is still a small fraction of the tuning split
(9/292, ~3%, up from ~2%). The underlying scarcity finding (G1-b: the
market spent 97%+ of the window in CAUTION/UNFAVORABLE) is a genuine
market-history fact this recalibration cannot and should not paper over;
it only corrects a real classifier defect sitting on top of that fact.
The full-window sanity check the human asked for ("months where NIFTY
was making new highs should mostly classify FAVORABLE") uses the
2026-01-02 all-time high, which falls in the VALIDATION split — reading
that number now would violate standing rule 6, so it is deliberately left
for Gate 2/3's validation-split read, not checked here.

**Addendum (2026-07-23, per the human's follow-up): trend_state alone vs
the combined verdict.** The 6→9 FAVORABLE headline understates how much
the trend classifier itself actually improved, and obscures where the
remaining bottleneck now sits. Trend_state alone, whole tuning split:

| | UPTREND | CHOPPY | DOWNTREND |
|---|---|---|---|
| Original | 38 | 179 | 75 |
| Recalibrated (asymmetric) | 51 | 166 | 75 |

DOWNTREND is byte-for-byte unchanged (75→75, confirms the asymmetric
design touched only the intended side). UPTREND is up 34% (38→51,
+13 days) -- a real, meaningful fix to the actual root cause identified
above.

**But** of those 51 recalibrated UPTREND days, 42 (82%) still get capped
back to CAUTION by `distribution_days >= 3` -- a separate gate this item
never touched (out of scope: B-7 was scoped to trend_state specifically,
not the distribution-day threshold). Under the original rule the cap
rate was 32 of 38 UPTREND days (84%) -- essentially identical. **The
correct framing is "root cause fixed, one layer down, exposing a new
bottleneck underneath it" -- not "regime scarcity solved."** The binding
constraint on FAVORABLE has shifted almost entirely onto the
distribution-day threshold, which was never part of this item's scope
and remains untouched. If Gate 2 shows EXECUTE's episode count still
stuck near n=20 despite this fix, `distribution_days >= 3` (not
trend_state) is where to look next -- but that is a future tuning
decision, not something to act on now.

**On the symmetric-variant rejection, precisely:** the choice between the
symmetric and asymmetric designs was made entirely on the tuning-split
CAUTION/UNFAVORABLE/FAVORABLE count trade-off above (worse UNFAVORABLE
false-negative rate, 75→86, for the symmetric variant) -- the new-high
sanity check was never actually available to inform this choice, since it
needs 2026-01-02 validation-split data. That check remains genuinely
pending for Gate 2/3, not something this recalibration has already
passed.
