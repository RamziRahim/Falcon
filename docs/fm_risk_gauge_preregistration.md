# Pre-registration: Falcon Momentum clean close, risk per trade and market gauge

**Status: DRAFT, written 2026-11-10. NOT FROZEN.** No code written, nothing run. IA to
confirm or change the variants and the adoption bar, then replace this line with
"FROZEN on <date, time>" before any run. After that: never edit; add dated notes.

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
