# Monthly momentum, bought on a pullback to weekly support — pre-registration

**Status: DRAFT (2026-11-22). Not frozen. No test code written.**

## Question

Monthly momentum (A10) picks the right stocks but buys them at whatever price the month-end open gives, and it has fallen about two thirds at worst. **If each new top-20 stock is bought only when it pulls back to a support level on its weekly chart, does that give a better entry price, a higher win rate and a smaller drawdown, without giving up much return?**

The closest earlier test was the momentum list bought only on a v3 pattern breakout (A10T). It made about 5% a year in 2019–26, because most slots sat in cash. This test therefore also runs a fallback.

## What stays exactly as A10

- The stock selection: top 20 by 12-month return excluding the last month, ranked at each month-end close, from the monthly top-500 universe.
- The exits: a stock is sold at the rebalance open when it leaves the top 20, and there is a 10% stop from the actual buy price.
- Sizing: each new name gets equity ÷ 20, limited by cash, as in `run_momentum`.
- Costs, fills on exits, data (`data/pit_v2`) and the six checks (`judge()`).

Only **how a new name is bought** changes.

## Weekly chart definitions (no look-ahead)

- **Weekly bars** are built from the daily adjusted data: one bar per calendar week (Mon–Fri) with open, high, low and close. A week's bar, and any level computed from it, can be used from the first session of the following week.
- **Weekly swing high:** a week whose high is above the highs of the 2 weeks before and the 2 weeks after it. It is confirmed, and usable, only after the second following week has closed.
- **Weekly swing low:** the mirror of a weekly swing high, using lows.

## The four support levels

Each is recomputed after every weekly close; it is the limit price for the following week.

- **S1 — Broken prior high:** the most recent confirmed weekly swing high that a later weekly close has risen above, and that is below the latest weekly close. This is old resistance turned support.
- **S2 — 10-week average:** the average of the last 10 weekly closes.
- **S3 — Last higher low:** the most recent confirmed weekly swing low, counted only if it is higher than the swing low before it (an uptrend). Otherwise there is no S3 level.
- **S4 — Confluence ("common support"):** of S1, S2 and S3, take those that exist and are below the latest weekly close. If two or more lie within 3% of each other (measured from the higher one), the level is the midpoint of the closest such pair. Otherwise there is no S4 level that week.

## How a new name is bought

1. At each month-end rebalance, every new top-20 name gets a **limit buy order at its support level**. Names A10 already holds are unchanged.
2. The order is active from the open of the first session after the rebalance signal, the session at which A10 would have bought.
3. **Fill:** in any session where the day's low is at or below the level, the order fills at the lower of the open and the level. If the stock opens below the level, it fills at the open.
4. If the stock has no level that week, there is no order that week. The order waits for the next weekly level.
5. The stop is 10% below the actual fill price.
6. The order lives until the next month-end rebalance. Then:
   - **BA (buy anyway):** if the name is still in the new top 20, it is bought at the rebalance open like A10. If not, the order is cancelled.
   - **CASH (support only):** if the name is still in the new top 20, it gets a fresh support order for the next month. If not, the order is cancelled. Unfilled slots stay in cash.

## Variants

There are 8 variants: 4 levels × 2 fallbacks.

| Code | Level | Fallback |
|---|---|---|
| **MWS_S4_BA (primary)** | Confluence | Buy anyway at the next rebalance |
| MWS_S1_BA, MWS_S2_BA, MWS_S3_BA | Broken high / 10-week avg / higher low | Buy anyway |
| MWS_S4_CASH, MWS_S1_CASH, MWS_S2_CASH, MWS_S3_CASH | as above | Stay in cash |
| A10 (reference) | — | Next open (unchanged) |

## Runs

- **Samples:** all stocks, half A and half B.
- **Windows:**
  - H0: 2001-01-01 → 2006-12-31
  - W2: 2008-01-01 → 2017-12-31
  - Y2018: 2018
  - W1: 2019-01-01 → 2026-10-30
- **Ethical filter:** not applied, so the results compare directly with the stored A10. The filtered version can follow if the primary passes.
- **Reference check first:** A10 on all stocks must reproduce the stored results within 0.05pp: `data/a_stop_result.txt` for W1, W2 and Y2018, and `data/history_2001_2006_result.txt` for H0.

**Reported for every variant:**
- CAGR, max drawdown, the six checks and win rate;
- average buy price vs what A10 paid on the same names, in %;
- share of orders filled at support vs bought by fallback vs never bought;
- average days to fill;
- average cash held.

## Adoption bar (primary only, all stocks, judged mechanically)

MWS_S4_BA is adopted in place of A10's entry only if **in both W1 and W2**:

1. its max drawdown is **at least 5 percentage points shallower** than A10's; and
2. its CAGR is **no more than 2 percentage points a year below** A10's; and
3. it passes **at least 4 of the 6 checks**.

H0, Y2018 and the halves are reported, not judged. The other 7 variants are reported for information only. There is no re-tuning and there are no extra variants.

## What it means

- **If the primary passes:** the paper-trading A10 sleeve would buy new names at weekly confluence support (BA fallback). That change would be written into the paper-trading plan before day one.
- **If it fails:** A10 keeps buying at the next open. A non-primary variant that looks better is a lead for a separate, new pre-registration, not a result.

## Output

- `data/momentum_weekly_support_result.txt`
- Runner: `tests/run_momentum_weekly_support.py`
- Dated Results section here; scorecard rows.
