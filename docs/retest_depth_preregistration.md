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
