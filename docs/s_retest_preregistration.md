# Pre-registration: #3 with retest entries

**Status: FROZEN on 2026-11-07 ~22:15 IST,** before any run. IA asked: "what if entry is
taken in retest for #3". Never edit; add dated notes.

## Baseline

#3 with the Nifty filter (S+ "market filter only"): W1 17.3%, W2 5.5%, 2018 −14.3%.

Signals are #3's S breakouts, taken only when the Nifty 50 is above its 50-SMA at the
signal close. A **breakout** is a day b on which #3's buy-stop at the 20-day high L
would have filled: high ≥ L and open ≤ L × 1.03. **Nothing is bought on day b.** The
stock is watched for the next **10 sessions** (b+1 … b+10).

## Two entry methods

**RL: limit at the breakout level**
- A limit buy at L, filled on the first session whose low ≤ L, at the lower of the open
  and L.
- The stop is #3's swing-low stop from the signal day.

**RR: retest + reclaim**
- First a low ≤ L (the retest), then a close above L in the same window (the reclaim).
- Buy at the next open; skipped if the open is more than 3% above the reclaim close.
- The stop is the lowest low from b+1 to the reclaim day − 0.25 × ATR(14), i.e. just
  under the retest low.

## Both methods

- **Targets:** 3R and 2R, each run separately (RL3, RL2, RR3, RR2).
- **Same as #3:**
  - 1% risk, positions ≤ 25% of equity, at most 10 positions;
  - skipped if the stop is more than 15% below the fill, or at or above it;
  - a 20-session time stop from the fill;
  - the stop wins a same-day tie, and gaps fill at the open after the fill day.
- **Same costs and data.**

## Windows and judgement

- **Windows:** W1, W2 and 2018, with the six checks.
- **Compared with:** the baseline.
- **Also reported:** how many breakouts retested, reclaimed and filled.
- **All windows are in-sample.** Confirmation can only come from paper trading.

## Outputs

- `data/s_retest_result.txt`
- trades in `data/s_retest_trades_*.csv`

---

## Results, 2026-11-07 (`data/s_retest_result.txt`)

| Version | W1 2019-26 | W2 2008-17 | 2018 | Win % W1 / W2 | Net per trade W1 / W2 |
|---|---|---|---|---|---|
| RL3 (limit at the level, 3R) | 11.0% (DD −48%) | −1.7% (−41%) | −16.6% | 44.6 / 42.4 | +1.15 / +0.01% |
| RL2 | 7.1% (−48%) | −0.2% (−43%) | −27.4% | 45.2 / 43.7 | +0.66 / +0.25% |
| RR3 (retest + reclaim, 3R) | 1.9% (−39%) | −6.3% (−59%) | −28.0% | 32.6 / 34.9 | +0.19 / +0.14% |
| RR2 | 1.0% (−46%) | −10.2% (−69%) | −32.6% | 37.5 / 38.4 | +0.22 / −0.18% |
| *Baseline: #3 + Nifty filter (breakout entry)* | *17.3% (−24%)* | *5.5% (−34%)* | *−14.3%* | | |

**Verdict:** all four fail, and all are worse than the breakout entry in every window.

**Reading:**
- About 90% of breakouts retested within 10 sessions, as the descriptive study found.
- **Limit at the level** buys at about the same price as the breakout entry, but later.
  It misses the breakouts that never come back, which are the best ones. By the time
  the retest comes, the last swing low is often further away (about 840-1,170
  "stop > 15%" skips per window), so the trades it does take are the weaker ones.
- **Retest + reclaim:** the stop just under the retest low is too tight for these
  stocks. Most trades are stopped out, giving a 33-38% win rate and deep drawdowns.
