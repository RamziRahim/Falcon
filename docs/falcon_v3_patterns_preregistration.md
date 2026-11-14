# Pre-registration: Falcon pattern engine v3 in the backtest

**Status: FROZEN on 2026-11-14 13:17 IST.** Frozen by IA before any test code was written or run.
Never edit; add dated notes.

**Samples.** Each variant runs once on half A, half B and all stocks, on W1 2019-01-01 →
2026-10-30, W2 2008-01-01 → 2017-12-31 and 2018, with the same six checks, costs and data,
and `PYTHONHASHSEED=0`. All windows are in-sample.
- Both halves have been used for earlier pattern tests (v2, retest, 2% risk), so neither is
  clean. A pass would mean "paper trade it", not "proven".
- In v3's favour: its detection thresholds come from PATTERN_ENGINE_SPEC.md, not from
  tuning on our data. The five changes made to it (`technical_analysis/pattern_system_v3/
  engine.py`) were driven by the spec's own tests, not by backtest results.

## Why

The blind audit of 2026-11-14 found Falcon's detectors judged real only 60% of the time
and labelled correctly 38% of the time. The v3 engine adds a Stage 2 trend gate,
volatility-scaled swing points and stricter geometry. This test asks whether its patterns
trade better than v2's.

## Rules

### Detection

1. Every 5 sessions (the same scan dates as v2), run `classify_nse_stock` from
   `technical_analysis/pattern_system_v3/engine.py` on every stock in that month's
   top-500 list, using its last 400 sessions up to and including the scan day.
2. Keep stocks whose verdict is `REAL_PATTERN` (P3) — or `REAL_PATTERN` or `UNSURE` (P3U).
   Each gives a breakout level (pivot) and a stop.

### Entry, stop, exits and sizing (as FV2, except the stop)

3. Entry as FV2's rules 6-7 (`docs/falcon_v2_preregistration.md`): within the 5 sessions
   after the scan, buy at the close of the first session with High > pivot, Close > pivot,
   (Close − Low) ÷ (High − Low) ≥ 0.5 and the Nifty 50 above its 50-DMA. A session that
   closes at or below the stop first cancels the order.
4. Stop = v3's stop (the pattern's structural low − 0.5 ATR). Skip the trade if it is not
   below the fill or more than 15% below it.
5. Target = fill + 3 × (fill − stop). Time stop 40 sessions (sell at the next open). No
   exit checks on the entry session; the stop wins ties.
6. 1% risk per trade, ≤ 25% per position, 10 slots. When signals exceed free slots, the
   higher 126-session return rank goes first.

## Versions

| Code | Detection | Role |
|---|---|---|
| FV2 | v2 detectors + v2 filters | reference; must reproduce `data/falcon_v2_result.txt` within 0.05pp (all samples, W1 and W2) |
| **P3** | v3, `REAL_PATTERN` only | **primary** |
| P3U | v3, `REAL_PATTERN` or `UNSURE` | reported |

## Adoption bar (P3; all must hold on both half A and half B, in both W1 and W2)

1. CAGR above the Nifty's;
2. at least 4 of the 6 checks;
3. max drawdown no deeper than −25.00%;
4. win rate at least 45.0%, and mean net per trade at least +1.00%;
5. CAGR higher than FV2's on the same sample and window.

Figures are compared as printed in the result file. Also reported: setups per year, trades
per year, the share of setups that triggered, exit mix, 2018, average capital invested,
and per-pattern trade counts, win rate and mean net per trade (information only).

## What adoption would mean

v3 would replace v2 as Falcon's pattern detector, subject to the round-2 blind audit also
passing (at least 80% of its picks judged real by IA). Running patterns beside monthly
momentum or as its entry timing would be a separate registered test.

## Expected, stated before the run

Far fewer setups than v2 (about 1.3% of stock-days are `REAL_PATTERN`), and fewer trades.
Higher win rate and net per trade than FV2 because of the Stage 2 gate and tighter stops
(2-11.5%). Low capital use, as with v2, so the return may still be close to the Nifty's;
rule 1 or rule 5 is the likeliest to fail.

## Output

`data/falcon_v3_patterns_result.txt`; scans `data/pit/falcon_setups_v3_<span>.parquet`;
runner `tests/run_falcon_v3_patterns.py`. Implemented by passing v3 setups to the existing
`run_setups_v2` (no change to its default behaviour).

---

## Results — 2026-11-14 (added after the run; nothing above was changed)

**Run notes.** Scans by `tests/scan_falcon_setups_v3.py` (2008-17, 2018, 2019-26; v2 scan
dates), then `tests/run_falcon_v3_patterns.py`, one run, `PYTHONHASHSEED=0`. The only
simulator change is the optional `stop_rule="setup"` of `run_setups_v2` (default
unchanged). **Reference check:** FV2 reproduced `data/falcon_v2_result.txt` exactly on
half A, half B and all stocks, W1 and W2 (6 of 6).
**Setups (REAL_PATTERN, 2008-2026):** half A 3,234, half B 2,986, all 6,220 (flat base
56%, bull flag 22%, cup 18%, VCP 3%, triangle 2%).

### Primary variant P3 against the frozen bar

| Sample, window | CAGR (Nifty) | Checks | Max DD | Win / net | CAGR vs FV2 | Bar |
|---|---|---|---|---|---|---|
| Half A, W1 | 6.34% (10.03%) ✗ | 2/6 ✗ | −23.34% ✓ | 51.3% / +2.62% ✓ | 6.34 < 9.50 ✗ | **FAIL** |
| Half A, W2 | 7.47% (5.54%) ✓ | 4/6 ✓ | −14.89% ✓ | 51.9% / +2.48% ✓ | 7.47 > 6.36 ✓ | pass |
| Half B, W1 | 13.12% (10.03%) ✓ | 3/6 ✗ | −15.77% ✓ | 56.2% / +4.52% ✓ | 13.12 > 11.64 ✓ | **FAIL** |
| Half B, W2 | 6.45% (5.54%) ✓ | 3/6 ✗ | −19.15% ✓ | 52.1% / +3.03% ✓ | 6.45 > 5.58 ✓ | **FAIL** |

**Verdict: P3 FAILED its bar (3 of 4 cells). Not adopted.** Rules 3 and 4 (drawdown,
win rate and net per trade) held in every cell, for the first time for any pattern
version. Rule 2 (4 of 6 checks) failed in three cells: the return was never 5 points
above the Nifty and never statistically significant. Rules 1 and 5 failed on half A
2019-26 only.

### All versions (CAGR / max DD / win / net per trade / closed trades / checks; average capital invested)

| Code | Sample | W1 2019–26 | W2 2008–17 | 2018 |
|---|---|---|---|---|
| FV2 | A | 9.50 / −29.59 / 45.7 / +1.79 / 431 / 3 | 6.36 / −25.13 / 48.2 / +1.72 / 417 / 4 | −7.55 / −15.07 |
| **P3** | A | 6.34 / −23.34 / 51.3 / +2.62 / 277 / 2; 43% | 7.47 / −14.89 / 51.9 / +2.48 / 297 / 4; 37% | −17.00 / −18.25 |
| P3U | A | 7.43 / −19.79 / 49.3 / +2.54 / 304 / 2; 46% | 6.74 / −16.96 / 51.4 / +2.51 / 313 / 3; 38% | −15.93 / −17.33 |
| FV2 | B | 11.64 / −21.95 / 46.5 / +2.59 / 383 / 3 | 5.58 / −28.34 / 46.4 / +1.50 / 403 / 4 | −2.01 / −11.37 |
| **P3** | B | 13.12 / −15.77 / 56.2 / +4.52 / 240 / 3; 38% | 6.45 / −19.15 / 52.1 / +3.03 / 265 / 3; 34% | −6.95 / −8.93 |
| P3U | B | 13.20 / −17.38 / 56.1 / +4.26 / 269 / 3; 42% | 6.74 / −16.77 / 50.7 / +2.51 / 306 / 3; 39% | −8.17 / −10.12 |
| FV2 | All | 12.20 / −24.63 / 44.6 / +1.88 / 491 / 3 | 4.31 / −30.39 / 44.9 / +0.88 / 497 / 4 | −1.19 / −15.67 |
| **P3** | All | 15.16 / −17.95 / 54.1 / +3.96 / 353 / 4; 55% | 7.57 / −21.31 / 49.3 / +2.35 / 383 / 4; 47% | −16.57 / −18.94 |
| P3U | All | 12.67 / −23.37 / 51.2 / +3.16 / 373 / 3; 56% | 7.27 / −19.71 / 48.6 / +2.18 / 397 / 3; 48% | −13.85 / −17.27 |

### Also reported for P3

| Sample, window | Setups/yr | Trades/yr | Orders filled | Pivot touches rejected by the close rule | Exit mix (time / stop / target) |
|---|---|---|---|---|---|
| Half A, W1 | 210 | 35.4 | 21.7% | 67.3% | 148 / 105 / 23 (+1 delisted) |
| Half A, W2 | 147 | 29.7 | 26.4% | 64.8% | 163 / 105 / 29 |
| Half B, W1 | 179 | 30.7 | 22.2% | 66.8% | 125 / 78 / 37 |
| Half B, W2 | 146 | 26.5 | 24.1% | 69.8% | 138 / 100 / 27 |
| All, W1 | 389 | 45.1 | 14.6% | 66.0% | 192 / 115 / 45 (+1 delisted) |
| All, W2 | 293 | 38.3 | 16.9% | 66.5% | 203 / 142 / 38 |

By pattern (P3, closed trades; information only, small counts for VCP and triangle):

| Pattern | Half A W1 | Half A W2 | Half B W1 | Half B W2 |
|---|---|---|---|---|
| Flat base | 123: 54.5% / +3.05% | 123: 59.3% / +2.84% | 106: 56.6% / +5.08% | 98: 58.2% / +3.83% |
| Bull flag | 72: 44.4% / +0.86% | 73: 39.7% / +0.85% | 69: 55.1% / +5.76% | 65: 41.5% / +2.47% |
| Cup with handle | 69: 47.8% / +2.83% | 82: 47.6% / +2.78% | 53: 58.5% / +2.52% | 79: 49.4% / +2.28% |
| VCP | 7: 71.4% / +6.64% | 14: 57.1% / +2.34% | 6: 50.0% / +3.59% | 16: 62.5% / +4.47% |
| Ascending triangle | 6: 83.3% / +7.66% | 5: 100% / +12.86% | 6: 50.0% / −0.86% | 7: 71.4% / +2.12% |

(trades: win rate / mean net per trade)

### Reading (information only; no decision rests on it)

- v3 picks are the best per-trade breakout signals Falcon has tested: win rates 51-56%,
  +2.5% to +4.5% net per trade, and drawdowns of −15% to −23% against −22% to −30% for
  v2. On half B, never used to design v3, 2019-26 returned 13.1% with a −15.8% worst drop.
- The return is held down by idle capital: on average only 34-43% of the account was
  invested on the halves. Setups are rarer than v2's, only about a fifth of orders fill,
  and most trades end at the 40-session time stop rather than the target.
- 2018 was poor (−17% on half A, −7% on half B): the Stage 2 gate does not protect against
  a broad small- and mid-cap fall.
- Flat bases were the most consistent pattern on both halves; bull flags were the
  weakest on half A.
- Expectation check: fewer trades (held: about 30% fewer than FV2); better win rate and
  net per trade (held); return near the Nifty in places (held); rule 1 or 5 likeliest to
  fail (rule 2 failed most).
