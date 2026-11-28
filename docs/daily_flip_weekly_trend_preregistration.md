# Daily structure flip inside a weekly uptrend — pre-registration

**Status: FROZEN on 2026-11-28 15:11 IST** (by IA; FR kept monthly as drafted)

## Question

IA (2026-11-28), after the weekly-flip trend-filter test (`docs/weekly_flip_trend_filter_preregistration.md`): run the same strategy one timeframe down.
- The stock must be in a **weekly** uptrend.
- Inside it, find a **daily** downtrend.
- Trade the daily flip (first or second) with the same entries and exits.

Daily flips have much nearer higher lows than weekly flips. Does this give tighter stops and still beat the Nifty?

## What changes from the weekly test

Every rule not listed here is as frozen in:
- `docs/structure_flip_preregistration.md`
- `docs/weekly_flip_exits_preregistration.md`
- `docs/weekly_flip_trend_filter_preregistration.md`

| Item | Weekly test | This test (daily) |
|---|---|---|
| Bars for the downtrend, swings, flip and higher lows | weekly | **daily sessions** |
| Swing strength | 2 bars each side | **3 sessions each side** (IA). A swing is confirmed 3 sessions after its bar. |
| Downtrend | two lower highs and two lower lows (weekly) | the same rule on daily swings |
| LL exit | a weekly close below the latest confirmed weekly swing low | **a daily close** below the latest confirmed daily swing low; sold at the next open |
| STR exit | the stop trails 1% under each higher weekly swing low | trails 1% under each higher **daily** swing low |
| Trend filter | monthly uptrend | **weekly uptrend** (below) |

The stop stays 1% below the higher low the entry was based on. Entries (a, b, a2, b2), the R2/R3/H2/H3 exits, sizing (1/20 of equity), 20 slots, the tie-break (largest prior fall first), universe, costs and data are all unchanged.

## Time limits: two versions (IA chose to test both)

| Limit | **C** = same calendar time | **B** = same bar count |
|---|---|---|
| Setup alive / buy-stop cancelled after | 65 sessions (13 weeks) | 13 sessions |
| HL1 must reach the HH2 close within | 130 sessions (26 weeks) | 26 sessions |
| T26 time exit, at the open after | 130 sessions | 26 sessions |

## Weekly-uptrend filters (IA: all three, weekly)

Each filter is evaluated at the last completed week (W-SUN bars) whose final session is on or before the session the daily setup is confirmed (`sig_idx`).

| Code | The stock's weekly trend is "up" when … |
|---|---|
| **FS** (weekly structure) | its last two confirmed weekly swing highs are rising **and** its last two confirmed weekly swing lows are rising. Weekly swings use k = 2, as in the weekly flip. |
| **FR** (momentum rank) | **unchanged from the monthly test:** top 100 of the month's point-in-time universe by A10's 12-1 score. It is evaluated at the last completed **month** on or before `sig_idx`, because the rank is a monthly A10 quantity. |
| **FM** (10-week average) | its weekly close is above the 10-week simple average of weekly closes, **and** that average is above the previous week's |

## Variants

The test has **224 variants** in total.

**Filtered: 168 variants,** named `DF_<filter>_<entry>_<exit>_<C|B>`, for example `DF_FM_b2_LL_C`:
- **Filters:** FS, FR, FM.
- **Entries:** a, b, a2, b2.
- **Exits:** STR, R2, R3, T26, LL, H2, H3.
- **Time versions:** C, B.

**Unfiltered daily flip: 56 variants,** named `DU_<entry>_<exit>_<C|B>`. These are the baseline for condition 4.

**References** (the run stops on any mismatch beyond 0.05pp):
- A10 must reproduce `data/buystop_mix_result.txt`.
- `WF_b_LL` and `WF_b2_LL` (weekly, unchanged code path) must reproduce `data/weekly_flip_exits_result.txt` in every window and sample.

## Runs

- **Windows:** H0 2001–06, W2 2008–17, W1 2019-01-01 → 2026-10-30.
- **Samples:** all stocks, half A and half B. Data `data/pit_v2`, no ethical filter.
- **Reported for every variant:**
  - CAGR, max DD, trades and win rate;
  - the exit mix;
  - the initial-risk distribution (< 5% / 5–10% / ≥ 10%) and the average risk;
  - year-by-year returns (all stocks);
  - signals found and signals kept by each filter.

## Adoption bar

**Judged: 12 primaries,** b and b2 with the LL exit under each filter, in both time versions:
- `DF_FS_b_LL_C`, `DF_FS_b2_LL_C`, `DF_FR_b_LL_C`, `DF_FR_b2_LL_C`, `DF_FM_b_LL_C`, `DF_FM_b2_LL_C`
- the same six with `_B`

`DF_FM_b2_LL_C` and `DF_FM_b2_LL_B` are the daily twins of today's weekly pass (`TF_FM_b2_LL`). They are judged like the others and named first in the verdict.

Each primary must pass all four conditions:
1. **All stocks, W1 and W2:** CAGR at least 3.0 percentage points a year above the Nifty 50's.
2. **Half B, W1 and W2:** CAGR above the Nifty's.
3. **H0 2001–06, all stocks:** CAGR above the Nifty's.
4. **All stocks, W1 and W2:** CAGR at least that of the same entry, exit and time version **without the filter** (`DU_b_LL_C`, `DU_b2_LL_B` and so on).

The verdict states how many of the 12 pass. The other 212 variants are reported only.

A pass means "candidate for paper trading"; IA decides. No re-tuning, no extra variants.

## Output

- `data/daily_flip_weekly_trend_result.txt`
- **Code:** in `backtesting/structure_flip.py`:
  - timeframe `"D"`, with K = 3;
  - optional `expiry`, `hl1_bars` and `time_exit` parameters;
  - `weekly_uptrend(panel, kind)`.
  - Defaults are unchanged, so the weekly and monthly results reproduce exactly.
- **Runner:** `tests/run_daily_flip_weekly_trend.py`. It runs after nothing else is loading a panel.
- A dated Results section here, and scorecard rows.
