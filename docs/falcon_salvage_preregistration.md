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
