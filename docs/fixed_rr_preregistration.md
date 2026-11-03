# Pre-registration: fixed 1:3 bracket (stop −2%, target +6%) on four entry signals

**Status: FROZEN on 2026-11-03 ~20:00 IST,** before any fixed-bracket run. Requested by IA:
R:R of 1:3, a stop 2% below entry and a target 6% above entry. IA chose 5 slots at 20%
of capital each and all four entry signals. Never edit; add dated notes.

## What changes vs the earlier tests

Only the **exits and sizing**. Every entry signal stays exactly as already frozen:
- **F:** Falcon setups, with a 5-session buy-stop at the pivot. It doesn't chase a >3%
  gap, and it is cancelled if Falcon's own stop level trades first.
- **S:** strong stock in a strong peer group, plus the Nifty 200-SMA switch, with a
  next-session buy-stop at the 20-session high.
- **B:** a close at a 52-week closing high on ≥ 1.5× 50-session volume, with close >
  50-SMA > 200-SMA. Buy at the next open, skipped if the open is ≥ 5% above the signal
  close.
- **MR:** RSI(2) < 5, with close > 200-SMA and Nifty > 200-SMA, in the top-100 universe.
  Buy at the next open.

Signal priority when slots are full is each strategy's own:
- F: pattern weight, then distance to the pivot;
- S: 126-session return;
- B: volume ratio;
- MR: lowest RSI(2).

## Bracket (all four)

- **Stop** = fill × 0.98. **Target** = fill × 1.06.
- Both are checked from the fill day on. If both trade the same day, the stop wins.
- After the fill day, a gap through either level fills at the open.
- **Time stop: 20 sessions** after entry, sold at the next open. This matches the 2-4
  week swing horizon. No other exits.
- **Sizing:** 20% of current equity per position, at most 5 positions, no leverage.
  - A stop-out costs about 0.4% of capital plus costs; a target hit gains about 1.2%.
  - Break-even before costs needs a 25% win rate. After round-trip costs of about 0.3%,
    it needs about 29%.
- **Costs, data, delisting rule (last close − 5%), universe** (point-in-time top 500,
  ETF-free, ≥ ₹5): unchanged.

## Windows and judgement

- **W1** = 2019-01-01 → 2026-10-30; **W2** = 2008-01-01 → 2017-12-31.
- Judged by the six checks of `docs/redesign_preregistration.md`.
- **Win rate, average win/loss and exit mix are reported prominently.**
- A combination passes only if it passes both windows.
- Four combinations are tested, so any pass is provisional; the next step is paper
  trading.

## Known caveat, stated up front

A 2% stop is inside the normal daily range of most stocks: a typical top-500 stock's
ATR(14) is about 2-3.5% of price. On daily bars, many trades will touch both −2% and +6%
within a day or two, and the stop-wins-tie rule makes those losses. The result therefore
tests this bracket as it would be traded with resting orders, under conservative
intraday ordering.
