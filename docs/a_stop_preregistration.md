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

---

## Results, 2026-11-07 (`data/a_stop_result.txt`)

| | A (no stop) | A10 (10% stop) | Nifty |
|---|---|---|---|
| W1 2019-26 CAGR | **33.0%** (6/6 checks, t 2.45) | 26.4% (5/6; fails only t = 1.74) | 10.0% |
| W1 max DD | −42.1% | −39.4% | −38.4% |
| W2 2008-17 CAGR | 8.4% (3/6) | **13.2%** (5/6; fails only t = 0.85) | 5.5% |
| W2 max DD | **−80.1%** | **−59.1%** | −59.9% |
| 2008 calendar year | −76.9% | −53.4% | |
| 2018 | −23.7% | **−38.9%** (7.6% wins) | +4.1% |
| Win % W1 / W2 | 52.4 / 49.3 | 39.1 / 32.4 | |
| Avg win / loss W1 | +28.0 / −12.5% | +27.6 / −9.7% | |

**Reading:**
- The 10% stop costs about 7 points a year in the 2019-26 bull market, but adds about 5
  points a year on 2008-17. It cuts the 2008-17 drawdown from −80% to −59%, about the
  Nifty's.
- A10 is the first strategy to pass 5 of the 6 checks in **both** decades. In each it
  fails only the luck test.
- **2018 is worse with the stop:** −38.9% vs −23.7%. In a steady mid-cap decline, the
  stop sells near lows, and the next rebalance buys again into the fall.
- Not proven. All windows are in-sample, and these are the same windows that shaped the
  stop idea.

---

## Dated addendum, 2026-11-07 ~23:00 IST, before these runs

IA asked: "what if test A considered top 10 and top 15 instead of top 20". The same
rules are run with **hold = 10** and **hold = 15** (equal weights of 1/10 and 1/15),
each without a stop and with the 10% stop. The windows and checks are the same.
**Output:** `data/a_topn_result.txt`.

### Top-N results, 2026-11-07 (`data/a_topn_result.txt`)

CAGR, with max drawdown in brackets.

| Holdings | Stop | W1 2019-26 | W2 2008-17 | 2018 | Checks W1 / W2 |
|---|---|---|---|---|---|
| Top 10 | none | 31.4% (−42%) | 4.4% (−84%) | −3.8% | 5/6 / 2/6 |
| Top 10 | 10% | 22.9% (−46%) | 5.2% (−65%) | −28.5% | 4/6 / 3/6 |
| Top 15 | none | **34.1%** (−44%) | 9.5% (−81%) | −16.3% | **6/6** / 3/6 |
| Top 15 | 10% | 25.8% (−39%) | 11.6% (−59%) | −34.4% | 5/6 / 5/6 |
| Top 20 | none | 33.0% (−42%) | 8.4% (−80%) | −23.7% | 6/6 / 3/6 |
| Top 20 | 10% | 26.4% (−39%) | **13.2%** (−59%) | −38.9% | 5/6 / 5/6 |

**Reading:**
- **Top 10** concentrates the profit: the top 3 positions make 54-65% of it, which fails
  the concentration check. It is the weakest in 2008-17.
- **Top 15 and top 20** are close. Top 15 has a slightly better W1; top 20 has a better W2
  with the stop.
- The 10% stop's trade-off is the same at every size:
  - lower W1;
  - higher W2, and a W2 drawdown of −59% instead of −80%;
  - a worse 2018.
