# Falcon Momentum: more risk on higher-conviction breakouts — pre-registration

**Status: FROZEN on 2026-11-23 09:56 IST**

## Question

IA (2026-11-23): within a 1:3 strategy, should trades with more supporting evidence at entry get more capital, and trades with less get less?

The strategy is **FM_C3**: Falcon Momentum breakouts bought at a clean close, with a swing-low / 3 ATR stop and a 1:3 target. It is the breakout half of tracks C_F_A, C_F_A_P3 and C_F_A_H.

FM_C3 already sizes every trade so that it risks the same amount (1% of equity, or 0.5% when the market gauge is below its 50-session average). This test changes **how much** each trade risks, by conviction.

## What the evidence says (descriptive study, half A only)

Source: `tools/conviction_study.py`, run 2026-11-23, output `data/conviction_study.txt`. It covers FM_C3's own trades on half A: 498 in W2, 460 in W1. Half B was not looked at.

Net return per trade after costs, by thirds of each fact at entry:

| Fact at entry | Bottom third W2 / W1 | Top third W2 / W1 | Consistent? |
|---|---|---|---|
| **Nifty's distance above its 50-DMA** | −0.37% / −0.02% | **+4.67% / +5.20%** | **Yes, strongly** |
| **Close above the prior 20-day high** | +1.23% / +2.33% | +2.76% / +4.09% | Yes, weaker (W2's middle third is best) |
| Stop distance (3 ATR as % of price) | +1.70% / +1.89% (tightest) | +2.64% / +3.64% (widest) | Tight stops are **worse** |
| 6-month momentum rank | +3.02% / +3.51% | +2.32% / +1.65% | Higher rank slightly worse |
| Distance below the 52-week high | +2.87% / +2.85% (closest) | +2.13% / +2.03% | Small |
| Volume vs 50-day average | no order | no order | No |
| Where the close sits in the day's range | no order | no order | No |

**Not tested:** "tight stop → bigger bet" as a reason to add risk. FM already gives tight-stop trades bigger positions, so each trade risks the same rupees, and the tightest stops did worst.

## Rule (FM_C3_CONV)

At each fill (the signal day's close), compute two facts, both known at that close:

1. **Market strength (m):** Nifty 50 close ÷ its 50-session average − 1.
2. **Breakout strength (k):** the stock's close ÷ its highest high of the previous 20 sessions − 1.

The cut points are the half-A thirds above, rounded: 1.4% and 4.1% for m, 2.2% for k.

**Risk multiplier** on FM's own risk per trade:

| Condition | Multiplier |
|---|---|
| m < 1.4% (weak market) | **0.5×** |
| m ≥ 4.1% and k ≥ 2.2% (strong market and strong breakout) | **1.5×** |
| Everything else | 1.0× |

Everything else is FM_C3 unchanged:
- FM's 25% position cap and cash limit still apply. The multiplier can only raise or lower the rupees risked, within the cap.
- Same watch list, signals, stops, 1:3 target, 40-session time stop and 10 slots.

New optional parameter: `run_fm_entries(..., conviction=None)`. The default leaves current behaviour unchanged.

## Variants

- **FM_C3:** the reference. It must reproduce the stored files: half A and half B (`data/fm_risk_gauge_result.txt`) and all stocks (`data/buystop_mix_result.txt`), within 0.05pp of CAGR and max DD. Otherwise the run stops.
- **FM_C3_CONV (primary):** the rule above.
- **FM_C3_MKT (reported):** the market part only: 0.5× when m < 1.4%, 1.5× when m ≥ 4.1%.
- **C_F_A_CONV (reported):** FM_C3_CONV combined with A10 as in track C_F_A, against C_F_A.

## Runs

- Windows: W2 2008-01-01 → 2017-12-31 and W1 2019-01-01 → 2026-10-30 (both judged); H0 2001–06 (reported).
- Samples: all stocks, half A and half B. Data `data/pit_v2`, no ethical filter.

## Adoption bar (judged: FM_C3_CONV vs FM_C3)

All four conditions must hold:

1. **All stocks, W1 and W2:** CAGR at least 1.0 percentage point a year above FM_C3's.
2. **All stocks, W1 and W2:** max drawdown no more than 2.0 points deeper than FM_C3's.
3. **Half B, W1 and W2:** CAGR not below FM_C3's.
   - Half B is the sample the rule was **not** derived from.
4. **H0 2001–06, all stocks:** CAGR not below FM_C3's.
   - This is the period the rule was not derived from.

Otherwise the verdict is **NOT ADOPTED**. A failed verdict flags only; IA decides. No re-tuning, no extra variants.

## Caveat

The cut points come from half A in W1 and W2, so **half A and the all-stocks results are partly in-sample**. That is why half B and 2001–06 carry their own conditions.

## Output

- `data/fm_conviction_sizing_result.txt`
- Runner: `tests/run_fm_conviction_sizing.py`
- Dated Results section here; scorecard rows.

## Dated note (2026-11-23 10:00 IST, approved by IA)

**Correction to the reference file.** `data/fm_risk_gauge_result.txt` was made on the older data (`data/pit`). On `data/pit_v2`, FM_C3's W2 numbers on the halves differ slightly from it.
- Example: half A W2 is 12.04% there vs 12.69% in the old file.
- W1 is identical in both files.

The reference for **all three samples** is therefore `data/buystop_mix_result.txt`, the pit_v2 file that every recent test uses. Nothing else changes.

## Results (2026-11-23, run once after freeze)

**References.** Passed: FM_C3 and C_F_A reproduced `data/buystop_mix_result.txt` exactly on all stocks, half A and half B, in every window present in the file. Output: `data/fm_conviction_sizing_result.txt`.

**Verdict (FM_C3_CONV vs FM_C3): NOT ADOPTED.** Four of the seven conditions failed.

| Condition | Result | |
|---|---|---|
| 1. All stocks W2, CAGR gain ≥ +1.0pp | −0.58pp (11.98% vs 12.56%) | FAIL |
| 1. All stocks W1, CAGR gain ≥ +1.0pp | −0.18pp (11.53% vs 11.71%) | FAIL |
| 2. All stocks W2, drawdown ≤ 2 pts deeper | 2.26 pts deeper (−28.4% vs −26.1%) | FAIL |
| 2. All stocks W1, drawdown ≤ 2 pts deeper | 4.15 pts **shallower** (−19.6% vs −23.8%) | pass |
| 3. Half B W2, CAGR not lower | −0.45pp | FAIL |
| 3. Half B W1, CAGR not lower | +2.36pp | pass |
| 4. All stocks H0, CAGR not lower | +3.59pp (34.62% vs 31.03%) | pass |

**CAGR % (max DD %)**

| Version | Sample | H0 2001–06 | W2 2008–17 | W1 2019–26 |
|---|---|---|---|---|
| FM_C3 | All | 31.03 (−14.2) | 12.56 (−26.1) | 11.71 (−23.8) |
| **FM_C3_CONV** | All | 34.62 (−13.6) | 11.98 (−28.4) | 11.53 (−19.6) |
| FM_C3_MKT | All | 36.63 (−17.7) | 12.62 (−25.3) | 9.49 (−20.9) |
| C_F_A (track 3) | All | 35.56 (−24.6) | 13.46 (−35.9) | 19.49 (−25.9) |
| C_F_A_CONV | All | 37.46 (−23.7) | 13.24 (−36.7) | 19.44 (−25.1) |
| FM_C3 / FM_C3_CONV | Half A | 15.20 / 14.30 | 12.04 / 13.17 | 14.49 / 14.65 |
| FM_C3 / FM_C3_CONV | Half B | 23.74 / 26.63 | 11.62 / 11.17 | 8.40 / 10.76 |

**How often each multiplier was used** (all stocks): 0.5× on about 18–31% of fills, 1.5× on 12–35%, 1× on the rest. The trades themselves are identical; only their size changes.

**What it means, in plain English:**
- The strong-market facts that marked better *individual* trades in the half-A study did **not** turn into a better *portfolio* in 2008–17 or 2019–26:
  - All stocks: −0.6 and −0.2 points a year.
  - Half B in 2008–17: −0.45.
- The gains appear only in the periods and samples where the rule happened to fit:
  - 2001–06: +3.6;
  - half B in 2019–26: +2.4;
  - half A in 2008–17, the sample the cut points came from: +1.1.
- The likely reasons:
  - FM already halves its risk when the market gauge is weak, so much of the market effect was already being captured.
  - Betting 1.5× after the market has run well above its average also means being biggest just before pullbacks. That deepened the 2008–17 drawdown.
- On the paper track C_F_A it makes almost no difference: −0.2 and −0.05 points a year.
- FM and the paper tracks stay as they are. IA decides.
