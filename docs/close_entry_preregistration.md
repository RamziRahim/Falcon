# Pre-registration: buy at the close on a clean breakout candle (#3 and FM), half A

**Status: FROZEN on 2026-11-09 ~12:40 IST,** before any run. IA's idea is to skip
breakouts whose candle closes red with an upper wick. A descriptive check on half A found
that breakouts closing red, or back below the level, lost on average in both decades.
You can only see the candle at the close, so the buy moves to the close. Never edit; add
dated notes.

## Hold-out

- Stocks are split by a SHA-256 hash of `entity_id` into half A (828) and half B (794).
  The split is in `data/holdout_split.csv`.
- **All tests here use half A only.** The universe file is filtered to half A, so ranks,
  peer groups and the equal-weight benchmark are all within half A.
- Half B is touched only once, by the final chosen version.

## Close entry ("clean candle")

On the session after the usual signal, i.e. the session the old buy-stop would have
been live, buy **at the close** if all of these hold:
- High > the level, the 20-day intraday high as of the signal day;
- Close ≥ the level;
- Close ≥ Open;
- the upper wick (High − max(Open, Close)) is less than 50% of High − Low;
- **CV versions only:** Volume ≥ 1.5 × the average of the 50 sessions before.

There is no gap cap. The position is not checked against that session's stop or target;
exits start the next session.

## Strategies

- **#3 + Nifty filter.** Candidates, stop and limits as in `entries_s` /
  `run_s_plus(market_filter=True)`: swing-low stop computed on the signal day, skipped if
  wider than 15%; 1% risk; 20-session time stop. Only the buy-stop is replaced by the
  close entry.
- **FM.** Watch list, sector-else-Nifty filter and rank exit unchanged. The entry is the
  close entry on the 20-day-high level. Stop = the higher of the swing low and
  fill − 3 ATR. 40-session time stop.

## Versions (all on half A)

| Code | Strategy | Entry | Target |
|---|---|---|---|
| S3_REF3, S3_REF2 | #3 + Nifty | buy-stop | 1:3, 1:2 |
| S3_C3, S3_C2 | #3 + Nifty | close entry | 1:3, 1:2 |
| S3_CV3, S3_CV2 | #3 + Nifty | close entry + volume | 1:3, 1:2 |
| FM_REF3, FM_REF2 | original FM | Monday open (`run_fm`) | 1:3, 1:2 |
| FM_H3 | FM | 20-day-high buy-stop | 1:3 |
| FM_C3, FM_C2 | FM | close entry | 1:3, 1:2 |
| FM_CV3, FM_CV2 | FM | close entry + volume | 1:3, 1:2 |

## Also reported: trade paths

For every trade, over 20 and over 40 sessions:
- **returned to buy:** a low ≤ the fill on any session after the fill day;
- **hit the stop:** a low ≤ the stop, counted from the fill day for buy-stop and open
  entries, and from the next session for close entries.

The full path classes of `tests/analyse_trade_paths.py` are also given.

## Windows and outputs

- **Windows:** W1, W2 and 2018, with the six checks.
- **Adoption rule:** a close-entry version is a candidate only if it beats its own
  half-A reference on CAGR in **both** W1 and W2.
- **All windows are in-sample.**
- **Outputs:**
  - `data/close_entry_result.txt`
  - `data/close_entry_paths.txt`
