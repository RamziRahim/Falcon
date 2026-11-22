# Monthly momentum, half sold at 1:1 (rest keeps the 10% stop), vs simply holding less — pre-registration

**Status: FROZEN on 2026-11-22 17:59 IST**

## Question

In `docs/momentum_tight_stops_preregistration.md`, **S10_H1** was a reported (not judged) version. Its rule: A10 with a 10% stop; when the high reaches +10% (1:1), sell half; the rest keeps the 10% stop and leaves with the list. It made:
- 18.46% a year, worst fall −27.4%, in 2019–26 (A10: 26.36%, −39.4%);
- 6.99%, −49.9%, in 2008–17 (A10: 13.17%, −59.1%).

Back-of-envelope, its 2019–26 result looks like A10 run with only ~70% of the money invested.

**Does selling half at 1:1 do anything better than simply investing less in plain A10?** If not, the simpler lever is the better one.

**Honesty note:**
- Both rules have already been seen on every window, and the 70% figure was chosen after seeing S10_H1's results.
- This test therefore cannot give fresh evidence of an edge. It can only show which of two ways of taking less risk was better on the same history.
- Forward paper trading is the only fresh test.

## Versions

| Code | Rule |
|---|---|
| **S10_H1 (judged)** | As in the frozen tight-stops doc: `run_momentum(stop_pct=0.10, half_at_r=1.0)` |
| A10_70 (comparison) | A10 with every slot at 70% of A10's size: `run_momentum(stop_pct=0.10, gauge_up=all False, down_level=0.7)`, so slots = equity × 0.7 ÷ 20 and about 30% stays in cash |
| A10 (reference) | Must reproduce `data/a_stop_result.txt` (W1, W2, Y2018) and `data/history_2001_2006_result.txt` (H0) within 0.05pp |

S10_H1 must also reproduce its own result in `data/momentum_tight_stops_result.txt` within 0.05pp in every window.

## Runs

- **Windows:**
  - H0: 2001-01-01 → 2006-12-31
  - W2: 2008-01-01 → 2017-12-31
  - Y2018: 2018
  - W1: 2019-01-01 → 2026-10-30
- **Samples:** all stocks (judged), half A and half B (reported).
- **No ethical filter.**

**Reported:**
- CAGR, max drawdown, the six checks, win rate, average win and loss, and trades a year;
- **the average share of money invested** for each version, measured daily;
- CAGR ÷ |max drawdown| (return per unit of worst fall).

## Bar (S10_H1 vs A10_70, all stocks, both W1 and W2)

S10_H1 is "better than simply holding less" only if, **in both W1 and W2**:

1. its CAGR is **at least as high** as A10_70's; **and**
2. its max drawdown is **no more than 1.0 point deeper** than A10_70's; **and**
3. it is **clearly better on one:** CAGR at least 1.0 point above A10_70's, or max drawdown at least 3.0 points shallower; **and**
4. it passes **at least 4 of the 6 checks**.

## What it means

- **S10_H1 passes:** selling half at 1:1 adds something beyond holding less. IA decides whether to add it as a paper-trading track.
- **It fails:** holding less (A10_70) is the simpler way to get smaller falls. IA decides whether either becomes a paper track.
- A10 itself is unchanged either way.

## Output

- `data/half_at_1to1_result.txt`
- Runner: `tests/run_half_at_1to1.py`
- Dated Results section here; scorecard rows.

## Implementation note (2026-11-22, before running)

`run_momentum(..., track_invested=True)` records the daily invested share (1 − cash ÷ equity) in `stats`, for reporting only. A10_70 uses the existing exposure mechanism with a constant 0.7 level.

## Results (2026-11-22, run once after freeze)

**References.** Passed: A10 and S10_H1 reproduced their stored results exactly in all four windows. Output: `data/half_at_1to1_result.txt`.

**Verdict: S10_H1 is NOT better than holding less. It fails its frozen bar.**
- **W1:** 18.46% vs 22.03% (−3.57pp); DD −27.4% vs −31.4% (4.0pp shallower).
- **W2:** 6.99% vs 11.17% (−4.18pp); DD −49.9% vs −46.9% (3.0pp *deeper*).

**All stocks:**

| Version | Period | Return a year | Max DD | Average invested | Return ÷ worst fall |
|---|---|---|---|---|---|
| A10 | 2001–06 | 37.52% | −38.0% | 83% | 0.99 |
| A10 | 2008–17 | 13.17% | −59.0% | 84% | 0.22 |
| A10 | 2019–26 | 26.36% | −39.4% | 85% | 0.67 |
| S10_H1 | 2001–06 | 22.07% | −35.5% | 59% | 0.62 |
| S10_H1 | 2008–17 | 6.99% | −49.9% | 60% | 0.14 |
| S10_H1 | 2019–26 | 18.46% | −27.4% | 62% | 0.67 |
| A10_70 | 2001–06 | 31.72% | −31.6% | 67% | **1.00** |
| A10_70 | 2008–17 | 11.17% | −46.9% | 68% | **0.24** |
| A10_70 | 2019–26 | 22.03% | −31.4% | 68% | **0.70** |

Both halves agree. On half A in W1, S10_H1 makes 18.8% (−23.6%) against A10_70's 21.5% (−26.1%). On half B in W2, it makes 8.5% (−48.2%) against 10.9% (−46.8%).

**What it means:**
1. **Selling half at 1:1 is a less efficient way of holding less.** It averages only about 60% invested, less than A10_70's 68%. Yet its return per unit of worst fall is no better in 2019–26 and worse in 2001–06 and 2008–17. It sells exactly the stocks that are working.
2. **Plain A10 is itself only about 84% invested on average.** A stopped stock's money waits in cash until the next month end.
3. **If smaller falls are wanted, holding less of plain A10 is the simpler and better lever.** At 70% slots it cut the worst fall by 7–12 points for about 2–6 points a year less return, with the same return per unit of fall.
4. **No rule changes.** A10 stays at full size. IA decides whether a reduced-size A10 becomes a paper track.
