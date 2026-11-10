# Pre-registration: Falcon Momentum clean close with more position slots

**Status: DRAFT, written 2026-11-10. NOT FROZEN.** No code written, nothing run. IA to
confirm or change the variants and the adoption bar, then replace this line with
"FROZEN on <date, time>" before any run. After that: never edit; add dated notes.

**Samples.** Each variant runs once on all stocks, half A and half B
(`data/holdout_split.csv`), on W1 2019-01-01 → 2026-10-30, W2 2008-01-01 → 2017-12-31
and 2018, with the same six checks, costs and data, and `PYTHONHASHSEED=0`. Half B has
been used twice for FM_C3 (2026-11-09 and 2026-11-10), so it is no longer unseen; nothing
here is tuned. One variant is **primary**; only it can be adopted. All windows are
in-sample.

## Why

- In `docs/fm_risk_gauge_preregistration.md`, FM_C3 was invested only 47-55% on average.
  Yet 394-614 clean-candle signals per decade were skipped on each half because all 10
  slots were full. The 25% position cap bound 0-3 times.
- Raising the risk per trade did not help: it made each position bigger without taking
  more of the signals.
- More slots takes more of the signals at the same risk per trade. That may raise the
  money at work and spread it over more stocks.

## Rules

FM_C3 exactly as in `docs/close_entry_preregistration.md` (`run_fm_entries`, "closebuy",
1:3, 40-session time stop, risk 1.0% / 0.5%, POS_CAP 25%), changing only the maximum
number of open positions.

| Code | Slots | Role |
|---|---|---|
| FM_C3 | 10 | reference |
| **FM_C3_S15** | 15 | **primary** |
| FM_C3_S20 | 20 | reported |

A buy is still limited by the cash on hand.

## Adoption bar (FM_C3_S15 against FM_C3, same sample)

Adopted only if **all** hold on **both** half A and half B:
1. CAGR at least 2pp higher in both W1 and W2;
2. max drawdown no more than 5pp deeper than FM_C3's in either decade, and no deeper than
   −30.00% in W1, W2 or 2018;
3. CAGR ÷ |max drawdown| not below FM_C3's in either decade.

Figures are compared as printed in the result file (two decimals). The FM_C3 reference
must reproduce the stored files within 0.05pp on half A and half B.

Also reported: average gross exposure, signals skipped because slots were full, trades,
win rate.

## Expected, stated before the run

Higher exposure and return, with a deeper drawdown. If the drawdown deepens faster than
the return rises (rule 3), 10 slots stay.

## Output

`data/fm_slots_result.txt`
