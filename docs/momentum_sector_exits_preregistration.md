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

## Implementation notes (2026-11-22, before running)

- **Sector frame:** `backtesting/sector_strength.py` (`sector_strong`) applies FM's `sector_maps`, `peer_strength` and `idx_ok` per session, using the latest month-end mapping on or before the session.
- **Exits:** `run_momentum(..., allowed, stop_mode="pwl", pwl, target_r)`. The previous week's low comes from calendar-week bars built from daily adjusted data (`backtesting/weekly_support._weekly`). Stops are checked before targets on the same day.

## Results (2026-11-22, run once after freeze)

**References.** Passed: M_X10 reproduced A10, and W_X10 reproduced WM12 (`data/weekly_momentum_result.txt`), exactly, in all four windows. Output: `data/momentum_sector_exits_result.txt`.

**Verdicts (all stocks):**
- **M_SEC_X10: FAILS ITS FROZEN BAR.**
  - W1 passes: 29.18% vs 26.36%, DD −32.7% vs −39.4%, 6/6 checks.
  - W2 fails: 9.36% vs 13.17%, DD −61.3% vs −59.1%.
- **W_SEC_X10: FAILS ITS FROZEN BAR.**
  - W1 passes: 21.18% vs 21.44%, DD −39.1% vs −47.3%.
  - W2 fails: −1.70% vs −2.14%, DD −77.3%, 1/6 checks.

**All stocks, CAGR % (max DD %):**

| Version | H0 2001–06 | W2 2008–17 | Y2018 | W1 2019–26 |
|---|---|---|---|---|
| **Monthly, 10% stop, no target (A10)** | **37.52 (−38.0)** | **13.17 (−59.0)** | −38.88 | 26.36 (−39.4) |
| Monthly, 10% stop, 1:2 | 7.65 (−45.1) | 2.00 (−53.0) | −39.13 | 14.36 (−36.3) |
| Monthly, 10% stop, 1:3 | 16.02 (−38.6) | 4.12 (−50.2) | −35.89 | 20.00 (−36.5) |
| Monthly, prev-week-low stop | 33.09 (−41.5) | 11.06 (−53.9) | −32.40 | 21.52 (−38.5) |
| Monthly, prev-week-low, 1:2 | 0.85 (−48.6) | −1.92 (−46.8) | −33.38 | 7.10 (−37.8) |
| Monthly, prev-week-low, 1:3 | 9.40 (−40.9) | 1.95 (−43.5) | −34.66 | 11.80 (−37.6) |
| **Monthly + sector, 10% stop** | 26.62 (−51.2) | 9.36 (−61.3) | −36.35 | **29.18 (−32.7)** |
| Monthly + sector, 1:2 | 7.20 (−48.4) | −0.18 (−56.2) | −29.80 | 17.93 (−34.1) |
| Monthly + sector, 1:3 | 12.38 (−47.7) | 3.25 (−56.8) | −31.78 | 20.16 (−33.5) |
| Monthly + sector, prev-week-low | 19.34 (−52.7) | 8.79 (−55.8) | −29.72 | 21.08 (−33.2) |
| Monthly + sector, prev-week-low, 1:2 | −3.04 (−49.8) | −2.69 (−50.7) | −26.35 | 10.16 (−34.9) |
| Monthly + sector, prev-week-low, 1:3 | 1.09 (−47.0) | 2.11 (−50.5) | −25.33 | 12.66 (−35.0) |
| Weekly, 10% stop | 17.75 (−60.4) | −2.14 (−82.8) | −34.27 | 21.44 (−47.3) |
| Weekly, 1:2 | −15.09 | −11.08 | −36.75 | 3.93 |
| Weekly, 1:3 | −6.89 | −8.57 | −33.95 | 8.91 |
| Weekly, prev-week-low | 8.93 | −5.66 | −34.15 | 18.52 |
| Weekly, prev-week-low, 1:2 | −24.58 | −15.63 | −38.62 | −3.37 |
| Weekly, prev-week-low, 1:3 | −16.36 | −12.22 | −37.45 | 1.26 |
| Weekly + sector, 10% stop | 3.66 (−72.0) | −1.70 (−77.3) | −29.99 | 21.18 (−39.1) |
| Weekly + sector, 1:2 | −11.24 | −10.27 | −24.56 | 6.75 |
| Weekly + sector, 1:3 | −6.08 | −6.65 | −26.67 | 11.71 |
| Weekly + sector, prev-week-low | −2.07 | −7.53 | −32.64 | 16.99 |
| Weekly + sector, prev-week-low, 1:2 | −23.47 | −17.30 | −35.83 | 1.13 |
| Weekly + sector, prev-week-low, 1:3 | −17.38 | −14.17 | −32.55 | 5.45 |

The sector rule rejected about half the unfiltered top-20 candidates: 52.6% in H0, 49.7% in W2 and 45.7% in W1 (monthly). The halves broadly agree. Monthly + sector in W1 was 17.0% on half A and 21.4% on half B, so the W1 gain on all stocks is not consistent across halves.

**What it means:**

1. **Fixed targets (1:2, 1:3) hurt every version, often badly.** Momentum's profit comes from a few stocks that rise 50–200%; a +20% or +30% target sells them early. Win rates rise, but the average win collapses.
2. **The previous-week-low stop is slightly worse than the 10% stop overall.** It is better only in 2018.
3. **Sector strength helped monthly momentum strongly in 2019–26 but hurt in 2001–06 and 2008–17.** It is not consistent across periods or halves, so by the frozen bar it is not adopted. It is a candidate for IA to watch, not a rule.
4. **Weekly review stays worse in every combination.**
5. **No rule changes.** A10 (monthly, 10% stop, no target, no sector filter) remains the strongest and most consistent momentum version tested.
