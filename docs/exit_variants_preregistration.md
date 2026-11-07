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

---

## Results, 2026-11-04

Full output: `data/exit_variants_{candle5,candle8,half2,half3}_result.txt`.
**All 14 combinations fail.**

### Test 1: stop below the breakout candle (CAGR W1 / W2, win % W1 / W2)

| Entry | +5% target | +8% target |
|---|---|---|
| S | −19.7 / −32.4 (48.8 / 48.3) | −10.5 / −22.1 (38.9 / 38.2) |
| B | −13.7 / −35.9 (56.2 / 53.4) | −1.6 / −27.3 (47.6 / 43.9) |
| F | −19.4 / −27.6 (37.4 / 40.9) | −19.5 / −23.3 (28.4 / 31.0) |

- **Skipped signals fell** from about 2,500 to about 200 per window for S and B.
- **But the breakout-day candle is large,** so its low is typically 5–7% below the fill.
  With +5%, the average loss is bigger than the average win. With +8%, the win rate
  falls.
- About 400–500 trades a year, so costs compound.
- **Max drawdowns reach −44% to −99%.**

### Test 2: half at the half-way level, then break-even (CAGR W1 / W2)

| Entry | 1:2 without half | 1:2 with half | 1:3 without half | 1:3 with half |
|---|---|---|---|---|
| S | +14.2 / −3.6 | +9.2 / −3.4 | **+20.4 / −0.2** | +16.4 / −3.6 |
| B | +2.1 / −3.4 | +1.9 / −4.4 | −0.1 / −3.2 | −1.9 / −1.2 |
| F | −3.3 / −8.7 | −4.0 / −13.0 | −0.4 / −7.7 | −5.0 / −9.5 |
| MR | −2.2 / −2.2 | −4.3 / −5.7 | −0.7 / −1.8 | −3.1 / −2.3 |

- **The win rate rises** by about 3–8 points, for example S 1:2 W1 48.5% → 53.1%.
- **But CAGR is lower in 14 of 16 cells.** The exceptions are S 1:2 W2 and B 1:3 W2,
  which improve by about 0.3 and 2 points.
- **Why:** the profit in these trades comes from the few full-size winners.
  - Selling half at +1R or +1.5R halves those winners.
  - The break-even stop then exits the rest on ordinary pullbacks.
  - Losers are unchanged: still a full 1R.
- **S 1:3 with half on W1** still passes 5 of 6 checks (t = 1.12), but W2 is −3.6%/yr.

**Verdict per the rules:** no demonstrated edge. The best exit design tested so far is
still the plain swing-low stop with a 1:3 target and no half exit, and that also failed
on 2008–17.
