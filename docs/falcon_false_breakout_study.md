# Falcon pattern breakouts: what separates real from false (descriptive study, half A)

**Date: 2026-11-10. Descriptive only; nothing here is a tested strategy.** Script:
`tools/fb_study.py`. Sample: half A only. Half B has never been used for any Falcon
pattern test.

## Method

- Every Falcon detection (`data/pit/falcon_setups_*.parquet`, the unchanged pattern
  engine) whose pivot was touched within 5 sessions: **8,175 breakouts** (4,244 in
  2019-26, 3,931 in 2008-17). This is every triggered pattern, not only the trades a
  10-slot portfolio took.
- Each is followed for 40 sessions with Falcon's own stop and target, from a fill at the
  pivot (or the open if higher).
- "Net" = the result after 0.4% round-trip costs.
- "Wick" = the trigger day closed back below the pivot.

## Findings

**1. More than half of all triggers are wick fakeouts, and nothing known beforehand
predicts them.**
- The wick rate is 54% (W1) and 56% (W2).
- It stays between 51% and 64% for every pre-trigger feature tested: pattern type,
  momentum rank, trend, distance from the 52-week high, base tightness, volume dry-up,
  market state, stop distance, and the gap at the open.
- A false breakout can only be recognised at the close of the trigger day.

**2. The close of the trigger day is the strongest signal in the data.**

| Trigger-day close | Share | Stopped | Hit target | Net per trade W1 / W2 |
|---|---|---|---|---|
| Back below the pivot (wick) | 55% | 53% / 52% | 25% / 27% | −0.35% / −0.47% |
| Above the pivot | 45% | 39% / 40% | 38% / 36% | +2.57% / +1.98% |
| 2-5% above the pivot | 9% | 31% / 38% | 44% / 41% | +3.98% / +2.70% |
| More than 5% above | 2% | 13% / 24% | 72% / 59% | +9.51% / +6.91% |

A stronger close is better, not "too extended". Volume ≥ 1.5× adds about 0.4-0.8pp on top.

**3. Three filters known before the trigger separate good detections from bad in both
decades.**

| Filter at detection | Passes: net W1 / W2 | Fails: net W1 / W2 |
|---|---|---|
| Close above a rising 200-DMA, with 50-DMA above 200-DMA | +1.37% / +0.98% | +0.33% / −0.11% |
| Within 10% of the 52-week high | +1.36% / +1.60% | +0.33% / −0.38% (10-25% below); +0.64% / −1.50% (more than 25% below) |
| Nifty 50 above its 50-DMA | +1.11% / +0.82% | +0.27% / −0.52% |

- 37% of triggered detections fail the first filter. Falcon's swing-structure "UPTREND"
  test lets them through.
- Combined (momentum top 20%, rising 200-DMA, within 15% of the high, Nifty above its
  50-DMA) and closing above the pivot: about +3% net per trade in both decades.

**4. Things that do not help, in both decades:**
- pattern type: VCP and bull flag are no better than a flat base, and their stop rates
  are higher;
- base tightness;
- volume dry-up before the breakout;
- an opening gap;
- a tighter stop: stops ≤ 5% away are hit 52-58% of the time.

**5. Detector defects confirmed.**
- Where the pivot had already been exceeded by more than 3% before detection, the wick
  rate rises to 60-64%, and W2 net falls to −0.14% (against +0.71%). These are the
  triangle-average and VCP-last-contraction pivots.
- The trend gate: see finding 3.

**6. After a clean close above the pivot, buying at that close still made money over the
next 20 sessions:** +2.75% (W1) and +1.70% (W2) for filtered detections, before costs.

## What follows for the design

- **Entry:** only on a close above the pivot, bought at that close (about 3:20 pm).
  A buy-stop cannot avoid the 55% of triggers that fail, and selling them at the close
  costs more than holding (`docs/wick_exit_preregistration.md`).
- **Detection:** fix the two pivots, replace the trend gate with the 200-DMA rule, and
  require closeness to the 52-week high.
- **Market:** keep a Nifty filter.
- **Pattern scores** (VCP 30, triangle 20 ...) carry no information and should not
  prioritise trades.
