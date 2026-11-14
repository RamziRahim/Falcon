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

---

## Results, 2026-11-09 (`data/pullback_diag.txt`, `data/mom_reversal_result.txt`), half A

### Step 1: signal edge (20-day excess over the Nifty 500, W1 + W2 pooled)

| Set | Signals | Ex 5d | Ex 10d | Ex 15d | **Ex 20d** | t(ex20) | Max gain / max drop in 20d |
|---|---|---|---|---|---|---|---|
| STRICT (all rules) | 297 | +0.29% | +0.12% | +0.45% | **+0.57%** | 0.75 | +9.2% / −7.5% |
| L1 (no volume / RSI) | 1,027 | +0.31% | +0.47% | +0.84% | **+1.08%** | 2.00* | +9.7% / −7.2% |
| L2 (looser dip) | 5,639 | +0.34% | +0.59% | +1.03% | **+1.21%** | 1.04 | +11.1% / −8.0% |
| L3 (leader + up close after a red week) | 1,685 | +0.31% | +0.43% | +0.96% | **+1.13%** | 1.68 | +11.3% / −7.8% |
| *L0 (leaders only, no dip, no trigger)* | *47,165* | +0.29% | +0.67% | +1.04% | ***+1.35%*** | ***3.03*** | +11.3% / −8.2% |

\*L1's t rounds to 2.00 but is below 2, so it is not flagged.

**Verdict:** no pullback set meets the edge rule (≥ +0.5% and t ≥ 2). **The pullback idea
is dropped, and Step 1b was not run,** as frozen.

The decisive comparison is with **L0**: plain momentum leaders with no dip and no trigger
have a *higher* 20-day excess (+1.35%, t 3.0) than every dip set. The dip conditions
select a subset of the leaders that does no better, and STRICT does worse. The edge is in
the leader filter, i.e. momentum, not in the pullback.

### Step 2: removing one filter at a time from STRICT

No filter clearly helps (≥ 0.5pp with t ≥ 2). Removing these *raises* the 20-day excess:

| Filter removed | Effect on 20-day excess |
|---|---|
| trigger (close > prior high) | +0.97pp, 1,391 signals |
| RSI 35-50 | +0.64pp |
| depth 5-12% | +0.40pp |
| market filter | +0.26pp |

nearma is redundant: removing it changes nothing, because a 5-12% dip of 3-8 days always
reaches the 20-EMA. Only trend (+0.39pp) and mom (+0.26pp) point the right way, both with
t < 1.

### Step 3: momentum + 5-day dip (REV) against momentum alone (MOM10)

| Version | W1 2019-26 | W2 2008-17 | 2018 | ₹10 L grew to (W1 / W2) | Checks W1 / W2 |
|---|---|---|---|---|---|
| REV_N | 16.9% (DD −38%) | −3.8% (−77%) | −29.5% | 33.9 / 6.8 L | 5 / 0 |
| MOM10_N | 15.3% (−39%) | −3.8% (−77%) | −30.0% | 30.4 / 6.8 L | 4 / 0 |
| REV_F (Nifty 200-DMA) | 11.3% (−32%) | 2.9% (−56%) | −32.3% | 23.1 / 13.4 L | 3 / 2 |
| MOM10_F | 8.6% (−30%) | 2.9% (−56%) | −31.3% | 19.0 / 13.3 L | 3 / 2 |

**Signal level** (20-day excess per pick over the Nifty 500):

| | REV | MOM10 |
|---|---|---|
| W1 | +1.40% (t 3.5) | +1.19% (t 3.3) |
| W2 | +0.20% | +0.29% |
| 2018 | −1.1% | −1.2% |

**Verdict:** not adopted.
- REV beats MOM10 in W1 (+1.6pp unfiltered, +2.7pp filtered), but ties it in W2.
- It passes only 0-2 checks in W2.
- Buying the 5-day dip adds about 0.2pp per pick in 2019-26, and nothing in 2008-17.

**On the Nifty 200-DMA filter:** it cost 5-7pp a year in W1, consistent with IA's VIX
observation. But in W2 it was the difference between −3.8% and +2.9%, and between −77%
and −56% drawdowns. Sitting out cost money in the calm decade and saved the portfolio in
the 2008 crash decade.

**This design is far worse than A10 on half A** (monthly 12-1 momentum, top 20, 10%
stop: 25.9% / 11.3%). The likely causes are the fixed 20-day turnover, the 6-month
lookback and the lack of a stop. Not tested.
