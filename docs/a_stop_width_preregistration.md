# Pre-registration: monthly momentum, stop width and re-entry

**Status: DRAFT, written 2026-11-10. NOT FROZEN.** No code written, nothing run. IA to
confirm or change the variants and the adoption bar, then replace this line with
"FROZEN on <date, time>" before any run. After that: never edit; add dated notes.

**Samples and hold-out.** Half B was used once on 2026-11-09, so it is no longer unseen.
To keep it meaningful, nothing in this test is tuned: every parameter below is fixed
here, before any run, from common practice and not from a search. Each variant runs once
on all stocks, half A and half B (`data/holdout_split.csv`), on W1 2019-01-01 →
2026-10-30, W2 2008-01-01 → 2017-12-31 and 2018, with the same six checks, costs and
data. One variant is named **primary**; only it can be adopted. The others are reported
for information. All windows are in-sample. Paper trading is still the real test.

## Why

- The 10% stop added about 5 points a year in W2 and cut the W2 drawdown from −80% to
  −59%. It cost about 7 points a year in W1 and 13-17 points of win rate
  (`docs/a_stop_preregistration.md`).
- 2018 was worse with it: −38.9% against −23.7%, with 145 closed trades against 57. The
  stop sold near lows and the next rebalance bought again into the fall.
- Without a stop the average loss was −12.5% (W1) and −19.4% (W2), so a 10% stop sits
  inside the normal range of a losing month.

## Rules

Monthly 12-1 momentum, top 20, exactly as A10, changing only the stop.

| Code | Stop | Re-entry after a stop | Role |
|---|---|---|---|
| A10 | fill × 0.90 | allowed at the next rebalance | reference |
| **A15** | fill × 0.85 | as A10 | **primary** |
| A20 | fill × 0.80 | as A10 | reported |
| A10C | fill × 0.90 | not re-bought at the next rebalance; allowed from the one after. Its slot stays in cash for that month | reported |
| A | none | — | reference |

Fill rules are A10's: sold at the stop, or at the open if it gaps through after the fill
day; the fill day's low counts.

## Adoption bar (A15 against A10, same sample)

Adopted only if **all** hold on **both** half A and half B:
1. CAGR above A10's in both W1 and W2;
2. max drawdown no more than 3pp deeper than A10's in either decade;
3. 2018 return better than A10's;
4. at least 5 of the 6 checks in both decades.

Also reported: exit mix, win rate, average win and loss, calendar-year returns.

## Expected, stated before the run

A higher win rate and W1 return than A10, and a deeper W2 drawdown. If the W2 drawdown is
more than 3pp deeper, the 10% stop stays.

## Output

`data/a_stop_width_result.txt`
