# Monthly momentum with tighter stops (5–7.5%), larger targets (1:3, 1:5), and half-at-1:1 with a trailing stop — pre-registration

**Status: FROZEN on 2026-11-22 17:28 IST**

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

## Implementation notes (2026-11-22, before running)

- `run_momentum(..., half_at_r, half_be, trail_step)` sells the half with `Ledger.trim`, so both halves are one trade record.
- Raised stops wait as "pending" and go live at the next session.
- Checked on a synthetic path: bought at 108 with a 5% stop. The first close above the 113.4 1:1 level was 116, so half sold there. The rest's stop moved to 108 and was hit at 108. Proceeds were as expected.

## Results (2026-11-22, run once after freeze)

**Reference check.** It passed: A10 reproduced the stored results in all four windows. Output: `data/momentum_tight_stops_result.txt`.

**Verdicts (all stocks):**
- **S6: FAILED ITS FROZEN BAR.**
  - W1: 24.68% vs 26.36% (−1.68pp), DD −38.0% vs −39.4%.
  - W2: 12.06% vs 13.17% (−1.11pp), DD −52.0% vs −59.1% (7.0pp shallower).
  - Return fell by more than 1.0pp in both windows.
- **S5_H1TR (IA's trailing plan): FAILED ITS FROZEN BAR.**
  - W1: 8.26% vs 26.36% (−18.1pp), DD −20.4%.
  - W2: −2.11% vs 13.17% (−15.3pp), DD −35.7%.

**All stocks, CAGR % (max DD %):**

| Version | H0 2001–06 | W2 2008–17 | Y2018 | W1 2019–26 |
|---|---|---|---|---|
| **A10 (10% stop)** | **37.52 (−38.0)** | **13.17 (−59.0)** | −38.88 | **26.36 (−39.4)** |
| 7.5% stop | 35.90 (−38.6) | 12.38 (−53.0) | −33.45 | 25.10 (−39.1) |
| 6% stop | 31.34 (−39.5) | 12.06 (−52.0) | −29.01 | 24.68 (−38.0) |
| 5% stop | 29.27 (−36.0) | 12.34 (−48.0) | −24.10 | 24.36 (−34.6) |
| 6% stop, 1:3 (+18%) | −2.62 (−51.2) | 1.65 (−45.2) | −29.52 | 12.53 (−32.2) |
| 6% stop, 1:5 (+30%) | 9.04 (−37.8) | 2.74 (−43.7) | −27.62 | 17.74 (−33.8) |
| 5% stop, 1:5 (+25%) | 1.34 (−39.5) | 1.42 (−41.8) | −22.74 | 14.38 (−31.0) |
| 10% stop, 1:5 (+50%) | 21.35 (−37.6) | 6.57 (−55.5) | −36.92 | 22.26 (−38.1) |
| 10% stop, 1:8 (+80%) | 22.68 (−37.5) | 9.93 (−57.3) | −39.16 | 23.57 (−37.8) |
| 10%, half at 1:1, rest break-even | 15.95 (−43.3) | 5.93 (−47.9) | −36.20 | 16.42 (−32.2) |
| 10%, half at 1:1, rest keeps 10% | 22.07 (−35.5) | 6.99 (−49.9) | −35.14 | 18.46 (−27.4) |
| 6%, half at 1:1, rest break-even | 8.06 (−45.6) | 4.52 (−37.5) | −25.19 | 14.70 (−25.1) |
| **5%, half at 1:1, trail 5%/5%** | −9.89 (−49.8) | −2.11 (−35.7) | −22.66 | 8.26 (−20.4) |
| 6%, half at 1:1, trail 5%/5% | −7.85 (−49.2) | −1.19 (−37.3) | −28.34 | 7.84 (−28.6) |
| 10%, half at 1:1, trail 5%/5% | 0.45 (−45.7) | 0.04 (−47.4) | −36.32 | 11.41 (−38.2) |

**Trades (all stocks, W1):**

| Version | Win rate | Average win | Average loss | Stops a year | Average hold |
|---|---|---|---|---|---|
| A10 | 39.1% | +27.6% | −9.7% | 65 | 48 days |
| 6% stop | 28.6% | +29.9% | −6.5% | 97 | 36 days |
| 5% stop | 25.4% | +30.7% | −5.7% | 108 | 33 days |
| 5% + half + trail | 57.2% | **+5.5%** | −5.6% | 228 | **9 days** |
| 10% + half at 1:1 | 43.7% | +16.7% | −7.9% | 65 | 48 days |

**What it means:**

1. **Tighter stops trade return for a smaller drawdown, roughly one for one.** A 5% stop cut the worst fall by 5–11 points but cost 1–2 points a year in 2008–26, and 8 points in 2001–06. More trades are stopped out: 108 a year vs 65.
2. **Fixed targets keep hurting, even at 1:5–1:8.** A +80% target still cost 2.8–3.2 points a year, because a few stocks rise far more than 80%.
3. **Selling half at 1:1 halves every winner.** The average win drops from +27.6% to +16.7%, and losses stay large.
4. **The step trailing stop turns momentum into short trading.** Each step leaves the stop only about 5% below a new high, and top-momentum stocks routinely dip that much. The rest is sold within about 9 days on average, so winners average only +5.5% and costs rise. The win rate looks good at 57%, but the system loses money over 2001–17.
5. **No rule changes.** A10's 10% stop with no target remains the best. The 5% stop is the only version that came close (−0.8 and −2.0 points, with 5–13 points smaller falls), and it is a lead only.
