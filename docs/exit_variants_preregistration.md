# Pre-registration: two exit variants (breakout-candle stop, half-profit + break-even)

**Status: FROZEN on 2026-11-04 ~11:50 IST,** before any run of these variants. IA asked
for both tests on 2026-11-04 after seeing the swing-low results
(`docs/swing_low_risk_preregistration.md`).

**Multiple testing.** This adds 14 combinations to the many already tested on the same
two windows. IA has chosen to keep adjusting, so this is recorded here: a pass is weaker
evidence each time, and the next step after any pass is forward paper trading, never
real money.

Never edit; add dated notes.

## Unchanged from the swing-low test

- **Entry signals and priorities:** F, S, B, MR.
- **Sizing:** 1% of equity at risk, each position ≤ 25% of equity, at most 10 positions,
  no leverage.
- **Skips:**
  - the stop is more than 15% below the fill;
  - the fill is at or below the stop.
- **Time stop:** 20 sessions.
- **Fill rules:** the stop wins a same-day tie; after the fill day, gaps fill at the open.
- **Unchanged:** costs, data, universe, windows (W1 2019-01-01 → 2026-10-30, W2
  2008-01-01 → 2017-12-31) and the six checks.
- A combination passes only if it passes both windows.

## Test 1: breakout entries (S, B, F) with a stop below the breakout candle

IA's reason: most breakout signals were skipped because the last swing low was more than
15% away.

- **Stop = the breakout-day low − 0.25 × ATR(14).**
  - **B** buys at the next open after a breakout close, so the breakout candle is the
    signal day and its low is known before the order.
  - **S and F** buy with a buy-stop that fills during the breakout day, so the breakout
    candle is the fill day. Its low is known only at that day's close:
    - the stop is set at that close and is live from the next session (a stop below the
      day's own low cannot trade that day);
    - the size at the fill uses the previous session's low − 0.25 × ATR, the only candle
      known at that moment, so the actual risk can differ from 1%.
- **Target = fill × 1.05 (Test 1a) or fill × 1.08 (Test 1b),** reported separately.
- **Exits:** stop, target or the 20-session time stop.
- **6 combinations.**

## Test 2: half profit at half the target, then the stop moves to break-even

This applies to all four entries, with the swing-low stop and both R multiples, so it
compares directly with the swing-low results.

- **Half-way level** = fill + (target − fill) / 2: +1R for 1:2, +1.5R for 1:3.
- **When the high reaches it:**
  - sell half the position there (at the open if it gapped above it, after the fill
    day);
  - from the next session, the stop on the rest moves up to the fill price (break-even).
- **The rest exits at the earliest of:** the full target, the break-even stop, or the
  20-session time stop.
- **Same-day order, conservative:**
  - if the original stop and the half-way level trade on the same day, the stop wins;
  - if the half-way level and the full target trade on the same day, both are taken
    (both are upward);
  - the break-even stop is not live on the day the half is sold.
- A position's two halves are reported as one trade, so the win rate is per position.
- **8 combinations.** Each is reported next to its swing-low result without the half
  exit, to show whether the half exit helps.

## Outputs

- `data/exit_variants_candle5_result.txt`
- `data/exit_variants_candle8_result.txt`
- `data/exit_variants_half2_result.txt`
- `data/exit_variants_half3_result.txt`
- trades in `data/exit_variants_*_trades_*.csv`
