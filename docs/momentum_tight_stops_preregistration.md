# Monthly momentum with tighter stops (5–7.5%), larger targets (1:3, 1:5), and half-at-1:1 with a trailing stop — pre-registration

**Status: DRAFT (2026-11-22). Not frozen. No test code written.**

## Question

Monthly momentum (A10) uses a 10% stop and no target. Earlier tests tried 15% and 20% stops and +20%/+30% targets, but never **a tighter stop**, and never **a target as far as 1:5**. IA (2026-11-22) asked:

**With a 5–6% stop, and targets at 1:3 or 1:5, does monthly momentum do better?**

Already known:

| | 2008–17 | 2019–26 |
|---|---|---|
| A10 (10% stop, no target) | 13.17% (DD −59.1%) | 26.36% (DD −39.4%) |
| 15% stop | 12.90% | 28.21% |
| 20% stop | 11.97% | 30.30% |
| 10% stop, +20% (1:2) | 2.00% | 14.36% |
| 10% stop, +30% (1:3) | 4.12% | 20.00% |

## What stays as A10

The selection (12-1 rank, top 20, monthly review, top-500 universe), the buy at the open after month end, sizing, the ranking exit, costs and data (`data/pit_v2`).

## Variants

Stops are measured from the buy price. Stops fill at the stop, or at the open if it gaps through. Targets fill at the target, or at the open if it gaps above. A target = buy + R × stop distance. Stops are checked before targets. **Half-exit rules (H1 variants):**
- The half is sold when the high reaches the 1:1 level, at that level, or at the open if it gaps above it after the buy day.
- If the stop and the 1:1 level trade on the same day, the stop wins.
- The break-even stop is live from the session after the half is sold.
- **Trailing (TR variants):**
  - Steps are measured from the buy price, using the day's high.
  - Once the high has reached the 1:1 level + k × 5%, the stop is the buy price + k × 5% (k = 1, 2, …), live from the next session.
  - The stop never moves down.
- Both halves count as one trade.

A stopped or target-hit stock can be re-bought at a later review if it is still on the list.

| Code | Stop | Target |
|---|---|---|
| **S6 (first judged)** | 6% | none |
| S5 | 5% | none |
| S7 | 7.5% | none |
| S6_T3 | 6% | 1:3 = +18% |
| S6_T5 | 6% | 1:5 = +30% |
| S5_T5 | 5% | 1:5 = +25% |
| S10_T5 | 10% | 1:5 = +50% |
| S10_T8 | 10% | 1:8 = +80% (to see whether a very far target still costs return) |
| S10_H1BE | 10% | **at 1:1 (+10%) sell half**; the rest's stop moves to the buy price (break-even) from the next session; the rest has no target and leaves with the list (added at IA's request, 2026-11-22) |
| S10_H1 | 10% | at 1:1 (+10%) sell half; the rest **keeps the original 10% stop**, no target, leaves with the list |
| S6_H1BE | 6% | at 1:1 (+6%) sell half; the rest moves to break-even, no target, leaves with the list |
| **S5_H1TR (second judged; IA's trailing plan, 2026-11-22)** | 5% | at 1:1 (+5%) sell half and move the rest's stop to the buy price; then **every further 5% rise raises the stop by 5%** (high reaches +10% → stop +5%, +15% → +10%, and so on); no target; the rest also leaves with the list |
| S6_H1TR | 6% | at 1:1 (+6%) sell half, rest to the buy price; then every further 5% rise (+11%, +16%, …) raises the stop by 5% of the buy price |
| S10_H1TR | 10% | at 1:1 (+10%) sell half, rest to the buy price; then every further 5% rise (+15%, +20%, …) raises the stop by 5% of the buy price |
| A10 (reference) | 10% | none |

The A10 reference must reproduce `data/a_stop_result.txt` (W1, W2, Y2018) and `data/history_2001_2006_result.txt` (H0) within 0.05pp before any variant runs.

## Runs

- **Windows:**
  - H0: 2001-01-01 → 2006-12-31
  - W2: 2008-01-01 → 2017-12-31
  - Y2018: 2018
  - W1: 2019-01-01 → 2026-10-30
- **Samples:** all stocks (judged), half A and half B (reported).
- **No ethical filter.**
- **Reported:** CAGR, max drawdown, checks, win rate, average win and average loss, trades and stops per year, and targets hit per year.

## Adoption bar (two judged versions, S6 and S5_H1TR; all stocks, both W1 and W2)

Each judged version replaces A10's 10% stop only if, **in both W1 and W2**:
- its CAGR is **no more than 1.0 point a year below** A10's; **and**
- its max drawdown is **no more than 1.0 point deeper**; **and**
- it is **clearly better on one:** CAGR at least 1.0 point **above**, or max drawdown at least 3.0 points **shallower**; **and**
- it passes **at least 4 of the 6 checks**.

The others are reported only. With 12 extra versions, the best-looking one is a lead for its own single-variant test, not a result.

## What it means

- **A judged version passes:** it becomes a paper-trading track. IA decides whether it replaces the 10% stop.
- **It fails:** no change.

## Output

- `data/momentum_tight_stops_result.txt`
- Runner: `tests/run_momentum_tight_stops.py`
- Dated Results section here; scorecard rows.
