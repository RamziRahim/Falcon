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

## Results (2026-11-23, run once after freeze)

**References.** Passed: FM_C3 and C_F_A reproduced `data/buystop_mix_result.txt` exactly on all stocks, half A and half B, in every window present (18 checks). Output: `data/fm_conviction_slots_result.txt`.

**Verdict (FM_C3_SWAP vs FM_C3): NOT ADOPTED.** Four of the seven conditions failed.

| Condition | Result | |
|---|---|---|
| 1. All stocks W2, CAGR gain ≥ +1.0pp | −2.00pp (10.56% vs 12.56%) | FAIL |
| 1. All stocks W1, CAGR gain ≥ +1.0pp | −0.61pp (11.10% vs 11.71%) | FAIL |
| 2. All stocks W2, drawdown ≤ 2 pts deeper | 4.73 pts deeper (−30.9% vs −26.1%) | FAIL |
| 2. All stocks W1, drawdown ≤ 2 pts deeper | 3.35 pts shallower | pass |
| 3. Half B W2, CAGR not lower | −2.48pp | FAIL |
| 3. Half B W1, CAGR not lower | +5.69pp | pass |
| 4. All stocks H0, CAGR not lower | +0.60pp | pass |

**CAGR % (max DD %)**

| Version | Sample | H0 2001–06 | W2 2008–17 | W1 2019–26 |
|---|---|---|---|---|
| FM_C3 | All | 31.03 (−14.2) | 12.56 (−26.1) | 11.71 (−23.8) |
| **FM_C3_SWAP** | All | 31.63 (−13.5) | 10.56 (−30.9) | 11.10 (−20.4) |
| FM_C3_PICK | All | 28.44 (−14.6) | 12.06 (−24.9) | 12.52 (−22.8) |
| C_F_A (track 3) | All | 35.56 (−24.6) | 13.46 (−35.9) | 19.49 (−25.9) |
| C_F_A_SWAP | All | 35.89 (−25.9) | 12.47 (−35.9) | 19.18 (−27.5) |
| FM_C3 / SWAP / PICK | Half A | 15.20 / 19.65 / 15.81 | 12.04 / 11.04 / 12.20 | 14.49 / 9.91 / 13.32 |
| FM_C3 / SWAP / PICK | Half B | 23.74 / 24.86 / 24.07 | 11.62 / 9.14 / 8.85 | 8.40 / 14.09 / 11.79 |

**Activity:** on all stocks, FM_C3_SWAP made 75 swaps in W2 and 72 in W1. Slot-full skips stayed high (632–768 for all stocks), since most skipped signals did not meet the high-conviction condition.

**What it means, in plain English:**
- Swapping a losing holding for a strong new breakout **did not help.** It cost 2.0 points a year in 2008–17 and 0.6 in 2019–26, with a deeper 2008–17 drawdown.
- Many of the losing holdings that were sold would have recovered, and each swap pays costs twice.
- Ordering same-day signals by breakout strength alone (PICK) was mixed:
  - All stocks: −0.5, +0.8 and −2.6 points a year across the three periods.
  - Half B in 2008–17: −2.8.
- Both are erratic across samples and periods: big gains in one cell, big losses in the next. That is the signature of noise, not an edge.
- FM's own order (momentum rank) stays. Nothing changes in paper trading. IA decides.
