# Monthly momentum, bought on a pullback to weekly support — pre-registration

**Status: FROZEN on 2026-11-22 14:08 IST**

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

## Implementation notes (2026-11-22, before running)

- **Code:** `backtesting/weekly_support.py` computes the levels. `run_momentum(..., support=<levels>, support_fallback="BA"|"CASH")` places the orders; `support=None` (default) leaves behaviour unchanged.
- The four levels were checked by hand on a synthetic weekly series.
- **Several orders filling in the same session** share the cash evenly: per name = min(equity ÷ 20, cash ÷ number filling).
- **Same-day stop:** a limit filled during a session is checked against that session's low for the 10% stop, the same treatment A10 gives its rebalance-day buys.

## Results (2026-11-22, run once after freeze)

**Reference check.** It passed: A10 on all stocks reproduced `data/a_stop_result.txt` (W1, W2, Y2018) and `data/history_2001_2006_result.txt` (H0) within 0.05pp. Output: `data/momentum_weekly_support_result.txt`.

**Verdict (MWS_S4_BA, all stocks): FAILED ITS FROZEN BAR.**

| Window | Max DD vs A10 | CAGR vs A10 | Checks | Result |
|---|---|---|---|---|
| W1 2019–26 | −27.55% vs −39.44% (11.9pp shallower) | 20.29% vs 26.36% (**−6.07pp**) | 4/6 | **FAIL** |
| W2 2008–17 | −33.21% vs −59.05% (25.8pp shallower) | 14.41% vs 13.17% (+1.24pp) | 5/6 | PASS |

**All stocks, CAGR % (max DD %):**

| Variant | H0 2001–06 | W2 2008–17 | Y2018 | W1 2019–26 |
|---|---|---|---|---|
| A10 (reference) | 37.52 (−38.0) | 13.17 (−59.0) | −38.88 | 26.36 (−39.4) |
| **S4 confluence, buy anyway (primary)** | 30.18 (−28.5) | 14.41 (−33.2) | −25.37 | 20.29 (−27.6) |
| S1 broken high, buy anyway | 31.76 (−32.7) | 10.19 (−45.0) | −23.68 | 19.44 (−32.6) |
| S2 10-week avg, buy anyway | 31.14 (−36.4) | 11.38 (−57.1) | −34.16 | 19.59 (−32.6) |
| S3 higher low, buy anyway | 33.09 (−29.1) | 11.28 (−49.0) | −23.44 | 20.61 (−29.8) |
| S4, cash only | 5.71 (−18.1) | 4.30 (−20.8) | −5.33 | 5.24 (−10.4) |
| S1, cash only | 15.52 (−25.5) | 7.30 (−36.2) | −9.10 | 10.51 (−24.7) |
| S2, cash only | 19.57 (−37.0) | 9.06 (−57.1) | −34.03 | 14.99 (−31.9) |
| S3, cash only | 8.65 (−26.4) | 2.49 (−39.6) | −11.10 | 5.34 (−18.9) |

**How the entries behaved (all stocks, W1 / W2):**

| Variant | Orders filled at support | Never bought | Cheaper than A10's open (support fills) | Fallback paid vs A10's open | Average cash |
|---|---|---|---|---|---|
| S4, buy anyway | 15.6% / 15.2% | 310 / 312 | −2.3% / −3.2% | +3.4% / +1.5% | 42% / 39% |
| S1, buy anyway | 48.6% / 46.2% | 198 / 199 | −1.3% / −2.7% | +5.9% / +4.1% | 35% / 33% |
| S3, buy anyway | 31.2% / 31.2% | 239 / 266 | −6.1% / −4.7% | +6.4% / +3.5% | 39% / 35% |
| S4, cash only | 14.6% / 14.0% | 500 / 534 | −3.7% / −4.0% | — | 79% / 78% |

Win rates: A10 39.1% / 32.4%; S4 buy anyway 38.7% / 34.7%; S4 cash only 44.1% / 38.9%.

**What it means:**

1. **The pullback entry did not give better trades on balance.**
   - When a pullback to support happened, the buy was 1–6% cheaper than A10's open.
   - But it happened for only 15–49% of names. The strongest momentum stocks usually kept rising, and those were then bought a month later at 2–6% *higher* prices, or never bought at all.
2. **The smaller drawdowns come mainly from holding less stock.** The buy-anyway versions held 33–42% cash on average, and the cash-only versions about 78%. A strategy that is only 60% invested falls less in a crash, and also earns less in a strong market. That is exactly the W1 vs W2 split: W2 (2008–17) contains the 2008 crash, where cash helped; W1 (2019–26) is a strong run where cash cost 6 points a year.
3. **The cash-only versions confirm the A10T lesson.** Waiting only for support leaves most of the money idle, and returns fall to 2–15% a year.
4. **No rule changes.** A10 keeps buying at the next open. If lower drawdowns matter more than return, the cleaner lever is how much is invested, not the entry. That would be a separate pre-registration. A10_E50, the exposure test, already examined part of this.
