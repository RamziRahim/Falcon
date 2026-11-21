# Pre-registration: FM exit variants and trade-path breakdown

**Status: FROZEN on 2026-11-07 ~21:55 IST,** before any run. IA asked for the same table
as for #3 (direct / retest / stop then down / stop then up / neither, over 20 and 40 days)
for "the Falcon strategy": FM, `docs/falcon_momentum_preregistration.md`. Never edit; add
dated notes.

## Versions

FM exactly as frozen (40-session time stop), with the exit varied:

| Code | Target | Extra |
|---|---|---|
| R3 | 3R (FM as frozen) | — |
| R2 | 2R | — |
| R3BE | 3R | once the high reaches fill × 1.05, the stop moves to the fill from the next session; nothing is sold |
| R2BE | 2R | same as R3BE |

The stop stays FM's: the tighter of the swing-low stop and fill − 3 ATR. R3 must
reproduce the frozen FM result (W1 11.2%, W2 8.6%); that is the regression check.

## Windows and outputs

- **Windows:** W1, W2 and 2018, with the six checks for each run.
- **Trade-path breakdown:** every trade's path is followed for 20 and for 40 sessions
  from the fill, ignoring the actual exit. The classes are those of
  `tests/analyse_trade_paths.py`. The levels are the actual fill, stop and target logged
  at entry.
- **All windows are in-sample.** This is descriptive, plus a comparison of variants;
  confirmation can only come from paper trading.
- **Outputs:**
  - `data/fm_variants_result.txt`
  - `data/fm_trade_paths.txt`
  - trades and levels in `data/fm_variants_*`

---

## Results, 2026-11-07 (`data/fm_variants_result.txt`, `data/fm_trade_paths.txt`)

R3 reproduces frozen FM exactly (W1 11.19%, W2 8.63%).

| Version | W1 2019-26 | W2 2008-17 | 2018 | Win % W1 / W2 | Net per trade W1 / W2 |
|---|---|---|---|---|---|
| R3 (FM) | **11.2%** (DD −26%) | **8.6%** (−27%) | **−26.7%** (−33%) | 39.8 / 43.7 | +1.55 / +1.81% |
| R2 | 10.0% (−22%) | 8.0% (−24%) | −19.0% (−27%) | 44.4 / 47.2 | +1.50 / +1.64% |
| R3BE | 6.8% (−19%) | 4.7% (−27%) | −31.0% | 20.7 / 23.2 | +0.96 / +0.56% |
| R2BE | 3.2% (−21%) | 1.6% (−31%) | −25.0% | 24.1 / 25.1 | +0.58 / +0.25% |

**Findings:**
- **FM lost 26.7% in 2018,** its first run on that year, while the Nifty rose 4%. That is
  worse than #3 + Nifty filter (−14%): the Nifty-based crash protection does not detect
  a small/mid-cap crash.
- R2 is close to R3 on both decades, with slightly lower CAGR and shallower drawdowns.
- Break-even at +5% lowers CAGR in every window, as it did in #3.

**Paths over 40 days (all years, R3):**

| Direct | Retest | Stop, down | Stop, then up | Neither |
|---|---|---|---|---|
| 5.7% | 10.5% | 40.9% | 7.6% | 35.3% |

"Stop, then up" is higher than in #3 (1.6%), because FM's stop is capped at 3 ATR, so it
sits closer to the price.

---

## Dated addendum, 2026-11-07 ~22:35 IST, before this run

IA asked: "what if I keep 5% SL and 10% target and buy in both strategies". A
descriptive per-trade check was made first (`data/fixed_long_5_10.txt`): FM entries came
out at about +0.3-0.4% per trade after costs in every period, and #3 entries at about
−0.3%. That check ignores sizing and slot competition.

So FM is now run as a full portfolio backtest with **F510**:
- stop = fill × 0.95, target = fill × 1.10;
- everything else as frozen FM: 1% risk, so about 20% positions, at most 25% of equity;
  10 slots, cash-limited; rank exit; 40-session time stop.

**Windows:** W1, W2 and 2018. **Output:** `data/fm_variants_F510_result.txt`.

### F510 result, 2026-11-07 (`data/fm_variants_F510_result.txt`)

| | W1 2019-26 | W2 2008-17 | 2018 |
|---|---|---|---|
| CAGR | −7.1% (DD −49%) | −10.1% (DD −71%) | −28.3% |
| Trades / win % | 1,530 / 36.3% | 1,843 / 37.6% | 204 / 28.4% |
| Net per trade | −0.05% | −0.32% | −1.21% |
| Checks | 0/6 | 0/6 | 0/6 |

**Verdict:** fails. It is far below FM's 1:3 (11.2% / 8.6%).

**Why the per-trade check was misleading:**
- **Gaps.** The descriptive check assumed every stop filled at exactly −5%. The backtest
  fills gaps through the stop at the open, so many losses are bigger than 5%.
- **Different trades.** Fast stop-outs free slots that are refilled at the next weekly
  ranking, often by re-buying the same names. That gives 2.5× more trades than FM, and
  the extra ones are of lower quality.
- **Larger positions.** About 20% positions raise spread and impact costs.
- **Paths:** within 40 days, 28.5% of trades hit the −5% stop and then reached +10%
  anyway. The stop sits inside the normal noise.
