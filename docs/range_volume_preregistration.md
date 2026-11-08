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
