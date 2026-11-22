# Falcon's ethical sector filter applied to 25 years of history — pre-registration

**Status: DRAFT (2026-11-22). Not frozen. No test code written.**
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
- A candidate that does not hold up comes off the list, unless IA explicitly decides to keep it.
- No strategy rule changes either way. If the filter is costly, that is a finding about Falcon's constraints, not a reason to retune.

## Output

- `data/ethical_filter_history_result.txt`
- Runner: `tests/run_ethical_filter_history.py`
- Dated Results section in this doc; rows in `docs/falcon_backtest_scorecard.csv`/`.md`.
