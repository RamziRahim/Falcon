# Pre-registration: pullback diagnostics and the momentum-plus-dip test (IA's three steps), half A

**Status: FROZEN on 2026-11-09 ~17:20 IST,** before any run. These are IA's steps, given
after the pullback strategy failed (`docs/pullback_preregistration.md`). Everything is on
half A. Never edit; add dated notes.

## Step 1: does the signal have an edge, separately from the exits?

**Signal cells.** Every (session t, half-A universe stock) gets a flag for each rule of the
frozen pullback strategy (`backtesting/pullback_signals.py`):

| Flag | Rule |
|---|---|
| mkt | Nifty 50 > 200-DMA, and the 50-DMA rising over 5 sessions |
| liq | traded price > ₹100, and 20-day average turnover > ₹10 cr |
| mom | 6-month return, skipping 2 weeks, in the top 20% |
| near52 | Close ≥ 85% of the 52-week high |
| trend | Close above a rising 50-DMA and a rising 200-DMA |
| trig | Close > the previous day's High |
| dip | 3-8 sessions from the swing high (the 12-session lookback) |
| depth | 5-12% |
| nearma | the pullback low ≤ 1.01 × the 20-EMA or the 50-DMA |
| vol | mean dip volume < the 50-day average before the swing high |
| rsi | minimum RSI in the dip between 35 and 50 |
| stop8 | (Close − (pullback low − 0.5 ATR)) / Close ≤ 8% |

**Signal sets:**

| Set | Rules |
|---|---|
| STRICT | all flags |
| L1 | STRICT without vol and rsi |
| L2 | L1 without nearma and stop8, with depth widened to 3-15% and dip to 2-10 sessions |
| L3 | mkt, liq, mom, near52, trend and trig, plus a 5-day return below 0 |
| L0 | mkt, liq, mom, near52 and trend only; momentum leaders with no dip |

**Measured for each signal:**
- the forward returns Close[t+k] / Close[t] − 1 for k = 5, 10, 15 and 20, and the same for
  the Nifty 500;
- the excess return = the stock's forward return minus the Nifty 500's;
- the biggest gain over 20 sessions (max High / Close[t] − 1) and the biggest drop
  (min Low / Close[t] − 1).

**t-statistic:** the excess is averaged by calendar month, and a Newey-West t (3 lags) is
taken over the months. This handles overlapping signals.

**Decision.** A set has an edge if its mean 20-day excess is **≥ +0.5%** with **t ≥ 2**.
- **Set with an edge:** it is rerun as a backtest (Step 1b) with a plain 20-session hold
  and only a stop at entry − 2.5 × ATR(14).
  - Entry: at the signal close.
  - Exit: at the open after 20 sessions.
  - 1% risk, ≤ 25% per position, 6 slots, ≤ 2 per sector, priority by momentum rank.
- **No set with an edge:** the pullback idea is dropped. No exit rule is tried.

## Step 2: remove one filter at a time

Starting from STRICT, drop each of the 12 flags in turn. For each, report:
- the number of signals and the mean 20-day excess, with and without it;
- the t of the difference (the monthly-paired Newey-West t of the with-set minus the
  without-set).

A filter **clearly helps** if removing it lowers the mean 20-day excess by **≥ 0.5pp
with t ≥ 2**. Filters that do not clearly help are listed as candidates to drop. This is
descriptive; a new combination would need its own pre-registration.

## Step 3: the academic momentum-plus-dip test (`backtesting/mom_reversal.py`)

**Ranking (every 10 sessions, at the close).**
- Universe: half-A members with 20-day average turnover ≥ ₹10 cr and a traded price
  > ₹100.
- Rank by the 6-month return skipping the last month: Close[t−21] / Close[t−126] − 1.
- Keep the top 10%.

**Portfolios:**
- **REV:** the 10 stocks in the top 10% with the worst 5-day return (Close[t] /
  Close[t−5] − 1).
- **MOM10:** every stock in the top 10%, equal weight. This is the control: momentum with
  no dip condition.

**Holding.**
- Two tranches, each with half the capital, rebalanced on alternate 10-session dates.
  Each position is held a fixed 20 sessions: bought at the next open, sold at the open 20
  sessions later.
- Equal weight within a tranche.
- Only a catastrophic stop: 15% below the entry, intraday (a gap below it fills at the
  open). A stopped name stays in cash until the tranche's next rebalance.

**Market filter versions:**
- **F:** a tranche does not buy if, at its rebalance close, the Nifty 50 ≤ its 200-DMA.
  It stays in cash for that cycle.
- **N:** no filter.

**Versions:** REV_F, REV_N, MOM10_F, MOM10_N. Costs as in all other tests (CostModel).

**Also reported:** a signal-level check. The mean 20-day forward excess against the Nifty
500 of the REV picks and of the MOM10 picks at each rebalance, with the Newey-West t.

**Adoption rule.** REV is a candidate if, in both W1 and W2:
- REV_N or REV_F beats its own MOM10 version on CAGR; and
- it passes at least 4 of the 6 checks.

## Windows and outputs

- **Windows:** W1, W2 and 2018 for the backtests. The signal statistics pool W1 and W2,
  and are also shown per window.
- **All in-sample.**
- **Outputs:**
  - `data/pullback_diag.txt`
  - `data/mom_reversal_result.txt`
