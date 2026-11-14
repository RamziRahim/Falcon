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

---

## Results, 2026-11-09 (`data/close_entry_result.txt`, `data/close_entry_paths.txt`), half A

**Note:** half-A figures are not comparable with the earlier full-universe tables. For
example, #3 + Nifty 1:3 makes 9.9% on half A against 17.3% on all stocks. Compare only
within this table.

| Version | W1 2019-26 | W2 2008-17 | 2018 | Trades W1 / W2 | ₹10 L grew to (W1 / W2) | Checks W1 / W2 |
|---|---|---|---|---|---|---|
| S3_REF3 (buy-stop) | 9.9% (DD −26%) | 3.4% (−33%) | −14.8% | 708 / 748 | 20.9 / 14.0 L | 3 / 3 |
| S3_REF2 | 7.0% (−24%) | 5.9% (−32%) | −12.5% | 735 / 774 | 17.0 / 17.8 L | 3 / 4 |
| S3_C3 (close entry) | 4.7% (−17%) | 0.5% (−24%) | −11.9% | 476 / 488 | 14.3 / 10.5 L | 2 / 1 |
| S3_C2 | 4.6% (−14%) | 1.8% (−22%) | −13.6% | 476 / 494 | 14.3 / 11.9 L | 2 / 2 |
| S3_CV3 (close + volume) | 5.3% (−18%) | 1.0% (−23%) | **−4.5%** | 339 / 335 | 15.0 / 11.1 L | 2 / 2 |
| S3_CV2 | 5.4% (−16%) | 2.2% (−23%) | −6.6% | 342 / 338 | 15.0 / 12.4 L | 2 / 3 |
| FM_REF3 (Monday open) | 9.1% (−22%) | 8.7% (−29%) | −12.2% | 599 / 710 | 19.8 / 23.1 L | 3 / 4 |
| FM_REF2 | 5.2% (−22%) | 8.2% (−26%) | −9.6% | 655 / 781 | 14.9 / 21.9 L | 2 / 4 |
| FM_H3 (20-day-high buy-stop) | 13.0% (−21%) | 10.0% (−33%) | −23.9% | 522 / 584 | 26.0 / 25.9 L | 3 / 4 |
| **FM_C3 (close entry)** | **14.5% (−18%)** | **12.7% (−23%)** | −14.7% | 460 / 486 | **28.8 / 33.0 L** | 3 / **5** |
| FM_C2 | 11.9% (−16%) | 8.2% (−23%) | −17.0% | 500 / 529 | 24.1 / 22.0 L | 3 / 3 |
| FM_CV3 | 7.6% (−20%) | 9.6% (−20%) | −15.9% | 421 / 414 | 17.8 / 24.9 L | 3 / 4 |
| FM_CV2 | 5.4% (−20%) | 8.1% (−21%) | −22.3% | 444 / 454 | 15.1 / 21.7 L | 2 / 4 |

**Against the adoption rule:**
- **#3:** no close-entry version beats S3_REF in both decades. Not adopted. The close
  entry does cut drawdowns (−14 to −18% against −26%), and with volume it cuts 2018 to
  −4.5%. It gives up too much return, though: the day-one gain is lost.
- **FM: FM_C3 is a candidate.**
  - It beats FM_REF3 in both decades: +5.4pp in W1, +4.0pp in W2.
  - It also beats FM_H3 in both, with smaller drawdowns.
  - It passes 5/6 checks in W2.
  - The clean-candle filter works for FM's watch list. In FM the stop is anchored at
    fill − 3 ATR, so a higher fill does not widen the stop. In #3 it does.

**Paths (half A):**

*Returned to buy* = a later low at or below the fill; *hit stop* = a low at or below the
stop. Each cell is 20 days / 40 days.

| Version | W1 returned to buy | W1 hit stop | W2 returned to buy | W2 hit stop |
|---|---|---|---|---|
| S3_REF3 | 93% / 95% | 28% / 42% | 92% / 94% | 27% / 42% |
| S3_C3 | 96% / 97% | 27% / 41% | 97% / 98% | 27% / 41% |
| FM_REF3 | 91% / 95% | 37% / 52% | 92% / 94% | 39% / 50% |
| FM_H3 | 93% / 94% | 31% / 46% | 94% / 96% | 34% / 48% |
| FM_C3 | 95% / 97% | 30% / 46% | 96% / 97% | 29% / 44% |

Nearly every trade revisits its buy price. 41-52% hit the stop within 40 days.

**Next:** FM_C3 can go to the one-time half-B check once tuning ends.
