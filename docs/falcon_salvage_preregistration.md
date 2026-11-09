# Pre-registration: Falcon patterns, audited and re-entered (half A)

**Status: FROZEN on 2026-11-09 ~17:50 IST,** before any run. IA asked for two things:
- test my diagnosis of why Falcon Leadership failed: its patterns, restricted to momentum
  leaders, with a confirmed entry and a wider stop;
- check how well the patterns are detected, including buy-stop triggers that fill on a
  wick and close back below the pivot.

Never edit; add dated notes.

## Data

- Falcon's own saved setups: `data/pit/falcon_setups_2008-01-01_2017-12-31.parquet` and
  `data/pit/falcon_setups_2019-01-01_2026-10-30.parquet`.
- These come from the unchanged pattern engine, scanned every 5 sessions, pre-breakout,
  within 5% below the pivot, with Falcon's stop, target and RR ≥ 1.25.
- **Half-A stocks only.** There is no 2018 scan, so the windows are W1 and W2 only.

## Part 1: wick fakeouts

On every F_REF fill (a buy-stop at the pivot), a **wick fakeout** is a fill-day close
below the pivot. Report:
- the share of fills that are wick fakeouts, by pattern;
- the win rate, the mean net per trade and the stop rate, for wick fills against
  closed-above fills.

## Part 2: detection sanity checks at the scan date (half A)

| Flag | Meaning | Rule |
|---|---|---|
| N_UP | no uptrend | not (Close > 200-DMA and 50-DMA > 200-DMA) |
| PIV_X | pivot already exceeded | max High of the 20 sessions up to the scan > pivot × 1.005 |
| CRASH | crash inside the base | the max close-to-close drawdown over the 60 sessions before the scan > 25% |
| WIDE | not consolidating | the 20-session (max High / min Low − 1) > 20% |
| FAR | far from the high | Close < 75% of the 52-week high |

**Report:**
- the share of detections with each flag, per pattern, and the share with any flag;
- the F_REF outcomes (win %, net per trade) of trades from flagged against clean
  detections.

**Also:** a contact sheet of 24 random half-A detections (6 per pattern), for IA to review
by eye.

## Part 3: re-entered backtests (`backtesting/falcon_salvage.py`)

**Common rules:**
- 1% risk, ≤ 25% per position, 10 slots, 40-session time stop;
- skip if the stop is more than 15% away;
- no market filter in any version, so that only the listed factors change;
- priority: Falcon's pattern priority, then distance to the pivot.

**MOM** = only setups whose 126-session return is in the top 20% of the half-A universe
on the scan date.

| Code | Setups | Entry | Stop / target |
|---|---|---|---|
| F_REF | all | pivot buy-stop | Falcon's |
| F_CC | all | clean close | Falcon's |
| F_MOM | MOM | pivot buy-stop | Falcon's |
| F_MOM_CC | MOM | clean close | Falcon's |
| F_CC_W | all | clean close | 3 ATR / 3R |
| **F_MOM_CC_W** | MOM | clean close | 3 ATR / 3R |

**Clean close** = High > pivot, Close > pivot, Close ≥ Open, upper wick < 50% of the
range, and Volume ≥ 1.5 × the 20-day average (Falcon's own breakout-volume rule). The
buy is at that close, in the 5 sessions after the scan.

## Reading the result

- **"Patterns were not the problem, only how they were used":** F_MOM_CC_W comes within
  3pp of FM_C3's CAGR on half A (14.5% / 12.7%) in both W1 and W2.
- **Otherwise:** the patterns add nothing over momentum plus a confirmed breakout.
- **Each factor's contribution** is read from the pairs:
  - REF → CC: the entry;
  - REF → MOM: the momentum filter;
  - CC → CC_W: the wider stop.

## Outputs

All in-sample.
- `data/falcon_salvage_result.txt`
- `data/falcon_salvage_audit.txt`
- `data/falcon_detections_sample.png`

## Dated note, 2026-11-09 ~18:05 IST, after a W1 smoke run (results not yet read beyond the flags)

The code shows the triangle pivot is the **average** of the last two swing highs, which
the detector allows to differ by up to 3%. PIV_X at 0.5% therefore partly reflects that
tolerance. An extra descriptive flag, **PIV_X3** (the 20-session max High > pivot × 1.03),
is added to Part 2. Nothing else changes.

---

## Results, 2026-11-09 (`data/falcon_salvage_result.txt`, `data/falcon_salvage_audit.txt`, `data/falcon_detections_sample.png`), half A

### Part 1: wick fakeouts (F_REF buy-stop fills, W1 + W2)

| Fill day | Share of fills | Win % | Net per trade | Stopped out | Hit target |
|---|---|---|---|---|---|
| **Closed back below the pivot (wick)** | **54.7%** | 36.9% | **−1.28%** | 56.2% | 24.3% |
| Closed above the pivot | 45.3% | 53.8% | **+2.57%** | 38.5% | 37.8% |

The pattern is the same in both decades:
- W1: wick −1.07% against closed-above +2.80%;
- W2: wick −1.46% against +2.34%.

Wick fills are 52-61% of the fills for every pattern. **IA's observation is confirmed:**
more than half of Falcon's buy-stop triggers are wick fakeouts, and they are the losing
half.

### Part 2: detection sanity flags (14,811 half-A detections)

| Pattern | Detections | No uptrend (N_UP) | Pivot exceeded (PIV_X) | Exceeded > 3% (PIV_X3) | Crash in base | Wide | Far from high | Any flag |
|---|---|---|---|---|---|---|---|---|
| Asc. triangle | 7,940 | 33.6% | 85.2% | 10.7% | 5.6% | 12.4% | 16.6% | 90.9% |
| Flat base | 5,584 | 27.5% | 10.5% | 0.2% | 1.2% | 0.1% | 7.6% | 35.9% |
| VCP | 1,103 | 41.6% | 74.0% | 37.7% | 11.5% | 21.5% | 24.8% | 86.3% |
| Bull flag | 184 | 26.6% | 50.5% | 19.6% | 10.3% | 96.2%* | 13.6% | 96.7% |

\*Bull flags are wide by construction, because the flagpole is in the window.

**Flaws seen in the code and the contact sheet:**
- **Triangle pivot.** It is the *average* of only the last two swing highs, which may be
  months apart and up to 3% different. The higher high is already above the buy level,
  so many "triangles" are choppy ranges with a spike.
- **VCP pivot.** It is the high of the *last* contraction, which is often below the
  base's real top. 38% of VCPs had traded more than 3% above their pivot in the 20 days
  before detection. The "first contraction low" can come from a different phase, months
  earlier.
- **Trend gate.** The swing-structure "UPTREND" passes 32% of stocks that are below
  their 200-DMA, or whose 50-DMA is below the 200-DMA.
- **Flat base.** It is the cleanest: only 36% have any flag.

**Do the flags matter?**
- **N_UP:** flagged trades net −0.29%, against +0.82% for clean ones.
- **FAR:** flagged −0.35%, against +0.61%.
- **PIV_X:** makes no difference to outcomes (+0.45% against +0.49%).

### Part 3: re-entered backtests

| Version | W1 2019-26 | W2 2008-17 | Trades W1 / W2 | Win % W1 / W2 | Net per trade W1 / W2 | ₹10 L grew to (W1 / W2) |
|---|---|---|---|---|---|---|
| F_REF (pivot buy-stop, Falcon stop/target) | 8.9% (DD −32%) | −1.6% (−48%) | 827 / 913 | 45 / 44 | +0.78 / +0.17% | 19.5 / 8.5 L |
| F_CC (clean close) | 1.2% (−25%) | −2.4% (−39%) | 567 / 602 | 53 / 52 | +0.37 / −0.36% | 11.0 / 7.9 L |
| **F_MOM (top-20% momentum only)** | **11.2% (−22%)** | **2.4% (−27%)** | 505 / 537 | 47 / 45 | +1.68 / +0.31% | 23.0 / 12.6 L |
| F_MOM_CC | 3.2% (−18%) | −0.5% (−16%) | 192 / 194 | 57 / 51 | +1.54 / +0.07% | 12.8 / 9.5 L |
| F_CC_W (3 ATR / 3R) | 2.4% (−34%) | 1.1% (−40%) | 493 / 518 | 42 / 42 | +0.67 / +0.20% | 12.0 / 11.1 L |
| F_MOM_CC_W | 5.1% (−15%) | 1.4% (−24%) | 217 / 224 | 48 / 43 | +2.07 / +1.06% | 14.8 / 11.5 L |
| *FM_C3 (reference)* | *14.5% (−18%)* | *12.7% (−23%)* | 460 / 486 | | | 28.8 / 33.0 L |

**Verdict:** F_MOM_CC_W is far from FM_C3 (5.1% / 1.4% against 14.5% / 12.7%). **My
salvage hypothesis is rejected.** Even with the momentum filter, a confirmed entry and a
wider stop, Falcon's pattern triggers add nothing over FM's simpler trigger. The patterns
themselves are part of the problem.

**Factor by factor:**
- **Momentum filter (REF → MOM):** helps in both decades, +2.3pp in W1 and +4.0pp in W2,
  with smaller drawdowns. It is the single most useful fix.
- **Clean-close entry (REF → CC, and MOM → MOM_CC):** *hurts*, by 3-8pp. Wick fills lose,
  but buying at the close gives up the day-one move that made the closed-above fills
  profitable. It also cuts the trade count by a third or more, because of the volume rule.
- **Wider stop (CC → CC_W, and MOM_CC → MOM_CC_W):** a small help, +1-3pp.

**Contrast with FM:** the clean-close entry *helped* FM. The likely reason is that FM's
3-ATR stop does not widen when the fill is higher, and its trigger is the 20-day high.
This is not tested.
