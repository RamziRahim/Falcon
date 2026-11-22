# Realistic entries for Falcon Momentum and v3 patterns — pre-registration

**Status: DRAFT (2026-11-22). Not frozen. No test code written.**

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
