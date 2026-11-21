# Pre-registration: range breakout with higher risk, and alongside another strategy (half A)

**Status: FROZEN on 2026-11-09 ~17:05 IST,** before any run. This follows
`docs/range_breakout_preregistration.md`: RB3 had better trades (57% wins, +2.2% per
trade) but a lower CAGR, because it had a third as many trades and much idle cash. IA
asked to test both remedies. Never edit; add dated notes.

## Part 1: higher risk per trade

RB3 exactly as frozen: range breakout, buy at the close, swing-low stop, 1:3, 20
sessions, 10 slots, ≤ 25% per position. Only the risk per trade changes:

| Code | Risk per trade |
|---|---|
| RB3_R15 | 1.5% |
| RB3_R20 | 2.0% |

RB3 at 1.0% is re-run here as the regression check, as RB3_R10.

## Part 2: alongside another strategy

Two sleeves, each with half the capital, reset to 50/50 at each month-end. The method is
`combine()` from `tests/run_portfolio_combo.py`; no cost is charged for rebalancing.

| Code | Sleeves (both on half A) |
|---|---|
| C_RB_A | RB3 (1%) + monthly momentum top 20 with a 10% stop (A10) |
| C_RB_F | RB3 (1%) + FM_C3 (FM, clean-candle close entry, 1:3) |

The sleeves' own half-A results are reported too, for A10, RB3 and FM_C3.

## Comparison and adoption

- **References (half A):**
  - S3_REF3: 9.9% / 3.4% / −14.8%
  - FM_C3: 14.5% / 12.7% / −14.7%
- **Part 1:** a version is a candidate if it beats S3_REF3 on CAGR in both W1 and W2,
  with a drawdown no worse than S3_REF3's.
- **Part 2:** a combination is a candidate if, in both W1 and W2:
  - its drawdown is smaller than each of its sleeves'; and
  - its CAGR is at least the higher-CAGR sleeve minus 3pp.

## Windows and outputs

- **Windows:** W1, W2 and 2018, with the six checks.
- **All windows are in-sample.**
- **Output:** `data/rb_risk_combo_result.txt`.

---

## Results, 2026-11-09 (`data/rb_risk_combo_result.txt`), half A

RB3_R10 reproduces RB3 exactly (6.88% / 3.58% / −7.16%), and FM_C3 reproduces exactly.

| Version | W1 2019-26 | W2 2008-17 | 2018 | ₹10 L grew to (W1 / W2) | Checks W1 / W2 |
|---|---|---|---|---|---|
| *S3_REF3 (reference)* | *9.9% (DD −26%)* | *3.4% (−33%)* | *−14.8%* | *20.9 / 14.0 L* | *3 / 3* |
| RB3_R10 (1%) | 6.9% (−13%) | 3.6% (−16%) | −7.2% | 16.8 / 14.2 L | 2 / 3 |
| RB3_R15 (1.5%) | 8.9% (−17%) | 5.2% (−21%) | −10.1% | 19.5 / 16.6 L | 3 / 4 |
| RB3_R20 (2%) | 9.8% (−22%) | 6.7% (−22%) | −10.8% | 20.8 / 19.0 L | 3 / 4 |
| A10 (half A) | 25.9% (−33%) | 11.3% (−59%) | −36.1% | 60.8 / 29.1 L | 6 / 5 |
| FM_C3 (half A) | 14.5% (−18%) | 12.7% (−23%) | −14.7% | 28.8 / 33.0 L | 3 / 5 |
| C_RB_A (RB3 + A10) | 16.8% (−18%) | 8.1% (−36%) | −22.5% | 33.7 / 21.8 L | 5 / 4 |
| C_RB_F (RB3 + FM_C3) | 10.8% (−14%) | 8.2% (−18%) | −10.8% | 22.3 / 22.0 L | 3 / 4 |

**Part 1 verdict:**
- RB3_R20 ties the reference in W1: 9.77% against 9.89%, i.e. 0.1pp short. So it
  formally fails the rule.
- It beats the reference in W2: 6.7% against 3.4%.
- Its drawdowns are smaller in both: −22% against −26%, and −22% against −33%. Its 2018
  loss is smaller too: −10.8% against −14.8%.
- **Not adopted under the frozen rule, but it is at least as good as the current #3
  everywhere except a 0.1pp shortfall in W1.**

**Part 2 verdict:** neither combination meets the frozen rule.
- **Drawdown:** in both, the drawdown is not below RB3's own (−13% / −16%).
- **CAGR:** C_RB_A is more than 3pp below A10, and C_RB_F more than 3pp below FM_C3.
- **Not adopted.**
- C_RB_F is the smoothest mix tested: −14% / −18% drawdowns and −10.8% in 2018. But
  FM_C3 alone earns more, with only slightly larger drawdowns.
