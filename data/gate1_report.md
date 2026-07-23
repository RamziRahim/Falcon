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

## Summary of what does NOT change (no engine edits made this phase)

Every number above comes from post-processing run #1's existing CSV plus a
benchmark-only regime reconstruction (`backtesting/regime_timeline.py`,
which never touches per-ticker replay). No threshold, weight, or
`categorize()` behavior was changed.

---

## Decisions needed from the human before Phase 2 starts

1. **Exposure-scaling adoption.** Given G1-a/c: adopt an exposure-scaling
   policy for CAUTION-capped signals (recommend: sector-aware variant (e),
   best Calmar among the scaled options)? Reject and keep the hard cap?
   Request a different variant?
2. **UNFAVORABLE risk.** Given the clustering result (6 of 8 periods,
   n=25, thin): trade UNFAVORABLE-capped signals at all (variant (c),
   1/4 size), or leave UNFAVORABLE fully blocked (variant (b/d)) pending
   more data from run #2?
3. **Pattern-weight recalibration scope.** Given G1-e's confirmed
   inversion: is re-deriving `PATTERN_WEIGHTS` in scope for run #2's
   engine changes (Phase 2), or held for Phase 4's calibrated scorer?
4. **No-pattern path (B-8).** Given G1-f: monitor-tier demotion, raised
   emission threshold, or something else, for the 78%-of-volume
   no-pattern population?
5. **Naive-momentum result.** Given G1-d's tie with naive momentum on this
   run: does this change what Phase 2/3 prioritizes (e.g. moving faster
   toward the structural-exit/RR-floor work in 2.2, which naive momentum
   has none of and might separate the two), or is this treated as
   noise pending run #2's larger/cleaner sample?
6. **Success criterion 4's construction.** Revisit the "beat random's 95th
   percentile" framing for run #2, given the mean-vs-percentile mismatch
   noted in G1-d?

**Per standing rule 5: this report does not proceed into Phase 2 on its
own. Awaiting the human's read.**
