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
