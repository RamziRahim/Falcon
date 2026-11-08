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

---

## Results, 2026-11-08 (`data/volume_exit_result.txt`)

| Version | W1 2019-26 | W2 2008-17 | 2018 | Trades W1 / W2 | Volume exits W1 / W2 | ₹10 L grew to (W1 / W2) |
|---|---|---|---|---|---|---|
| *#3 + Nifty 1:3 (reference)* | 17.3% | 5.5% | −14.3% | 820 / 895 | — | 34.8 / 17.0 L |
| *S3_REF2 #3 + Nifty 1:2 (reference)* | 15.4% (DD −29%) | 5.1% (−35%) | −12.6% | 862 / 930 | — | 30.6 / 16.4 L |
| S3_VX3 | 0.7% (−43%) | −4.2% (−52%) | −26.3% | 1,874 / 1,876 | 1,191 / 1,129 | 10.6 / 6.5 L |
| S3_VX2 | −1.1% | −7.2% | −26.9% | 1,984 / 1,983 | 1,263 / 1,201 | 9.2 / 4.8 L |
| S3_RX3 | −3.1% | −7.9% | −28.2% | 1,906 / 1,899 | 1,288 / 1,233 | 7.8 / 4.4 L |
| S3_RX2 | −4.7% | −8.0% | −23.2% | 1,989 / 1,970 | 1,343 / 1,271 | 6.9 / 4.3 L |
| *FM H3 (reference)* | 9.4% | 9.7% | −19.6% | 567 / 602 | — | — |
| FM_VX3 | 4.0% (−24%) | 3.6% (−54%) | −27.9% | 1,157 / 1,159 | 693 / 657 | 13.5 / 14.2 L |
| FM_VX2 | 0.7% | 1.1% | −27.1% | 1,292 / 1,265 | 771 / 714 | 10.5 / 11.2 L |
| FM_RX3 | 9.0% (−22%) | 1.3% (−54%) | −20.0% | 1,139 / 1,090 | 734 / 662 | 19.7 / 11.3 L |
| FM_RX2 | 2.8% | 0.3% | −20.3% | 1,241 / 1,182 | 799 / 716 | 12.4 / 10.3 L |

**Verdict:** every version fails, and all are far below their references. Not adopted.

**Why:** about 64% of entries fail the volume check and are sold at the close. The
buy-stop then re-arms, so the same stock is often bought again the next day, sold again,
and so on. Trades more than double, and each round trip pays costs and the day's
slippage.

**Descriptive check, after the run, on the S3_REF2 trades (no exit rule):**

| Entry-day volume | W1 trades / win / avg net | W2 trades / win / avg net |
|---|---|---|
| < 1.5× | 476 / 47.7% / +0.79% | 515 / 44.9% / −0.22% |
| ≥ 1.5× | 386 / 51.3% / **+2.61%** | 415 / 53.3% / **+1.90%** |

Volume on the breakout day *does* separate better trades from worse ones, in both
decades. The exit rule wasted it through re-entries. A follow-up would need a cool-down,
with no re-buy of a stock after a volume exit; that would be a new pre-registration.
