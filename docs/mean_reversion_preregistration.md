# Mean-reversion pre-registration: classic Connors RSI-2 on liquid Indian large caps

**Status: FROZEN on 2026-11-02 19:40 IST.**

Written:
- before any mean-reversion strategy was run on any Indian data in this project;
- before any 2007-2017 data existed in usable form. The download had been started on
  the laptop, but the combined bhavcopy file still covered only 2018-2026, and
  `data/pit/` had not been rebuilt.

The rules come from the published Connors RSI-2 method, not from looking at our data.
Never edit; add dated notes.

## Why

Every strategy tested so far was trend-following: Falcon breakouts, A momentum, B
52-week-high breakout. C was a dip-buy inside momentum leaders, held up to 20 days.

Classic short-term mean reversion is the remaining well-documented family:
- buy a sharp 2-5 day drop in a stock that is in a long-term uptrend;
- sell on the bounce within days.

It typically has the highest win rate and the thinnest edge per trade, so costs decide
it. Evidence: Connors' US data shows +0.5% to +1.0% average 1-week returns after RSI(2)
below 5. In India, large monthly moves in liquid stocks partly reverse
(Parthasarathy & Sendilvelu, 2022).

## Rules (strategy MR)

**Universe:** on each day, the top 100 by median traded value in the latest month-end
point-in-time universe (`rank <= 100` in `data/pit/universe_monthly.parquet`, ETFs
excluded).

**Signal at close t**, all of these:
- RSI(2) of the stock's close < 5. RSI uses Wilder smoothing:
  `ewm(alpha = 1/2, adjust = False)` of gains and losses.
- Close_t > the stock's 200-session SMA.
- The Nifty 50 close > its own 200-session SMA.

**Entry:** buy at the open of t+1. When more signals arrive than free slots, the lowest
RSI(2) goes first.

**Exits**, whichever comes first; there is no stop-loss, as in Connors' original:
- the first close above the 5-session SMA, sold at the next open;
- a time stop of 10 sessions after entry, sold at the next open;
- delisting: sold at the last close minus 5%, as in all PIT tests.

**Sizing:** 10% of current equity per position, at most 10 positions, no leverage. Costs
use `mtm_portfolio.CostModel` (statutory charges, liquidity spread, square-root impact).
Starting capital ₹10 lakh.

**Secondary, reported only (never used for the verdict):** the same with a disaster
stop 3 × ATR(14) below the fill.

## Windows: both must pass

| window | dates | status |
|---|---|---|
| W1 | 2019-01-01 → 2026-10-30 | data seen for other strategies; MR not yet run on it |
| W2 | 2008-01-01 → 2017-12-31 | unseen; includes the 2008 crash, 2011 and 2013 slumps, 2014-17 bull |

## Pass criteria (each window; all must pass in both)

Mean reversion is out of the market much of the time, so "beat the Nifty's CAGR by 5
points" is the wrong yardstick. These are chosen for a high-frequency, partly invested
strategy:

| # | check | threshold |
|---|---|---|
| 1 | mean net return per trade (after costs) | > 0 with t-stat ≥ 2 |
| 2 | win rate after costs | ≥ 55% |
| 3 | Sharpe ratio (daily, annualised, rf = 0) | > Nifty 50's Sharpe over the same sessions |
| 4 | max drawdown | no worse than the Nifty 50's over the same window |
| 5 | consistency | net profitable in ≥ 70% of calendar years in the window |
| 6 | concentration | top 3 trades < 20% of total profit |

Also reported: CAGR, Nifty CAGR, average holding days, exposure and trades per year.

## Outcomes

- **Both windows pass:** provisional edge; forward paper trading next.
- **Only W1 passes:** treated as period-specific; no real-money plan.
- **No re-tuning** of RSI level, exits, universe size or filters on either window.
