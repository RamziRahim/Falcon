# Pre-registration: swing-structure retest and higher-low pullback

**Status: DRAFT (2026-11-14). Not frozen. No test code written.**

**Samples.** Each version runs once on half A, half B and all stocks, on W1 2019-01-01 →
2026-10-30, W2 2008-01-01 → 2017-12-31 and 2018, with the same six checks, costs and data,
and `PYTHONHASHSEED=0`. All windows are in-sample: both halves have been used for earlier
tests. A pass would mean "paper trade it", not "proven".

## Why

IA (2026-11-14): the earlier pullback and retest tests were not the standard setups. They
bought dips after 20-day-high breakouts (#3 retests), quiet dips in momentum leaders
(leader pullback) or returns to a pattern pivot (v2 retest); none used swing structure.
This test trades the two standard swing-structure setups:
1. **Trend-change retest (TCR):** a stock in a short-term downtrend (lower highs, lower
   lows) closes above its last lower high, then comes back to retest that level from
   above and turns up.
2. **Higher-low pullback (HLP):** a stock in a short-term uptrend (higher highs, higher
   lows) pulls back, holds above its last swing low, and turns up.
Both only in stocks whose longer-term trend is up.

## Swing points

1. ATR(14) with Wilder's smoothing. Swing highs and lows from the ATR zigzag of
   `technical_analysis/pattern_system_v3/engine.py` (`detect_atr_zigzag`, reversal
   threshold 2.2 × ATR): strictly alternating highs and lows.
2. The zigzag is run once over each stock's full adjusted history. Each swing point has
   the session it occurred on and the session it was **confirmed** (the first session on
   which price reversed 2.2 ATR from it). On any session t, only swing points confirmed
   on or before t are used.

## Setup 1: trend-change retest (TCR)

3. **Downtrend, then the break.** Session b is the first session with Close > H2, where
   the last four swing points confirmed by b are, in order, H1, L1, H2, L2 with
   H2 < H1 (a lower high) and L2 < L1 (a lower low).
4. **Retest window:** the 15 sessions after b. The setup is dropped if, before an entry,
   any session closes below H2 − 1.0 × ATR or trades below L2.
5. **Entry:** the close of the first session e in the window on which (a) some session from
   b + 1 to e had a Low at or below H2 + 0.5 × ATR (the retest touch), (b) Close > the
   previous session's High (the turn up), and (c) Close > H2.
6. **Stop:** the lowest Low from b to e, minus 0.5 × ATR(e).

## Setup 2: higher-low pullback (HLP)

7. **Uptrend, then the pullback.** On session t the last four confirmed swing points are,
   in order, La, Ha, Lb, Hb with Lb > La (a higher low) and Hb > Ha (a higher high); the
   last one, Hb, is the swing high the stock is now pulling back from.
8. **The higher low.** PL = the lowest Low from Hb's session to t. Require PL > Lb (the
   low holds above the last swing low) and a retracement (Hb − PL) ÷ (Hb − Lb) of at
   least 0.382.
9. **Entry:** the close of the first session t, within 30 sessions of Hb's session, on
   which (a) PL was set within the last 5 sessions (t − PL's session ≤ 4), (b) Close > the
   previous session's High (the turn up), and (c) Close < Hb (still below the old high).
   One entry per Hb.
10. **Stop:** PL − 0.5 × ATR(t).

## Common rules (both setups)

11. **Longer-term trend (stock filter):** on the entry session, Close > the 200-day SMA and
    the 200-day SMA is higher than 20 sessions earlier.
12. **Market filter:** the Nifty 50 closes above its 50-day average on the entry session.
13. **Risk window:** skip the trade if the stop is less than 1.5% or more than 10% below the
    entry.
14. **Exits:** target = entry + 3 × (entry − stop); time stop 40 sessions (sold at the next
    open). No exit checks on the entry session; the stop wins ties; gaps fill at the open.
15. **Sizing:** 1% risk per trade, at most 25% of equity per position, 10 slots, top-500
    universe of that month. When signals exceed free slots, the higher 126-session return
    rank goes first. One position per stock; a stock with both setups on one session is
    one trade.

These exits and sizing are the same as P3 (`docs/falcon_v3_patterns_preregistration.md`),
so the two can be compared directly.

## Versions

| Code | What | Role |
|---|---|---|
| P3 | v3 patterns, as stored | reference; must reproduce `data/falcon_v3_patterns_result.txt` within 0.05pp (all samples, W1 and W2) |
| **PB** | TCR and HLP together, rules 1-15 | **primary** |
| PB_TCR | TCR only | reported |
| PB_HLP | HLP only | reported |
| PB_NF | TCR and HLP without the stock filter (rule 11) | reported |

## Adoption bar (PB; all must hold on both half A and half B, in both W1 and W2)

1. CAGR above the Nifty's;
2. at least 4 of the 6 checks;
3. max drawdown no deeper than −25.00%;
4. win rate at least 45.0%, and mean net per trade at least +1.00%;
5. more closed trades per year than P3 on the same sample and window (more tradeable
   entries).

Figures are compared as printed in the result file. Also reported: signals per year per
setup, the share of TCR breaks that got an entry, exit mix, average capital invested,
2018, and per-setup trade counts, win rate and mean net per trade.

## What adoption would mean

PB would join the paper-trading tracks as a separate strategy. Running it beside monthly
momentum would be a separate registered test.

## Expected, stated before the run

HLP fires far more often than TCR. Earlier dip and retest entries on this data did worse
than buying breakouts, so a lower win rate than P3 is likely; rule 4 or rule 1 is the
likeliest to fail. Rule 5 should pass.

## Output

`data/structure_pullback_result.txt`; signals `data/pit/structure_pullback_signals.parquet`;
code `backtesting/structure_pullback.py`, runner `tests/run_structure_pullback.py`. Nothing
existing changes.
