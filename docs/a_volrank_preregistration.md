# Pre-registration: monthly momentum ranked by return per unit of volatility

**Status: FROZEN on 2026-11-10 15:28 IST.** Frozen by IA before any code was written or run. Never edit;
add dated notes.

**Samples and hold-out.** Half B was used once on 2026-11-09, so it is no longer unseen.
To keep it meaningful, nothing in this test is tuned: every parameter below is fixed
here, before any run, from common practice and not from a search. Each variant runs once
on all stocks, half A and half B (`data/holdout_split.csv`), on W1 2019-01-01 →
2026-10-30, W2 2008-01-01 → 2017-12-31 and 2018, with the same six checks, costs and
data. One variant is named **primary**; only it can be adopted. The others are reported
for information. All windows are in-sample. Paper trading is still the real test.

## Why

- A10 ranks on raw 12-1 return, which favours the most volatile stocks. Falcon Momentum
  already ranks on return ÷ volatility (`falcon_momentum.momentum_score`), and its
  drawdowns are about half of A10's, though it differs in many other ways too.
- On 2024-08 → 2026-10 test A's whole gain came from one stock
  (`docs/momentum_confirmation_preregistration.md`). A steadier ranking may reduce that
  dependence.

## Rules

A10 exactly as frozen, changing only the month-end ranking score.

| Code | Score | Role |
|---|---|---|
| A10 | close[t−21] ÷ close[t−252] − 1 | reference |
| **A10V** | the A10 score ÷ annualised standard deviation of daily returns over the last 252 sessions (at least 200 valid) | **primary** |
| A10Z | average of two z-scores across the list: (6-1 month return ÷ vol) and (12-1 month return ÷ vol) | reported |

Stocks without a valid volatility are not ranked. Everything else (top 20, equal
amounts, next-open rebalance, 10% stop) is unchanged.

## Implementation notes (confirmed by IA before the freeze)

1. **Volatility window.** It ends at the month-end session itself (the latest 252
   sessions), although the return skips the last 21. Daily returns are computed as in
   `falcon_momentum.momentum_score` (closes carried forward up to 5 sessions), annualised
   by √252.
2. **A10Z's returns.** Both skip the last month: close[t−21] ÷ close[t−126] − 1 and
   close[t−21] ÷ close[t−252] − 1. FM's own score does not skip it, so A10Z is not
   identical to FM's score.
3. **A10Z's z-scores.** Across the list members that have both scores: subtract the mean,
   divide by the sample standard deviation, as in `falcon_momentum.weekly_ranks`.
4. **Extra reports.**
   - Average volatility of holdings = the mean, over rebalances, of the 252-session
     volatility of the 20 chosen names.
   - Overlap with A10 = the mean share of chosen names that A10 chose at the same month end.
5. **Rule 3, "no deeper".** Max drawdowns are compared as printed in the result file (two
   decimals), with no allowance.
6. **Ordering and tolerance** (as decided in `docs/a_exposure_preregistration.md`,
   2026-11-10): every run uses `PYTHONHASHSEED=0`; the A10 reference counts as reproduced
   if CAGR and max drawdown are within 0.05pp of the stored file.

## Adoption bar (A10V against A10, same sample)

Adopted only if **all** hold on **both** half A and half B:
1. CAGR ÷ |max drawdown| higher than A10's in both W1 and W2;
2. CAGR no more than 2pp below A10's in either decade;
3. max drawdown no deeper than A10's in either decade;
4. at least 5 of the 6 checks in both decades.

Also reported: top-3 profit share, average 252-session volatility of the holdings,
overlap of holdings with A10.

## Expected, stated before the run

Slightly lower return and a shallower drawdown. If the return falls more than 2pp, raw
12-1 ranking stays.

## Output

`data/a_volrank_result.txt`

---

## Results, 2026-11-10 (`data/a_volrank_result.txt`)

Run with `PYTHONHASHSEED=0`. The A10 reference matched the stored files within 0.01pp on
all nine sample × window cells.

Each cell is CAGR (max drawdown); checks are out of 6.

| Sample | Version | W1 2019-26 | W2 2008-17 | 2018 | CAGR ÷ max DD, W1 / W2 | Checks W1 / W2 | Top-3 profit share W1 / W2 | Avg vol of holdings W1 / W2 | Overlap with A10 W1 / W2 |
|---|---|---|---|---|---|---|---|---|---|
| Half A | A10 (reference) | 25.9% (−32.51%) | 11.3% (−58.90%) | −36.1% | 0.80 / 0.19 | 6 / 5 | 0.22 / 0.37 | 50% / 54% | — |
| Half A | **A10V** | 24.3% (−34.15%) | 12.9% (−56.66%) | −29.5% | 0.71 / 0.23 | 6 / 5 | 0.22 / 0.32 | 45% / 49% | 78% / 81% |
| Half A | A10Z | 18.5% (−30.10%) | 11.4% (−58.05%) | −25.0% | 0.61 / 0.20 | 5 / 5 | 0.18 / 0.36 | 44% / 48% | 63% / 68% |
| Half B | A10 (reference) | 23.2% (−41.36%) | 12.2% (−58.58%) | −36.0% | 0.56 / 0.21 | 5 / 5 | 0.47 / 0.37 | 51% / 54% | — |
| Half B | **A10V** | 20.5% (−35.03%) | 13.6% (−57.76%) | −29.2% | 0.59 / 0.24 | 5 / 5 | 0.50 / 0.34 | 46% / 49% | 81% / 79% |
| Half B | A10Z | 19.7% (−36.14%) | 8.5% (−59.26%) | −27.1% | 0.54 / 0.14 | 4 / 4 | 0.56 / 0.31 | 45% / 48% | 65% / 67% |
| All stocks | A10 (reference) | 26.4% (−39.44%) | 13.2% (−59.05%) | −38.9% | 0.67 / 0.22 | 5 / 5 | 0.41 / 0.31 | 53% / 57% | — |
| All stocks | **A10V** | 26.8% (−31.53%) | 11.4% (−57.18%) | −34.4% | 0.85 / 0.20 | 5 / 5 | 0.40 / 0.31 | 47% / 51% | 75% / 79% |
| All stocks | A10Z | 23.3% (−36.57%) | 10.2% (−55.46%) | −25.3% | 0.64 / 0.18 | 5 / 4 | 0.47 / 0.31 | 46% / 51% | 58% / 64% |

### Verdict on the primary, A10V, against the frozen bar: **FAILS. Not adopted.**

| Rule | Half A | Half B |
|---|---|---|
| 1. CAGR ÷ max DD higher in both decades | W1 0.71 against 0.80: **fail**; W2 0.23 against 0.19: pass | W1 0.59 against 0.56: pass; W2 0.24 against 0.21: pass |
| 2. CAGR ≤ 2pp below A10 in either decade | W1 −1.7pp: pass; W2 +1.6pp: pass | W1 −2.7pp: **fail**; W2 +1.5pp: pass |
| 3. Drawdown no deeper in either decade | W1 −34.15% against −32.51%: **fail**; W2 shallower: pass | both shallower: pass |
| 4. ≥ 5 of 6 checks in both decades | 6 / 5: pass | 5 / 5: pass |

It fails on half A (rules 1 and 3, both in W1) and on half B (rule 2, in W1). Raw 12-1
ranking stays.

**What it did do:**
- **Volatility:** holdings were about 5 points less volatile.
- **W2:** returns 1.5-1.6pp a year higher on both halves, with drawdowns 1-2pp shallower.
- **2018:** about 7pp better.
- **W1:** returns 1.7-2.7pp lower, and the effect on the W1 drawdown was inconsistent:
  deeper on half A, shallower on half B and on all stocks.
- **Concentration:** the top-3 profit share did not fall.

**For information (not judged):** A10Z gives the best 2018 (−25% to −27%) but loses 3.5-7.4pp
a year in W1, and 3.7pp in W2 on half B.
