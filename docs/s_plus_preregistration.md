# Pre-registration: S+, improving strategy #3 (momentum breakout + swing-low stop, 1:3)

**Status: FROZEN on 2026-11-05 ~21:55 IST,** before any run. IA asked to focus on
improving #3: S entries, swing-low stop, 1% risk, 1:3 target, 20 sessions
(`docs/swing_low_risk_preregistration.md`). It made +20.4%/yr on 2019-26 but −0.2% on
2008-17. Never edit; add dated notes.

## Honest framing

The three changes below come from a diagnosis of #3's own trades **on both windows**,
and from lessons learned in FM. W1 and W2 are therefore **no longer out-of-sample**:
any improvement there is partly fitted.

The one period never used to trade or judge anything is **2018**. Until now it served
only as look-back for W1. It is the **hold-out check**, and it is a demanding one: 2018
had the small/mid-cap crash. It is only one year, so it is a sanity check, not proof.
The real proof remains paper trading.

## Diagnosis (data/swing_risk_1to3_trades_S_*.csv)

| | W1 2019-26 | W2 2008-17 |
|---|---|---|
| Mean trade, Nifty > 50-SMA at entry | +2.46% (712 trades) | +1.24% (800) |
| Mean trade, Nifty ≤ 50-SMA at entry | +0.49% (313) | **−1.99%** (353) |
| Trades ending at the 20-session time stop | 63%, of which 66% in profit (mean +4.2%) | 63%, of which 58% in profit (mean +3.2%) |
| Signals skipped (swing low > 15% away) | 2,162 | 2,747 |
| Losing years | 2019, 2026 | 2008, 2010, 2011, 2015, 2016 (weak markets) |

## The three changes

1. **Market filter:** new orders only when the Nifty 50 close is above its 50-session
   SMA. Entries in weaker markets lost money on W2 and earned little on W1. Existing
   positions are managed normally.
2. **Time stop of 40 sessions instead of 20.** Most time-stop exits were winners still
   running. FM also did far better at 40 than at 20.
3. **ATR-capped stop:** the stop = the higher of the swing-low stop and fill − 3 ×
   ATR(14), as in FM. Signals whose swing low is far away are no longer skipped. Their
   stop moves up to 3 ATR, which is usually 8-10%. The trade is still skipped if the
   stop is more than 15% away.

**Everything else is unchanged:**
- S entry rules and priorities, including the market switch for peer groups;
- 1% risk, each position ≤ 25% of equity, at most 10 positions;
- 1:3 target;
- fill rules, costs and data.

## Runs

| Run | Windows | Role |
|---|---|---|
| **S+ = all three changes** | W1, W2, **2018** | **Primary** |
| Original #3 | 2018 | Hold-out comparison (W1/W2 already known) |
| Only change 1, only change 2, only change 3 | W1, W2 | To show what each change contributes. Not judged. |

## Judgement

- **S+ on W1 and W2:** the same six checks, and it must pass both. Reported as
  **in-sample**.
- **The 2018 hold-out:** reported against the Nifty, the equal-weight universe and the
  original #3. A sanity check, not a pass/fail gate.
- **Whatever the result, the next step is paper trading.** No further rule changes will
  be tried on 2008-2026 after this run.

## Outputs

- `data/s_plus_result.txt`
- trades in `data/s_plus_trades_*.csv`

---

## Dated addendum, 2026-11-05 ~23:10 IST, after seeing the W1/W2 results and before this run

The single-change runs show that only the market filter helped on both windows, while
the 40-session hold and the ATR cap each hurt both. "Original + market filter only"
was not part of the 2018 hold-out. It is run **once** on 2018 now. This variant was
chosen after seeing W1/W2, so only the 2018 figure says anything about it out-of-sample.
No other variant will be run.

## Results, 2026-11-05 (`data/s_plus_result.txt`)

| Variant | W1 2019-26 | W2 2008-17 | 2018 hold-out | Max DD W1 / W2 |
|---|---|---|---|---|
| Original #3 | 20.4% | −0.2% | −21.4% | −22.6 / −56.6 |
| S+ (all three changes) | 10.8% | 4.9% | −16.0% | −34.1 / −51.9 |
| Only market filter | **17.3%** (5/6 checks, t 1.17) | **5.5%** (4/6) | −14.3% (addendum) | **−24.3 / −34.4** |
| Only 40-session hold | 12.8% | 1.2% | — | −29.2 / −50.3 |
| Only ATR-capped stop | 12.5% | −4.1% | — | −31.0 / −59.8 |

*Nifty: 10.0% / 5.5% / +4.1% (2018). Equal-weight universe: 15.2% / 4.2% / −24.4%.*

**Verdict per the rules:** no variant passes. S+ as pre-registered is worse than the
original on W1.

**Reading:**
- **The 40-session hold and the ATR cap each hurt on both windows.**
  - The ATR cap admits the extended stocks that #3 used to skip, and those trades lose.
  - For breakout entries, extra holding time adds risk without adding return. This is
    the opposite of FM's weekly-ranked entries.
- **The market filter alone helps on both windows.** W2 goes from −0.2% to +5.5% (equal
  to the Nifty), and the W2 drawdown goes from −57% to −34%, at a cost of 3 points on W1.
- **2018 (unseen):** all three variants lost 14-21% while the Nifty rose 4%. That was
  the small/mid-cap crash, when the equal-weight universe fell 24%. The filter-only
  variant lost the least.
- **Conclusion:** "#3 + market filter" is the best version of this strategy. It is not
  proven: it fails on W2 (+5 pp), on the t-test, and on 2018. Per the rules, no further
  variants will be tried on 2008-2026; the next step is paper trading.
