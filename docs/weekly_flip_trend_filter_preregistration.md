# Weekly structure flip inside a monthly uptrend — pre-registration

**Status: DRAFT — awaiting IA's freeze**

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
