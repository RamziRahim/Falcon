# STOP GATE 2 — Consolidated Report (corrected run #2)

Phase 2 diagnostics against the **corrected** run #2 output
(`data/backtest_results_run2_corrected.csv`, 16,958 raw signals). This is
run #2's original replay (`data/backtest_results_run2_raw.csv`) with the
2.2 stop/target bug fixed via salvage (`tests/salvage_run2.py`), not a
fresh replay — see that script's own docstring for exactly what was and
wasn't re-derived. All four checks below are reported in the priority
order requested.

## Context: what the salvage actually touched

Of 16,958 rows, only **223** had their stop/target priced off a real
pattern low (`stop_provenance` in `STRUCTURAL`/`STRUCTURAL_CLAMPED_TO_ATR_FLOOR`/
`STRUCTURAL_CLAMPED_TO_ATR_CEILING`) — every other row used the flat-ATR
fallback, which the two-low-model fix left byte-for-byte identical. Those
223 rows were re-detected (per-ticker only, against cached
`data/technical/*.parquet` truncated to entry_date — not a full replay)
and their outcomes re-measured against the corrected geometry. Re-detected
entry prices matched run #2's originally recorded entries exactly (0
mismatches) — confirms the fix didn't accidentally perturb detection
itself, only pricing.

Of the 5 rows that had been downgraded EXECUTE→ALERT_WATCHLIST by the
(buggy) RR floor in raw run #2: **4 now clear the corrected floor and are
genuinely EXECUTE; 1 remains capped.** Buggy-RR downgrade rate was
effectively 100% (5/5, matching the earlier diagnosis that RR≈1.0 was
structurally forced); corrected downgrade rate is **20% (1/5)**.

## 1 — EXECUTE episode count (the real B-7 + scaling test)

| level | n |
|---|---|
| raw signal rows | 4 |
| episodes (after `episode_builder.py` absorption) | **3** |

**Still nowhere near n=20.** The bug fix recovered signal from zero, but
the underlying scarcity Gate 1/B-7 was already fighting — pattern
detection + RR floor + ceiling cascade jointly gating down to almost
nothing — is still the dominant effect. All 4 raw EXECUTE signals fired
under `CAUTION` market / `STRONG` sector, 3 of 4 via
`is_ascending_triangle_breakout`; this is a thin, concentrated sample,
not a diversified one. n=3–4 is too small for any of Gate 1's episode-level
comparisons (or criterion 4's permutation test) to say anything
statistically meaningful — noted, not glossed over.

## 2 — AVOID monotonicity (EXECUTE > ALERT_WATCHLIST > AVOID)

Episode level, net of transaction cost:

| category | n (episodes) | win rate | net expectancy | mean r_multiple |
|---|---|---|---|---|
| EXECUTE | 3 | 66.7% | **10.05%** | 0.924 |
| ALERT_WATCHLIST | 97 | 75.3% | **6.38%** | 1.017 |
| MONITOR | 274 | 51.1% | 0.71% | 0.094 |
| AVOID | 5,320 | 48.6% | **0.51%** | 0.041 |

**By net expectancy %, the ordering holds: EXECUTE (10.05%) > ALERT_WATCHLIST
(6.38%) > AVOID (0.51%)** — criterion 2 passes. **By mean r_multiple
(return ÷ planned stop distance), it inverts**: EXECUTE (0.924) <
ALERT_WATCHLIST (1.017). This is very likely just n=3 noise (one of the 4
EXECUTE signals, BIOCON.NS, was a clean -7.5% stop-out with a
ceiling-widened stop, which drags the r_multiple mean hard on a 3-episode
base) rather than a real inversion — flagged rather than resolved, since
n=3 can't distinguish "real inversion" from "one bad trade in a tiny
sample."

## 3 — Detector funnel (bull-flag/flat-base starvation)

**Regenerated** (`tests/regenerate_funnel.py`, detection-only re-run
across all 16,958 corrected-CSV rows against cached
`data/technical/*.parquet` truncated histories — no universe scoring,
~2h50m wall clock; not needed for the fix itself since the two-low-model
change never touched any detector's own confirmation/threshold logic, but
run #2's original funnel counts were only ever printed to the now-gone
stdout of the original ~11-hour run and never written to disk, so there
was nothing to diff against otherwise). Saved to
`data/detector_funnel_run2_corrected.csv`.

All 5 detectors share the same UPTREND gate: 11,551 of 16,958 evaluations
(68.1%) never clear it, leaving 5,407 (31.9%) where each detector's own
precondition actually gets exercised:

| detector | in-uptrend evaluations | dominant failure | share of in-uptrend |
|---|---|---|---|
| Bull_Flag | 5,407 | `FLAGPOLE_TOO_WEAK` | **96.7%** (5,227) |
| Cup_Handle | 5,407 | `CUP_NOT_ROUNDED` | 67.0% (3,622) |
| Ascending_Triangle | 5,407 | `SETUP_VALID_NO_BREAKOUT` | 58.5% (3,165) |
| Flat_Base | 5,407 | `SETUP_VALID_NO_BREAKOUT` | 57.8% (3,124) |
| VCP | 5,407 | `NOT_CONTRACTING` | 95.5% (5,164) |

**Bull-flag starvation is confirmed, not a run #1 artifact**: `FLAGPOLE_TOO_WEAK`
still consumes 96.7% of every in-uptrend bull-flag evaluation, matching
run #1's own 96.7% almost to the decimal — this is a stable, structural
property of the current flagpole-strength threshold against this
universe, not sampling noise. This is the single clearest Phase 4 tuning
candidate you flagged. Flat-base's bottleneck is more balanced
(`BASE_TOO_DEEP` 40.5% vs `SETUP_VALID_NO_BREAKOUT` 57.8% of in-uptrend) —
less obviously "one threshold is wrong" than bull-flag's case. **Not
touched here** — logged as a Phase 4 tuning candidate, tuning-split-only,
per the standing constraint.

## 4 — RR floor downgrade rate + expectancy by realized-RR bucket

Downgrade rate: **20% (1/5)** post-fix, down from **100% (5/5)** pre-fix
(see Context above).

Expectancy by realized RR, all patterned real trades (EXECUTE +
ALERT_WATCHLIST, n=156 — every real-category row is patterned now, since
B-8 already demotes no-pattern signals to MONITOR):

| RR bucket | n | win rate | avg return |
|---|---|---|---|
| < 1.0 | 8 | 50.0% | -0.51% |
| [1.0, 1.25) | 18 | 83.3% | 5.75% |
| [1.25, 2.0) | 79 | 78.5% | 6.53% |
| ≥ 2.0 | 51 | 62.7% | 6.72% |

Not a clean monotonic story: win rate actually *falls* as RR rises
(83.3% → 78.5% → 62.7%) while avg return rises slightly (5.75% → 6.53% →
6.72%) — the classic RR tradeoff (fewer, bigger wins at higher RR) rather
than "higher RR strictly better." The <1.0 bucket (n=8) is the one
genuinely weak segment, consistent with the RR floor's own design intent.
All buckets ≥1.0 look broadly similar and much stronger than <1.0 — some
support for the floor's placement at 1.25 being reasonable, though n=18
in the [1.0, 1.25) bucket means "the floor should be lower" isn't ruled
out either.

## 5 — Extended choke-point decomposition (score >= 65, episode level)

Gate 1's ceiling-attribution table, extended to the two gates Phase 2
added (RR floor, pattern requirement / MONITOR). Classification follows
`categorize()`'s actual internal precedence, not a naive top-to-bottom
reading of the 5 labels — **pattern requirement (MONITOR) is checked
first**, because in the real code a no-pattern signal is demoted to
MONITOR *before* the market/sector ceiling or RR floor are ever
consulted, so it would have stayed MONITOR regardless of what those would
have said. RR floor is checked before regime/sector because it only ever
fires on a pre-floor EXECUTE — i.e. exactly the population the ceiling
did *not* already block. See `tests/choke_point_decomposition.py`'s own
docstring for the full reasoning. Confirmed empirically: a score>=65 row
is always MONITOR/ALERT_WATCHLIST/EXECUTE, never AVOID (disqualifiers
always zero out confidence_score, so a disqualified row can never reach
65 in the first place).

| gate | N | win rate | gross expectancy | net expectancy |
|---|---|---|---|---|
| 1_regime_ceiling | 6 | 83.3% | 6.00% | 5.70% |
| 2_sector_ceiling | 12 | 75.0% | 4.39% | 4.09% |
| 3_rr_floor | 1 | 100.0% | 3.04% | 2.74% |
| 4_pattern_requirement (MONITOR) | 31 | 64.5% | 3.86% | 3.56% |
| 5_execute | 3 | 66.7% | 10.35% | 10.05% |

(N = 53 total score>=65 episodes; all populations except pattern_requirement
are under the n=20 low-sample threshold — flagged, not hidden.)

**This directly answers the question the decomposition was built to
answer.** Every blocked population — regime (5.7%), sector (4.09%), *and*
pattern-requirement/MONITOR (3.56%, the one population large enough to
trust, n=31) — shows real positive net expectancy, comfortably above
Gate 1's own 2.5%+ benchmark for "this capped population resembles
EXECUTE, not AVOID." None of them looks like a gate correctly screening
out weak signals; all three look like value being left on the table by
category boundaries, not by the underlying score. That is the "some
combination" / exposure-scaling answer, not "loosen gate X": the score
itself (>=65) is already doing the real discriminating work across
every one of these populations regardless of which single gate
happened to cap it.

## 6 — Unified scaled-exposure portfolio simulation

The choke-point decomposition (section 5) shows every blocked population
looking strong at the *episode* level -- but per-episode expectancy can't
be trusted alone (this is the second time that's been confirmed
explicitly: G1's own capped-vs-genuine finding needed the portfolio
simulator too before it was actionable). `backtesting/portfolio_simulator.py`'s
new `make_unified_scaling_policy()` trades any score>=65 episode
regardless of which gate capped it, at gate-specific risk (EXECUTE/
RR-floor at full risk, regime/sector-ceiling at half risk matching the
existing CAUTION precedent, MONITOR/pattern-requirement as a tunable
parameter with no Gate 1 precedent -- tested at both 0.5 and 0.75). Run
via `tests/run_gate2_unified_scaling.py`, 5 slots / 1% base risk, against
the existing best performer (`e_sector_aware_caution`) as baseline:

| policy | episodes deployed | slot utilization | max drawdown | CAGR | Calmar |
|---|---|---|---|---|---|
| e_sector_aware_caution (baseline) | 16 | 100.0% | -1.16% | 4.46% | 3.84 |
| unified_scaling (MONITOR@0.5) | **52** | 98.1% | -1.87% | 7.97% | **4.26** |
| unified_scaling (MONITOR@0.75) | 52 | 98.1% | -2.68% | 9.74% | 3.63 |

**MONITOR@0.5 clears the adoption bar as specified**: episodes deployed
more than tripled (16 → 52, actual starvation relief, not just a
theoretical one) while Calmar *improved* (3.84 → 4.26), not just held.
Drawdown did widen (-1.16% → -1.87%) but stays small in absolute terms,
and CAGR nearly doubled (4.46% → 7.97%) -- the extra episodes are
carrying their own weight at the portfolio level, not just adding
uncompensated variance.

**MONITOR@0.75 does not clear the bar.** Same 52 episodes deployed
(eligibility doesn't depend on the risk weight, only sizing does, so
n_taken is identical for both variants -- 53 total score>=65 episodes,
minus 1 missed to slot exhaustion), higher CAGR (9.74%) but Calmar
*drops below baseline* (3.63 < 3.84) because drawdown (-2.68%) grew
faster than CAGR did. Reported honestly per the pre-agreed rule: this
is exactly the "drawdown worsens materially enough to matter" case for
the 0.75 weight specifically, even though the 0.5 weight on the same
underlying population does not have this problem.

**Recommendation given this data**: `unified_scaling` at MONITOR@0.5 is
the candidate for run #3 consideration; MONITOR@0.75 is a documented
negative result, not a second viable option. Both are n=52 episodes
total (up from EXECUTE's own n=3-4) -- a real improvement in evidence
volume, but still well short of the kind of sample size that would make
this a confident production decision on its own; this is "worth carrying
into run #3," not "proven."

## What did NOT change

`data/backtest_results.csv` (run #1) and `data/backtest_results_run2_raw.csv`
(run #2's original, buggy output) are both untouched — confirmed via
`git status`/`git diff`. The corrected file
(`data/backtest_results_run2_corrected.csv`) is a new, separately-named
artifact.
