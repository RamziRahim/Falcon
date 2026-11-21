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

---

## Results, 2026-11-09 (`data/wick_exit_result.txt`), half A

Every reference reproduces its earlier half-A run exactly.

### Part 1: wick exit

| Strategy | W1 ref → WX → WXC | W2 ref → WX → WXC | 2018 ref → WX → WXC | Win % (W1 ref → WX) |
|---|---|---|---|---|
| #3 + Nifty 1:3 | 9.9 → 4.6 → −1.0% | 3.4 → −4.0 → 0.0% | −14.8 → −21.3 → −20.1% | 48 → 25 |
| FM 20-day-high buy-stop 1:3 | 13.0 → 8.8 → 3.0% | 10.0 → 4.8 → 0.1% | −23.9 → −23.7 → −19.0% | 47 → 26 |
| Falcon patterns | 8.9 → −0.6% | −1.6 → −10.2% | — | 45 → 23 |
| Falcon patterns, momentum only | 11.2 → 4.5% | 2.4 → −4.0% | — | 47 → 25 |

**Verdict:** every wick-exit version is worse than its reference in both decades. Not
adopted.
- Wick fills lose on average over the full trade, but many of them recover and finish as
  winners. Selling at the fill-day close turns all of them into small certain losses.
  The win rate halves.
- Freed slots are refilled, so the trade count roughly doubles. The cool-down does not
  help: it blocks the stocks that later recover.

### Part 2: the pair

| Version | W1 2019-26 | W2 2008-17 | 2018 | ₹10 L grew to (W1 / W2) | Checks W1 / W2 |
|---|---|---|---|---|---|
| FM_C3 alone | 14.5% (DD −18%) | 12.7% (−23%) | −14.7% | 28.8 / 33.0 L | 3 / 5 |
| A10 alone | 25.9% (−33%) | 11.3% (−59%) | −36.1% | 60.8 / 29.1 L | 6 / 5 |
| RB3_R20 alone | 9.8% (−22%) | 6.7% (−22%) | −10.8% | 20.8 / 19.0 L | 3 / 4 |
| **C_F_A (FM_C3 + A10)** | **20.7% (−21%)** | **12.6% (−36%)** | −25.9% | **43.5 / 32.7 L** | **5 / 5** |
| C_F_A_R (+ RB3_R20) | 17.2% (−16%) | 10.9% (−26%) | −21.0% | 34.7 / 28.1 L | 5 / 5 |

**Against the frozen rule:**
- **C_F_A:**
  - W1: met. CAGR 20.7% ≥ 14.5%; drawdown −21% against A10's −33%, 12pp shallower.
  - W2: drawdown met (−36% against −59%, 23pp shallower). CAGR 12.60% against FM_C3's
    12.69%: **misses by 0.09pp**.
  - **Formally not adopted.**
- **C_F_A_R:** W2 CAGR 10.9% < 12.7%. Not adopted.

**Reading.** FM_C3 + A10 passes 5 of the 6 checks in both decades: the only combination
or strategy here to do so. It earns 6pp a year more than FM_C3 in W1 and the same in W2.
The price is deeper drawdowns (−21% / −36% against −18% / −23%) and a worse 2018 (−26%
against −15%). It misses the frozen rule by 0.09pp, which is noise-level. Whether to
prefer it over FM_C3 alone is a question of risk appetite, not something the test settles.
