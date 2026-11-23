# Falcon Momentum: conviction decides which signal gets a slot — pre-registration

**Status: FROZEN on 2026-11-23 10:20 IST**

## Question

IA (2026-11-23, "test that too"): FM_C3 holds at most 10 positions.
- On half A it skipped 394–614 clean-close signals per period because all 10 slots were full (`docs/fm_risk_gauge_preregistration.md`).
- When signals compete for a slot, today the order is FM's own priority, its momentum rank on the watch list.

Should conviction decide instead?

## Which fact can rank signals

Market strength is the same for every signal on a given day, so it cannot rank them. The one stock-level fact that marked better FM_C3 trades in both decades of the half-A study (`data/conviction_study.txt`) is **breakout strength**, k = close ÷ the highest high of the previous 20 sessions − 1:

| k | Net per trade, W2 / W1 |
|---|---|
| Bottom third | +1.23% / +2.33% |
| Top third (≥ 2.2%) | +2.76% / +4.09% |

## Variants

All other FM_C3 rules are unchanged: watch list, clean-close test, stops, 1:3 target, 40-session time stop, risk sizing, caps and 10 slots.

- **FM_C3 (reference):** must reproduce `data/buystop_mix_result.txt` within 0.05pp (CAGR and max DD) on all stocks, half A and half B, in every window present. Otherwise the run stops.
- **FM_C3_SWAP (primary).** Two changes:
  1. **Reordering.** Each day's closing signals are filled in order of k, highest first, instead of FM's priority. Ties keep FM's priority.
  2. **Swapping.** A clean signal that finds all 10 slots full replaces a holding, if:
     - Nifty is ≥ 4.1% above its 50-session average, **and** the signal's k ≥ 2.2% (the "1.5×" condition of the conviction-sizing test);
     - **and** some holding bought before today is below its fill price at today's close.

     The holding with the lowest return since its fill is then sold at today's close (exit reason SWAP_OUT, normal costs), and the signal is bought at the same close. At most one swap per signal.
- **FM_C3_PICK (reported):** reordering only, no swapping.
- **C_F_A_SWAP (reported):** FM_C3_SWAP combined with A10 as in track C_F_A, against C_F_A.

New optional parameter: `run_fm_entries(..., slot_rule=None)`, with values "pick" or "swap". The default is unchanged behaviour. The runner reports swaps and the number of slot-full skips.

## Runs

- Windows: W2 2008-01-01 → 2017-12-31 and W1 2019-01-01 → 2026-10-30 (judged); H0 2001–06 (reported, with its own condition).
- Samples: all stocks, half A and half B. Data `data/pit_v2`, no ethical filter.

## Adoption bar (judged: FM_C3_SWAP vs FM_C3)

The same bar as the conviction-sizing test. All four conditions must hold:

1. **All stocks, W1 and W2:** CAGR at least 1.0 percentage point a year above FM_C3's.
2. **All stocks, W1 and W2:** max drawdown no more than 2.0 points deeper.
3. **Half B, W1 and W2:** CAGR not below FM_C3's. The rule's thresholds came from half A.
4. **H0 2001–06, all stocks:** CAGR not below FM_C3's.

Otherwise the verdict is **NOT ADOPTED**. It flags only; IA decides. No re-tuning, no extra variants.

## Output

- `data/fm_conviction_slots_result.txt`
- Runner: `tests/run_fm_conviction_slots.py`
- Dated Results section here; scorecard rows.
