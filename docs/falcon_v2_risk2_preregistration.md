# Pre-registration: Falcon v2 patterns at 2% risk per trade

**Status: FROZEN on 2026-11-13 18:20 IST.** Frozen on IA's instruction ("Try with 2% risk")
before any test code was written or run. Never edit; add dated notes.

**Samples.** Each variant runs once on half A, half B and all stocks, on W1 2019-01-01 →
2026-10-30, W2 2008-01-01 → 2017-12-31 and 2018, with the same six checks, costs and
data, and `PYTHONHASHSEED=0`. The stored v2 scans are reused. Neither half is clean
(half A shaped v2; half B was used for the v2 and retest tests), so a pass would mean
"paper trade it", not "proven". All windows are in-sample.

## Why

FV2 makes +1.5% to +2.6% per trade after costs, but with 1% risk per trade it kept only
47-61% of capital invested, so its yearly return only matched the Nifty. This test asks
whether doubling the risk per trade turns the per-trade edge into a return clearly above
the Nifty without an unacceptable drawdown.

## Rules

Everything is exactly FV2 (`docs/falcon_v2_preregistration.md`, rules 1-10) except the
risk per trade in rule 10:
- position value = min(risk × equity ÷ stop distance, 25% of equity, cash × 0.999);
- 10 slots and the 25% per-position cap are unchanged.

## Versions

| Code | Risk per trade | Role |
|---|---|---|
| FV2 | 1% | reference; must reproduce `data/falcon_v2_result.txt` within 0.05pp (all samples, W1 and W2) |
| **FV2_R2** | 2% | **primary** |
| FV2_R15 | 1.5% | reported |

## Adoption bar (FV2_R2; all must hold on both half A and half B, in both W1 and W2)

The same absolute bar as the v2 test:
1. CAGR above the Nifty's;
2. at least 4 of the 6 checks;
3. max drawdown no deeper than −25.00%;
4. win rate at least 45.0%, and mean net per trade at least +1.00%;

and:
5. CAGR higher than FV2's on the same sample and window.

Figures are compared as printed in the result file. Also reported: average capital
invested, how often the 25% cap or the cash limit sets the size, slots-full skips, and
2018.

## Expected, stated before the run

Return higher than FV2 in most cells, but the 25% cap will limit many positions (a 2%
risk with a stop more than 8% away is under the cap, nearer stops are capped), so the
gain is less than double. Drawdowns deeper, roughly 1.5×: likely to fail rule 3 in at
least one cell.

## Output

`data/falcon_v2_risk2_result.txt`, runner `tests/run_falcon_v2_risk2.py`. Implemented as
an optional `risk` parameter of `run_setups_v2` defaulting to 1%.
