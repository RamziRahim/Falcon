# Pre-registration: swing-structure retest and higher-low pullback

**Status: FROZEN on 2026-11-15 01:05 IST.** Frozen unchanged on IA's instruction ("Take the setup which
you think suits best and go ahead"), which left the open choices to Claude, before any test code was
written or run. Never edit; add dated notes.

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

---

## Results — 2026-11-15 (added after the run; nothing above was changed)

**Run notes.** `tests/run_structure_pullback.py`, one run, `PYTHONHASHSEED=0`; unit tests
`tests/test_structure_pullback.py` (3 pass: the zigzag matches the v3 engine's swing points
exactly; signals on truncated history equal those on full history; a synthetic retest
fires). **Reference check:** P3 reproduced `data/falcon_v3_patterns_result.txt` exactly on
half A, half B and all stocks, W1 and W2.
**Signals 2007-2026 (before the stock filter):** half A 20,722 (TCR 2,868, HLP 17,854),
half B 19,040 (2,685 / 16,355); about 60% pass the 200-day filter.

**Implementation note found while writing the tests.** Rule 5 counts a retest touch on any
session after the break, including the next one, when price is often still just above H2.
About half of TCR entries (46-50% in W1 and W2) came within 2 sessions of the break, so
many were breakout follow-through rather than a return to the level. The rule was run as
frozen.

### Primary PB against the frozen bar

| Sample, window | CAGR (Nifty) | Checks | Max DD | Win / net | Trades/yr (P3) | Bar |
|---|---|---|---|---|---|---|
| Half A, W1 | 12.14% (10.03%) ✓ | 3/6 ✗ | −37.76% ✗ | 40.9% / +2.10% ✗ | 81.8 (35.4) ✓ | **FAIL** |
| Half A, W2 | 5.57% (5.54%) ✓ | 4/6 ✓ | −33.77% ✗ | 40.5% / +0.93% ✗ | 71.3 (29.7) ✓ | **FAIL** |
| Half B, W1 | 8.70% (10.03%) ✗ | 3/6 ✗ | −36.08% ✗ | 37.3% / +1.07% ✗ | 83.3 (30.7) ✓ | **FAIL** |
| Half B, W2 | 1.39% (5.54%) ✗ | 2/6 ✗ | −40.43% ✗ | 37.7% / +0.79% ✗ | 76.6 (26.5) ✓ | **FAIL** |

**Verdict: PB FAILED its bar in all four cells. Not adopted.** Only rule 5 (more trades than
P3) held. Drawdown (rule 3) and win rate (rule 4) failed everywhere.

### All versions (CAGR / max DD / win / net per trade / closed trades / checks; average capital invested)

| Code | Sample | W1 2019–26 | W2 2008–17 | 2018 |
|---|---|---|---|---|
| P3 | A | 6.34 / −23.34 / 51.3 / +2.62 / 277 / 2; 43% | 7.47 / −14.89 / 51.9 / +2.48 / 297 / 4; 37% | −17.00 |
| **PB** | A | 12.14 / −37.76 / 40.9 / +2.10 / 640 / 3; 69% | 5.57 / −33.77 / 40.5 / +0.93 / 713 / 4; 61% | −16.06 |
| PB_TCR | A | 6.03 / −31.11 / 39.8 / +1.39 / 352 / 3 | 4.46 / −22.11 / 37.5 / +0.61 / 341 / 3 | −8.06 |
| PB_HLP | A | 8.52 / −38.02 / 39.2 / +1.79 / 623 / 3 | 5.02 / −30.62 / 41.6 / +1.11 / 654 / 4 | −12.85 |
| PB_NF | A | 17.15 / −35.19 / 41.0 / +1.99 / 710 / 5 | 5.82 / −43.81 / 39.0 / +0.99 / 831 / 4 | −28.94 |
| P3 | B | 13.12 / −15.77 / 56.2 / +4.52 / 240 / 3; 38% | 6.45 / −19.15 / 52.1 / +3.03 / 265 / 3; 34% | −6.95 |
| **PB** | B | 8.70 / −36.08 / 37.3 / +1.07 / 652 / 3; 69% | 1.39 / −40.43 / 37.7 / +0.79 / 766 / 2; 62% | −21.00 |
| PB_TCR | B | 4.53 / −35.19 / 40.3 / +1.50 / 283 / 2 | −1.44 / −27.98 / 35.7 / −0.47 / 294 / 1 | −15.63 |
| PB_HLP | B | 3.82 / −33.83 / 34.7 / +0.46 / 636 / 3 | 5.00 / −37.31 / 39.6 / +1.08 / 707 / 3 | −16.64 |
| PB_NF | B | 5.18 / −44.08 / 36.8 / +0.88 / 717 / 2 | 3.19 / −41.31 / 37.0 / +0.65 / 859 / 3 | −25.91 |
| P3 | All | 15.16 / −17.95 / 54.1 / +3.96 / 353 / 4 | 7.57 / −21.31 / 49.3 / +2.35 / 383 / 4 | −16.57 |
| **PB** | All | 10.61 / −41.84 / 39.3 / +1.48 / 707 / 3 | 3.37 / −46.70 / 38.9 / +0.67 / 818 / 3 | −15.76 |
| PB_TCR | All | 9.76 / −29.12 / 39.7 / +1.67 / 464 / 3 | −0.09 / −37.03 / 37.3 / +0.28 / 499 / 1 | −11.68 |
| PB_HLP | All | 5.76 / −43.24 / 38.0 / +1.18 / 698 / 3 | 3.31 / −46.65 / 39.9 / +0.93 / 766 / 3 | −13.89 |
| PB_NF | All | 12.19 / −33.14 / 38.2 / +1.41 / 746 / 3 | 8.56 / −41.22 / 39.1 / +0.99 / 884 / 4 | −17.87 |

Within PB (trades, win rate, mean net): half A W1 HLP 518 / 42.7% / +2.66%, TCR 122 / 33.6% /
−0.29%; half A W2 HLP 578 / 41.0% / +0.97%, TCR 135 / 38.5% / +0.76%; half B W1 HLP 536 /
37.5% / +1.18%, TCR 116 / 36.2% / +0.59%; half B W2 HLP 641 / 39.6% / +1.34%, TCR 125 / 28.0%
/ −2.02%. Exit mix (PB): stops 51-59% of trades, targets 19-22%, time stops 19-23%.

### Reading (information only; no decision rests on it)

- Both structure setups trade far more often than P3 (70-90 trades a year against 27-35),
  and keep 60-70% of capital invested, but the trades are worse: win rates 35-42% against
  P3's 51-56%, and more than half end at the stop. Drawdowns of −34% to −47% are about
  twice P3's.
- The trend-change retest was the weaker setup, near zero or negative in 2008-17 on both
  halves; half its entries came within 2 sessions of the break (see the note above).
- The higher-low pullback was positive per trade everywhere outside 2018 but too weak to
  carry the portfolio.
- The 200-day stock filter did not help consistently: without it (PB_NF) half A 2019-26 was
  better and half B worse.
- This is the fourth family of dip or retest entries to trail breakout entries on this
  data (#3 retests, leader pullback, v2 retest, and now swing structure).
- Expectation check: HLP fires far more often than TCR (held, about 6-7 times); win rate
  lower than P3 (held); rule 4 or 1 likeliest to fail (both failed, and rule 3 too); rule 5
  passes (held).
