# Momentum with sector strength, monthly and weekly, and different stop/target rules — pre-registration

**Status: FROZEN on 2026-11-22 17:09 IST**

## Question

IA (2026-11-22) asked three things:

1. **Sector strength.** Does buying only top-momentum stocks whose **sector is also strong** help, for the monthly review (A10) and for the weekly review (WM12, `docs/weekly_momentum_preregistration.md`)?
2. **Stops and targets.** Do different stop/target rules help? These are 1:2 and 1:3 risk-reward targets, and a stop at the previous week's low.
3. All of these combined: four review/sector bases × six exit rules.

## Sector strength (Falcon's existing rule; no new tuning)

This is the sector confirmation already used by Falcon Momentum (`backtesting/falcon_momentum.py`, `sector_maps` and `peer_strength`), recomputed at each month end from data available then.

- **Stocks matched to an NSE sector index:** a stock is matched to the NSE sector index its daily returns correlate with most over the past 252 sessions, if that correlation is at least 0.5. The indices are Auto, Bank, Energy, Financial Services, FMCG, IT, Media, Metal, Pharma, PSU Bank and Realty, where they exist on the day.
  - Its sector is **strong** when that index's 6-month return beats the Nifty 50's **and** the index is above its 50-day average.
- **Stocks with no index match:** the sector is judged by the stock's **peer group**, its 20 most-correlated universe stocks over the past 252 sessions.
  - It is **strong** when the peer group's average 6-month return ranks in the top third of the universe.

**How it is applied (variants marked SEC):**
- At each review, the ranking is taken **only among stocks whose sector is strong on that day**. The top 20 of those are the list.
- A holding whose sector weakens leaves the list at the next review and is sold, as with any name leaving the list.

## Bases

| Code | Review | Sector |
|---|---|---|
| M | Monthly (A10's ranking and timing) | no |
| M_SEC | Monthly | yes |
| W | Weekly (WM12's ranking and timing) | no |
| W_SEC | Weekly | yes |

## Exit rules (applied to every base)

The **ranking exit always applies**: a stock leaving the list at a review is sold at the next open.

| Code | Stop | Target |
|---|---|---|
| **X10** | 10% below the buy price (as A10) | none |
| X10_T2 | 10% below the buy price | 2 × risk = +20% |
| X10_T3 | 10% below the buy price | 3 × risk = +30% |
| XPWL | **Previous week's low**: the low of the last full calendar week before the buy | none |
| XPWL_T2 | previous week's low | 2 × (buy − stop) |
| XPWL_T3 | previous week's low | 3 × (buy − stop) |

**Rules for all exit variants:**
- **Stops:** filled at the stop, or at the open if it gaps through (as A10).
- **Targets:** filled at the target when the day's high reaches it, or at the open if the stock gaps above it.
- **Previous-week-low safeguard:** if that low is at or above the buy price, or more than 15% below it, the 10% stop is used for that position instead. The count is reported.
- **After a stop or target exit,** the stock can be bought again only at a later review, if it is still on the list. This is A10's existing rule for stops.

There are 4 bases × 6 exits = **24 versions**, each on all stocks, half A and half B, in H0, W2, Y2018 and W1.

## Data and references

- **Data:** `data/pit_v2`. Sector indices from `data/pit_sources/indices_2000_2026.parquet`. In 2001–06 only Bank, Energy, FMCG, IT and Pharma exist; other stocks use the peer-group rule.
- **No ethical filter.**
- **References first:**
  - M_X10 must reproduce A10 (`data/a_stop_result.txt`, `data/history_2001_2006_result.txt`) within 0.05pp.
  - W_X10 must reproduce WM12 in `data/weekly_momentum_result.txt` within 0.05pp. That frozen test runs first, unchanged.

## What is judged (all stocks, both W1 and W2; mechanical)

Two questions are judged; everything else is reported.

1. **Does sector strength help the monthly review?** M_SEC_X10 vs M_X10.
2. **Does sector strength help the weekly review?** W_SEC_X10 vs W_X10.

**Each passes if, in both W1 and W2:**
- its CAGR is **no more than 1.0 point a year below** the base;
- its max drawdown is **no more than 1.0 point deeper**;
- it is **clearly better on one:** CAGR at least 1.0 point **above**, or max drawdown at least 3.0 points **shallower**;
- it passes **at least 4 of 6 checks**.

The exit rules are **reported, not judged**. 20 extra versions would make chance winners likely, so the best-looking exit is a lead for a fresh, single-variant pre-registration, not a result.

**Reported for every version:**
- CAGR, max drawdown, checks and win rate;
- trades per year and average hold;
- stop and target exits per year;
- the share of top-20 candidates rejected by the sector rule.

## What it means

- **A sector question passes:** sector strength is added to that review's paper-trading track, and IA decides whether it replaces the plain version.
- **It fails:** no change.
- No other rule changes. IA decides on any list change.

## Output

- `data/momentum_sector_exits_result.txt`
- Runner: `tests/run_momentum_sector_exits.py`
- Dated Results section here; scorecard rows.
