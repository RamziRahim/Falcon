# Pre-registration: wick-exit rule for buy-stop entries, and the FM_C3 + A10 pair (half A)

**Status: FROZEN on 2026-11-09 ~17:55 IST,** before any run. This follows
`docs/falcon_salvage_preregistration.md`. There, 55% of buy-stop fills closed back below
the trigger on the fill day, losing −1.28% per trade against +2.57% for the rest. IA said
"Yes" to testing a wick exit, and to the pair. Never edit; add dated notes.

## Part 1: wick exit

**Rule.** On the fill session of a buy-stop entry, if neither the stop nor the target was
hit that day and Close < the trigger level, sell at that close. The trigger level is:
- #3: the 20-day high;
- FM: the 20-day high;
- Falcon patterns: the pivot.

This is a 3:20 pm decision; the backtest uses the close.

**Cool-down (C versions).** After a wick exit, no new order for that stock for 20
sessions. A Falcon pattern setup is consumed when it fills, so its versions need no
cool-down.

**Versions (half A):**

| Strategy | Reference | Wick exit | Wick exit + cool-down |
|---|---|---|---|
| #3 + Nifty 1:3 (`run_s_plus`, `entries_s`, `market_filter`) | S3_REF3 | S3_WX | S3_WXC |
| FM 20-day-high buy-stop 1:3 (`run_fm_entries` "high20") | FM_H3 | FM_WX | FM_WXC |
| Falcon patterns, pivot buy-stop, Falcon stop/target (`run_setups`) | F_REF | F_REF_WX | — |
| Same, top-20% momentum only | F_MOM | F_MOM_WX | — |

The references are re-run in this script as the regression check against their earlier
results.

**Adoption rule:** a wick-exit version is a candidate if it beats its own reference on
CAGR in both W1 and W2.

## Part 2: the pair

Each sleeve runs on its own capital; the sleeves are reset to equal weights at each
month-end (`combine()`, no rebalancing cost).

| Code | Sleeves |
|---|---|
| C_F_A | FM_C3 + A10 (monthly 12-1 momentum, top 20, 10% stop), 1/2 each |
| C_F_A_R | FM_C3 + A10 + RB3_R20 (range breakout at 2% risk), 1/3 each |

**Candidate if, in both W1 and W2:**
- CAGR ≥ FM_C3 alone; and
- the maximum drawdown is at least 10pp shallower than A10 alone.

## Windows and outputs

- **Windows:** W1, W2 and 2018. The Falcon pattern versions are W1 and W2 only, because
  there is no 2018 scan.
- **All in-sample.**
- **Output:** `data/wick_exit_result.txt`.
