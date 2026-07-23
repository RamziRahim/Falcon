# Falcon — Backtest Success Criteria (I-8)

Pre-registered before reading any Phase 1 diagnostic output, per the master
execution spec's standing rule 6: nothing here may be adjusted after the
fact to match whatever a given run produced. If a run fails a criterion,
the criterion doesn't move -- the finding gets reported as a failure and
the human decides what to do about it at the relevant STOP GATE.

## Criteria

1. **Net expectancy per EXECUTE episode >= +0.20R.** Measured at the
   episode level (`backtesting/episode_builder.py`'s `r_multiple`, which is
   already net of `ROUND_TRIP_COST_PCT`), not the raw per-signal level --
   an episode is the unit a real portfolio would actually trade.

2. **Strict ordering: EXECUTE > ALERT_WATCHLIST > AVOID**, net expectancy,
   episode level. AVOID's forward outcomes come from A-1 (Phase 2.5) since
   run #1 never recorded them; this criterion isn't testable until that
   instrumentation lands and a new run captures it.

3. **Max drawdown <= 20%** in the portfolio simulator
   (`backtesting/portfolio_simulator.py`, I-5) at 1% risk per trade / 5
   concurrent slots.

4. **[AMENDED 2026-07-23 -- see note below] EXECUTE's mean net return beats
   the 95th percentile of the distribution of random-resample means, each
   resample matched to n = EXECUTE's actual episode count in the run being
   judged** (I-4 baseline, K=100 resamples, each resample itself drawn as
   `n` random-entry draws averaged to a single mean; the 95th percentile is
   taken across the K resample means, not across individual trades).

   > **Amendment note (2026-07-23):** the original construction compared
   > EXECUTE's *mean* return against the 95th percentile of *individual*
   > random-trade outcomes. That comparison is mis-specified: the top 5%
   > of individual random trades will always be large by construction
   > (that's what a 95th percentile of single-trade noise is), so no
   > strategy's average trade could realistically clear it -- it is not a
   > test of whether the strategy beats chance. Discovered during Gate 1
   > (`data/gate1_report.md`) when EXECUTE's 2.74% mean (n=20) failed to
   > clear the original criterion's 7.12% while decisively beating the
   > random control's own mean (-0.45%) and median (-1.01%). The corrected
   > test is a proper permutation test: compare EXECUTE's mean against the
   > sampling distribution of *means* of equal-sized random samples --
   > which asks the right question (would EXECUTE's average performance
   > be unusual for a same-sized random sample?) instead of an
   > unanswerable one. Editing a pre-registered criterion is exactly what
   > pre-registration is meant to guard against; this note exists so the
   > change is loud, not quiet, and is not a licence to revisit criteria
   > again without an equally explicit, dated justification.

## Tuning / validation split

Run #1's window is 2024-07-22 -> 2026-07-14 (~24 months, by `entry_date`).
Split at the 14-month mark:

- **Tuning split: 2024-07-22 -> 2025-09-21** (~14 months). Every threshold,
  weight, or scorer coefficient decision in Phase 4 is made only against
  episodes whose `episode_start_date` falls in this range.
- **Validation split: 2025-09-22 -> 2026-07-14** (~10 months). Read-only.
  Evaluated exactly once per candidate model (e.g. once for the calibrated
  v2 scorer at Gate 3) -- never iterated against. More than one look at
  this split to "see how a change did" and decide whether to keep it
  defeats the entire purpose of holding it out.

This split boundary is fixed by this document, not recomputed per run --
if a later run extends the window (Phase 5.4, history back to ~2019), the
split date is revisited deliberately and explicitly, not silently shifted.

## What is never tuned

- These criteria, once committed.
- The validation split, at any point before its one-time read.
- Anything against the full undivided dataset (tuning happens only on the
  tuning split, per standing rule 6).
