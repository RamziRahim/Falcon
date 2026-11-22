# Two more pullback approaches: large-cap mean reversion, and adding to momentum winners on a pullback — pre-registration

**Status: FROZEN on 2026-11-22 16:39 IST**

## Why

Every mechanical rule that *waits for* a pullback before entering has done worse than buying strength. The main reason is that the best stocks rarely come back, so their entries are missed. See `docs/momentum_weekly_support_preregistration.md`, Results. This doc tests the two pullback uses that do not depend on that:

- **Part 1 — LMR, large-cap mean reversion.** A different kind of strategy: short trades of a few days in the most liquid stocks, buying a sharp dip in an uptrend and selling the bounce.
- **Part 2 — A10P, momentum with a pullback add-on.** Monthly momentum always buys part of each new name at the open, so no winner is missed, and adds the rest on the first pullback.

A third idea, discretionary pullback trading, cannot be backtested fairly. It is handled as a logged manual track in paper trading, not here.

Per IA (2026-11-22), the day's close is accepted as equivalent to a 3:15 pm decision price. Close fills are therefore used where a rule acts on the day's close.

## Common to both parts

- **Data:** `data/pit_v2`, survivorship-free, with costs as in `CostModel`.
- **Windows:**
  - H0: 2001-01-01 → 2006-12-31
  - W2: 2008-01-01 → 2017-12-31
  - Y2018: 2018
  - W1: 2019-01-01 → 2026-10-30
- **Samples:** all stocks (judged), half A and half B (reported). Six checks per `judge()`. No ethical filter, so the results compare with stored references.

## Part 1 — LMR: large-cap mean reversion

**Universe:** that month's top 100 by turnover (`rank` ≤ 100 in `universe_monthly`).

**Entry signal at the close of day t** (all must hold):
1. The stock is in the top-100 universe for day t's month.
2. Its close is above its 200-day simple average (an uptrend).
3. RSI(2) is below 10, using Wilder smoothing, period 2, on daily closes (a sharp 1–3 day dip).

**Buy at the close of day t.** If more signals than free slots, the lowest RSI(2) first, ties by entity_id.

**Exit:**
- Sell at the close of the first day whose close is above the stock's 5-day simple average (the bounce).
- **Time stop:** sell at the close of the 10th session after entry if still held.
- No price stop in the primary.
- A stock leaving the top 100 does not force a sale. Delisting follows `_delisting_exits`.

**Sizing:** 10 slots. Each new position is equity ÷ 10, limited by cash. At most one position per stock.

**Variants:**

| Code | Difference |
|---|---|
| **LMR (primary)** | As above |
| LMR_O | Signals at day t's close, buy at day t+1's open; exit signals at a close, sell at the next open (fully next-open) |
| LMR_S8 | Adds an 8% stop below the buy price, filled at the stop or at the open if it gaps through |
| LMR_N | Adds a market filter: no new entries unless the Nifty 50 closed above its 200-day average on day t |

**Adoption bar (LMR, all stocks, in both W1 and W2):**
1. CAGR at least 2 percentage points a year above the Nifty's;
2. max drawdown shallower than −25%;
3. at least 4 of the 6 checks.

If adopted, LMR becomes a candidate sleeve for paper trading. Reported: win rate, average hold, average trade, trades per year, time invested.

## Part 2 — A10P: monthly momentum, part bought at the open, the rest added on a pullback

**Unchanged from A10:**
- the selection (top 20 by 12-1 return at the month-end close, from the monthly top 500);
- leavers are sold at the rebalance open;
- the 10% stop;
- costs.

**How a new name is bought:**
1. At the rebalance open, buy **half** of its slot (half of equity ÷ 20, limited by cash, split evenly as in `run_momentum`). The stop is 10% below this first fill and applies to the whole position.
2. **The other half is a limit buy at the weekly broken-prior-high level** (S1, exactly as defined in `docs/momentum_weekly_support_preregistration.md`; the level with the highest fill rate there, 46–49%).
   - It is active from the session after the first fill.
   - It fills in a session whose low is at or below the level, at min(open, level).
   - It is placed only while the position is held. It is cancelled if the position is stopped out or sold.
3. **If the add is not filled by the next month-end rebalance** and the name is still in the top 20, it is bought at the rebalance open (fallback). If the name has left, the add is cancelled with the sale.
4. After an add, the stop stays at 10% below the first fill. It is not moved.

**Variants:**

| Code | Difference |
|---|---|
| **A10P (primary)** | 50% at the open, 50% at S1, fallback at the next rebalance |
| A10P_67 | 67% at the open, 33% at S1, fallback |
| A10P_NF | 50/50, no fallback: an unfilled add stays in cash for as long as the name is held |
| A10 (reference) | Must reproduce `data/a_stop_result.txt` (W1, W2, Y2018) and `data/history_2001_2006_result.txt` (H0) within 0.05pp before any variant runs |

**Adoption bar (A10P, all stocks, in both W1 and W2):**
1. CAGR no more than 1.0 percentage point a year below A10's;
2. max drawdown at least 3 percentage points shallower than A10's;
3. at least 4 of the 6 checks.

Reported: share of adds filled at S1 vs by fallback vs cancelled; average add price vs the first fill; average cash held.

## What it means

- **LMR adopted:** a short-term mean-reversion sleeve joins the paper-trading candidates.
- **A10P adopted:** paper trading's A10 sleeve buys in two halves.
- **Either fails:** no change, and the finding is recorded.
- Only the primaries are judged. There is no re-tuning and there are no extra variants. IA decides on any list change.

## Output

- `data/pullback_two_ways_result.txt`
- Runner: `tests/run_pullback_two_ways.py`
- Dated Results section here; scorecard rows.
