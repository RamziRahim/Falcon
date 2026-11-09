# Pre-registration: one-time confirmation on half B

**Status: FROZEN on 2026-11-09 ~18:00 IST,** before any half-B run. IA agreed to stop
tuning and run the shortlist once on the held-back half B: 794 stocks, a SHA-256 split
in `data/holdout_split.csv`, never used in any test since the split. This is the only
half-B run. Whatever it shows is reported as is, with no re-tuning. Never edit; add dated
notes.

## What runs (unchanged code and parameters from the half-A tests)

| Code | Strategy |
|---|---|
| **FM_C3** | Falcon Momentum with the clean-candle close entry, 1:3 (`run_fm_entries` "closebuy") |
| **C_F_A** | FM_C3 + A10, half each, reset monthly (`combine`) |
| FM_REF3 | original FM, Monday open, 1:3 (`run_fm`): the reference for FM_C3 |
| A10 | monthly 12-1 momentum, top 20, 10% stop: C_F_A's other sleeve |
| S3_REF3 | #3 + Nifty filter, 1:3: the current-strategy reference |
| RB3_R20 | #3 range breakout at 2% risk: for information |

Universe: half-B stocks only, so ranks, peer groups, sector maps and the equal-weight
benchmark are all within half B. Windows: W1, W2 and 2018. Six checks each.

## Confirmation rules (both decades, W1 and W2)

**FM_C3 is confirmed if:**
1. its CAGR beats the Nifty in both decades;
2. it passes at least 4 of the 6 checks in both decades; and
3. it beats FM_REF3 on CAGR in both decades. This tests whether the entry change itself
   holds up out of sample.

**C_F_A is confirmed if:**
1. its CAGR beats the Nifty in both decades;
2. it passes at least 4 of the 6 checks in both decades; and
3. its maximum drawdown is at least 10pp shallower than A10's in both decades.

**Also reported:**
- each strategy's half-B CAGR against its half-A CAGR (the "shrinkage");
- the half-A + half-B view.

## Output

`data/halfB_confirmation_result.txt`
