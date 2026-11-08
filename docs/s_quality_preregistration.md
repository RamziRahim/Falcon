# Pre-registration: #3 with quality breakouts (base, tight range, volume, close above)

**Status: FROZEN on 2026-11-08 ~22:05 IST,** before any run. IA asked to add the four
checks the 20-day-high rule lacks. Never edit; add dated notes.

## Entry

#3's stock filters are unchanged (`backtesting/fixed_bracket.entries_s`):
- 6-month momentum in the top 20%;
- peer group in the top third (top 10% when the Nifty is below its 200-SMA);
- close above the 50- and 200-SMA.

The breakout must also be a **quality breakout** on day i:
1. **Base:** the prior 20-day high L (the max High of sessions i−20 … i−1) was set at least
   **5 sessions** before day i.
2. **Tight range:** from that day to day i−1, max High / min Low − 1 ≤ **10%**.
3. **Volume:** volume on day i ≥ **1.5×** the prior 50-day average.
4. **Close above:** the close on day i is above L.

**Buy** at the next open; skipped if the open is more than 3% above the close on day i.

## Same as the best #3 (S+ "market filter only")

- **Filter:** new orders only while the Nifty 50 is above its 50-SMA.
- **Stop:** swing-low stop − 0.25 ATR; skipped if more than 15% away.
- **Sizing:** 1% risk, positions ≤ 25%, at most 10 positions.
- **Time stop:** 20 sessions.
- **Fill rules:** the stop wins a same-day tie; gaps fill at the open.

**Targets:** Q3 = 3R and Q2 = 2R.

## Windows and judgement

- **Windows:** W1, W2 and 2018, with the six checks.
- **Compared with:** #3 + Nifty filter (17.3 / 5.5 / −14.3%, 820 / 895 / 90 trades).
- **All windows are in-sample.**

## Output

`data/s_quality_result.txt`

---

## Results, 2026-11-08 (`data/s_quality_result.txt`)

| | W1 2019-26 | W2 2008-17 | 2018 | Trades W1 / W2 / 2018 | Net per trade W1 / W2 | Capital in use W1 / W2 |
|---|---|---|---|---|---|---|
| Q3 (quality breakout, 3R) | 1.5% (DD −20%) | 0.6% (−21%) | −9.7% | 298 / 304 / 54 | +0.79 / +0.16% | 25 / 21% |
| Q2 (2R) | 1.9% (−17%) | −0.1% (−23%) | −8.0% | 304 / 308 / 58 | +0.90 / −0.06% | 25 / 20% |
| *#3 + Nifty filter (plain 20-day high)* | *17.3% (−24%)* | *5.5% (−34%)* | *−14.3%* | *820 / 895 / 90* | *+1.99 / +0.85%* | |

**Verdict:** fails (1/6 checks). It is far below plain #3.

**Reading:**
- The four checks cut trades to about a third.
- **Per-trade results are also worse,** not better: +0.8% vs +2.0% on W1. The quality
  breakouts more often stall: about 67% of trades end at the 20-session time stop, and
  only 2-5% reach the 3R target.
- Only 20-25% of capital is in use.
- Losses are smaller in 2018 and the drawdowns are shallower, simply because the
  strategy is mostly in cash.
- This agrees with the random-day screens: IA's range-breakout pattern did not beat
  random days in either decade.
