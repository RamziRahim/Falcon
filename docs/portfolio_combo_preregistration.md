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

---

## Results, 2026-11-09 (`data/portfolio_combo_result.txt`)

The sleeves reproduce their earlier runs exactly: A10 26.4% / 13.2%; S 17.3% / 5.5%;
F 11.2% / 8.6%. Nifty: W1 10.0% (DD −38%), W2 5.5% (DD −60%), 2018 +4.1%.

| Version | W1 2019-26 | W2 2008-17 | 2018 | ₹10 L grew to (W1 / W2) | Checks W1 / W2 |
|---|---|---|---|---|---|
| *A alone* | 26.4% (DD −39%) | 13.2% (−59%) | −38.9% | 62.4 / 34.4 L | 5 / 5 |
| *S alone* | 17.3% (−24%) | 5.5% (−34%) | −14.3% | 34.8 / 17.0 L | 5 / 4 |
| *F alone* | 11.2% (−26%) | 8.6% (**−27%**) | −26.7% | 22.9 / 22.9 L | 2 / 4 |
| **P_ASF_R** | 18.9% (**−22%**) | 9.7% (−34%) | −26.9% | 38.6 / 25.3 L | 5 / 4 |
| P_ASF_H | 19.4% (−25%) | 9.5% (−32%) | −26.6% | 40.1 / 24.8 L | 5 / 4 |
| P_AS_R | 22.4% (−26%) | 10.0% (−42%) | −27.3% | 48.5 / 25.9 L | 5 / 4 |
| P_AF_R | 19.3% (−27%) | **11.4%** (−40%) | −32.6% | 39.7 / 29.4 L | 5 / **5** |
| P_SF_R | 14.5% (−21%) | 7.3% (−30%) | −20.5% | 28.9 / 20.2 L | 3 / 4 |

**Monthly return correlation** (A-S / A-F / S-F): W1 0.65 / 0.57 / 0.68; W2 0.48 /
0.67 / 0.61; 2018 0.83 / 0.52 / 0.75.

**Against the frozen success criterion:**
- *Drawdown smaller than every single sleeve in both decades.*
  - W1: met; P_ASF_R is at −22%, against a best single sleeve of −24%.
  - W2: **not met**; −34% against F alone at −27%.
- *CAGR at least Nifty + 5pp in both decades.*
  - W1: met.
  - W2: **not met**; 9.7% against 10.5% needed.
- **Criterion not met.**

**Closest to the goal:**
- **P_ASF_R** is the most balanced. It is about 19% / 10% a year, with worst drops of
  −22% / −34%. That compares with A alone at 26% / 13%, but −39% / −59%.
- **P_AF_R** is the only combination to pass 5/6 checks in both decades, and the only one
  above Nifty + 5pp in both. Its W2 drawdown, though, is −40%.

**2018:** combining does not help. All three are momentum strategies and lose together.
Correlations of 0.5-0.8 are too high for much diversification.
