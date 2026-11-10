# Pre-registration: monthly momentum, stop width and re-entry

**Status: FROZEN on 2026-11-10 15:25 IST.** Frozen by IA before any code was written or run. Never edit;
add dated notes.

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

## Implementation notes (confirmed by IA before the freeze)

1. **Code names.** "A15" here means a 15% stop. In `data/a_topn_result.txt` and earlier
   scorecard rows, "A15" means top 15 stocks. The result file keeps this doc's codes; the
   scorecard rows are labelled "15% stop" / "20% stop" in words.
2. **A10C's empty slot.** A stock stopped since the previous rebalance is skipped at the
   next rebalance if it is still in the top 20. Nothing replaces it (the 21st-ranked
   stock is not bought); its slot's cash stays idle until the following rebalance.
3. **References.** A10 is checked against the stored files on all stocks, half A and
   half B. The no-stop reference "A" has a stored result only for all stocks, so it is
   checked there only.
4. **Ordering and tolerance** (as decided in `docs/a_exposure_preregistration.md`,
   2026-11-10): every run uses `PYTHONHASHSEED=0`; a reference counts as reproduced if
   CAGR and max drawdown are within 0.05pp of the stored file.

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

---

## Results, 2026-11-10 (`data/a_stop_width_result.txt`)

Run with `PYTHONHASHSEED=0`. All 12 reference checks matched within 0.01pp: A10 on three
samples × three windows, and A on all stocks × three windows. Nifty: W1 10.0%, W2 5.5%,
2018 +4.1%.

Each cell is CAGR (max drawdown); checks are out of 6.

| Sample | Version | W1 2019-26 | W2 2008-17 | 2018 | Checks W1 / W2 | Win % W1 / W2 |
|---|---|---|---|---|---|---|
| Half A | A10 (reference) | 25.9% (−32.5%) | 11.3% (−58.9%) | −36.1% | 6 / 5 | 40 / 32 |
| Half A | **A15** | 25.4% (−33.9%) | 10.2% (−67.0%) | −33.3% | 6 / 4 | 47 / 39 |
| Half A | A20 | 27.5% (−33.2%) | 10.7% (−69.0%) | −32.5% | 6 / 5 | 51 / 43 |
| Half A | A10C | 23.3% (−28.7%) | 14.5% (−48.7%) | −31.9% | 5 / 5 | 40 / 35 |
| Half A | A (no stop) | 31.2% (−41.6%) | 6.9% (−80.1%) | −23.2% | 6 / 3 | 54 / 50 |
| Half B | A10 (reference) | 23.2% (−41.4%) | 12.2% (−58.6%) | −36.0% | 5 / 5 | 36 / 34 |
| Half B | **A15** | 24.2% (−38.6%) | 11.8% (−64.3%) | −39.7% | 5 / 5 | 43 / 41 |
| Half B | A20 | 24.7% (−41.1%) | 13.8% (−65.3%) | −33.3% | 5 / 5 | 46 / 46 |
| Half B | A10C | 20.2% (−37.9%) | 14.5% (−46.6%) | −28.8% | 4 / 5 | 35 / 36 |
| Half B | A (no stop) | 25.5% (−41.6%) | 13.3% (−73.5%) | −26.4% | 5 / 4 | 49 / 52 |
| All stocks | A10 (reference) | 26.4% (−39.4%) | 13.2% (−59.1%) | −38.9% | 5 / 5 | 39 / 32 |
| All stocks | **A15** | 28.2% (−36.9%) | 12.9% (−64.9%) | −38.6% | 6 / 5 | 46 / 40 |
| All stocks | A20 | 30.3% (−37.4%) | 12.0% (−69.5%) | −34.0% | 6 / 5 | 50 / 43 |
| All stocks | A10C | 26.8% (−34.1%) | 15.7% (−46.2%) | −30.3% | 5 / 5 | 38 / 34 |
| All stocks | A (no stop) | 33.0% (−42.1%) | 8.4% (−80.1%) | −23.7% | 6 / 3 | 52 / 49 |

Exit mix, average win and loss, and calendar-year returns for every run are in the result
file.

### Verdict on the primary, A15, against the frozen bar: **FAILS. Not adopted.**

| Rule | Half A | Half B |
|---|---|---|
| 1. CAGR above A10 in both decades | W1 25.4 against 25.9: **fail**; W2 10.2 against 11.3: **fail** | W1 24.2 against 23.2: pass; W2 11.8 against 12.2: **fail** |
| 2. Drawdown ≤ 3pp deeper in either decade | W1 1.4pp: pass; W2 8.1pp deeper: **fail** | W1 shallower: pass; W2 5.8pp deeper: **fail** |
| 3. 2018 better than A10 | −33.3% against −36.1%: pass | −39.7% against −36.0%: **fail** |
| 4. ≥ 5 of 6 checks in both decades | 6 / 4: **fail** | 5 / 5: pass |

As expected before the run, the win rate rises (by 6-8 points) and the W2 drawdown is
deeper. It is more than 3pp deeper on both halves, so the 10% stop stays.

**For information (not judged):**
- **A20** shows the same pattern: a higher W1 return on both halves, but W2 drawdowns 7-10pp
  deeper.
- **A10C** (no re-buy of a stopped stock at the next rebalance) is the most interesting row:
  - W2: +2.4 to +3.2pp a year on both halves, with a drawdown 10-12pp shallower;
  - 2018: 4-7pp better;
  - W1: 2.6-3.0pp a year lower on both halves (+0.4pp on all stocks).

  It was not the primary and cannot be adopted from this test. It would need its own
  pre-registration.
