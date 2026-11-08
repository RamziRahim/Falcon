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
