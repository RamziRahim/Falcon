# Pre-registration: Falcon Momentum clean close, risk per trade and market gauge

**Status: FROZEN on 2026-11-10 15:32 IST.** Frozen by IA before any code was written or run. Never edit;
add dated notes.

**Samples and hold-out.** Half B was used once on 2026-11-09, so it is no longer unseen.
To keep it meaningful, nothing in this test is tuned: every parameter below is fixed
here, before any run, from common practice and not from a search. Each variant runs once
on all stocks, half A and half B (`data/holdout_split.csv`), on W1 2019-01-01 →
2026-10-30, W2 2008-01-01 → 2017-12-31 and 2018, with the same six checks, costs and
data. One variant is named **primary**; only it can be adopted. The others are reported
for information. All windows are in-sample. Paper trading is still the real test.

## Why

- FM_C3's per-trade result is steady (+2.1% to +2.8% a trade on both halves and both
  decades), but with 50-60 trades a year at 1% risk much of the account sits in cash.
  It made 8.4% in W1 on half B, below the Nifty (`data/halfB_confirmation_result.txt`).
- On the range breakout, raising risk from 1% to 2% took W1 from 6.9% to 9.8% and the
  drawdown from −13% to −22% (`docs/rb_risk_combo_preregistration.md`). FM has never
  been run above 1%.
- FM's crash protection reads the Nifty 50. In 2018 the Nifty stayed up while the list
  fell 24%, and FM lost 12-31%.

## Rules

FM_C3 exactly as in `docs/close_entry_preregistration.md` (`run_fm_entries`,
"closebuy", 1:3, 40-session time stop). SLOTS = 10 and POS_CAP = 25% are unchanged.

**Part 1: risk per trade** (`RISK_ON` / `RISK_SOFT`)

| Code | Risk, gauge above its 50-day / below it | Role |
|---|---|---|
| FM_C3 | 1.0% / 0.5% | reference |
| **FM_C3_R15** | 1.5% / 0.75% | **primary for part 1** |
| FM_C3_R20 | 2.0% / 1.0% | reported |

**Part 2: gauge.** Replace the Nifty 50 in the crash protection only (no new buys below
the 200-session average; soft risk below the 50-session average) with the equal-weight
index of the sample's own list (`equal_weight_universe`, cumulated). The sector check
still compares sector indices with the Nifty.

| Code | Gauge | Risk | Role |
|---|---|---|---|
| **FM_C3_EW** | equal-weight list | 1.0% / 0.5% | **primary for part 2** |
| FM_C3_EW_R15 | equal-weight list | 1.5% / 0.75% | reported |

## Implementation notes (confirmed by IA before the freeze)

1. **Where the gauge is replaced.** `run_fm_entries` reads the Nifty in three places, and
   all three switch to the equal-weight gauge. The sector check still compares sector
   indices with the Nifty.
   - The weekly watch list is built only when the gauge is above its 200-session average.
   - A daily trigger is blocked when the gauge is not above its 200-session average.
   - The risk level depends on the 50-session average.
2. **References.** FM_C3 has stored results only for half A (`data/close_entry_result.txt`)
   and half B (`data/halfB_confirmation_result.txt`); it is checked against those. The
   all-stocks FM_C3 run is new and has nothing to be checked against.
3. **Ordering and tolerance** (as decided in `docs/a_exposure_preregistration.md`,
   2026-11-10): every run uses `PYTHONHASHSEED=0`; a reference counts as reproduced if
   CAGR and max drawdown are within 0.05pp of the stored file.
4. **Extra reports.**
   - Average gross exposure = the average share of the account invested.
   - 25% cap binds = the count of buys whose size was set by the cap.
   - Slots bind = the count of valid entry fills skipped because all 10 slots were full.
   - Weeks blocked = the count of weekly ranking dates with the gauge not above its
     200-session average.
5. **Rule comparisons.** Figures are compared as printed in the result file (two
   decimals), with no allowance. "No deeper than −30%" means −30.00 passes and −30.01
   fails.

## Adoption bars (same sample; all must hold on both half A and half B)

**FM_C3_R15 against FM_C3:**
1. CAGR at least 2pp higher in both W1 and W2;
2. max drawdown no deeper than −30% in W1, W2 or 2018;
3. CAGR ÷ |max drawdown| not below FM_C3's in either decade.

**FM_C3_EW against FM_C3:**
1. 2018 return at least 5pp better;
2. CAGR no more than 1pp lower in either decade;
3. max drawdown no more than 3pp deeper in either decade.

Also reported: average gross exposure, how often the 25% cap and the 10 slots bind,
weeks blocked by the gauge.

## What this does not decide

Whether FM_C3 beats the Nifty on its own; it did not on half B in W1. An adopted change
here only feeds a later, separately registered re-run of the C_F_A pair.

## Output

`data/fm_risk_gauge_result.txt`

---

## Results, 2026-11-10 (`data/fm_risk_gauge_result.txt`)

Run with `PYTHONHASHSEED=0`. The FM_C3 reference reproduced the stored files exactly on
half A and half B (six sample × window cells). The all-stocks FM_C3 run is new. Nifty:
W1 10.0%, W2 5.5%, 2018 +4.1%.

Each cell is CAGR (max drawdown); checks are out of 6.

| Sample | Version | W1 2019-26 | W2 2008-17 | 2018 | Checks W1 / W2 | Avg exposure W1 / W2 | 25% cap binds W1 / W2 | Weeks blocked W1 / W2 / 2018 |
|---|---|---|---|---|---|---|---|---|
| Half A | FM_C3 (reference) | 14.49% (−17.95%) | 12.69% (−23.22%) | −14.73% (−16.25%) | 3 / 5 | 55% / 48% | 1 / 3 | 110 / 176 / 12 |
| Half A | **FM_C3_R15** | 12.96% (−34.59%) | 14.35% (−30.16%) | −16.13% (−18.83%) | 3 / 5 | 62% / 53% | 12 / 6 | same |
| Half A | FM_C3_R20 | 13.98% (−35.10%) | 14.24% (−33.43%) | −11.81% (−16.71%) | 3 / 5 | 65% / 56% | 26 / 27 | same |
| Half A | **FM_C3_EW** | 14.78% (−24.73%) | 9.57% (−28.45%) | −12.87% (−13.49%) | 3 / 4 | 54% / 43% | 1 / 3 | 121 / 212 / 39 |
| Half A | FM_C3_EW_R15 | 17.21% (−36.66%) | 14.78% (−30.87%) | −11.30% (−12.74%) | 5 / 5 | 62% / 48% | 4 / 10 | 121 / 212 / 39 |
| Half B | FM_C3 (reference) | 8.40% (−25.57%) | 11.34% (−24.16%) | −16.34% (−18.97%) | 2 / 5 | 53% / 47% | 2 / 2 | 110 / 176 / 12 |
| Half B | **FM_C3_R15** | 13.48% (−25.07%) | 11.97% (−26.59%) | −19.13% (−21.86%) | 3 / 5 | 60% / 53% | 7 / 6 | same |
| Half B | FM_C3_R20 | 13.53% (−29.21%) | 9.57% (−26.45%) | −17.74% (−22.34%) | 3 / 4 | 62% / 55% | 26 / 26 | same |
| Half B | **FM_C3_EW** | 8.79% (−32.10%) | 5.10% (−42.69%) | −11.57% (−15.23%) | 3 / 3 | 48% / 43% | 1 / 3 | 143 / 201 / 38 |
| Half B | FM_C3_EW_R15 | 13.62% (−38.33%) | 5.21% (−43.81%) | −13.93% (−18.45%) | 3 / 4 | 54% / 49% | 12 / 8 | 143 / 201 / 38 |
| All stocks | FM_C3 (new) | 11.71% (−23.76%) | 12.85% (−26.14%) | −13.39% (−16.49%) | 3 / 5 | 53% / 46% | 0 / 5 | 110 / 176 / 12 |
| All stocks | **FM_C3_R15** | 10.22% (−30.13%) | 15.33% (−35.42%) | −15.98% (−18.32%) | 2 / 5 | 61% / 54% | 6 / 8 | same |
| All stocks | FM_C3_R20 | 10.02% (−33.41%) | 15.07% (−36.23%) | −15.21% (−17.37%) | 2 / 5 | 63% / 56% | 17 / 22 | same |
| All stocks | **FM_C3_EW** | 12.85% (−30.51%) | 10.86% (−24.87%) | −11.41% (−12.74%) | 3 / 5 | 51% / 41% | 0 / 3 | 131 / 207 / 38 |
| All stocks | FM_C3_EW_R15 | 13.20% (−34.29%) | 11.47% (−29.60%) | −12.40% (−14.39%) | 3 / 5 | 59% / 48% | 6 / 4 | 131 / 207 / 38 |

- Weeks are out of 408 (W1), 522 (W2) and 52 (2018).
- **Slots bind:** clean-candle signals skipped because all 10 slots were full: 394-614 in
  W1 and 402-478 in W2 on the halves, in every version. The slot limit binds far more
  often than the 25% cap. The counts are in the result file.

### Verdict, part 1: FM_C3_R15 against the frozen bar: **FAILS. Not adopted.**

| Rule | Half A | Half B |
|---|---|---|
| 1. CAGR ≥ 2pp higher in both decades | W1 −1.53pp: **fail**; W2 +1.66pp: **fail** | W1 +5.08pp: pass; W2 +0.63pp: **fail** |
| 2. Drawdown no deeper than −30% in W1, W2 or 2018 | W1 −34.59%: **fail**; W2 −30.16%: **fail** | −25.07% / −26.59% / −21.86%: pass |
| 3. CAGR ÷ max DD not below FM_C3's | W1 0.37 against 0.81: **fail**; W2 0.48 against 0.55: **fail** | W1 0.54 against 0.33: pass; W2 0.45 against 0.47: **fail** |

Raising risk from 1% to 1.5% lifted exposure only from about 53% to 61%, because the 10
slots, not the risk per trade, limit how much is invested. On half A it nearly doubled
the W1 drawdown and lowered the return.

### Verdict, part 2: FM_C3_EW against the frozen bar: **FAILS. Not adopted.**

| Rule | Half A | Half B |
|---|---|---|
| 1. 2018 ≥ 5pp better | +1.86pp: **fail** | +4.77pp: **fail** |
| 2. CAGR ≤ 1pp lower in either decade | W1 +0.29pp: pass; W2 −3.12pp: **fail** | W1 +0.39pp: pass; W2 −6.24pp: **fail** |
| 3. Drawdown ≤ 3pp deeper in either decade | W1 6.78pp deeper: **fail**; W2 5.23pp: **fail** | W1 6.53pp deeper: **fail**; W2 18.53pp: **fail** |

The equal-weight gauge did what it was meant to do in 2018: it blocked 38-39 of 52 weeks
against the Nifty's 12, and cut exposure to about 16%. But the year still lost 12-13%,
and in both decades the gauge was worse than the Nifty: lower W2 returns and deeper
drawdowns on both halves. The Nifty gauge stays.

**For information (not judged):** FM_C3_R20 and FM_C3_EW_R15 show no consistent gain
either. FM_C3_EW_R15 looks good on half A (17.2% / 14.8%) but poor on half B (W2 5.2%,
drawdowns −38% / −44%).

**As the doc says, this does not change FM_C3's standing.** On half B in W1 it is still
below the Nifty (8.4% against 10.0%). On all stocks, run here for the first time, FM_C3
made 11.7% / 12.9% a year with drawdowns of −24% / −26%.
