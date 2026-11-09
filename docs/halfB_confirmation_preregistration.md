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

---

## Results, 2026-11-09 (`data/halfB_confirmation_result.txt`): half B, the one-time run

Nifty: W1 10.0%, W2 5.5%, 2018 +4.1%.

| Strategy | Half B W1 | Half B W2 | Half B 2018 | Checks W1 / W2 | ₹10 L grew to (W1 / W2) | Half A W1 / W2 (for comparison) |
|---|---|---|---|---|---|---|
| FM_C3 | 8.4% (DD −26%) | 11.3% (−24%) | −16.3% | 2 / 5 | 18.8 / 29.3 L | 14.5% / 12.7% |
| FM_REF3 | 8.3% (−24%) | 4.1% (−31%) | −30.6% | 2 / 3 | 18.6 / 14.9 L | 9.1% / 8.7% |
| A10 | **23.2%** (−41%) | **12.2%** (−59%) | −36.0% | **5 / 5** | 51.3 / 31.5 L | 25.9% / 11.3% |
| **C_F_A** | **16.1%** (−31%) | **12.4%** (−36%) | −26.3% | **5 / 5** | 32.2 / 32.3 L | 20.7% / 12.6% |
| S3_REF3 | 6.2% (−34%) | 0.5% (−49%) | −12.5% | 2 / 2 | 16.0 / 10.5 L | 9.9% / 3.4% |
| RB3_R20 | −2.9% (−31%) | 4.1% (−26%) | −13.2% | 1 / 3 | 8.0 / 15.0 L | 9.8% / 6.7% |

**FM_C3: NOT confirmed.**
- **W1:** 8.4% is below the Nifty's 10.0%, with 2 of 6 checks. Fails rules 1 and 2.
- **Rule 3:** beats FM_REF3 in W1 by 0.1pp (8.4% against 8.3%) and in W2 by 7.3pp.
- So the clean-close entry's improvement held strongly in 2008-17 but vanished in
  2019-26 on these stocks.

**C_F_A: NOT confirmed, by the narrowest margin.**
- Rules 1 and 2 are met in both decades: 16.1% / 12.4% against the Nifty's 10.0% /
  5.5%, with 5 / 5 checks.
- Rule 3 is met in W2 (−36% against A10's −59%, 22pp shallower).
- In W1 its drawdown is −31.4% against A10's −41.4%: **9.94pp shallower, 0.06pp short of
  the 10pp required.**
- Formally it is not confirmed. In substance it held up: its returns are within 4.6pp
  and 0.2pp of half A, and it beats the Nifty by 6-7pp a year in both decades.

**The most consistent result across every sample is A10, monthly momentum:**

| Sample | W1 | W2 |
|---|---|---|
| All stocks | 26.4% | 13.2% |
| Half A | 25.9% | 11.3% |
| Half B | 23.2% | 12.2% |

It passes 5 of 6 checks or more everywhere, but always with deep drawdowns (−33% to −41%
in W1, −59% in W2) and about −36% in 2018.

**Not robust out of sample:** #3 (6.2% / 0.5%) and the range breakout (−2.9% / 4.1%).
Their half-A results were partly luck of the stock sample.
