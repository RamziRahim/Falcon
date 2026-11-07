# Pre-registration: test A (monthly momentum, top 20) with a 10% stop loss

**Status: FROZEN on 2026-11-07 ~22:50 IST,** before any run. IA asked: "what happens to
test A if we keep 10% SL". Never edit; add dated notes.

## Rules

Test A exactly as frozen (`docs/redesign_preregistration.md`):
- at each month end, rank the universe by 12-1 momentum;
- hold the top 20 in equal amounts;
- rebalance at the next open.

**Plus:**
- each holding is sold if its low reaches its **fill price × 0.90**: at the stop, or at
  the open if it gaps through after the fill day;
- the fill day's low counts, since the buy is at that day's open;
- a stopped stock is not re-bought before the next month-end rebalance; it is re-bought
  then only if it is still in the top 20, with a new stop;
- the freed cash waits until that rebalance.

## Runs

- **A** (no stop) and **A10** (10% stop), on:
  - W1 2019-01-01 → 2026-10-30 (test A has never been run as one block on this window);
  - W2 2008-01-01 → 2017-12-31;
  - 2018.
- The same six checks, costs and data.
- **All windows are in-sample.**

## Output

`data/a_stop_result.txt`
