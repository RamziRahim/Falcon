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
