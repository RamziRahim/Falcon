# Realistic entries for Falcon Momentum and v3 patterns — pre-registration

**Status: FROZEN on 2026-11-22 14:08 IST**

## Question

Two of the three paper-trading candidates contain sleeves that **buy at the close of the day that confirms the signal**:

- **Falcon Momentum, clean close (FM_C3):** buys at the close of a day that closes above the 20-day high with a clean candle.
- **v3 patterns (P3):** buys at the close of a breakout day that closes above the pivot, in the upper half of the day's range.

A real trader cannot do exactly this:
- the candle is only confirmed at 3:30 pm, when the market has closed;
- NSE's official close is a weighted average of the last 30 minutes, not a tradable price;
- a paper engine running at 7 pm would give itself fills no person could get.

**If these sleeves instead buy at the next day's open, after the close confirms the signal, do the three candidates still hold up?** A next-open order can be placed the evening before, so it is fully automatic and fully realistic.

Already known, not re-run (`docs/falcon_momentum_entries_preregistration.md`, half A, 1:3): FM with a resting buy-stop at the 20-day high (also realistic, but with no candle check) made 12.98% in W1 and 9.98% in W2. The clean close made 14.49% and 12.69%, and the Monday open after the weekly rank made 9.10% and 8.74%.

## Variants (only the fill changes; signals, stops, targets, sizing, slots and costs are unchanged)

- **FM_C3O:** the same clean-close signal on day t; a market buy at the **open of day t+1**.
  - Skip if that open is more than 5% above day t's close (`falcon_momentum.MAX_GAP`, FM's existing gap rule).
  - Stop = max(swing stop, fill − 3 ATR), with ATR as of day t; target 3R from the fill. This is the existing rule, applied to the new fill.
- **P3O:** the same v3 breakout-day signal on day t; a market buy at the **open of day t+1**.
  - Skip if that open is more than 5% above day t's close, or at or below the setup's stop.
  - Stop = the setup's own stop (`stop_rule="setup"`); target, time stop and stop-window rules as P3.
- **The mixes, rebuilt from these sleeves:**
  - **C_F_A_O** = FM_C3O + A10, half each.
  - **C_F_A_P3O** = FM_C3O + A10 + P3O, a third each.
  - Both use `combine(..., True)`, as for C_F_A and C_F_A_P3.
- **References,** run in the same script:
  - FM_C3, P3, C_F_A and C_F_A_P3 with close fills (unchanged);
  - A10, which is unchanged in both.

## Runs

- **Data:** `data/pit_v2`.
- **Windows:**
  - H0: 2001-01-01 → 2006-12-31
  - W2: 2008-01-01 → 2017-12-31
  - Y2018: 2018
  - W1: 2019-01-01 → 2026-10-30
- **Pattern setups:** the same per-window v3 scans as `docs/ethical_filter_history_preregistration.md`.
- **Samples:** all stocks, half A and half B.
- **Ethical filter:** not applied, so the results compare directly with the stored references. The filtered version would follow for whichever entry is adopted.
- **Reference check first:** on all stocks, the close-fill FM_C3, P3, C_F_A and C_F_A_P3 must reproduce `data/ethical_filter_history_result.txt` (unfiltered blocks) within 0.05pp in every window.

**Reported for each variant:**
- CAGR, max drawdown, the six checks, win rate and trades;
- average gap (next open vs signal close);
- the number of signals skipped for a gap.

## What counts as "holds up with realistic entries" (judged: all stocks, C_F_A_O and C_F_A_P3O)

Both conditions must hold for each mix:

1. **It beats the Nifty in each of H0, W2 and W1.**
2. **In W1 and in W2, its CAGR is no more than 2.0 percentage points a year below its close-fill version.**

FM_C3O, P3O, Y2018 and the halves are reported, not judged.

## What it means

- **If a mix holds up:** paper trading uses next-open entries for its FM and P3 sleeves, and the whole system runs from the 7 pm job with orders for the next open.
- **If it does not:** that mix's edge depends on buying at the close. IA then decides among three options:
  - (a) use FM's resting buy-stop at the 20-day high (already tested; it would need its own forward test as a mix);
  - (b) build a 3:15 pm decision job using live prices from a broker data feed, as a bigger build;
  - (c) drop the mix from paper trading.

  The verdict never removes a candidate by itself (IA, 2026-11-22).
- No strategy rules change otherwise.

## Output

- `data/entry_realism_result.txt`
- Runner: `tests/run_entry_realism.py`
- Dated Results section here; scorecard rows.

## Implementation notes (2026-11-22, before running)

- **FM_C3O:** `run_fm_entries(..., next_open=True)`. A confirmed clean close becomes a market order for the next open, using FM's existing market-order path: gap rule `MAX_GAP` 5% from the signal close, stop = max(swing, fill − 3 ATR), with ATR(14) **as of the signal day** as this doc says. The old close-fill code uses the ATR of the session before the signal day, a one-session difference.
  - The watch-list entry is kept until a fill, as for every other FM order type. A signal skipped for a gap can therefore signal again on a later day.
  - The fill day gets the normal same-day stop and target checks, since it was not bought at the close.
- **P3O:** `run_setups_v2(..., entry="next_open")`. Pending orders fill at the next open, before that session's exit checks, so the same-day stop and target apply.
  - Skipped when: the open is > 5% above the signal close; the open is at or below the setup stop; the stop window (MAX_STOP) fails at the fill; or slots are full at the open.
  - Slots are also checked at the signal, as in P3.

## Results (2026-11-22, run once after freeze)

**Reference check.** It passed: the close-fill FM_C3, P3, C_F_A and C_F_A_P3 reproduced `data/ethical_filter_history_result.txt` exactly in H0, W2, Y2018 and W1. Output: `data/entry_realism_result.txt`.

**Verdict (mechanical, all stocks):**

| Mix | Beats Nifty H0 / W2 / W1 | CAGR shortfall vs close-fill, W1 / W2 | Verdict |
|---|---|---|---|
| **C_F_A_O** | yes / yes / yes | 2.37 / 2.67pp | **DOES NOT HOLD UP** (limit 2.0pp) |
| **C_F_A_P3O** | yes / yes / yes | 3.44 / 2.26pp | **DOES NOT HOLD UP** |

**All stocks, CAGR % (max DD %), close fill → next open:**

| Strategy | H0 2001–06 | W2 2008–17 | Y2018 | W1 2019–26 |
|---|---|---|---|---|
| FM_C3 → FM_C3O | 31.03 → 20.39 (−18.2) | 12.56 → 7.22 (−29.4) | −13.39 → −16.02 | 11.71 → 7.23 (−26.5) |
| P3 → P3O | 11.66 → 9.43 (−14.7) | 7.57 → 6.11 (−22.3) | −16.57 → −15.62 | 15.16 → 9.71 (−18.1) |
| C_F_A → C_F_A_O | 35.56 → 30.05 (−26.1) | 13.46 → 10.79 (−34.8) | −26.85 → −27.95 | 19.49 → 17.12 (−26.6) |
| C_F_A_P3 → C_F_A_P3O | 27.59 → 23.25 (−21.7) | 11.75 → 9.49 (−25.2) | −23.41 → −23.91 | 18.35 → 14.91 (−22.4) |

The halves show the same picture. The weakest is FM_C3O on half B in W1, at 0.95%.

**How big the gap is:**
- The average next-open gap was small: +0.6% to +1.1% for FM and +0.3% for P3, and few signals were skipped for gaps over 5%.
- The loss is larger than the gap. FM's mean net per trade in W1 fell from +1.90% to +1.46%, and its win rate from 44.0% to 41.4%.
- Buying the next open also gives up the "no stop check on the entry day" advantage of a close fill.

**What it means:**
- Much of FM's and P3's measured edge sits in buying the confirming close.
- A realistic next-open entry keeps both mixes ahead of the Nifty in every period, but costs 2–3½ points a year.
- By the frozen rule, IA now decides among three options:
  - (a) FM's resting buy-stop at the 20-day high;
  - (b) a 3:15 pm decision job with live prices;
  - (c) running the mixes with next-open entries anyway, accepting the lower expected return.
- Nothing is removed automatically.
