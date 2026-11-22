# Falcon's Screener quality gate (D/E < 0.33, ROCE > 10%) applied to history — pre-registration

**Status: DRAFT (2026-11-22). Not frozen. No data collected, no test code written. The data route needs IA's decision (see "Data").**

## Question

Live, Falcon only considers stocks that pass its Screener query, `candidate_generation/strategies/Leadership/screen.query`: **debt to equity < 0.33 and return on capital employed > 10%**. These are applied on top of the ethical sector filter. No backtest has applied them, because no history of the figures was available.

**With the sector filter AND this quality gate, what would the paper-trading candidates have returned, and do they still hold up?** This is Part 2 of the ethical-filter work (`docs/ethical_filter_history_preregistration.md`).

## Data

### Source

Screener.in company pages give up to 12 years of **annual** balance sheets and ratios: borrowings, equity capital, reserves, and ROCE %. That reaches back to about FY2015, but **only for companies that are still listed**.

### Coverage

Every stock that was in the monthly top 500 at any month from 2015-09 to 2026-10 and is on Screener today. That is roughly 1,200 companies; the exact count will be recorded.

### Point in time

- Figures for the financial year ending 31 March of year Y are used **from 1 September of year Y**. Annual results are published by about the end of May, with a margin added.
- Until then, the previous year's figures apply.
- No figure is ever used before it was published.
- D/E = borrowings ÷ (equity capital + reserves). ROCE = Screener's ROCE % for that year.
- Banks and NBFCs are already removed by the sector filter.

### Stocks with no figures

These are mostly delisted companies, plus a few that Screener lacks.

- **Primary:** they **pass** the gate. Failing them would quietly remove most companies that later failed, which is survivorship bias and would make the results look better than they were.
- **Reported:** they **fail** (fail-closed, as live).

### Collection route — IA to choose before freeze

| Route | How | Notes |
|---|---|---|
| **(a) Screener exports** | Screener's "Export to Excel" on each company page, run in IA's browser (logged in), about 1,200 pages, slowly paced | Same source as live Falcon. Slow, perhaps several hours. Check that this fits Screener's terms for a personal account. |
| **(b) NSE XBRL filings** | Annual results filed with NSE, downloaded from the laptop | Official, and also covers some delisted companies. Much more parsing work, and older years are patchy. |
| **(c) Narrower test** | Only the stocks the strategies actually bought or would have bought in 2016–2026, a few hundred, via route (a) | Faster. The gate only matters for stocks a strategy would pick, so the result is the same, provided candidates are taken from the unfiltered and filtered runs iteratively until no new names appear. |

## Window

**WQ: 2016-01-01 → 2026-10-30.** This is the period the data covers with a full point-in-time year in hand. W1 (2019-01-01 → 2026-10-30) is reported separately inside it.

## Strategies

- **Judged:** A10, C_F_A and C_F_A_P3 (close fills, the tested versions).
- **Reported:** A10P, C_F_A_O, C_F_A_P3O, FM_C3 and P3.

Each runs **sector filter only** (the existing exclusion list) and **sector filter + quality gate**, in the same script, on `data/pit_v2`. A stock that fails the gate on a month-end is out of the universe for that month, so the strategies take the next eligible stock.

**Reference check first:** the sector-filter-only runs must reproduce `data/ethical_filter_history_result.txt` (`+ETH` blocks) within 0.05pp in W1.

## What counts as "holds up with the full filter" (judged: all stocks, each of A10, C_F_A, C_F_A_P3)

Both conditions must hold:

1. **With the full filter, CAGR beats the Nifty over WQ and over W1.**
2. **The quality gate costs no more than 3.0 percentage points a year over WQ** compared with the sector filter only.

**Reported:**
- CAGR, max drawdown, the six checks;
- how often a top-20 momentum pick failed the gate, by year;
- the missing-data share;
- the fail-closed variant.

## What it means

- A candidate that holds up stays on the paper-trading list, which applies the full filter live.
- A candidate that does not is flagged, and **IA decides** (2026-11-22).
- No rule changes.

## Output

- `data/quality_gate_history_result.txt`
- Runner: `tests/run_quality_gate_history.py`
- Data: `data/fundamentals/screener_annual.parquet` (or the XBRL equivalent), with a collection log
- Dated Results section here; scorecard rows.
