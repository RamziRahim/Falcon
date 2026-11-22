# Weekly momentum: the A10 strategy reviewed every week instead of every month — pre-registration

**Status: DRAFT (2026-11-22). Not frozen. No test code written.**

## Question

A10 ranks the top-500 stocks on their 12-month return (skipping the last month) once a month, holds the top 20, and uses a 10% stop. A month can be a long time to hold a stock that has stopped leading, or to wait before buying a new leader.

**If the same strategy is reviewed every week, does it earn more or fall less?** And does a shorter look-back suit a weekly review better?

What is already known and relevant:
- Very short-term winners tend to give back part of their gains (short-term reversal), which is why A10 skips the latest month.
- Weekly reviews also mean more trades and more costs.
- Falcon Momentum's original weekly-rank, Monday-open version made about 9% a year on half A (different rules otherwise).

## What stays as A10

- The universe: monthly top 500 by turnover, in force on the ranking day.
- 20 names, equal slots (equity ÷ 20, limited by cash, split across new names as in `run_momentum`).
- The 10% stop from the buy price. A stopped name is not re-bought before the next review.
- Costs, data (`data/pit_v2`) and the six checks.

## What changes: a weekly review

- **Ranking day:** the last trading session of each calendar week (usually Friday), at its close.
- **Trades:** at the next session's open (usually Monday), exactly as A10 trades at the open after month end.
  - Names leaving the list are sold.
  - New names are bought.
  - Names that stay are kept, with no resizing (as A10).

## Variants

| Code | Ranking (all in sessions, 5 ≈ 1 week, 21 ≈ 1 month) | Holding rule |
|---|---|---|
| **WM12 (primary)** | 12-month return skipping the last month: close[t−21] ÷ close[t−252] − 1 (A10's own ranking) | Top 20; sell when out of the top 20 |
| WM12_B40 | same | Buffer: keep a holding while it ranks in the top 40; new buys fill free slots from the top of the list (fewer trades) |
| WM6 | 6-month return skipping the last week: close[t−5] ÷ close[t−126] − 1 | Top 20 |
| WM3 | 3-month return skipping the last week: close[t−5] ÷ close[t−68] − 1 | Top 20 |
| A10 (reference) | unchanged, monthly | — must reproduce `data/a_stop_result.txt` (W1, W2, Y2018) and `data/history_2001_2006_result.txt` (H0) within 0.05pp before any variant runs |

## Runs

- **Windows:**
  - H0: 2001-01-01 → 2006-12-31
  - W2: 2008-01-01 → 2017-12-31
  - Y2018: 2018
  - W1: 2019-01-01 → 2026-10-30
- **Samples:** all stocks (judged), half A and half B (reported).
- **Ethical filter:** not applied, for comparison with the stored A10. Filtered runs can follow for an adopted variant.

**Reported:**
- CAGR, max drawdown, the six checks and win rate;
- trades per year and turnover;
- total costs as % a year;
- average holding period;
- stops per year.

## Adoption bar (WM12, all stocks, in both W1 and W2, judged mechanically)

WM12 replaces A10's monthly review only if, **in both W1 and W2**:

1. its CAGR is **no more than 1.0 point a year below** A10's; **and**
2. its max drawdown is **no more than 1.0 point deeper** than A10's; **and**
3. it is **clearly better on at least one:** CAGR at least 1.0 point a year **above** A10's, or max drawdown at least 3.0 points **shallower**; **and**
4. it passes **at least 4 of the 6 checks**.

The other variants are reported for information only. There is no re-tuning and there are no extra variants.

## What it means

- **WM12 adopted:** a weekly-review momentum track is added to paper trading and IA decides whether it replaces A10 there.
- **It fails:** A10 stays monthly. A reported variant that looks better is a lead for a new pre-registration, not a result.

## Output

- `data/weekly_momentum_result.txt`
- Runner: `tests/run_weekly_momentum.py`
- Dated Results section here; scorecard rows.
