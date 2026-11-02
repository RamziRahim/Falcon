# Redesign pre-registration: two simple strategies on unseen, survivorship-free data

**Status: FROZEN on 2026-11-02.** IA approved it by merging PR #14, before any backtest
of these strategies was run and before the survivorship-free data was even downloaded.
Never edit the rules; add dated notes instead.

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

---

## Dated addendum, 2026-11-02 18:05 IST: Strategy C added before any result exists

IA chose to add a third strategy before any of these strategies had been run. At the time
of writing, the bhavcopy download had only just started on the laptop:
`data/pit/` and all universes, panels and strategy results did not exist yet. Strategies
A and B and the judgement above are unchanged.

**Why C:** it fits IA's 2–4 week horizon, and it follows the only clues seen on the
2024-26 window. Those clues were limit-at-pivot entries beating chased entries in variant
B (9 vs 9 trades), and watchlist signals being mildly positive in run #5. They were
recorded at the time as hypotheses, not evidence. This window, 2019-2024, is where the
hypothesis is tested.

### Strategy C: buy the short dip in a strong stock (2–4 week swing)

**Signal on day t**, all of these must hold:
- **Market:** Nifty 50 close_t > its 200-session SMA. Otherwise there are no new entries;
  open positions are managed normally.
- **Leader:** the stock is in the current month's universe and in the top 30% of that
  universe by 126-session return (close_t / close_(t−126) − 1).
- **Uptrend:** close_t > 200-SMA, 50-SMA > 200-SMA, close_t > 50-SMA.
- **Dip:** close_t < 10-session SMA and close_t / close_(t−3) − 1 ≤ −3%.
- **Liquidity:** median traded value over the last 20 sessions ≥ ₹20 crore.

**Entry:** buy at the open of t+1. If more signals arrive than free slots, take the highest
126-session return first.

**Exits**, whichever comes first:
- stop: 2 × ATR(14) below the fill;
- target: the fill + 2 × (fill − stop);
- the stop wins a same-day tie, and a gap through either level fills at the open;
- time stop: 20 sessions, sold at the next open.

**Sizing:** 1% of equity at risk per trade, at most 10 positions and 100% gross exposure.
Same cost model, delisting rule (last close − 5%), window and six checks as A and B.

**Multiple testing:** three strategies are now tested, so a lucky pass is more likely.
Any pass is provisional, and the next step is forward paper trading, never real money.
If two or more pass, that is reported, not cherry-picked.

---

## Dated note, 2026-11-02 ~18:40 IST: data-preparation fix, before any strategy was run

The download completed (1,727 sessions, 2018-01-01 → 2024-12-31, no errors).

Building `data/pit/` showed that the bhavcopy **PrevClose is not adjusted on ex-dates**.
For example, RELIANCE's 1:1 bonus on 2024-10-28 shows PrevClose 2655.70 against a close of
1334.35. So the "split/bonus-adjusted with NSE's own PrevClose" method above would have
corrupted prices.

It was replaced, before any strategy was run, by NSE's corporate-action records:
- "Bonus A:B" → B/(A+B); a face-value split from Rs X to Rs Y → Y/X;
- several actions on the same day are combined;
- demergers use the ex-date drop (only when it is 5–90%);
- where a record disagrees with the observed ex-date move, the observed factor is used.
  This happened 5 times.

Diagnostics before the run:
- 535 adjustments; 28 one-day moves over 40% remain among universe stocks. These are
  mostly real events, such as the Yes Bank 2020 crash, DHFL and Jet Airways.
- Against the project's own adjusted `data/technical` series (73 overlapping stocks),
  the 2019-24 return differs by >3% for 16. Spot checks (IOC, APLAPOLLO, IRCON) show
  `data/technical` missed smaller bonuses (e.g. IOC's 1:2 bonus in 2022 is still an
  unadjusted −32% day there), so the PIT series is the more accurate one.

The strategy rules, window and checks are unchanged.
