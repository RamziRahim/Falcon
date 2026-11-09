# Pre-registration: #3 retest entries at the breakout candle's low, the 20-EMA or the 20-SMA (half A)

**Status: FROZEN on 2026-11-09 ~12:50 IST,** before any run. IA asked how every version
of #3 would fare if the entry waited for a retest of:
1. the base of the breakout candle;
2. the 20-EMA or the 20-SMA.

The earlier retest test (`docs/s_retest_preregistration.md`) used the breakout level
itself and failed. Never edit; add dated notes.

## Breakouts

#3's signals as in `backtesting/s_retest.py`:
- S candidates;
- Nifty above its 50-day SMA at the signal close;
- a breakout on day b when the next-day buy-stop at the 20-day high L would have filled
  (High ≥ L, Open ≤ L × 1.03).

**K versions use only clean breakout candles:** Close[b] ≥ L, Close[b] ≥ Open[b], and an
upper wick under 50% of the range. This is known at b's close.

## Entry: a limit buy on sessions b+1 to b+10

| Mode | Limit price |
|---|---|
| candle_low | Low[b], the base of the breakout candle |
| ema20 | the 20-day EMA of closes, as of the previous close |
| sma20 | the 20-day SMA of closes, as of the previous close |

- **Fill:** when the day's low ≤ the limit; fill = min(open, limit).
- **Cancel:** if a session closes below the stop before the fill.
- **Expire:** unfilled after 10 sessions.

## Stop, target and sizing (as #3)

- Stop: #3's swing-low stop from the signal day. Skip if the fill is ≤ the stop, or the
  stop is more than 15% below the fill.
- Target: 3R or 2R from the fill.
- 1% risk, ≤ 25% per position, 10 slots, 20-session time stop; the stop wins ties,
  including on the fill day.

## Versions (half A only, universe filtered as in `docs/close_entry_preregistration.md`)

| | candle_low | ema20 | sma20 |
|---|---|---|---|
| **All breakouts** | RCL3, RCL2 | RE3, RE2 | RS3, RS2 |
| **Clean breakouts** | KCL3, KCL2 | KE3, KE2 | KS3, KS2 |

## Comparison

The half-A references from `data/close_entry_result.txt`:
- S3_REF3 / S3_REF2: buy-stop entry;
- S3_C3 / S3_C2: clean-candle close entry.

## Windows and outputs

- **Windows:** W1, W2 and 2018, with the six checks.
- **Adoption rule:** a version must beat S3_REF of the same target on CAGR in **both**
  W1 and W2.
- **All windows are in-sample.**
- **Output:** `data/retest_depth_result.txt`.

---

## Results, 2026-11-09 (`data/retest_depth_result.txt`), half A

**Half-A references:**
- S3_REF3: 9.9% / 3.4% / −14.8%
- S3_REF2: 7.0% / 5.9% / −12.5%

| Version | W1 2019-26 | W2 2008-17 | 2018 | Trades W1 / W2 | ₹10 L grew to (W1 / W2) |
|---|---|---|---|---|---|
| RCL3 (candle low) | 8.3% (DD −26%) | 3.7% (−30%) | −20.4% | 790 / 786 | 18.7 / 14.4 L |
| RCL2 | 6.5% (−24%) | 1.9% (−31%) | −16.3% | 826 / 817 | 16.4 / 12.0 L |
| RE3 (20-EMA) | 9.2% (−30%) | 3.2% (−30%) | −10.2% | 760 / 797 | 20.0 / 13.7 L |
| RE2 | 9.6% (−25%) | −0.8% (−41%) | −3.3% | 808 / 825 | 20.5 / 9.2 L |
| RS3 (20-SMA) | 6.2% (−31%) | 2.3% (−32%) | −10.3% | 752 / 769 | 16.1 / 12.6 L |
| RS2 | 4.4% (−31%) | −1.3% (−42%) | −15.9% | 795 / 797 | 14.0 / 8.8 L |
| KCL3 (clean + candle low) | 4.9% (−25%) | 6.0% (−17%) | −16.6% | 441 / 395 | 14.6 / 17.9 L |
| KCL2 | 1.6% (−29%) | 4.4% (−16%) | −18.0% | 446 / 398 | 11.3 / 15.4 L |
| KE3 (clean + EMA) | 3.0% (−23%) | 1.8% (−21%) | −16.3% | 437 / 404 | 12.6 / 11.9 L |
| KE2 | 5.5% (−18%) | 0.0% (−25%) | −18.8% | 442 / 410 | 15.2 / 10.0 L |
| KS3 (clean + SMA) | 4.3% (−20%) | 1.4% (−19%) | −13.5% | 421 / 385 | 13.9 / 11.4 L |
| KS2 | 5.6% (−16%) | −0.5% (−24%) | −17.0% | 430 / 390 | 15.3 / 9.5 L |

**Verdict:** no version beats its S3_REF in both W1 and W2. Not adopted.
- **Nearest:** RE2 beats S3_REF2 in W1 (9.6% vs 7.0%) but loses 0.8% in W2.
- KCL3 beats S3_REF3 in W2 (6.0% vs 3.4%, with a DD of −17%) but loses in W1.
- The waits for a deeper dip trade the breakout level for a lower price, but they miss
  the strongest breakouts, which never come back.
