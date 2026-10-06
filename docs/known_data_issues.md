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

**New concrete downstream impact found, 2026-09/10 (Trailing-Exit Backtest
Experiment)**: building `tests/run_trailing_exit_experiment.py` (a
post-processing exit-rule comparison against run #4's raw episode log)
surfaced the SAME corruption in a new, previously-unmeasured way: for 10
of 213 EXECUTE/ALERT_WATCHLIST episodes, run #4's own recorded
`entry_price` disagrees with `data/technical/{ticker}.parquet`'s CURRENT
cached `Close` on that same entry date by a factor of 1.53x-5.29x (e.g.
NAUKRI.NS 2024-09-19: entry_price 1494.58 vs cached Close 7902.10, a
5.29x gap) -- clear evidence that at least these tickers' cached price
series has been rebased (a real stock split/bonus corrected in the cache)
*after* run #4's own entry_price was captured, so the two numbers are on
different price bases, not evidence of a real move. Left undetected, this
single-handedly fabricated >400% "returns" in the trailing-exit
simulation once real forward price-walking was attempted against
today's cache (the original run #4 backtest itself is NOT affected --
its own entry/exit/return_pct are entirely self-contained within
whatever price basis existed when it ran, no dependency on today's
cache).

Affected tickers/dates found this way (a strictly *ratio-based* detection,
[0.67x, 1.5x] bounds -- confirmed NOT exhaustive, see caveat below):
NAUKRI.NS (2024-09-19, 5.29x), METROPOLIS.NS (2024-10-04/2025-06-12/
2025-07-10, 4.17x-4.64x), LALPATHLAB.NS (2024-10-04, 2.06x),
PIDILITIND.NS (2025-05-15, 2.11x), SHILPAMED.NS (2025-05-22, 2.07x),
GLENMARK.NS (2025-07-17, 1.53x), ANANDRATHI.NS (2025-07-17, 2.36x),
HFCL.NS (2026-05-05, 1.69x) -- overlapping partially, but not entirely,
with the ~34-ticker list this item's earlier checks already tracked.

**Caveat, investigated not assumed**: the ratio threshold has a real
false-negative gap -- a second GLENMARK.NS episode (2025-07-10,
entry_price 1455.0, cached Close 1904.0, ratio 1.31x, same entry_price
value recorded 9 days apart for two separate signals) sits just under
the 1.5x cutoff and could not be confidently classified as corruption vs.
a legitimate pivot-below-current-price reading (a breakout's `entry_price`
is the pattern's pivot level, not necessarily that day's Close --
`get_entry_target_stop()`'s own `entry = pivot_level`, so some
entry-vs-Close divergence is expected by design, not itself a bug).
Checked whether this ambiguity matters: it doesn't touch this
experiment's own headline numbers either way -- neither GLENMARK.NS
episode was among the 5-slot-selected "taken" episodes in the trailing-
exit portfolio simulation, confirmed by re-running the comparison with
GLENMARK.NS excluded entirely and getting an identical result (92.20%
total return, 27.09 Calmar, both runs).

**Status: still open, same as the rest of this item** -- this is
additional confirmed evidence of the corruption's real downstream cost
(fabricating a >400% return in a naive replay), not a new issue and not
a resolution. Any future backtest experiment that joins an OLD episode
log's `entry_price` against the CURRENT `data/technical/` cache must
repeat this same entry-price-vs-cached-Close sanity check before trusting
results -- see `tests/run_trailing_exit_experiment.py`'s own
`_price_basis_mismatch()`/`filter_price_basis_mismatches()` for a
reusable reference implementation of the check (not promoted to a shared
module here, since this item's root cause -- and therefore the "right"
place to fix it once -- is still unresolved).

---

## 2. Full test suite runtime (~3h47m) not explained by Phase 4.6 (downgraded: not reproducing)

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

**Downgraded, 2026-08-17**: a subsequent full-suite run (after the
predicted_p/model_version fix, `ec41e0a`) completed in **32.12s** --
519 passed, 5 deselected, same population plus 8 new tests. Not a fix
(no root cause was ever identified, so this can't honestly move to
"Resolved" per this document's own convention), but strong circumstantial
support for the standing hypothesis: whatever caused the 3h47m run was
a one-off (most likely a slow/flaky real network call that specific day),
not a structural cost of anything in this codebase's normal test path.
Leaving this open rather than closed, since "it didn't reproduce once"
isn't the same as "it can't happen again" -- revisit if it recurs.

---

## 3. ROCE/D-E quality gating moved to Screener, Falcon's own check now unused (deliberate, open)

**Decision date: 2026-08-18.**

**What changed**: `decision_engine/leadership_decision_engine.py`'s
`FUNDAMENTAL_DISQUALIFIERS` (the `D_E > 0.5` / `ROCE < 10.0` AVOID
checks) is now an empty list -- ROCE and D_E no longer gate AVOID
anywhere on the live path. In their place,
`candidate_generation/strategies/Leadership/screen.query` now filters on
`Return on capital employed > 10` alongside the pre-existing
`Debt to equity < 0.33` -- both fundamental quality gates live entirely
in Screener's own query today, not in Falcon's own code. Verified live
against Screener.in directly before landing: the updated query parses
and runs cleanly (115 real matches the day this was tested), not
guessed syntax.

**Why**: found while spot-checking a live scan's AVOID breakdown at
scale (135-ticker run, 2026-08-18) -- a *separate* bug from the row-
matching bug fixed earlier the same week (`ed5e1ae`): the underlying
`get_roce()` computation is correct, but `fundamental_analysis/
fundamental_cache.py` caches fundamentals for 7 days
(`REFRESH_INTERVAL_DAYS = 7`) with no invalidation tied to code changes,
so any ticker cached before a fix lands keeps silently serving the
pre-fix value for up to a week. Confirmed 3 tickers (HAPPYFORGE.NS,
DIVISLAB.NS, SONACOMS.NS) wrongly AVOIDed on stale sub-1%-looking ROCE
readings when their real, freshly-computed ROCE was 12-18% -- well
clear of the 10% floor. 13 of that day's 26 `LOW_ROCE` AVOIDs were
cached before the row-matching fix landed and were never re-verified
individually beyond those 3.

Given Screener's own query already enforces both gates today (D/E<0.33
is *tighter* than the removed D_E>0.5 check ever was; ROCE>10 matches
the removed ROCE<10.0 check exactly), and Screener IS the entire live
universe source right now -- every candidate that can reach
`categorize()` at all has already cleared both filters before Falcon
ever sees it -- Falcon's own redundant, cache-fragile copy of the same
gate was retired rather than patched. `get_roce()` and D_E's own
computation are untouched and still real; only the disqualifier
*reference* to them was removed (see `FUNDAMENTAL_DISQUALIFIERS`'s own
comment for the exact two lines to restore). ROCE/D_E are still fetched
and cached for the dashboard's own Fundamentals-panel *display*
(`ui/dashboard_data.py`'s `fetch_fundamentals_view()`) -- confirmed the
only other real (non-dead-code) consumer via a full-codebase usage
audit before this decision -- so no fetch was skipped and there's no
scan-speed change here. The stale-cache bug itself is **not fixed**,
just lowered in stakes: it can now only show a stale number in the UI,
not silently reject a genuinely good stock. Fixing the cache
invalidation itself remains open, at leisure, not urgent.

**This must be revisited before the live universe source ever changes
from Screener to anything else** -- a wider self-built universe, a
backtest-replay-driven live scan, or any candidate source that doesn't
already carry its own D/E-and-ROCE prefilter. On that day, fundamental
quality filtering silently disappears entirely (not degrades -- Screener's
gate goes away and nothing replaces it) unless the two disqualifier
lines above are restored into `FUNDAMENTAL_DISQUALIFIERS` first. This is
the single most important thing to check before trusting results from a
non-Screener candidate source.

**Status: open by design** -- not a bug to fix, a scope decision to
track so it isn't silently forgotten. Revisit trigger: any change to
`ticker_universe`'s source in `app.py` / `services/scan_pipeline_service.py`
away from `candidate_generation.candidate_generator.generate_candidates()`.

---

## 4. Fundamental data sourcing consolidated to the Screener scrape (complete)

**Decision date: 2026-08-18. Completed: 2026-08-19.** Parts 1-4 (scrape
extension, storage, redirected call sites, live validation) are all
implemented, tested (`tests/fundamental_analysis/`,
`tests/candidate_generation/`), and validated against real tickers --
see the Part 4 results below.

**Scope**: ROCE, D/E, FII holding + trend, DII holding + trend, promoter
holding + trend, and margin trend (via OPM, not NPM -- OPM matches the
core-operations intent this signal is meant to detect; NPM is noisier
from tax/one-off items, confirmed directly: HCLTECH/WIPRO/POWERGRID all
showed OPM and NPM trend DIRECTIONS disagreeing, not just magnitude) move
from independent live Yahoo/NSE calls to the single Screener scrape
`candidate_generation/candidate_generator.py` already does to build the
candidate list. `days_to_earnings` and bulk/block deal activity stay on
their existing live sources -- Screener has no equivalent for either.

**Acceptance criteria correction**: the original spec targeted "at most 2
external fundamentals calls per candidate" (days-to-earnings,
deal-activity). The real number is **3**, not 2 -- a deliberate tradeoff,
not an incomplete implementation. `institutional_sponsorship`
(`heldPercentInstitutions`, Yahoo's *combined* FII+DII+mutual-fund
institutional holding) stays on its existing Yahoo call rather than being
approximated as Screener's FII%+DII% -- those two sums are a narrower,
different measurement (missing mutual-fund/other-institutional holding),
a real definitional gap, not a formatting difference. `promoter_holding`
does NOT have this problem and was routed to Screener as planned -- a
company's disclosed promoter shareholding is a single unambiguous
regulatory figure, not something that varies by data provider the way a
composite "institutional" aggregate can.

**Infrastructure note -- read before ever editing Screener's account
column list**: while implementing this, discovered that three columns
Falcon's scraper used to expect (Market Cap, Div Yield, Sales Qtr) had
already silently disappeared from the Screener account's own column
preferences (`screener.in/user/columns/`) at some earlier, unknown point
-- harmless purely by luck, since nothing downstream ever consumed those
three fields. That account-level column list is now a **real, load-
bearing piece of Falcon's infrastructure**, not a cosmetic display
setting -- `candidate_generation/sources/screener_adapter.py` parses the
results table by fixed COLUMN POSITION, not by reading header text, so
any future edit to that account's column list (add, remove, or reorder --
by this project or anyone else with access to the account) can silently
shift every value one or more positions to the wrong field, with no
error raised, until something downstream starts getting an unexpectedly
`None` or nonsensical number. The account is also on Screener's free
tier, hard-capped at 15 columns -- already at that cap, so adding any
further column in the future requires either an account upgrade or
dropping an existing one first (see `EXPECTED_COLUMNS`'s own comment in
`screener_adapter.py` for the current list and why each entry is there).

**Part 4 validation (2026-08-19)**: spot-checked 10 real tickers already
captured by a live scan (MCX, ENRIN, GLAXO, ANANDRATHI, OFSS, ATLANTAELE,
NAM-INDIA, GRSE, HINDCOPPER, TRAVELFOOD), comparing the new Screener-
store-sourced values against the pre-change sources they replaced:

- **ROCE** (vs. `metrics_engine.get_roce()`, Yahoo, unchanged): Screener's
  value was higher than Yahoo's for all 10 tickers, consistent with the
  known accounting-convention gap already confirmed for NESTLEIND (85.3%
  Screener vs. 56.84% Yahoo) -- a systematic, expected offset, not
  noise or a sign of a broken mapping.
- **D/E** (vs. `metrics_engine.get_risk_vitals()`, Yahoo, unchanged):
  tight agreement across all 10 (e.g. ANANDRATHI 8% Screener vs. 8.25%
  Yahoo, TRAVELFOOD 17% vs. 16.72%) -- D/E has far less cross-provider
  convention drift than ROCE, and the results confirm that.
- **margin_trend_yoy** (new: Screener OPM-based vs. old: an inline
  reimplementation of the removed Yahoo-NPM-based calc): 7/10 tickers
  agreed on direction, 3/10 (GLAXO, ANANDRATHI, TRAVELFOOD) disagreed --
  this ~70/30 split matches the magnitude of real OPM-vs-NPM divergence
  already found and accepted earlier in this investigation (HCLTECH/
  WIPRO/POWERGRID), not a regression.
- **promoter/FII/DII trend** (new: Screener query-table vs. old:
  `shareholding_scraper.get_shareholding_trend()`'s per-company-page
  scrape): FII and DII trend agreed 10/10; promoter trend agreed 9/9
  where both sides had data (MCX's old-path fetch returned no promoter
  row at all, consistent with MCX being a demutualized exchange with no
  promoter category to report -- an honest absence, not a mismatch).

No sign flips, no wrong-direction surprises outside the already-
understood OPM/NPM divergence. Scoring thresholds were calibrated against
the OLD Yahoo-convention absolute values (ROCE, NPM-based margin) -- if
anyone ever reintroduces an absolute-value disqualifier or threshold on
these fields (e.g. re-enabling the ROCE/D-E disqualifiers removed in item
#3 above), it must be re-calibrated against Screener's convention, not
reused as-is from the old Yahoo-based thresholds.

**External-call-count and scan-time measurement (2026-08-19)**: reading
the actual pre-change source (`git show HEAD:fundamental_analysis/
fundamental_cache.py` etc., before this spec's edits) showed the real
per-candidate cost in `decision_engine/live_scorer.py`'s Path A was worse
than this spec's own opening description ("4 separate calls") -- the old
`fundamental_cache.get_fundamentals()` didn't make one call, it called
`fundamental_engine.get_complete_data_packet()`, which itself fanned out
to FOUR more live calls (`corporate_engine`, `metrics_engine.get_risk_vitals()`,
`institutional_engine.get_shareholding_profile()`, `news_engine.get_ticker_catalysts()`)
plus a fifth direct call to `metrics_engine.get_roce()` -- and every one of
those five calls except the debt-to-equity figure was **fetched and then
discarded**, since `get_fundamentals()` only ever read `roce` and
`debt_to_equity` back out of the packet. On top of that,
`live_scorer.py` separately called `corporate_engine` and
`institutional_engine.get_shareholding_profile()` AGAIN directly
(duplicating 2 of the 5), plus `institutional_engine`'s old
`get_shareholding_profile_with_trend()` made a live Screener.in
company-page visit via Playwright (`shareholding_scraper.get_shareholding_trend()`)
for the promoter/FII/DII trend, and `deal_activity` made its own NSE call.

Actual measured, not estimated, external network calls per candidate:

| | Before | After |
|---|---|---|
| Cache-miss (first scan of a ticker, or 7-day TTL expiry) | **9** | **3** |
| Cache-hit (repeat scan within 7 days) | 4 (2 duplicate Yahoo calls + 1 Screener page + 1 NSE call -- the cache only gated `fundamental_cache`'s own 5 calls, not the other 4) | **3** |

The 3 calls remaining after this change (`corporate_engine` for
`days_to_earnings`/revenue growth, `institutional_engine` for
Yahoo's `institutional_sponsorship`, `deal_activity` for NSE bulk/block
deals) match the acceptance-criteria correction recorded above.

Live-timed (`time.perf_counter()`, 5 real tickers: MCX, ENRIN, GLAXO,
ANANDRATHI, OFSS) per-candidate cost:

- **After (measured directly)**: 2.68s/candidate average
  (`fundamental_cache` store read: ~0.001s, `corporate_engine`: ~0.70s,
  `institutional_engine`: ~0.68s, `deal_activity`: ~1.29s).
- **Before, cache-miss (built from the same measured per-call-type
  costs -- not a literal re-run of the deleted code, to avoid reverting
  production files)**: ~7.5s/candidate (5 discarded Yahoo/news calls
  inside the old `get_fundamentals()` at ~0.7s each, ~3.5s total, +2
  duplicate Yahoo calls (~1.4s), + one live Screener page visit, separately
  measured at 1.27s average across the same 5 tickers, +1.3s NSE call).
- **Before, cache-hit**: ~4.0s/candidate (the 4 calls the 7-day TTL
  didn't gate: 2 duplicate Yahoo calls + 1 Screener page visit + 1 NSE
  call).

Net effect: **~64% less time per candidate on a cold cache, ~33% less on
a warm one** -- and the store-based design has no cache-miss case at all
going forward, since it's populated once per scan by the same scrape that
builds the candidate list, not fetched lazily per candidate.

---

## 5. P/E vs Sector wired up; account column swap (2026-08-20)

**Decision date / completed: 2026-08-20.**

While investigating a GLAXO.NS chart-staleness question, discovered
`ui/dashboard_data.py`'s "P/E vs Sector" field had been hardcoded `NA`
since the dashboard was first built -- but "P/E" had actually been part
of `screener_adapter.py`'s `EXPECTED_COLUMNS` since the 2026-08-18
Screener-consolidation spec, just never added to
`screener_fundamentals_store.py`'s `COLUMN_TO_FIELD` mapping, so it was
scraped and immediately discarded every single scan. Also discovered, by
grepping the whole codebase, that 5 of the account's original columns
(`P/E`, `NP Qtr Rs.Cr.`, `Qtr Profit Var %`, `Qtr Sales Var %`,
`CMP / BV`) had **zero** downstream readers -- scraped, then silently
dropped by `consolidator.py`'s named-aggregation groupby, same fate as
the columns identified in item #4.

**Account column swap** (free tier, still hard-capped at 15 -- see item
#4's infrastructure note): dropped `Net Profit latest quarter`
(confirmed zero downstream readers), added `Industry PE` (Screener's own
peer/sector-average P/E) in its place -- an even trade, no upgrade
needed. `Price to book value` was also flagged as currently-unused but
explicitly kept at the user's request, reserved for a future column
need rather than dropped now. Screener renders this new column's header
as **"Ind PE"**, not "Industry PE" (the picker's own label text) --
confirmed live; `EXPECTED_COLUMNS` and the positional mapping in
`screener_adapter.py`'s `parse_results()` use the real rendered text,
re-verified against a live query run the same way item #4's column
changes were (never assumed to match the picker's label or the UI-
addition order).

**Code changes**: `COLUMN_TO_FIELD` gained `"P/E": "pe_ratio"` and
`"Ind PE": "industry_pe_ratio"`; two new display getters
(`get_pe_ratio_display()`, `get_industry_pe_display()`) follow the same
`"N/A"`-on-missing convention as every other getter in that module.
`fetch_fundamentals_view()`'s "P/E vs Sector" row now reads both and
shows `"{pe} vs {industry_pe}"` only when BOTH are real -- a half-
comparison (one real number, one N/A) shows the honest `NA` sentinel
instead of implying a comparison that doesn't fully exist.

**Not done**: no relative-valuation bucketing (CHEAP/FAIR/EXPENSIVE-
style labels) was added -- `valuation_engine.py` already has that logic
for a *different* P/E source (NSE's market-wide snapshot) and is flagged
elsewhere in this doc as dead code worth a future revival-or-removal
decision; duplicating similar logic here against a different P/E source
was out of scope for this pass. The field shows both raw numbers, not a
computed verdict.

---

## 6. Scan performance + a real same-day data-freshness bug (resolved 2026-08-22)

**Found**: user-reported live scan times climbing (28min -> 41min ->
58min across three real runs on 2026-08-20/21) and, separately, cached
technical data for many tickers still dated the 20th despite a scan run
the evening of the 21st, after market close.

**Cause 1 (performance, real and worsening over time)**:
`technical_analysis/pattern_engine.py`'s `PatternEngine.execute_pipeline()`
reprocessed pattern detection for **every** `*.parquet` file already
sitting in `data/technical/` -- not just today's actual
`ticker_universe` -- confirmed as the single largest phase of a real
scan (~20 of ~50+ total minutes, 568 cached tickers against a
110-ticker daily universe). Since every scan (including repeated manual
testing) adds more tickers to that cache and none are ever pruned, this
phase's cost is O(every ticker ever scanned), strictly increasing scan
over scan, not O(today's candidates) -- explaining the climbing times
directly. Fixed: `execute_pipeline()` gained an optional
`ticker_universe` parameter; `services/scan_pipeline_service.py`'s
call site now passes today's real universe, so only those tickers get
re-detected. Every other caller (`run_full_pipeline.py`,
`services/screener_service.py`, the module's own `__main__` block, and
existing tests) omits the argument and keeps its original full-directory
behavior unchanged. A ticker outside today's universe simply keeps
whatever `data/patterns/*.parquet` it already has -- the exact staleness
case `ui/dashboard_data.py`'s `format_stale_data_notice()` already exists
to surface honestly on its card/chart, not a new failure mode.

**Cause 2 (correctness, more serious than the performance issue)**:
`market_data/downloader.py`'s `_download_symbol()` computed
`start_date = last_cached_date + 1 day`, then skipped the fetch entirely
whenever `start_date >= today`. For a ticker last cached the day before
(the exact case after any prior day's scan), `start_date == today` --
and the old `>=` check treated that as "already caught up," so a scan
run **the same day**, even hours after market close with real EOD data
already published, never even attempted to fetch that day's own bar.
Silent, no warning, no error -- the ticker just kept yesterday's cached
close indefinitely until a scan ran on some *later* day. This is the
same underlying mechanism independently confirmed on GLAXO.NS earlier
(2026-08-19/20), except that case was correctly explained by the ticker
being absent from that day's screened universe entirely; this bug hits
tickers that ARE in the universe and should have gotten fresh data.
Fixed: changed `>=` to `>` -- `start_date == today` now always attempts
the fetch; the existing empty-response handling immediately below
(`"returned no new data"` / `"already up to date"`, an honest outcome
already relied on elsewhere, not new) correctly covers the case where
today's data genuinely isn't published yet, so this doesn't risk
fabricating a "new" data point that doesn't exist.

Both fixes are minimal, scoped, additive to their respective functions'
existing default behavior (verified: `git grep` for every other caller
of both changed functions, all unaffected), full suite green with new
regression tests for each (`tests/technical_analysis/test_pattern_engine_persistence.py::TestTickerUniverseScoping`,
`tests/market_data/test_downloader.py::TestFreshnessCheckDoesNotSkipTodaysOwnData`).

---

## 7. Zero EXECUTE/WATCHLIST across a 93-ticker scan (2026-09-27) -- not yet root-caused, may be correct

**Found**: while verifying the MONITOR-tier/tooltip work end-to-end on a
real live scan (2026-09-27), the run screened 93 tickers from the
Leadership query and produced 0 EXECUTE, 0 ALERT_WATCHLIST, 10 MONITOR,
82 AVOID.

**Not yet investigated**: this could be genuinely correct (a market-
regime-driven `UNFAVORABLE`/`CAUTION` day, or a real scarcity of pattern-
confirmed, model-cleared setups on this particular date -- the market
regime badge that same scan showed UNFAVORABLE with NIFTY in a DOWNTREND,
which is at least consistent with a defensively-skewed outcome) -- or it
could mean an upstream filter (a disqualifier, a cap, the ROCE/D-E gate
now living in Screener's own query per item #3, or the calibrated
model's execute_cutoff) is being overly restrictive in a way that isn't
actually intended. One 93-ticker sample on one date isn't enough to tell
the difference.

**How to check, if this recurs or is worth confirming now**: same
diagnostic method already used for the ROCE/D-E investigation in item
#3 -- a real live scan's AVOID breakdown by exact disqualifier/cap
reason (not just the aggregate AVOID count), to see whether the 82 AVOID
tickers are failing for a plausible, expected spread of reasons or
whether one single check is doing nearly all of the rejecting.

**Status: open, not blocking** -- flagged as a diagnostic follow-up, not
a confirmed bug. Nothing about this session's MONITOR/tooltip/VWAP work
touches any disqualifier, cap, or the model's cutoff, so it's unrelated
to what was actually being verified that day.

---

## 8. VWAP Reclaim chip -- never visually confirmed rendering in a real browser

**Status as of 2026-09-27**: the VWAP Reclaim mechanism itself (VWAP
computation, coverage-ratio fail-closed check, market-hours gating,
EXECUTE/WATCHLIST-only scoping) is covered by 18 unit/integration tests
across `tests/technical_analysis/test_vwap_reclaim.py`,
`tests/market_data/test_market_hours.py`,
`tests/market_data/test_intraday_fetcher.py`, and
`tests/services/test_scan_pipeline_service.py`, plus a Jinja-level render
check with synthetic data confirming the three chip states produce valid
HTML. **None of that is the same as having actually seen the chip render
in a live browser against a real EXECUTE/WATCHLIST candidate** -- every
real live scan run so far either happened outside market hours (a
weekend, so `is_live_market_hours()` correctly suppressed the whole
feature) or, on 2026-09-27, produced zero EXECUTE/WATCHLIST candidates
for the chip to appear on regardless of market hours (see item #7 above).

**Do not treat "tests pass" as "confirmed working" for this specific
feature** -- close this out with an actual screenshot, not another round
of code-reading, the next time a weekday scan during live NSE hours
(9:15-15:30 IST) produces at least one EXECUTE or ALERT_WATCHLIST
candidate. Once confirmed, update this entry to reflect that (or move it
to a "Resolved" state per this doc's own convention) rather than leaving
it open indefinitely once it's actually been seen.

---

## 9. Exit-rule parameter tuning is underpowered at the current backtest universe/window (open)

**Found**: while tuning `trailing_exit_simulator.py`'s parameters (partial-
exit trigger %, trailing MA period) on the Trailing-Exit Backtest
Experiment's own tuning split (`tests/run_trailing_exit_experiment.py`,
episodes entered <= 2025-09-21, n=121 candidate episodes -> 29-31 actually
taken trades after 5-slot selection depending on config), a 10-day
trailing MA appeared to beat the spec's 20-day baseline on Calmar (25.72
vs 23.73). A leave-top-3-out robustness check (drop the 3 largest-
magnitude taken trades from each config, recompute) **flipped the
ranking**: baseline 20-day Calmar fell to 13.84, 10-day fell further to
9.30 -- 20-day came out ahead once those 3 trades were removed from each.
Confirmed this wasn't hidden price corruption (item #1) driving it: the
single largest contributor in both configs, RPOWER.NS, was checked
directly against its cached price history and shows a continuous,
non-discontinuous price path -- a genuine large winner, not a data
artifact.

**Root cause: sample size, not a data bug.** Top-1/top-3 log-growth
concentration on this tuning split ranges 13.6%-20.0% (top-1) and
31.8%-39.9% (top-3) across the four configs tested -- meaning each
config's own result is substantially decided by 2-3 trades out of
~29-31 taken, not a stable population-level difference. At this n, a
parameter ranking is not a safe signal to select on, and switching to a
"more robust" selection rule after seeing the naive one flip would just
be tuning the tuning method post-hoc -- the same overfitting risk this
project guards against everywhere else, one level removed. The parameter
search was left explicitly marked inconclusive rather than resolved
either way; no parameter was carried into the experiment's validation-
split run (which used the spec's original, pre-registered 8%/50%/20DMA
defaults instead).

**Status: open, not a blocker for anything already shipped** -- this
doesn't touch any live/production code (the trailing-exit rule was never
wired into `categorize()` or the live scan). It IS a blocker for trusting
any *future* per-trade exit-rule (or similar) parameter tuning done
against this same run #4 episode population: any such attempt needs a
materially larger sample before the tuning step itself can be trusted --
a bigger corruption-exclusion population (item #1) does not by itself
fix this, since the underlying constraint is the total number of
EXECUTE/ALERT_WATCHLIST episodes run #4's window+universe ever produced
(213 candidates, ~55-60 actually taken across the full population), not
how many of those are corrupted. Extending the backtest window,
widening the universe, or accumulating more real trading history are the
only things that actually address this.

---
