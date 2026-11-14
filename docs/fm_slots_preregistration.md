# Pre-registration: Falcon Momentum clean close with more position slots

**Status: FROZEN on 2026-11-10 16:00 IST.** Frozen by IA before any code was written or run. Never edit;
add dated notes.

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

---

## Dated note, 2026-11-10 ~16:20 IST

The first run of `tests/run_fm_slots.py` was killed by the operating system during its
all-stocks stage, because an unrelated smoke test was run at the same time and used up
the memory. Nothing was changed. The run was restarted from scratch and completed; the
result file is from that single complete run.

## Results, 2026-11-10 (`data/fm_slots_result.txt`)

Run with `PYTHONHASHSEED=0`. The FM_C3 reference reproduced the stored files exactly on
half A and half B (six cells).

Each cell is CAGR (max drawdown).

| Sample | Version | W1 2019-26 | W2 2008-17 | 2018 | Trades W1 / W2 | Avg exposure W1 / W2 | Signals skipped, slots full W1 / W2 |
|---|---|---|---|---|---|---|---|
| Half A | FM_C3 (10 slots) | 14.49% (−17.95%) | 12.69% (−23.22%) | −14.73% (−16.25%) | 460 / 486 | 55% / 48% | 570 / 420 |
| Half A | **FM_C3_S15** | 10.27% (−22.98%) | 13.12% (−21.81%) | −15.44% (−17.83%) | 612 / 601 | 58% / 49% | 146 / 92 |
| Half A | FM_C3_S20 | 11.36% (−22.13%) | 12.12% (−20.52%) | −15.44% (−17.83%) | 649 / 632 | 57% / 49% | 8 / 1 |
| Half B | FM_C3 (10 slots) | 8.40% (−25.57%) | 11.34% (−24.16%) | −16.34% (−18.97%) | 462 / 502 | 53% / 47% | 511 / 469 |
| Half B | **FM_C3_S15** | 4.91% (−25.14%) | 14.55% (−21.37%) | −15.42% (−19.34%) | 598 / 611 | 54% / 48% | 98 / 105 |
| Half B | FM_C3_S20 | 6.01% (−24.92%) | 13.91% (−24.24%) | −15.55% (−19.34%) | 626 / 637 | 54% / 48% | 0 / 4 |
| All stocks | FM_C3 (10 slots) | 11.71% (−23.76%) | 12.85% (−26.14%) | −13.39% (−16.49%) | 493 / 514 | 53% / 46% | 747 / 637 |
| All stocks | **FM_C3_S15** | 13.36% (−22.52%) | 12.90% (−31.84%) | −19.09% (−19.56%) | 652 / 656 | 57% / 49% | 225 / 191 |
| All stocks | FM_C3_S20 | 13.31% (−22.70%) | 12.10% (−27.50%) | −19.07% (−19.53%) | 706 / 696 | 57% / 49% | 42 / 20 |

### Verdict on the primary, FM_C3_S15, against the frozen bar: **FAILS. Not adopted.**

| Rule | Half A | Half B |
|---|---|---|
| 1. CAGR ≥ 2pp higher in both decades | W1 −4.22pp: **fail**; W2 +0.43pp: **fail** | W1 −3.49pp: **fail**; W2 +3.21pp: pass |
| 2. Drawdown ≤ 5pp deeper and not past −30% | W1 5.03pp deeper: **fail** | pass |
| 3. CAGR ÷ max DD not below FM_C3's | W1 0.45 against 0.81: **fail**; W2 pass | W1 0.20 against 0.33: **fail**; W2 pass |

**What it shows.** The expectation was wrong. Fifteen slots took about 30% more trades
and almost removed the "slots full" skips. But the average exposure barely moved (55% to
58%), and the W1 return fell by 3.5-4.2pp on both halves. The signals arrive in clusters,
so the extra slots take the lower-ranked names of each cluster, and those are worse. Ten
slots stay.
