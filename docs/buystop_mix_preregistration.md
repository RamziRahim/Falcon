# The current mix with Falcon Momentum entering on a resting buy-stop — pre-registration

**Status: FROZEN on 2026-11-22 18:06 IST**

## Question

Paper-trading track 7 needs a Falcon Momentum entry that is both realistic and automatic. `docs/entry_realism_preregistration.md` showed that buying at the next open costs the mixes 2.4–3.4 points a year against buying at the confirming close.

A **resting buy-stop at the 20-day high** is realistic: the order sits with the broker and fills the moment the price crosses. It was tested as a standalone strategy in `docs/fm_high20_preregistration.md` (half A, 1:3: 12.98% in W1, 9.98% in W2) but never inside a mix.

**Does the current mix (half monthly momentum, half Falcon Momentum) still hold up when FM enters this way?**

## Variants (no rule changes beyond the FM entry)

- **FM_H3:** `run_fm_entries(..., mode="high20", r_mult=3.0)`, exactly as frozen in `docs/fm_high20_preregistration.md`.
  - While on the watch list, a one-session buy-stop at the 20-day high fills at max(level, open).
  - It is skipped if the open is more than 3% above the level.
  - Stop = higher of the swing-low stop and fill − 3 ATR; target 3R.
  - There is no candle check.
- **C_F_A_H (primary):** FM_H3 + A10, half each, via `combine(..., "FA", True)`, as for C_F_A.
- **C_F_A_P3_HO (reported):** FM_H3 + A10 + P3O, a third each. P3O is the next-open v3 pattern sleeve from `docs/entry_realism_preregistration.md`, so all three sleeves are realistic.
- **References,** in the same script:
  - FM_C3, C_F_A (close fill) and C_F_A_O (next open) on all stocks must reproduce `data/entry_realism_result.txt` within 0.05pp in every window.
  - If any does not, the run stops and IA is told.

## Runs

- **Data:** `data/pit_v2`.
- **Windows:**
  - H0: 2001-01-01 → 2006-12-31
  - W2: 2008-01-01 → 2017-12-31
  - Y2018: 2018
  - W1: 2019-01-01 → 2026-10-30
- **Samples:** all stocks (judged), half A and half B (reported).
- **Ethical filter:** not applied, so the results compare with the stored references.
- **Pattern setups:** as in `docs/entry_realism_preregistration.md`.
- **Reported:** CAGR, max drawdown, the six checks, win rate, trades, gap skips, and FM_H3 fills per year.

## What counts as "holds up with a buy-stop" (judged: C_F_A_H, all stocks)

Both conditions must hold:

1. **It beats the Nifty in each of H0, W2 and W1.**
2. **In W1 and in W2, its CAGR is no more than 2.0 percentage points a year below C_F_A (close fill).**

This is the same bar the next-open mixes were held to.

## What it means

- **If it holds up:** track 7 (current mix, FM on a buy-stop) joins paper trading.
- **If it does not:** IA decides whether track 7 runs anyway. The verdict never removes it by itself (IA, 2026-11-22).
- No strategy rules change.

## Output

- `data/buystop_mix_result.txt`
- Runner: `tests/run_buystop_mix.py`
- Dated Results section here; scorecard rows.

## Results (2026-11-22, run once after freeze)

**References.** Passed: FM_C3, C_F_A and C_F_A_O reproduced `data/entry_realism_result.txt` exactly in all four windows. Output: `data/buystop_mix_result.txt`. The runner prints the verdict label "HOLDS UP WITH REALISTIC ENTRIES"; it is the same bar.

**Verdict (C_F_A_H, all stocks): HOLDS UP WITH A BUY-STOP.**
- It beats the Nifty in H0 (31.91% vs 21.19%), W2 (11.68% vs 5.54%) and W1 (18.23% vs 10.03%).
- Its CAGR shortfall against C_F_A is 1.26pp in W1 and 1.78pp in W2, within the 2.0pp limit.

**All stocks, CAGR % (max DD %):**

| Version | H0 2001–06 | W2 2008–17 | Y2018 | W1 2019–26 |
|---|---|---|---|---|
| C_F_A (FM buys the close) | 35.56 (−24.6) | 13.46 (−35.9) | −26.85 | 19.49 (−25.9) |
| **C_F_A_H (FM on a buy-stop)** | **31.91 (−29.0)** | **11.68 (−36.8)** | −29.53 | **18.23 (−24.4)** |
| C_F_A_O (FM at the next open) | 30.05 (−26.1) | 10.79 (−34.8) | −27.95 | 17.12 (−26.6) |
| C_F_A_P3_HO (FM buy-stop + A10 + P3 next open) | 24.50 (−23.8) | 10.10 (−26.9) | −25.02 | 15.68 (−20.1) |
| FM_H3 alone | 24.19 (−20.5) | 9.08 (−36.4) | −19.64 | 9.45 (−28.1) |

The halves agree. C_F_A_H vs C_F_A in W1 / W2: half A 19.84 / 10.82 vs 20.66 / 12.29; half B 15.75 / 13.07 vs 16.13 / 12.58.

**What it means:**
- Track 7 (current mix with FM on a resting buy-stop) joins paper trading.
- It is the most realistic fully automatic version of the current mix: about 1.3–1.8 points a year behind buying the close, and about 0.9–1.1 ahead of buying the next open.
