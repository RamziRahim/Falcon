# Pre-registration: the shortlisted strategies on 2001-2006 (new, unseen history)

**Status: FROZEN on 2026-11-22 10:27 IST**

## Why

Every period from 2007 to 2026 has been used to make decisions. On 2026-11-21 Falcon
downloaded NSE bhavcopies for 2000-2006 (`tools/download_nse_history.bat`) and rebuilt the
point-in-time dataset from 2000 (`tests/build_pit_v2.py` -> `data/pit_v2/`). 2001-2006 (the
2001 slump after the dot-com bust, the 2003-2006 bull market and the May 2006 crash) has
never been used for any Falcon decision, so it is the only clean out-of-sample test the
survivors can still get before paper trading.

## Data and its known weakness

- Prices: `data/pit_v2/prices_adjusted.parquet` and `universe_monthly.parquet`, built with
  the same rules as `data/pit/` (`market_data/pit_universe.py`).
- NSE's corporate-action records before 2006 contain almost no splits or bonuses (3 in
  2000-2004, against 60-140 a year from 2006). Unrecorded splits are inferred from
  standard-ratio price gaps for stocks in the universe, as for later years.
- Benchmark and filters: `data/pit_sources/indices_2000_2026.parquet` (Nifty 50 and sector
  indices; a sector index that does not exist yet on a date is treated as missing, as in
  later years).

### Data-quality gate (checked before any strategy is run)

1. **Consistency:** on `data/pit_v2`, A10 on all stocks for W1 (2019-2026) and W2
   (2008-2017) must be within 0.50pp of CAGR and max drawdown of the stored results in
   `data/a_stop_result.txt`. (The wider tolerance allows for entity-linking changes from the
   newer symbol-change list; anything larger means the rebuild differs and the test stops.)
2. **Cleanliness:** the number of one-day moves larger than 40% while a stock is in the
   universe (`data/pit_v2/big_moves_in_universe.csv`), per year, averaged over 2001-2005,
   must be no more than twice the average over 2008-2015. If it is higher, the 2001-2006
   result is reported as unreliable and no conclusion is drawn from it.

## Window and samples

- **H0:** 2001-01-01 → 2006-12-31 (2000 is used only as history for 12-month momentum and
  200-day averages). Nifty 50 over H0 is reported with the result.
- Samples: all stocks (primary), and half A and half B (reported; stocks first listed after
  the split was made are assigned by the same SHA-256 hash rule as `data/holdout_split.csv`).
- Same six checks, costs and fills as every earlier test; `PYTHONHASHSEED=0`.

## Strategies (all as already specified; nothing re-tuned)

| Code | What | Source of rules |
|---|---|---|
| **A10** | monthly momentum, top 20, 10% stop | `run_momentum(stop_pct=0.10)` |
| **C_F_A** | half A10, half Falcon Momentum clean close, monthly reset | `docs/portfolio_combo_preregistration.md`, `combine()` |
| **C_F_A_P3** | a third each of A10, FM_C3 and v3 patterns (P3) | `docs/momentum_patterns_preregistration.md` |
| A10C | A10 without re-buying a stopped stock that month (the paper-trading shadow) | `docs/a_exposure_preregistration.md` (reported version) |
| FM_C3, P3 | the sleeves on their own | reported |

P3 needs the v3 pattern scan for 2000-2006 (`tests/scan_falcon_setups_v3.py` on the v2 data).

## What counts as holding up (each strategy judged on its own, all stocks)

A strategy **holds up** on 2001-2006 if both:
1. its CAGR is above the Nifty 50's over H0, and
2. it passes at least 4 of the 6 checks.

Reported for each: CAGR, max drawdown, the six checks, 2006 crash drawdown (May-June 2006),
win rate, trades, and the result on each half.

## What the outcome would mean

- A strategy that holds up stays on the paper-trading list.
- A strategy that does not hold up stays on the list only if IA decides so explicitly, with
  the 2001-2006 result recorded next to it.
- Nothing about any strategy's rules changes because of this test.

## Expected, stated before the run

2003-2006 was one of the strongest Indian bull markets, so the Nifty itself returned a lot;
beating it is a real test. Momentum strategies should beat it, with a deep drawdown in May
2006. FM and P3 depend on sector indices, several of which start later, which may weaken FM
in the early years.

## Output

`data/history_2001_2006_result.txt`, runner `tests/run_history_2001_2006.py`.

## Data check on the rebuilt data (2026-11-21, before freeze; no strategy run)

Rebuilt data/pit_v2 (2000-01-03 → 2026-11-20): 10.1M bhavcopy rows, 5,179 entities, 1,762 adjustments (177 inferred), 317 monthly universes (2000-07 → 2026-11).

- **Consistency with data/pit (2007 → 2026-10-30):** 99.92% of price rows are identical. The differences come from 9 entities: six split/bonus ex-dates on 4–16 Nov 2026 and one on 23 Oct 2026, now applied backwards, plus three small old fixes. 99.97% of monthly-universe rows match with the same rank.
- **Gate part 2 (big moves):** **fails as built.** The one-day moves over 40% inside the universe average 23.2 a year in 2001–05 (31, 11, 10, 27, 37), against 3.75 a year in 2008–15, which is 6.2×; the limit is 2×. 74 of the 116 sit at standard split/bonus ratios (e.g. ITC 21 Sep 2005, HDFC 12 Dec 2002). Inference missed them because the ex-day open was 2–10% away from the ratio, while the build accepts only 2%.
- **Measured, not applied:** an opening-gap tolerance of 10% for ex-dates before 2006-01-01 (2% unchanged afterwards) leaves 5.4 a year in 2001–05 against 3.6 a year in 2008–15, which is 1.5× and would pass. What remains is mostly genuine 2001 small-cap jumps. This is a change of data method, so it awaits IA's decision.
- Gate part 1 (A10 reproduces W1/W2 within 0.50pp) has not been run yet.

### Rebuild with the 10% pre-2006 tolerance (2026-11-21, IA: "Apply the fix")

- Adjustments went from 1,762 to 2,065. Inferred splits went from 177 to 480 (457 before 2006).
- **Gate part 1 passes:** A10 on pit_v2 gives W1 26.36% (reference 26.36%) and W2 13.17% (reference 13.16%); tests/check_pit_v2_gate.py. Data from 2006 on is unchanged.
- **Gate part 2 still fails.** The yearly counts for 2001–05 are 39, 1, 1, 6 and 2, an average of 9.8 a year, against 3.75 for 2008–15: 2.6×. 2002–05 alone is fine. In 2001 the count rose from 31 to 39.
- **Cause:** 133 of the 457 early inferences are false. The open printed near a split ratio, but the close did not confirm it, so the day was an ordinary one. Each false inference creates an artificial jump in the adjusted series, typically +50% at the 2/3 ratio. 24 of the 49 big moves in 2001–05 are these artefacts. Removing them leaves 25, i.e. 5.0 a year, 1.3×.
- **Proposed refinement (code ready, not yet built):** before 2006, the close-to-close ratio must also lie within 15% of the ratio (`early_close_tolerance=0.15`). Awaits IA's decision.

### Rebuild with close confirmation (2026-11-21, IA: "go") — data gate PASSES

The build now uses `early_tolerance=0.10` and `early_close_tolerance=0.15` (before 2006 only). It has 1,932 adjustments, 347 of them inferred.

- **Gate part 1, PASS:** A10 W1 26.36% (reference 26.36%), W2 13.17% (reference 13.16%).
- **Gate part 2, PASS:** the yearly counts for 2001–05 are 17, 2, 1, 7 and 4, an average of 6.2 a year, against 3.75 for 2008–15: 1.65× (limit 2×). 14 of the 17 in 2001 are up-moves, mostly in stocks priced under ₹10.

This is the data the 2001–2006 run will use, once the doc is frozen.

## Results (2026-11-22, run once after freeze)

**Data gate.** Part 1 passes: A10 on pit_v2 gives W1 26.36% / −39.44% and W2 13.17% / −59.05%, matching the stored 26.36% / −39.44% and 13.16% / −59.05%. Part 2 passes at 1.65×, as recorded above.

**Inputs.**
- v3 scan of 2001–06 on pit_v2: 1,913 setups (`data/pit_v2/falcon_setups_v3_2001-01-01_2006-12-31.parquet`).
- Sector indices that existed at the start of H0: Bank, Energy, FMCG, IT and Pharma.
- Output in `data/history_2001_2006_result.txt` (runner `tests/run_history_2001_2006.py`).
- Stocks not in `data/holdout_split.csv` were assigned to a half by its own rule (SHA-256 of entity_id, even → A), which reproduces all 1,622 stored assignments.

**Over H0 the Nifty 50 returned 21.19% a year** (max drawdown −39.7%; −29.9% in May–June 2006). Owning every universe stock equally returned 34.8% a year.

| Strategy (all stocks) | CAGR | Max DD | Checks | May–Jun 2006 | Half A | Half B | Verdict |
|---|---|---|---|---|---|---|---|
| **A10** | 37.52% | −38.04% | 4/6 | −26.83% | 23.87% | 32.12% | **HOLDS UP** |
| **C_F_A** | 35.56% | −24.58% | 5/6 | −18.31% | 20.51% | 28.89% | **HOLDS UP** |
| **C_F_A_P3** | 27.59% | −20.87% | 4/6 | −13.89% | 16.77% | 21.96% | **HOLDS UP** |
| A10C (reported) | 37.41% | −38.08% | 4/6 | −23.54% | 20.88% | 30.23% | — |
| FM_C3 (reported) | 31.03% | −14.19% | 4/6 | −13.30% | 15.20% | 23.74% | — |
| P3 (reported) | 11.66% | −15.04% | 2/6 | −7.17% | 8.49% | 7.76% | — |

May–Jun 2006 is the lowest equity in May–June 2006 against the highest equity before it.

**Failed checks (all stocks).**
- A10: monthly excess t (NW3 1.70) and top-3 profit share (0.56).
- C_F_A: monthly excess t only (1.68).
- C_F_A_P3: monthly excess t (0.85) and "beats the equal-weight universe" (27.6% vs 34.8%).

**What it means.** All three paper-trading candidates hold up on six years of history that no decision ever used, by the frozen rule. No rules change. The plain-English points:

1. **The margin over the Nifty is large, but 2003–06 lifted almost every stock.** Owning everything equally made 34.8%. A10 beat that by only 2.7 points a year. C_F_A beat it by less than a point, and C_F_A_P3 trailed it. None of the three shows statistically strong excess returns in this window (t below 2).
2. **A10's result leans on a few big winners.** The top three positions made 56% of the profit, and on half A alone it made 23.9% a year, below the equal-weight universe.
3. **The mixes did what they were built to do.** C_F_A kept about the same return with a much smaller drawdown (−24.6% vs −38.0%) and the smallest May 2006 crash loss of the two momentum-led strategies. It beat the Nifty in all 6 years. C_F_A_P3 had the shallowest drawdown of the three.
4. **P3 on its own lagged the Nifty badly** (11.7%), the same picture as in 2008–2026.
5. **A10C ≈ A10** (37.41% vs 37.52%), so skipping re-buys after a stop changed little.
