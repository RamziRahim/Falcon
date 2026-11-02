# Step 2 pre-registration: refit the model on honest labels

**Written 2026-11-02, after run #5 and variant B failed and before any refit was
fitted or scored.** Same rule as `docs/run5_preregistration.md`: never edit this file
after the result is seen. Add dated notes below instead.

## Why

Model v1 (`models/consolidation_quality_v1.json`) decides EXECUTE vs ALERT_WATCHLIST
for pattern-confirmed setups. It was fitted on run #3's labels, which were measured with
the pivot fill that run #4 exposed as impossible. So it learned which setups "win" when
you get an impossible price.

Run #5 measured the same setups with honest next-open fills. Variant B also failed.
This is step 2 of the pre-registered plan: re-fit on honest labels using the existing
tuning/validation split, and judge on the validation half only.

## Data

- **Run #5b:** `tests/run_backtest.py` with `ENTRY_MODEL = ENTRY_NEXT_OPEN`, same window,
  universe and model v1 as run #5. Its only difference is that it records the model's
  inputs (`mf_*` columns) and `predicted_p` on every signal row.
  - It must reproduce run #5's rows exactly. The script checks this and stops if not.
  - Recorded inputs reproduce v1's `predicted_p` exactly (verified on a sample, max
    difference 0.0). So the refit uses what `categorize()` actually saw, not a separately
    recomputed feature set.
- **Population:**
  - Built with `build_episodes()` from the full run #5b log (as for v1).
  - Includes EXECUTE + ALERT_WATCHLIST episodes whose model inputs are all present.
  - This population does not depend on the model: it is every pattern-confirmed setup
    above the score floor. ALERT_WATCHLIST includes RR-capped and model-rejected setups.
- **Label:** `net_return_pct > 0`, after the 0.3% round-trip cost, under next-open fills.

## Fit (identical specification to v1, no choices)

- **Features, baselines, standardisation:** exactly
  `tests/run_v2_calibration_full.py`'s `_build_design_matrix()`. That is 11 numeric
  features, `rs_line_new_high`, and the regime / sector / pattern / MACD dummies.
- **Training data:** tuning half only, episode start ≤ **2025-09-21** (v1's split).
- **EXECUTE cutoff:** v1's Reading A rule, on tuning predictions only. Take quintiles; the
  cutoff is the p_min of the lowest quintile such that it and every quintile above it beat
  the tuning base rate.
- **No feature selection, regularisation, alternative cutoffs or second tries.**

## Judgement (validation half only, unchanged scorecard)

- Validation-half signal rows (entry after 2025-09-21) are re-labelled with the new
  model. A row is EXECUTE iff all of these hold:
  - p ≥ cutoff;
  - no cap other than the RR caps;
  - reward:risk is present and ≥ `MIN_REWARD_RISK`.
- That replicates `categorize()`. As a self-check, re-labelling with v1 must reproduce
  run #5's categories exactly, or the script stops.
- Judged by `tests/evaluate_backtest_run.py` on those rows, unchanged. All six checks must
  pass, as before (beat Nifty by ≥10pp, trade t ≥ 2, alpha t ≥ 2, top-3 < 50% of profit,
  both halves profitable, ≥ 99% achievable fills).

## Outcomes, decided now

- **The fit fails or doesn't converge, no quintile beats the base rate, or no validation
  trades result:** step 2 FAILS.
- **All six checks pass:** "edge demonstrated on held-out data", still only a backtest. The
  next step is paper trading with `v2_honest`, and only then could
  `config.ACTIVE_MODEL_VERSION` change.
- **Any check fails:** step 2 FAILS. Per the run #5 pre-registration, the Leadership
  breakout strategy is then treated as **unproven**, and the next work is a redesign. One
  candidate is the ALERT_WATCHLIST/MONITOR hypothesis recorded on 2026-11-01, tested on
  data the system hasn't seen.

## Known weakness, stated up front

The tuning half will probably contain only about 100–150 episodes for about 20
parameters, which is fewer than v1's 169. The fit may be unstable, and the validation half
may contain few trades, so the scorecard may fail for lack of power alone. That is
accepted. The point of this step is to apply the pre-registered rule honestly, not to
engineer a pass.
