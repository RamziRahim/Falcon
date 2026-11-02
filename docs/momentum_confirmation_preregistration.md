# Momentum confirmation pre-registration: strategy A on a later window

**Status: FROZEN on 2026-11-02 18:50 IST.** Written after strategy A passed on 2019-01 →
2024-07 (`docs/redesign_preregistration.md`). It was written before any 2025-2026
bhavcopy was downloaded and before strategy A was run on any date after 2024-07-31.
Never edit; add dated notes.

## What is tested

**Strategy A, exactly as frozen.** Monthly 12-1 momentum, top 20 of the point-in-time
top-500-by-liquidity universe, equal weight, next-open rebalancing, CostModel costs,
delisting at last close − 5%. The code is `backtesting/pit_strategies.run_momentum`,
unchanged.

**Window: 2024-08-01 → the last session in the data** (the download runs to 2026-10-31).
This is about 27 months, and it includes the 2024-25 correction in Indian mid/small
caps.

**Data:** NSE bhavcopies 2025-01-01 → 2026-10-31 are added to the 2018-2024 set. They
are built into `data/pit/` with the same `tests/build_pit_universe.py` and the same
adjustment rules. The universe and momentum look-backs use 2023-2024 data, which is
already downloaded.

## Honest caveat about this window

Falcon's breakout system was developed and tested on 2024-08 → 2026-08. During runs #5
and #6, a *survivorship-biased* momentum benchmark was printed for that window: +25% and
+39%. So we already knew momentum did reasonably well there, measured with today's
stocks only.

Strategy A itself was never designed on or run on this window. Its rules came from the
literature, and they were frozen before this window's point-in-time data existed. This
is a confirmation run, not a fully clean out-of-sample test. Forward paper trading is
still the real test.

## Pass criteria, chosen for a 27-month window, decided now

All of these must hold for "confirmed on the later window":

| # | check | threshold |
|---|---|---|
| 1 | CAGR minus Nifty 50 CAGR (same sessions) | > 0 |
| 2 | CAGR minus PIT equal-weight universe CAGR | > 0 |
| 3 | max drawdown | no worse than Nifty's max drawdown − 15 points |
| 4 | concentration | top 3 positions < 50% of profit |

The monthly-excess t-stat is **reported but not required**. With about 27 months it
can't reach 2 unless the edge is enormous, and requiring it would make this a test of
sample size rather than of the strategy.

There is a wider drawdown allowance (15 points instead of 10) for one reason only:
momentum is known to fall harder than the index in sharp reversals, and this window
contains one. A breach would still be reported prominently.

## Outcomes

- **Confirmed:** start forward paper trading of A, using the monthly tracker. Real money
  only after at least 6 months of paper trading behave in line with the backtest.
- **Not confirmed:** report it plainly. A's 2019-2024 pass is then treated as likely
  period-specific luck. Paper trading can still run as a learning exercise, but no
  real-money plan follows from it.
- **Nothing is re-tuned either way.**

---

## Result, 2026-11-02 (`data/momentum_confirmation_result.txt`)

**Data:** 452 new sessions, 2025-01-01 → 2026-10-30, no download errors. Rebuilt
`data/pit/` has 719 split/bonus adjustments. The 2019-24 results reproduce exactly
(CAGR 42.35%).

| 2024-08-01 → 2026-10-30 | Strategy A | Nifty 50 | PIT equal-weight |
|---|---|---|---|
| CAGR | 10.3% | −3.6% | −2.6% |
| Max drawdown | **−35.6%** (peak 2024-09-20 → trough 2025-03-03) | −15.8% | |
| Period returns | 2024 (Aug-Dec) −8.5%, 2025 +2.7%, 2026 (Jan-Oct) +32.6% | −5.5%, +10.5%, −11.8% | |

**Verdict: NOT CONFIRMED on the later window.**
- Checks 1-2 pass.
- **Check 3 (drawdown) fails:** −35.6% vs the −30.8% limit.
- **Check 4 (concentration) fails.** Of the window's ₹2.46 lakh gain, a single stock
  still held at the end (CUPID, a genuine ~15× move, correctly adjusted for its 4:1 bonus
  in 2026-03) contributes ₹3.12 lakh. Without it the strategy lost money in this window.

**Implementation note.** The first concentration output was `inf`, because `judge()`
counted only closed positions and the closed ones summed to a loss. `_result()` now also
reports positions still open at the end (OPEN_AT_END). With them included the share is
1.62, so the check fails either way.

Re-running 2019-24 with the same fix leaves every verdict unchanged:
- top-3 share A 0.18 (was 0.24), B 0.32, C 0.17;
- recorded in `data/redesign_result_concentration_incl_open.txt`.

**Consequence, as pre-registered:** strategy A's 2019-2024 pass is treated as likely
period-specific. It fell 36% in the 2024-25 correction against the Nifty's 16%, and its
later recovery came from one stock. Paper trading may still run as a learning exercise,
but no real-money plan follows from these results. Nothing is re-tuned.
