# Pre-registration: breakout entry with a volume check at the close

**Status: FROZEN on 2026-11-08 ~22:20 IST,** before any run. This follows
`docs/range_volume_preregistration.md`: waiting for the day's volume and buying the next
open cut 2019-26 returns in half. IA approved testing the alternative: buy at the
breakout level as before, and use volume to exit a breakout that turns out to be weak.
Never edit; add dated notes.

## Rules

**Entry: unchanged.**
- #3 + Nifty filter: a buy-stop at the 20-day intraday high, valid the next session,
  with a 3% gap cap.
- FM with the 20-day-high entry (`docs/fm_high20_preregistration.md`, H3/H2): FM watch
  list, a buy-stop at the 20-day high, 3% gap cap.

**Range check (RX versions only).** This is known before the fill, so there is no
look-ahead.
- On the fill day i: L = the highest high of the 20 sessions before i; k = the day it was
  made.
- Skip the fill unless L / (lowest low from k to i−1) − 1 ≤ 10%.

**Volume exit (all versions).**
- At the close of the fill day, sell at the close if Volume[i] < 1.5 × the average volume
  of the 50 sessions before i.
- This applies only if the stop or target was not hit that day.
- Practical note: in live trading this is a decision near 3:20 pm on the
  volume-so-far. The backtest uses the full-day volume and the closing price.

**Everything else as frozen for each strategy:**
- stops (#3: swing low; FM: the higher of the swing low and fill − 3 ATR);
- 1% risk, 10 slots;
- time stops (#3: 20; FM: 40 sessions);
- filters, and FM's rank exit.

## Versions

| Code | Strategy | Target | Range check |
|---|---|---|---|
| S3_VX3 | #3 + Nifty | 1:3 | no |
| S3_VX2 | #3 + Nifty | 1:2 | no |
| S3_RX3 | #3 + Nifty | 1:3 | yes |
| S3_RX2 | #3 + Nifty | 1:2 | yes |
| FM_VX3 | FM 20-day-high | 1:3 | no |
| FM_VX2 | FM 20-day-high | 1:2 | no |
| FM_RX3 | FM 20-day-high | 1:3 | yes |
| FM_RX2 | FM 20-day-high | 1:2 | yes |

## Comparison and outputs

**References (same entries, no volume exit):**

| Reference | W1 | W2 | 2018 |
|---|---|---|---|
| #3 + Nifty 1:3 | 17.3% | 5.5% | −14.3% |
| #3 + Nifty 1:2 | run here as S3_REF2 | | |
| FM H3 | 9.4% | 9.7% | −19.6% |
| FM H2 | 9.0% | 12.2% | −22.8% |

- **Windows:** W1, W2 and 2018, judged with the six checks.
- **All windows are in-sample.**
- **Output:** `data/volume_exit_result.txt`.
