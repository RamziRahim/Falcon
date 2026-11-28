# Weekly structure flip inside a monthly uptrend — pre-registration

**Status: FROZEN on 2026-11-28 12:17 IST**

## Question

IA (2026-11-28): the weekly flip had no trend filter; about half its flips failed within two weeks (`docs/weekly_flip_exits_preregistration.md`). Take weekly flips only when the stock's **monthly** trend is up, so that the weekly downtrend is a pullback inside a bigger uptrend. Does that remove false flips and give better entries, for the first flip and the second flip?

## What changes

**Only one thing:** a filter on which setups may trade. Entries, stops, exits, portfolio, universe, costs, slots and tie-break are exactly as frozen in `docs/weekly_flip_exits_preregistration.md` and `docs/structure_flip_preregistration.md`. The setup itself already requires a weekly downtrend (two lower highs and two lower lows) before the flip.

## Monthly-uptrend filters

Each filter is evaluated at the last completed calendar month whose final session is on or before the session the setup is confirmed (its `sig_idx`). Nothing uses a month that has not closed.

| Code | The stock's monthly trend is "up" when … |
|---|---|
| **FS** (monthly structure) | Its last two confirmed monthly swing highs are rising **and** its last two confirmed monthly swing lows are rising. Swings are monthly bars with k = 1, confirmed one month later, as in the monthly flip. |
| **FR** (momentum rank) | It is in the top 100 of that month's point-in-time universe by A10's 12-1 score: close 21 sessions back ÷ close 252 sessions back − 1, at the month's last session. |
| **FM** (10-month average) | Its monthly close is above the 10-month simple average of monthly closes, **and** that average is above the previous month's. |

## Variants

3 filters × 4 entries × 7 exits = **84 variants**, named `TF_<filter>_<entry>_<exit>`, for example `TF_FS_b2_LL`.
- **Entries:** a, b, a2, b2.
- **Exits:** STR, R2, R3, T26, LL, H2, H3.

**References:**
- A10 must reproduce `data/buystop_mix_result.txt`.
- The unfiltered `WF_<entry>_<exit>` must reproduce `data/weekly_flip_exits_result.txt` within 0.05pp in every window and sample.
- If either does not, the run stops.

## Runs

- **Windows:** H0 2001–06, W2 2008–17, W1 2019-01-01 → 2026-10-30.
- **Samples:** all stocks, half A and half B. Data `data/pit_v2`, no ethical filter.
- **Reported for every variant:**
  - CAGR, max DD, trades, win rate;
  - share of exits at the original stop;
  - the initial-risk distribution (< 5% / 5–10% / ≥ 10%);
  - year-by-year returns (all stocks);
  - signals kept by each filter.

## Adoption bar

**Judged: six primaries**, the two best entry/exit pairs of the unfiltered test under each filter:
- `TF_FS_b_LL`, `TF_FS_b2_LL`
- `TF_FR_b_LL`, `TF_FR_b2_LL`
- `TF_FM_b_LL`, `TF_FM_b2_LL`

Each must pass all four conditions:

1. **All stocks, W1 and W2:** CAGR at least 3.0 percentage points a year above the Nifty 50's.
2. **Half B, W1 and W2:** CAGR above the Nifty's.
3. **H0 2001–06, all stocks:** CAGR above the Nifty's.
4. **All stocks, W1 and W2:** CAGR at least that of the **same entry and exit without the filter** (`WF_b_LL` or `WF_b2_LL`). The filter must help, not just pass.

The verdict states how many of the six pass. The other 78 variants are reported only.

A pass means "candidate for paper trading" — IA decides. No re-tuning, no extra variants.

## Output

- `data/weekly_flip_trend_filter_result.txt`
- Code: `backtesting/structure_flip.py` gains `monthly_uptrend(panel, kind)` and a filter helper. Defaults are unchanged.
- Runner: `tests/run_weekly_flip_trend_filter.py`
- Dated Results section here; scorecard rows.

## Results (2026-11-28, run as frozen)

Full output: `data/weekly_flip_trend_filter_result.txt`. A10 reproduced `data/buystop_mix_result.txt`. All 28 unfiltered `WF_*` variants reproduced `data/weekly_flip_exits_result.txt` in every window and sample. There were 261 reference checks and 0 mismatches.

**Signals kept by each filter** (all stocks, all history):

| Filter | First flip | Second flip |
|---|---|---|
| FS monthly structure | 3,922 of 13,955 (28.1%) | 2,719 of 5,776 (47.1%) |
| FR top-100 momentum | 1,200 (8.6%) | 847 (14.7%) |
| FM rising 10-month average | 7,314 (52.4%) | 4,851 (84.0%) |

**Verdict: 1 of 6 primaries passes.** Nifty CAGR is H0 21.19, W2 5.54 and W1 10.03. Each cell below is CAGR %.

| Primary | ALL W2 | ALL W1 | B W2 | B W1 | ALL H0 | vs unfiltered (W2 / W1) | Result |
|---|---|---|---|---|---|---|---|
| TF_FS_b_LL | 11.81 | 13.17 | **4.19** | 11.12 | 26.32 | **11.81 < 17.21** / 13.17 ≥ 12.45 | FAILS |
| TF_FS_b2_LL | 10.65 | **9.63** | **4.55** | **4.90** | 23.53 | **10.65 < 12.05** / **9.63 < 16.98** | FAILS |
| TF_FR_b_LL | 17.25 | **12.07** | 13.39 | 14.45 | 31.49 | 17.25 ≥ 17.21 / **12.07 < 12.45** | FAILS |
| TF_FR_b2_LL | 12.23 | 16.13 | 8.97 | 15.84 | 30.46 | 12.23 ≥ 12.05 / **16.13 < 16.98** | FAILS |
| TF_FM_b_LL | 10.95 | **8.16** | 10.04 | 16.86 | 28.71 | **10.95 < 17.21** / **8.16 < 12.45** | FAILS |
| **TF_FM_b2_LL** | 13.76 | 20.16 | 7.98 | 18.07 | 32.98 | 13.76 ≥ 12.05 / 20.16 ≥ 16.98 | **PASSES** |

Bold marks a failed condition.

**TF_FM_b2_LL** (second-flip breakout, weekly lower-low exit, monthly close above a rising 10-month average):
- **Max drawdown, all stocks:** H0 −31.2%, W2 −28.9%, W1 −31.7%.
- **Trades, all stocks:** H0 118, W2 228, W1 249.
- **Win rate, all stocks:** H0 48%, W2 46%, W1 39%.
- **Average initial risk to the stop:** 24% in H0, 19% in W2, 18% in W1. Under 5% of risk: 0% of entries. Under 10%: 3–12% of entries.

Recorded for IA's decision; none of this changes the verdict:
- **Half A 2019–26 is weak.** TF_FM_b2_LL made 9.58%, below the Nifty's 10.03. Half A is not part of the bar.
- **All stocks beats both halves in 2019–26.** ALL made 20.16 against A 9.58 and B 18.07. Some of the gain comes from which setups win the 20 slots when the whole universe competes, not from the filter alone.
- **The stops are still very wide.** The filter does not narrow them. This is the same practical concern as the unfiltered weekly flip (17–29% below the buy price).

Per the pre-registration, a pass means "candidate for paper trading"; IA decides.
