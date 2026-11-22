# Monthly momentum with a confluence stop, 1:3 target and risk-based sizing — pre-registration

**Status: FROZEN on 2026-11-23 00:20 IST**

Frozen by Claude on IA's explicit authority (IA, 2026-11-22 23:50 IST: "create the spec, start back testing, freeze the code as you think, choose wise decisions as you think, and execute it"). The idea is IA's (2026-11-22 23:52 IST); the exact rules below are Claude's, written before any test code.

## Question

IA proposed four changes to monthly momentum (A10):
- Choose each stock's stop dynamically, from where support levels cluster (confluence) or from its own price history, rather than a flat 10%.
- Take profit at 1:3.
- Put **more capital where the stop is tight and less where it is wide**, so every trade risks the same amount.

Does that beat A10?

Already known (`docs/momentum_sector_exits_preregistration.md`): a 1:3 target on A10 cost 9 points a year in W2 and 6 in W1; a previous-week-low stop alone cost 2–5. Neither the confluence stop nor risk-based sizing has been tested.

## Entry list (unchanged)

A10's monthly 12-1 ranking, top 20, bought at the open after the month-end close. Leavers are sold at that open. Stops and targets are checked daily as in A10: stop first, then target, with a gap through either filling at the open (after the fill day).

## Confluence stop (stop_mode = "conf")

For a stock bought at open P on session i, there are four candidate support levels, all known before that open:
1. **c1:** the previous calendar week's low (as in the sector-exits test).
2. **c2:** the lowest low of the 20 sessions up to session i − 1.
3. **c3:** close(i − 1) − 2 × ATR(14) at i − 1 (Wilder ATR). This is the stock's own volatility.
4. **c4:** the weekly S1 support level valid for session i (`backtesting/weekly_support.py`).

**Choosing the stop:**
- A candidate is valid if it lies 3% to 15% below P: 0.85 P ≤ c < 0.97 P.
- For each valid candidate, count the valid candidates (itself included) within ±2% of P of it.
- **Confluence:** if the highest count is 2 or more, take the cluster with that count; on a tie, the cluster around the highest candidate. The stop is 1% below the lowest level in that cluster.
- **No cluster, but c3 is valid:** the stop is c3 (the volatility stop).
- **Otherwise:** the stop is 10% below P, as in A10.

The runner reports how often each branch was used and the average stop distance.

## Sizing

- **Equal (EQ):** A10's slots, equity ÷ 20 per new name.
- **Risk-based (RS):**
  - Each new name gets value = min(0.5% × equity ÷ d, 10% × equity), where d = (P − stop) ÷ P.
  - 0.5% is A10's own risk per name: a 5% slot with a 10% stop.
  - If the new names' total exceeds the cash on hand (× 0.995), all are scaled down in proportion.
  - Survivors are not resized, as in A10.

## Variants

- **A10 (reference):** 10% stop, no target, equal slots.
  - On all stocks it must reproduce `data/buystop_mix_result.txt` within 0.05pp (CAGR and max DD) in every window.
  - If it does not, the run stops and nothing is judged.
- **RS_CONF_T3 (primary, IA's specification):** confluence stop, 1:3 target, risk-based sizing.
- **RS_CONF (reported):** confluence stop, no target, risk-based sizing.
- **EQ_CONF_T3 (reported):** confluence stop, 1:3 target, equal slots.
- **EQ_CONF (reported):** confluence stop, no target, equal slots.

The new options are optional `run_momentum` parameters (`stop_mode="conf"`, `conf_levels`, `risk_frac`, `max_pos`) that default to current behaviour.

## Runs

- **Data:** `data/pit_v2`, no ethical filter.
- **Windows:**
  - W2: 2008-01-01 → 2017-12-31 (judged)
  - W1: 2019-01-01 → 2026-10-30 (judged)
  - H0: 2001-01-01 → 2006-12-31 (reported)
- **Samples:** all stocks (judged), half A and half B (reported).
- **Reported:** CAGR, max drawdown, the six checks, win rate, trades, exit mix, stop-branch counts and the average stop distance.

## What counts as "better than A10" (judged: RS_CONF_T3, all stocks)

Both conditions must hold, in **both** W1 and W2:

1. **Its CAGR is at least 1.0 percentage point a year above A10's.**
2. **Its max drawdown is no more than 2.0 points deeper than A10's.**

Otherwise the verdict is **NOT BETTER THAN A10**.

## What it means

- **If better:** it becomes a candidate paper-trading track. IA decides; the frozen plan is not changed by this test.
- **If not:** A10 stays as is.
- A reported variant that clears the bar does not pass by itself. It would need its own frozen test.
- No re-tuning, no extra variants.

## Output

- `data/momentum_risk_sizing_result.txt`
- Runner: `tests/run_momentum_risk_sizing.py`
- Dated Results section here; scorecard rows.
