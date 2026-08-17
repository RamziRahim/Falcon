# Falcon — Known Data Issues (standing, open)

Issues found in the underlying market data that are confirmed real,
partially investigated, and **not closed** -- tracked here so they don't
quietly get forgotten between sessions. An entry only moves to "Resolved"
when the fix (not just a workaround/exclusion) has landed and been
re-verified.

---

## 1. ~34-ticker price corruption (open)

**Found**: 2026-07-29/30, while fixing the separate unadjusted-stock-split
issue (`market_data/corporate_actions.py`) for run #3's momentum baseline.
`market_data/corporate_actions.py`'s `confirm_and_adjust()` correctly
left ~11,000 single-day price discontinuities (>40% single-day move)
unadjusted because no matching NSE corporate-action record exists for
them -- i.e. they are not splits/bonuses. Investigated further rather
than assumed benign: these are concentrated in ~34 tickers (not spread
across the ~496-ticker universe), including large, liquid names (SBIN,
HDFCBANK, TATASTEEL, BRITANNIA, JSWSTEEL, NTPC, M&MFIN). Confirmed
directly as genuine data corruption, not real price action: NTPC.NS's
real Close in January 2024 was consistently ~Rs 1,100-1,300 that month,
but the cached series shows scattered days at Rs 10.65 and Rs 306 --
numbers that never happened. Most likely a raw fetch/parsing reliability
bug in the NSE provider path (`market_data/providers/nse_provider.py` /
`nselib.capital_market.price_volume_and_deliverable_position_data()`) for
these specific symbols, not yet root-caused.

**What has been verified clean, and what hasn't:**

- ✅ **Run #3's 459 real traded episodes**: two targeted checks (both in
  `tests/check_corruption_exposure.py`, committed) confirmed zero
  material exposure --
  1. Own-ticker indicator/RS lookback window: 1 of 459 trades touched
     (SHRIRAMFIN.NS, and that specific trade wasn't even among the 115
     episodes the portfolio simulator actually deployed).
  2. Cross-sectional RS percentile-rank contamination: max 2-percentile-
     point shift across 437 traded-ticker/date rows when the actually-
     distorting corrupted tickers are excluded from the ranking
     population that date -- immaterial given `RS_Rating` enters
     `compute_score()` linearly (`RS_Rating/100 * 20`), not via a
     threshold tier.
  - **This clears run #3's headline numbers specifically** (12.39%
    total return / -5.8% max drawdown / 1.09 Calmar, Falcon MONITOR@0.5
    vs. Nifty buy-and-hold) -- those are confirmed unaffected.

- ❌ **NOT yet re-verified for Phase 4.** Both checks above were scoped
  to the 459 tickers/dates run #3 *actually traded* -- a small,
  score-filtered subset of the full universe. Phase 4's feature-fitting
  process (calibrating weights/thresholds, `RS_Rating` explicitly among
  the inputs being fit) will read the **full ~496-ticker universe**
  across the **full tuning split**, not just the traded subset. A
  corrupted ticker that never happened to get traded can still pollute
  the cross-sectional ranking population (and hence `RS_Rating`, and
  hence any weight fit against it) for every OTHER ticker scored on the
  same date, at a scale run #3's narrow exposure check never measured.

**Status: BLOCKING for trusting Phase 4's *calibration output* specifically
-- not blocking for starting Phase 4's implementation work.** Before any
Phase 4 fitted weights/thresholds are treated as real (used to size real
capital, reported as a finding, or carried into Phase 5), either:
(a) re-run the same style of exposure check
(`tests/check_corruption_exposure.py`'s methodology, generalized from
"the 459 traded rows" to "every (ticker, date) the tuning-split
feature-fit actually reads"), and confirm it's still clean at that
larger scale, or
(b) root-cause and fix the underlying corruption directly (the more
durable option, given (a) would need re-running every time the universe
or window changes).

Do not start sizing real capital, reporting Phase 4 results as validated,
or carrying calibrated weights into Phase 5 before this item is resolved
or re-verified at Phase-4 scale.

**✅ Re-verified clean at Phase-4 scale, 2026-08-09** (option (a) above,
`tests/check_corruption_exposure_phase4.py`): re-ran both checks against
the actual 265-row fitting-set population (78 distinct entry dates,
tuning + validation splits combined) that `tests/backfill_rs_macd.py`
read when computing `RS_Rating` -- not the narrower 459-row/101-date run
#3 population the original check used.

- Check 1 (own-ticker lookback exposure): 1 of 265 fitting-set rows
  touches its own corrupted date (SHRIRAMFIN.NS, 2024-08-30) -- same
  finding as the original 459-row check, same single ticker, now
  confirmed at the correct scale.
- Check 2 (cross-sectional RS percentile-rank exposure): 264 of 265 rows
  checked, max |delta| = 2.0 percentile points, **zero rows at or above
  the 3-point materiality bar** the original check used. 65/264 rows
  show a nonzero shift, all ±1 or ±2 points -- immaterial for the same
  reason the original check gave (`RS_Rating` enters `compute_score()`
  linearly).

**This clears the Phase-4-calibration-output blocking condition above.**
Phase 4's fitted weights and thresholds (the spec-complete logistic
regression and its derived EXECUTE/WATCHLIST cutoffs) may now be treated
as validated with respect to this specific issue and carried into Gate 3.

The underlying corruption itself is **still not fixed** -- this is a
re-verification of a workaround's safety at a larger scale, not a root-
cause fix, so per this document's own convention the item stays open
below, not moved to Resolved.

**✅ Re-verified clean at run #4 scale, 2026-08-17**
(`tests/check_corruption_exposure_run4.py`): run #4 (the canonical
baseline under the new production `categorize()`, Phase 4.6) reads a
much larger real-signal population than the Phase-4 fitting-set check
above -- 357 rows, 94 distinct entry dates, every EXECUTE/ALERT_WATCHLIST
signal the new categorize() actually produced, not just the 265-row
tuning+validation fitting set.

- Check 1: 1 of 357 rows touches its own corrupted date (SHRIRAMFIN.NS,
  2024-09-12) -- same recurring single ticker every prior check at
  every scale has found.
- Check 2: 335 rows checked, max |delta| = 3.0 percentile points, with
  **one row at the materiality bar**: ANURAS.NS, 2024-12-10, delta =
  -3.0 (the first check at any scale to actually reach the 3-point
  bar, not stay comfortably under it). Investigated directly rather
  than waved through: confirmed this (ticker, date) is NOT among the
  59 taken EXECUTE episodes behind the +82.74% headline, nor among the
  111 taken MONITOR@0.5 episodes -- it's `category=="EXECUTE"` but was
  one of the 5 episodes dropped to slot exhaustion, never entered
  either reported equity curve.

**This clears run #4's own headline numbers specifically** (both the
EXECUTE-only +82.74% and the MONITOR@0.5 +11.08% readings) -- the one
boundary-case exposure found doesn't touch either. The underlying
corruption is still open/unfixed; this is a re-verification at a third,
larger scale, not a resolution.

---

## 2. Full test suite runtime (~3h47m) not explained by Phase 4.6 (open)

**Found**: 2026-08-09, running the full suite after Phase 4.6 (replacing
`get_ceiling()` with the calibrated model) -- `511 passed, 5 deselected`
took 3:47:31, long enough to be worth checking whether the new v2-feature
computation (now called from `candidate_assembler.assemble_candidate()`
on every candidate, live and backtest) was the driver.

**Checked, hypothesis rejected**: timed 4 representative integration
test files (`test_replay_engine.py`, `test_live_scorer.py`,
`test_candidate_assembler.py`, `test_leadership_decision_engine.py` --
the ones most likely to exercise the new per-candidate v2-feature path
against real data) on the commit immediately before Phase 4.6
(`0269597`, via an isolated `git worktree`, not a stash/checkout of the
main tree) versus HEAD (`b42092f`). Result: HEAD is FASTER (6.85s vs.
39.31s) with more tests passing (67 vs. 61, the new tests Phase 4.6
added). The v2-feature computation is not the driver of the long
full-suite runtime -- if anything these specific files got faster.

**Status: open, not investigated further** (time-boxed check, per
explicit instruction). The 3h47m full-suite time most likely comes from
a small number of pre-existing, real-network-dependent integration tests
elsewhere in the suite (this project tests against real data/live APIs
by design in several places, e.g. sector index / VIX / corporate-actions
fetches) -- not yet identified which specific test(s). Worth a targeted
per-file timing pass later if the full-suite runtime becomes a real
workflow bottleneck (e.g. blocking CI), with an eye toward fixture-level
caching for whichever real-network calls turn out to dominate -- not
urgent now, not blocking anything.

---
