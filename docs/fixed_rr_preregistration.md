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

---

### Dated addendum, 2026-11-03 ~19:56 IST: parallel 3:6 bracket (requested by IA before any result)

IA asked for a second, separately reported bracket, run in parallel. It was added before
either bracket had produced any result: the 1:3 run had started minutes earlier and had
not finished.

- **Stop** = fill × 0.97 (−3%). **Target** = fill × 1.06 (+6%). That makes R:R 1:2.
- Everything else is identical to the 1:3 bracket: entries, 20-session time stop,
  5 × 20% sizing, costs, windows and the six checks.
- Break-even win rate is about 33% before costs, about 36% after.
- Output: `data/fixed_rr_3_6_result.txt`, with trades in `data/fixed_rr_3_6_trades_*.csv`.
- This adds four more combinations, eight in total, so a single pass is weaker evidence.

---

## Results, 2026-11-03

Full output: `data/fixed_rr_result.txt` (1:3) and `data/fixed_rr_3_6_result.txt` (3:6).

**All 16 combinations fail** (4 entries × 2 brackets × 2 windows):

| Entry | Bracket | Win % W1 / W2 | Mean net per trade W1 / W2 | CAGR W1 / W2 |
|---|---|---|---|---|
| MR | −2/+6 | 25.6 / 25.5 | −0.35% / −0.40% | −11.3% / −13.0% |
| MR | −3/+6 | 33.5 / 33.3 | −0.41% / −0.46% | −10.2% / −11.9% |
| B | −2/+6 | 22.7 / 21.4 | −0.62% / −1.08% | −47.2% / −63.9% |
| B | −3/+6 | 31.9 / 29.2 | −0.59% / −1.19% | −37.1% / −58.8% |
| F | −2/+6 | 17.5 / 17.5 | −1.15% / −1.43% | −50.1% / −57.9% |
| F | −3/+6 | 29.6 / 28.3 | −0.92% / −1.37% | −32.4% / −46.0% |
| S | −2/+6 | 11.8 / 10.6 | −1.49% / −1.90% | −84.7% / −88.3% |
| S | −3/+6 | 20.7 / 18.7 | −1.57% / −2.08% | −77.4% / −83.4% |

Nifty over the same periods: +10.0% (W1) and +5.5% (W2) a year.

Break-even win rates after costs are about 29% (1:3) and about 36% (1:2). No combination
reached break-even:
- the best, MR −3/+6, won 33.5% of trades;
- the average loss exceeds the stop distance because of costs and gaps;
- the 6% target caps the large winners that drove momentum's earlier gains.

### Sensitivity, reported only (`data/fixed_rr_sensitivity.txt`)

For the buy-stop entries (F, S), the run was repeated with a fill-day stop that counts
only on a close at or below it, the most generous reading of daily bars. Win rates rise
to 28-37%. The only non-negative result is S −2/+6 on W1, at +2.6%/yr, still well below
the Nifty's 10.0%. Every other combination still loses money. **The verdicts don't
depend on the intraday-ordering assumption.**
