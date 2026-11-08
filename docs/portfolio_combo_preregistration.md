# Pre-registration: combining the top strategies into one portfolio

**Status: FROZEN on 2026-11-09 ~01:05 IST,** before any run. IA approved step 1 of the
improvement plan: run several strategies side by side so that their bad years offset
each other. Never edit; add dated notes.

## Sleeves (each exactly as frozen elsewhere)

| Code | Strategy | Source |
|---|---|---|
| A | monthly 12-1 momentum, top 20, with a 10% stop | `docs/a_stop_preregistration.md`, A10 |
| S | #3 + Nifty filter, 1:3 | `run_s_plus(entries_s, r=3, market_filter=True)` |
| F | Falcon Momentum, 1:3 | `run_fm(time_stop=40)`, FM R3 |

## How the sleeves are combined

Each sleeve runs on its own capital, with its own slots and risk sizing; the sleeves do
not share cash. The combined equity is built from the sleeves' daily equity curves:
- **Rebalanced (R):** at each month-end the sleeves are reset to equal weights, so the
  combined daily return = Σ wᵢ × sleeve return, with w reset monthly.
- **Hold (H):** each sleeve starts with an equal share of capital and is never
  rebalanced; combined equity = the sum of the sleeves.

**Rebalancing is an approximation.** In practice the cash would be moved between sleeves
as positions close. No extra cost is charged for it, so the R versions are slightly
optimistic.

For the top-3 profit check, each trade's profit is scaled by the sleeve's share of the
combined capital at its entry date.

## Versions

| Code | Sleeves | Weights | Rebalance |
|---|---|---|---|
| P_ASF_R | A, S, F | 1/3 each | monthly |
| P_ASF_H | A, S, F | 1/3 each | never |
| P_AS_R | A, S | 1/2 each | monthly |
| P_AF_R | A, F | 1/2 each | monthly |
| P_SF_R | S, F | 1/2 each | monthly |

## Windows, checks and outputs

- **Windows:** W1, W2 and 2018, judged with the six checks.
- **Also reported:** the correlation of the sleeves' monthly returns; the sleeves' own
  results, as a regression check against the earlier runs.
- **Success criterion:** the combination beats every single sleeve on worst drawdown in
  both decades, while keeping a CAGR of at least the Nifty + 5pp in both decades.
- **All windows are in-sample.**
- **Outputs:**
  - `data/portfolio_combo_result.txt`
  - sleeve equity curves in `data/portfolio_combo_equity_*.csv`
