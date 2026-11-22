# Falcon's ethical sector filter applied to 25 years of history — pre-registration

**Status: FROZEN on 2026-11-22 12:07 IST**
(The exclusion list in `data/pit_v2/ethical_exclusions.csv`, copied to `docs/paper_trading/ethical_exclusions_history.csv` for review, is classification data, built and reviewed before freeze; no returns were computed with it.)

## Question

Every backtest so far ignored Falcon's ethical rules, which are applied only live. This test asks: **if the shortlisted strategies could never have held financial-services, alcohol or tobacco stocks, what would they have returned from 2001 to 2026, and do they still hold up?**

This is Part 1 of the filter. **The debt-to-equity < 0.33 rule is NOT applied**, because no point-in-time balance-sheet history exists for 2001–2014 or for delisted companies. Part 2 (D/E from about 2014, from Screener exports) would be a separate pre-registration.

## The filter (frozen with this doc)

`tests/build_ethical_exclusions.py` → `data/pit_v2/ethical_exclusions.csv`.

It covers every stock that was ever in the monthly top 500 of `data/pit_v2` (2,047 stocks). For each stock, the first rule that matches decides:

1. **Excluded on a fixed list.** Its ticker is in `config.EXCLUDED_TICKERS` (Falcon's live alcohol list), or in the hand-reviewed list in the script. That list has 7 stocks found during review: McDowell, an earlier Radico listing, Jagatjit, VST Industries, Northern Arc, Kissht and the Morgan Stanley Growth Fund.
2. **Classified by Falcon's live sector source** (`data/sector_map.json`, Yahoo, 552 stocks):
   - Excluded if its sector is in `config.EXCLUDED_SECTORS` (Financial Services).
   - Excluded if its industry contains one of `config.FAIL_INDUSTRY_KEYWORDS` (bank, insurance, credit services, mortgage, consumer finance, tobacco, wineries, distilleries).
   - Otherwise kept.
3. **Excluded by company name.** The name comes from the NSE corporate-action records and matches a whole-word pattern in `NAME_RULES` (e.g. bank, finance, financial, insurance, credit, leasing, securities, stock brokers, asset management, investments limited, brewery, distillery, spirits, wine, tobacco, cigarette). One stock was reviewed and kept despite a match: Network18 Media & Investments.
4. **Otherwise kept.** This includes 55 stocks with no name record, almost all listed in 2024–26.

**Result:** 210 stocks are excluded (189 financial, 17 alcohol, 4 tobacco). That is 10% of the top-500 member-months in 2001, 13% in 2008, 15% in 2012, 17% in 2020 and 19% in 2026. The excluded stocks include ITC, Godfrey Phillips, HDFC, every bank, NBFC, insurer and exchange in the Yahoo Financial Services sector, United Spirits, United Breweries and Radico.

**How it is applied:**
- Excluded stocks are removed from the monthly universe for the whole history, so every strategy behaves as if they never existed. Monthly momentum takes the next-ranked eligible stock.
- v3 pattern setups on excluded stocks are dropped.
- The equal-weight benchmark is computed on the filtered universe.

**Known limits, accepted before running:**
- Classifications are today's, applied backwards. A company that changed business, such as a former NBFC, is classed by what it is now.
- Name rules can miss or over-catch a few small names.
- Live, Falcon also excludes by Yahoo's business-summary keywords (`SUMMARY_KEYWORDS`). That is not reproducible for delisted companies and is not applied here.

## Data and windows

- **Data:** `data/pit_v2` (2000 → 2026-11-20), which passed the data gate in `docs/history_2001_2006_preregistration.md`. Costs, fills and the six checks (`judge()`) are unchanged. The benchmark is the Nifty 50 from `data/pit_sources/indices_2000_2026.parquet`.
- **Windows:**
  - H0: 2001-01-01 → 2006-12-31
  - W2: 2008-01-01 → 2017-12-31
  - Y2018: 2018
  - W1: 2019-01-01 → 2026-10-30
  - **L25** (reported, not judged per window): one continuous run, 2001-01-01 → 2026-10-30
- **Pattern setups:**
  - H0 uses `data/pit_v2/falcon_setups_v3_2001-01-01_2006-12-31.parquet`.
  - W2, Y2018 and W1 use the existing `data/pit/falcon_setups_v3_<span>.parquet` files.
  - L25 uses one new v3 scan of 2001-01-01 → 2026-10-30 on `data/pit_v2`, every 5th session; it is the only new input.
- **Samples:** all stocks (judged); half A and half B (reported). Stocks not in `data/holdout_split.csv` use its own rule (SHA-256 of entity_id, even → A).

## Strategies (no rule changes)

- **Judged:** A10, C_F_A and C_F_A_P3.
- **Reported:** A10C, FM_C3 and P3.

Each runs twice in every window and sample: **unfiltered** and **filtered**. Both runs use the same code and data, so the difference is the filter alone.

**Reference check, before any filtered run:**
- On all stocks, the unfiltered runs on `pit_v2` must reproduce the stored results within 0.50pp of CAGR and max drawdown:
  - A10 against `data/a_stop_result.txt` (W1, W2, Y2018);
  - C_F_A, C_F_A_P3, FM_C3 and P3 against `data/momentum_patterns_result.txt`;
  - all six against `data/history_2001_2006_result.txt` (H0).
- If any reference misses, stop and report to IA before running anything filtered.

## What counts as "holds up with the filter" (judged: all stocks, each of A10, C_F_A, C_F_A_P3)

Both conditions must hold:

1. **Filtered CAGR beats the Nifty in each of H0, W2 and W1.** Y2018 is reported only; no strategy beat the Nifty in 2018 unfiltered.
2. **The filter costs no more than 3.0 percentage points a year over L25:** filtered CAGR ≥ unfiltered CAGR − 3.0pp over 2001–2026.

**Reported for every strategy:**
- CAGR, max drawdown, the six checks, win rate, trades and ₹10 lakh grown, filtered vs unfiltered, in every window;
- L25 totals and drawdowns;
- the halves;
- the 2008 and 2020 crash drawdowns within L25;
- how often an excluded stock would have been in the A10 top 20 (unfiltered) per year.

**What it means:**
- A candidate that holds up stays on the paper-trading list. Paper trading always applies the filter.
- A candidate that does not hold up is flagged. **IA decides whether it comes off the paper-trading list** (IA, 2026-11-22); the verdict itself does not remove it.
- No strategy rule changes either way. If the filter is costly, that is a finding about Falcon's constraints, not a reason to retune.

## Output

- `data/ethical_filter_history_result.txt`
- Runner: `tests/run_ethical_filter_history.py`
- Dated Results section in this doc; rows in `docs/falcon_backtest_scorecard.csv`/`.md`.

## Results (2026-11-22, run once after freeze)

**Reference check.** It passed on all stocks: every unfiltered run on `pit_v2` reproduced the stored results within 0.50pp, so the filtered runs went ahead. The checks covered W1, W2 and Y2018 (A10, C_F_A, C_F_A_P3, FM_C3, P3) and H0 (all six). W1, Y2018 and H0 matched exactly. W2 C_F_A, C_F_A_P3 and FM_C3 were within 0.29pp of CAGR and 0.44pp of drawdown; those small gaps come from the few entity ids that differ between `pit` and `pit_v2`.

Inputs: L25 v3 scan, 13,519 setups (`data/pit_v2/falcon_setups_v3_2001-01-01_2026-10-30.parquet`). Output: `data/ethical_filter_history_result.txt`.

**Verdict (mechanical; all stocks):**

| Strategy | Beats Nifty filtered: H0 / W2 / W1 | L25 cost of the filter | Verdict |
|---|---|---|---|
| **A10** | yes / yes / yes | −1.39pp (filter **helped**) | **HOLDS UP WITH THE FILTER** |
| **C_F_A** | yes / yes / yes | +0.47pp | **HOLDS UP WITH THE FILTER** |
| **C_F_A_P3** | yes / yes / yes | +0.36pp | **HOLDS UP WITH THE FILTER** |

**Twenty-five years, 2001-01-01 → 2026-10-30, all stocks, unfiltered → filtered.** The Nifty 50 returned 11.93% a year (₹10 lakh → about ₹1.8 crore, price index only).

| Strategy | CAGR | Max drawdown | Checks (filtered) | ₹10 lakh grew to (filtered) |
|---|---|---|---|---|
| A10 | 20.70% → **22.09%** | −68.0% → −65.4% | 6/6 | ₹12.9 cr → **₹17.3 cr** |
| A10C (reported) | 21.46% → 22.12% | −61.6% → −62.2% | 6/6 | ₹15.2 cr → ₹17.4 cr |
| C_F_A | 18.78% → **18.31%** | −46.9% → −45.1% | 5/6 | ₹8.5 cr → **₹7.7 cr** |
| C_F_A_P3 | 15.18% → **14.82%** | −36.0% → −33.9% | 4/6 | ₹3.8 cr → **₹3.6 cr** |
| FM_C3 (reported) | 15.39% → 13.16% | −27.1% → −34.7% | 3/6 | ₹4.0 cr → ₹2.4 cr |
| P3 (reported) | 7.28% → 7.11% | −25.2% → −22.8% | 3/6 | ₹0.6 cr → ₹0.6 cr |

**By window, all stocks, CAGR unfiltered → filtered:**

| Strategy | H0 2001–06 | W2 2008–17 | Y2018 | W1 2019–26 |
|---|---|---|---|---|
| Nifty | 21.19% | 5.54% | 4.11% | 10.03% |
| A10 | 37.52 → 37.42 | 13.17 → 14.94 | −38.88 → −36.02 | 26.36 → 28.76 |
| C_F_A | 35.56 → 32.59 | 13.46 → 12.09 | −26.85 → −25.49 | 19.49 → 21.16 |
| C_F_A_P3 | 27.59 → 25.61 | 11.75 → 10.32 | −23.41 → −20.92 | 18.35 → 19.80 |
| FM_C3 | 31.03 → 25.52 | 12.56 → 8.06 | −13.39 → −14.09 | 11.71 → 12.74 |

**Halves, L25 CAGR unfiltered → filtered:**

| Strategy | Half A | Half B |
|---|---|---|
| A10 | 16.63 → 18.70 | 18.45 → 19.15 |
| C_F_A | 15.44 → 16.08 | 16.43 → 14.85 |
| C_F_A_P3 | 12.15 → 12.03 | 13.68 → 12.90 |

One weak spot: on half B in W1, FM_C3 filtered fell to 1.23% (8.40% unfiltered), pulling C_F_A to 13.42% (16.13%).

**Crash drawdowns within L25** (lowest equity in the window against the highest equity before it), unfiltered → filtered:

| Strategy | 2008-01 → 2009-03 | 2020-02 → 2020-04 |
|---|---|---|
| A10 | −68.0 → −65.4 | −57.0 → −54.6 |
| C_F_A | −46.9 → −45.1 | −41.7 → −40.8 |
| C_F_A_P3 | −36.0 → −33.9 | −32.1 → −33.9 |

The 2020 figures include the 2018 losses that had not been recovered.

**How often A10 (unfiltered) held an excluded stock.** On average 0.2–4.7 of its 20 names, by year. It was highest in 2001 (3.4), 2019 (3.9), 2023 (3.7) and 2024 (4.7).

**What it means:**

1. **The ethical filter does not cost the strategies their edge.** All three candidates hold up. Over 25 years the filter cost the mixes about half a point a year, and monthly momentum on its own did 1.4 points a year better with the filter than without.
2. **Why momentum gains:** financial stocks that ranked high on momentum (2019, 2023–24 especially) were mostly replaced by other strong stocks that did as well or better. This is one sample of history, not a reason to expect the filter to add return.
3. **Falcon Momentum (the FM sleeve) is the part the filter hurts.** It made 2.2 points a year less over 25 years and fell further at worst (−34.7% vs −27.1%), probably because bank and finance setups were a large share of its trades. Since C_F_A is half FM, its cost comes from there. The weak half-B 2019–26 number above is the same effect.
4. **Drawdowns remain the real problem, filter or not.** Monthly momentum fell about two thirds in 2008. The three-way split is the smoothest at about one third.
5. **No rule changes and no list changes follow from this.** All three stay on the paper-trading list, which will always run with the filter.
