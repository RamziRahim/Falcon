# Dynamic capital allocation across the paper-trading tracks — pre-registration

**Status: FROZEN on 2026-11-22 23:55 IST**

Frozen by Claude on IA's explicit authority (IA, 2026-11-22 23:50 IST: "create the spec, start back testing, freeze the code as you think, choose wise decisions as you think, and execute it"). IA chose between nothing here; Claude picked the reading, the variants and the bar below before writing any test code.

## Question

IA (2026-11-22): across the paper-trading tracks, if the low-risk, high-reward ones had been given relatively more capital and the high-risk, low-reward ones relatively less, would returns have been higher?

Reading used: **one pot of money split across the automatic tracks, re-split every month** (IA's option A). Trade-by-trade sizing inside a strategy (option B) is a separate question and is not tested here.

**The split each month uses only what was known at that month's close.** Choosing the tracks from the 25-year results and then backtesting them would be hindsight.

## The tracks (sleeves)

The ten automatic tracks of `docs/paper_trading_plan.md`, built exactly as in their own frozen tests:

| Sleeve | Build |
|---|---|
| A10 | `run_momentum(stop_pct=0.10)` |
| A10C | the same with `skip_after_stop=True` |
| A10P | `add_frac=0.5`, `add_level` = weekly S1 |
| M_SEC | `allowed=sector_strong(...)` |
| A10_70 | 70% size: `gauge_up` all false, `down_level=0.7` |
| C_F_A | FM_C3 + A10 via `combine(..., "FA", True)` |
| C_F_A_O | FM at the next open + A10 |
| C_F_A_H | FM on the 20-day-high buy-stop + A10 |
| C_F_A_P3 | FM_C3 + A10 + P3 (close entry), `"FAP"` |
| C_F_A_P3O | FM next open + A10 + P3 next open, `"FAP"` |

Track 8 (IA's manual trades) has no history and is left out.

Each sleeve runs on the full capital over the window. A sleeve's return does not depend on its size (apart from rounding to whole shares), so the portfolio is built from the sleeves' daily equity curves.

## Allocation rules

- **Rebalance:** at the close of the last session of each month. New weights apply from the next session. Between rebalances, holdings drift with each sleeve.
- **Rebalancing cost:** 0.25% of every rupee moved between sleeves (Σ |change in rupees| × 0.0025). This covers selling in one sleeve and buying in another.
- **Look-back:** each sleeve's own equity curve over the last 252 sessions up to the rebalance close. With fewer than 126 sessions of history (the start of a window), every variant uses equal weights.
- **Score ("reward per unit of risk"):** score = max(look-back return, 0) ÷ max(look-back max drawdown, 5%).

### Variants

- **EW (baseline):** 10% in each sleeve, reset to 10% every month.
- **DA_RR (primary):** half equal weight, half in proportion to the score.
  - Formula: w = 0.5 × (1/10) + 0.5 × score ÷ Σ score.
  - If every score is 0, it falls back to EW.
  - This is IA's idea, "relatively higher" and "relatively lower" rather than all-or-nothing.
- **DA_IV (reported):** in proportion to 1 ÷ (standard deviation of daily returns over the look-back). Risk only, no reward.
- **DA_TOP3 (reported):** a third each in the three highest scores. If every score is 0, it falls back to EW.
- **A10 alone (reported):** the single best-known track, for comparison.

## Runs

- **Data:** `data/pit_v2`, no ethical filter, so the sleeves reproduce stored results.
- **Windows:**
  - W2: 2008-01-01 → 2017-12-31 (judged)
  - W1: 2019-01-01 → 2026-10-30 (judged)
  - H0: 2001-01-01 → 2006-12-31 (reported)
- **Samples:** all stocks (judged), half A and half B (reported).
- **Reference check:** before any allocation is computed, A10, C_F_A, C_F_A_O and C_F_A_H on all stocks must reproduce `data/buystop_mix_result.txt` within 0.05pp (CAGR and max DD) in every window. If any does not, the run stops and nothing is judged.
- **Reported:** CAGR, max drawdown, final value of ₹10 lakh, yearly rebalancing turnover, and each sleeve's average weight.

## What counts as "dynamic allocation helps" (judged: DA_RR vs EW, all stocks)

Both conditions must hold, in **both** W1 and W2:

1. **DA_RR's CAGR is at least 1.0 percentage point a year above EW's.**
2. **DA_RR's max drawdown is no more than 2.0 points deeper than EW's.**

Otherwise the verdict is **DOES NOT HELP**.

## What it means

- **If it helps:** IA may consider allocating real capital across the tracks this way once paper trading has run. Nothing in the frozen paper-trading plan changes; every track keeps running on its own capital.
- **If it does not:** equal capital per track stays the default. The verdict flags; IA decides.
- No strategy rules change. No re-tuning, no extra variants.

## Output

- `data/dynamic_allocation_result.txt`
- Runner: `tests/run_dynamic_allocation.py`
- Dated Results section here; scorecard rows.

## Results (2026-11-23, run once after freeze)

**References.** Passed: A10, C_F_A, C_F_A_O and C_F_A_H on all stocks reproduced `data/buystop_mix_result.txt` exactly in H0, W2 and W1. Output: `data/dynamic_allocation_result.txt`.

**Verdict (DA_RR vs EW, all stocks): DOES NOT HELP.**
- W2: DA_RR returned **0.97 points a year less** than EW (11.26% vs 12.23%), with the same max drawdown (−42.4%).
- W1: DA_RR returned **1.21 points a year less** (20.49% vs 21.70%), and its drawdown was 2.14 points deeper (−31.0% vs −28.8%).
- It needed +1.0 point in both windows.

**One pot of ₹10 lakh across the ten tracks: CAGR % (max DD %)**

| Split | H0 2001–06 | W2 2008–17 | W1 2019–26 | Money moved per year |
|---|---|---|---|---|
| **EW: equal, reset monthly** | **31.91 (−29.8)** | **12.23 (−42.4)** | **21.70 (−28.8)** | 0.15–0.21× |
| DA_RR: half equal, half by reward-per-risk (judged) | 31.41 (−29.9) | 11.26 (−42.4) | 20.49 (−31.0) | 1.0–1.7× |
| DA_IV: less to the more volatile tracks | 31.08 (−28.8) | 11.89 (−40.6) | 20.85 (−28.2) | 0.23–0.27× |
| DA_TOP3: all in the 3 best recent tracks | 29.13 (−33.0) | 9.54 (−42.4) | 20.41 (−35.0) | 3.1–5.9× |
| A10 alone (for comparison) | 37.52 (−38.0) | 13.17 (−59.0) | 26.36 (−39.4) | — |

The halves agree: every dynamic split is below EW in W2 and W1 on half A and on half B.

W2's worst fall (2008) came inside the first 126 sessions, when every split is equal by rule. That is why EW, DA_RR and DA_TOP3 share the same W2 max drawdown.

**What it means, in plain English:**
- Moving more money each month into the tracks that had the best reward for their risk over the past year did **not** raise returns. It lowered them by about 1 point a year in both decades, and the more aggressively it chased (top 3), the worse it did.
- The tracks are close cousins: most hold A10's stocks. So the one that led last year is usually not the one that leads next year by enough to pay for the switching.
- Shifting money away from the jumpier tracks (DA_IV) gave slightly smaller drawdowns, but also slightly lower returns. That is not enough to be worth it.
- An **equal split** across the tracks is the better simple rule.
- A10 on its own still has the highest return, with much deeper drops (−59% in 2008–17 against −42% for the equal split).
- Nothing changes in paper trading: each track keeps its own capital, as frozen. IA decides.
