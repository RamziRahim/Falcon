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
