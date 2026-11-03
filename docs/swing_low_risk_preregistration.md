# Pre-registration: swing-low stop, 1% risk per trade, 1:2 and 1:3 targets

**Status: FROZEN on 2026-11-03 ~20:10 IST,** before any run. Requested by IA:
- place the stop below the previous swing low;
- size each trade so it risks 1% of total capital;
- test R:R 1:2 and 1:3 separately.

The details IA didn't specify were fixed by Claude before any result, using Falcon's
existing conventions where one exists. Never edit; add dated notes.

## Entries: unchanged

Same four frozen signals and priorities as `docs/fixed_rr_preregistration.md`: F, S, B
and MR. They use the same generators (`backtesting/fixed_bracket.py`).

## Stop: below the previous swing low

- **Swing low:** a Falcon fractal pivot (`config.SWING_WINDOW = 3`), meaning no bar within
  3 sessions on either side has a strictly lower low. It must be **confirmed by the
  signal day**: the pivot is at least 3 sessions before it, so there is no look-ahead.
- **Which one:** the most recent confirmed swing low within the last 60 sessions whose
  low is below both the signal close and the order price.
- **Stop** = that low − 0.25 × ATR(14) on the signal day. This is Falcon's
  `STOP_BUFFER_ATR_MULTIPLE`, so the stop doesn't sit exactly on an obvious level.
- **No such swing low** → no order.

## Sizing: 1% of capital at risk

- Position value = 1% of current equity × fill / (fill − stop). If the stop is hit,
  the loss is about 1% of capital plus costs.
- **Limits:**
  - each position ≤ 25% of equity, so a stop closer than 4% risks less than 1%;
  - at most 10 positions;
  - no leverage (cash limits).
- **Skipped at the fill:**
  - the open is at or below the stop;
  - the stop is more than 15% below the fill, which is too wide for a 2–4 week trade.

## Target and exits

- **Target** = fill + R × (fill − stop).
  - **Track A:** R = 2 (1:2).
  - **Track B:** R = 3 (1:3).
  - The two tracks are reported separately.
- **Time stop:** 20 sessions, sold at the next open.
- **Same intraday rules as before:**
  - the stop and target are live from the fill day;
  - the stop wins a same-day tie;
  - after the fill day, a gap through either level fills at the open.
- **Break-even win rate before costs:** 33% for 1:2, 25% for 1:3. Costs push both up
  slightly; they matter less here than in the fixed bracket because stops are wider.

## Windows and judgement

- **W1** = 2019-01-01 → 2026-10-30; **W2** = 2008-01-01 → 2017-12-31.
- Judged by the six checks of `docs/redesign_preregistration.md`.
- A combination passes only if it passes both windows.
- **Reported:** win rate, average win/loss in R, exit mix, and skipped-signal counts.
- 8 combinations (4 entries × 2 targets), so any pass is provisional, and the next step
  is paper trading.
- Same costs, data, delisting rule and universe as all earlier tests.
