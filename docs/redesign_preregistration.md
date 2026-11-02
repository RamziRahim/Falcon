# Redesign pre-registration: two simple strategies on unseen, survivorship-free data

**Status: DRAFT, not yet frozen.** It becomes binding when IA approves it and it is
merged, before any backtest of these strategies is run. After that, never edit the rules.
Add dated notes instead.

## Why

The Leadership breakout system is unproven: run #5, variant B and the step 2 refit all
failed (`docs/run5_preregistration.md`, `docs/refit_preregistration.md`). The common
cause is that under honest fills it finds too few trades to test.

This document fixes, in advance, the rules for two much simpler strategies:
- **A, momentum rotation:** the strongest well-documented effect in Indian equities,
  and the benchmark that did best in runs #5 and #6 (+25% / +39%, with survivorship bias).
- **B, simple breakout:** a textbook rule with no fitted model.

## Data and window: never used to design anything in Falcon

- **Prices and universe:** `data/pit/` from `tests/build_pit_universe.py`, built from NSE
  bhavcopies.
  - Includes every stock that traded, including those later delisted or merged.
  - Split/bonus-adjusted with NSE's own PrevClose.
  - Universe at each month end = top 500 by median traded value over the prior 126
    sessions (EQ series, ≥ 80% of sessions traded).
- **Test window: 2019-01-01 → 2024-07-31.** Falcon's development, tuning and every
  earlier backtest used 2024-07 onwards, so this window is unseen. 2018 data is used only
  for look-back.
- **Delisted, suspended or merged stocks:** exit at their last available close with an
  extra 5% haircut. A stock that disappears is assumed to have ended badly, not at par.

## Strategy A: monthly momentum rotation (no parameters fitted)

1. At each month end, take the universe of that month end.
2. Rank by 12-1 momentum: the return from 252 sessions ago to 21 sessions ago. Stocks
   with less than 252 sessions of history are skipped.
3. Hold the top 20, equal-weight. Rebalance at the **next session's open**. Names that
   stay keep their position; only changes are traded (no re-weighting of names that stay).
4. No stops, no market filter, no leverage.
5. Costs use `backtesting/mtm_portfolio.CostModel`: statutory charges, liquidity-tiered
   spread and square-root impact. Starting capital ₹10 lakh.

## Strategy B: simple breakout (textbook rules, chosen before any test)

**Entry:** a signal on day t, for a stock in the current month's universe, needs all of:
- Close_t > the highest close of the prior 252 sessions (52-week closing high);
- Volume_t ≥ 1.5 × the 50-session average volume;
- Close_t > 50-session SMA > 200-session SMA.

Buy at the open of t+1. No buy if that open is ≥ 5% above Close_t, since the price would
be chased.

**Exits**, whichever comes first:
- stop: 2 × ATR(14) at entry below the fill price (a gap through the stop fills at the
  open);
- trend exit: the first close below the 50-session SMA, sold at the next open;
- time stop: 60 sessions, sold at the next open.

**Sizing:**
- 1% of equity at risk per trade (risk = fill − stop);
- at most 10 positions and at most 100% gross exposure;
- when more signals arrive than free slots, take them in order of highest volume ratio;
- the same CostModel as Strategy A.

## Judgement: same for both, decided now

Each strategy is judged on 2019-01-01 → 2024-07-31 against these benchmarks:
- **Nifty 50 total-price index**, buy-and-hold (`data/raw/^NSEI.parquet`);
- **PIT equal-weight universe**, rebalanced monthly. This shows whether returns come from
  stock selection or just from owning smaller stocks.

All of the following must pass to say "edge demonstrated":

| # | check | threshold |
|---|---|---|
| 1 | CAGR minus Nifty CAGR | ≥ 5 percentage points per year |
| 2 | CAGR minus PIT equal-weight CAGR | > 0 |
| 3 | monthly excess return over Nifty | t-stat ≥ 2 (Newey-West, 3 lags) |
| 4 | consistency | excess over Nifty positive in at least 4 of the 6 calendar years (2019-2024, 2024 partial) |
| 5 | drawdown | max drawdown no worse than Nifty's max drawdown minus 10 points |
| 6 | concentration | the 3 best positions (by rupee P&L) < 50% of total profit |

**Outcomes:**
- **Both strategies are judged independently.** Testing two raises the chance of a lucky
  pass, so a pass is treated as provisional. The next step is always forward paper
  trading, never real money.
- **No other variants, parameters or windows** will be tried on 2019-2024 after the
  results are seen. If both fail, the next step is to rethink the approach, not to tune
  these on this window.

## Known limitations, stated up front

- **The universe is a liquidity proxy for the Nifty 500, not the official list.** Market
  cap and free-float are not in the bhavcopies.
- **Dividends are not in the prices,** for the strategies or the benchmarks, so returns
  understate total return roughly equally on all sides.
- **The 5% haircut on disappearing stocks** is an assumption. Most disappearances are
  mergers paid near market price, so this probably understates returns slightly.
