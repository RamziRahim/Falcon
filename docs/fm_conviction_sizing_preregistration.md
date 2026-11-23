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
