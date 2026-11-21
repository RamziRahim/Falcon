# Pre-registration: range + volume breakout for #3 and FM

**Status: FROZEN on 2026-11-08,** before any run. IA asked to keep only two of the
quality-breakout checks (`docs/s_quality_preregistration.md`) and retry both #3 and
FM. Never edit; add dated notes.

## Breakout day t (both strategies)

- L = the highest intraday high of the 20 sessions before t; k = the day it was made.
- **Crossed:** High[t] > L (intraday; no close above L required).
- **Tight range:** L / (lowest low from k to t−1) − 1 ≤ 10%.
- **Volume:** Volume[t] ≥ 1.5 × the average volume of the 50 sessions before t.
- Full-day volume is known only at the close, so the order is a **buy at the open of
  t+1** (no look-ahead).

## #3 (run_s_plus + entries_s_quality(base_min=1, need_close=False))

- Candidates as #3: top 20% 6-month momentum, top third of its peer group, close above
  the 50- and 200-day SMA, Nifty 50 above its 50-day SMA.
- Skip if the open is more than 3% above the breakout-day close.
- Stop: swing-low stop (skip if no swing low or wider than 15%). 1% risk, ≤25%
  per position, 10 slots, 20-session time stop.
- Targets: **R3** = 3R, **R2** = 2R.

## FM (run_fm_entries mode "rangevol")

- FM watch list, ranking exits, sector-else-Nifty filter and 40-session time stop, all
  unchanged.
- Entry: buy at the next open after a breakout day while on the watch list; FM's 5%
  gap cap.
- Stop: the higher of the swing-low stop and fill − 3 ATR.
- Targets: **R3** and **R2**.

## Windows, checks and outputs

- **Windows:** W1 2019-01-01 → 2026-10-30; W2 2008 → 2017; 2018.
- **Checks:** the six `judge()` checks.
- **Comparison:** #3 + Nifty filter (17.3% / 5.5% / −14.3%) and FM R3 / R2
  (11.2% / 8.6%; 10.0% / 8.0%).
- **All windows are in-sample.**
- **Output:** `data/range_volume_result.txt`.

---

## Results, 2026-11-08 (`data/range_volume_result.txt`)

Nifty CAGR: W1 10.0%, W2 5.5%, 2018 4.1%.

| Version | W1 2019-26 | W2 2008-17 | 2018 | Trades W1 / W2 / 2018 | ₹10 lakh grew to (W1 / W2) | Checks W1 / W2 |
|---|---|---|---|---|---|---|
| #3 range+vol R3 | 5.4% (DD −28%) | −0.8% (−33%) | −14.5% | 687 / 719 / 84 | 15.0 / 9.3 L | 3 / 1 |
| #3 range+vol R2 | 6.8% (−21%) | 1.3% (−31%) | −12.9% | 714 / 748 / 88 | 16.7 / 11.4 L | 2 / 1 |
| FM range+vol R3 | 5.5% (−22%) | 9.0% (−28%) | −20.9% | 470 / 485 / 59 | 15.3 / 23.7 L | 3 / 4 |
| FM range+vol R2 | 3.9% (−22%) | 7.5% (−24%) | −21.3% | 515 / 539 / 62 | 13.5 / 20.5 L | 2 / 4 |
| *#3 + Nifty filter (reference)* | 17.3% (−24%) | 5.5% (−34%) | −14.3% | 820 / 895 / 90 | 34.8 / 17.0 L | 5 / 4 |
| *FM R3 (reference)* | 11.2% (−26%) | 8.6% (−27%) | −26.7% | 610 / 691 / 86 | 22.9 / 22.9 L | 2 / 4 |

**Verdict:** the range + volume entry is worse than the reference in 2019-26 for both
strategies (#3 17.3% → 5.4%; FM 11.2% → 5.5%). It roughly matches or slightly beats
FM in 2008-17 (9.0% vs 8.6%) and softens FM's 2018 loss (−20.9% vs −26.7%), but
not enough to offset losing half the W1 return. Not adopted.

**Why:** buying the next open after a high-volume breakout day pays up — the stock has
usually already run on day t, so the entry is higher and the stop distance wider, which
shrinks position size and leaves less room to the target. The #3 reference buys at the
level itself with a buy-stop.
