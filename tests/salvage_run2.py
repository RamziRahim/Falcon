"""
Falcon — Run #2 Salvage Script (2.2 two-low-model fix)
Run from project root: python tests/salvage_run2.py

Corrects run #2's RR-approx-1.0 bug (the measured-move target and the
stop were priced off the SAME structural low, forcing reward:risk toward
1.0 whenever the stop was unclamped -- see
decision_engine/leadership_decision_engine.py's get_entry_target_stop()
docstring for the full two-low-model fix) WITHOUT re-running the full
~11-hour replay.

Only rows whose stop was actually priced off a real pattern low
(stop_provenance in {STRUCTURAL, STRUCTURAL_CLAMPED_TO_ATR_FLOOR,
STRUCTURAL_CLAMPED_TO_ATR_CEILING} -- 223 of run #2's 16,958 rows) could
possibly have been affected by the bug: every ATR_FALLBACK_* row (no
pattern, or a missing/nonsensical structural low) used the identical
flat-ATR formula before and after the fix, so those ~16,735 rows are
carried over byte-for-byte, unchanged. For the 223 affected rows, this
re-runs ONLY per-ticker pattern detection (indicator_calculator +
analyze_ticker, against the truncated cached data/technical/*.parquet
history through entry_date) -- not the expensive universe-wide RS/sector
scoring, which score/market_regime_verdict/sector_health_verdict/
confidence_score never depended on the buggy geometry and so don't need
recomputing at all.

Category correction: the RR floor (categorize()'s min_reward_risk check)
only ever downgrades a PRE-FLOOR "EXECUTE" to "ALERT_WATCHLIST" -- so:
  - AVOID rows: category is untouched by definition (the AVOID branch in
    categorize() returns before any pricing happens at all); only the
    hypothetical stop/target/RR/outcome are corrected, for the AVOID-
    outcome monotonicity check.
  - ALERT_WATCHLIST rows WITHOUT "RR_BELOW_FLOOR" in caps_applied: were
    already ALERT_WATCHLIST before the RR check ever ran (score-based, or
    ceiling-capped) -- correcting RR cannot change that, by construction.
  - ALERT_WATCHLIST rows WITH "RR_BELOW_FLOOR": pre-floor category WAS
    EXECUTE -- re-evaluated against the corrected RR: promoted back to
    EXECUTE if the corrected RR now clears MIN_REWARD_RISK, otherwise
    stays ALERT_WATCHLIST (RR_BELOW_FLOOR kept).

Outcomes are genuinely re-measured (measure_forward_outcome) against the
corrected stop/target and the ticker's full cached history -- NOT just a
post-hoc category relabel, since the affected rows' original exit_date/
exit_price/exit_reason/return_pct were all measured against the wrong
(buggy) geometry.

Writes data/backtest_results_run2_corrected.csv -- does NOT touch
data/backtest_results.csv (run #1) or data/backtest_results_run2_raw.csv
(run #2's original, buggy output), both left exactly as they are.
"""
import sys
sys.path.insert(0, ".")

import pandas as pd

from technical_analysis.indicator_calculator import indicator_calculator
from technical_analysis.pattern_engine import analyze_ticker, build_pattern_row_fields
from scoring.relative_volume import calculate as calculate_relative_volume
from decision_engine.candidate_assembler import assemble_pattern_details
from decision_engine.leadership_decision_engine import get_entry_target_stop
from backtesting.outcome_measurement import measure_forward_outcome
from backtesting.portfolio_simulator import policy_sector_aware_caution
from config import MIN_REWARD_RISK

RAW_PATH = "data/backtest_results_run2_raw.csv"
CORRECTED_PATH = "data/backtest_results_run2_corrected.csv"

# The only provenances whose stop/target actually depended on the pre-fix
# buggy same-low formula. Everything else (ATR_FALLBACK_NO_PATTERN,
# ATR_FALLBACK_NO_STRUCTURAL_LOW/NO_PROXIMAL_LOW) computed an identical
# flat-ATR result both before and after the fix.
AFFECTED_PROVENANCES = {
    "STRUCTURAL", "STRUCTURAL_CLAMPED_TO_ATR_FLOOR", "STRUCTURAL_CLAMPED_TO_ATR_CEILING",
}

ENTRY_PRICE_MISMATCH_TOLERANCE = 0.01


def _truncate(df: pd.DataFrame, as_of_date: pd.Timestamp) -> pd.DataFrame:
    ordered = df.sort_values("Date").reset_index(drop=True)
    return ordered[ordered["Date"] <= as_of_date].reset_index(drop=True)


def _load_history(ticker: str) -> pd.DataFrame:
    df = pd.read_parquet(f"data/technical/{ticker}.parquet")
    df["Date"] = pd.to_datetime(df["Date"])
    return df.sort_values("Date").reset_index(drop=True)


def _reprice(ticker: str, entry_date: pd.Timestamp, pattern_used: str, history_cache: dict) -> tuple[dict, pd.DataFrame]:
    """Re-runs detection ONLY (indicator_calculator + analyze_ticker,
    against this ticker's own truncated cached history) -- not the
    universe-wide RS/sector scoring build_scored_universe_as_of() does,
    which none of this depends on."""
    if ticker not in history_cache:
        history_cache[ticker] = _load_history(ticker)
    full_history = history_cache[ticker]
    truncated = _truncate(full_history, entry_date)

    enriched = indicator_calculator.calculate(truncated)
    enriched = calculate_relative_volume(enriched)
    analysis = analyze_ticker(enriched)
    pattern_row = {**enriched.iloc[-1].to_dict(), **build_pattern_row_fields(analysis)}
    pattern_details = assemble_pattern_details(pattern_row)
    best_result = pattern_details.get(pattern_used)

    candidate = {"Close": pattern_row["Close"], "ATR_14": pattern_row.get("ATR_14")}
    ets = get_entry_target_stop(candidate, pattern_used, best_result)
    return ets, full_history


def main():
    raw = pd.read_csv(RAW_PATH)
    raw["entry_date"] = pd.to_datetime(raw["entry_date"])

    affected_mask = raw["stop_provenance"].isin(AFFECTED_PROVENANCES)
    print(f"Total rows: {len(raw)}; affected by the buggy same-low geometry: {affected_mask.sum()}")

    corrected = raw.copy()
    corrected["proximal_low"] = pd.NA

    history_cache: dict = {}
    mismatches = []
    promoted_to_execute = 0
    stayed_capped = 0

    affected_idx = raw.index[affected_mask]
    for n, idx in enumerate(affected_idx, start=1):
        row = raw.loc[idx]
        ticker, entry_date, pattern_used = row["ticker"], row["entry_date"], row["pattern_used"]

        ets, full_history = _reprice(ticker, entry_date, pattern_used, history_cache)

        if abs(ets["entry"] - row["entry_price"]) > ENTRY_PRICE_MISMATCH_TOLERANCE:
            mismatches.append((ticker, str(entry_date.date()), ets["entry"], row["entry_price"]))

        entry_price, stop_loss, target = ets["entry"], ets["stop_loss"], ets["target"]
        reward_risk = (
            (target - entry_price) / (entry_price - stop_loss)
            if (entry_price - stop_loss) > 0 else None
        )

        caps_list = [c for c in str(row["caps_applied"]).split(",") if c and c != "nan"]

        new_category = row["category"]
        if row["category"] != "AVOID":
            if "RR_BELOW_FLOOR" in caps_list:
                # Pre-floor category was EXECUTE -- re-evaluate against
                # the corrected RR.
                if reward_risk is not None and reward_risk >= MIN_REWARD_RISK:
                    new_category = "EXECUTE"
                    caps_list = [c for c in caps_list if c != "RR_BELOW_FLOOR"]
                    promoted_to_execute += 1
                else:
                    new_category = "ALERT_WATCHLIST"
                    stayed_capped += 1
            # else: already ALERT_WATCHLIST before the RR check ever ran
            # (score-based, or ceiling-capped) -- unaffected by RR either way.

        outcome = measure_forward_outcome(
            entry_date=entry_date,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target=target,
            full_history=full_history,
            max_holding_days=ets["max_holding_days"],
        )

        decision_like = {
            "category": new_category,
            "confidence_score": row["confidence_score"],
            "market_regime_verdict": row["market_regime_verdict"],
            "sector_health_verdict": row["sector_health_verdict"],
        }
        recommended_risk_fraction = (
            None if row["category"] == "AVOID" else policy_sector_aware_caution(decision_like)
        )

        corrected.at[idx, "entry_price"] = entry_price
        corrected.at[idx, "category"] = new_category
        corrected.at[idx, "exit_date"] = outcome["exit_date"]
        corrected.at[idx, "exit_price"] = outcome["exit_price"]
        corrected.at[idx, "exit_reason"] = outcome["exit_reason"]
        corrected.at[idx, "return_pct"] = outcome["return_pct"]
        corrected.at[idx, "days_held"] = outcome["days_held"]
        corrected.at[idx, "target_pct"] = ((target - entry_price) / entry_price) * 100
        corrected.at[idx, "stop_pct"] = ((entry_price - stop_loss) / entry_price) * 100
        corrected.at[idx, "stop_provenance"] = ets["stop_provenance"]
        corrected.at[idx, "target_provenance"] = ets["target_provenance"]
        corrected.at[idx, "reward_risk"] = reward_risk
        corrected.at[idx, "proximal_low"] = ets["proximal_low"]
        corrected.at[idx, "caps_applied"] = ",".join(caps_list)
        corrected.at[idx, "recommended_risk_fraction"] = recommended_risk_fraction

        if n % 50 == 0 or n == len(affected_idx):
            print(f"  Repriced {n}/{len(affected_idx)}...")

    print(f"\nPromoted ALERT_WATCHLIST(RR-capped) -> EXECUTE: {promoted_to_execute}")
    print(f"Stayed ALERT_WATCHLIST (still RR-capped after correction): {stayed_capped}")

    if mismatches:
        print(f"\nWARNING: {len(mismatches)} entry-price mismatches (unexpected detection drift):")
        for m in mismatches[:10]:
            print(f"  {m}")
    else:
        print("\nNo entry-price mismatches -- re-detection agrees with run #2's recorded entries.")

    # entry_date was parsed to Timestamp up front (for truncation/lookup);
    # exit_date is a mix of the original CSV's plain "YYYY-MM-DD" strings
    # (untouched rows) and freshly-assigned Timestamps (repriced rows,
    # from measure_forward_outcome()'s own full_history["Date"] column) --
    # normalize both to the same plain-string format before writing, or
    # a mixed-dtype column round-trips inconsistently (Timestamps pick up
    # a " 00:00:00" suffix plain strings don't have).
    corrected["entry_date"] = corrected["entry_date"].dt.strftime("%Y-%m-%d")
    corrected["exit_date"] = pd.to_datetime(corrected["exit_date"]).dt.strftime("%Y-%m-%d")

    corrected.to_csv(CORRECTED_PATH, index=False)
    print(f"\nCorrected results saved -> {CORRECTED_PATH} ({len(corrected)} rows)")
    print(f"\nCorrected category counts:\n{corrected['category'].value_counts(dropna=False)}")


if __name__ == "__main__":
    main()
