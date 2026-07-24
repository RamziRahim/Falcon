"""
Falcon — Extended Choke-Point Decomposition (post-hoc, corrected run #2)
Run from project root: python tests/choke_point_decomposition.py

Extends Gate 1's ceiling-attribution table (backtesting/backtest_runner.py's
aggregate_ceiling_attribution/_ceiling_cause) to cover the two gates Phase 2
added (RR floor, pattern requirement / MONITOR), for every EPISODE whose
founding signal scored >= 65 in data/backtest_results_run2_corrected.csv.
Pure post-processing -- no replay, no engine change.

Classification (mutually exclusive, exhaustive over the score>=65
population -- see the module-level comment below for why this ordering,
which follows categorize()'s ACTUAL internal precedence, not a
top-to-bottom reading of the 5 labels):

  5_execute          category == EXECUTE -- passed every gate.
  4_pattern_requirement  category == MONITOR -- no confirmed pattern
                       (B-8). In categorize()'s real control flow this
                       demotion happens BEFORE the market/sector ceiling
                       or the RR floor are ever consulted, so a MONITOR
                       row would have stayed MONITOR regardless of what
                       the regime/sector/RR would have said -- this is
                       the correct "first blocker," not a leftover label
                       after checking regime/sector/RR first.
  3_rr_floor         category == ALERT_WATCHLIST with "RR_BELOW_FLOOR" in
                       caps_applied -- pre-floor category WAS EXECUTE
                       (ceiling didn't block it), the corrected RR did.
  1_regime_ceiling   category == ALERT_WATCHLIST, no RR_BELOW_FLOOR,
                       market_regime_verdict == "UNFAVORABLE" -- blocks
                       regardless of sector (get_ceiling()'s own rule).
  2_sector_ceiling   category == ALERT_WATCHLIST, no RR_BELOW_FLOOR,
                       market NOT UNFAVORABLE (i.e. CAUTION) -- sector
                       verdict is what actually capped it (CAUTION+STRONG
                       would NOT have capped, per get_ceiling()).

A score>=65 row can never be AVOID: categorize()'s disqualifier branch
always sets confidence_score=0.0, and the score-based cascade only
produces AVOID for score<40 -- so the population here is strictly
{MONITOR, ALERT_WATCHLIST, EXECUTE}, confirmed empirically below too.

Episode-level, not raw-signal-level, per the request -- episodes absorb
the same resampling-duplicate-signal artifact Gate 1's own ceiling
attribution collapsed for. episode_builder.py's own output doesn't carry
caps_applied/reward_risk (out of its original run #1 scope), so this
re-attaches them via a merge back onto the corrected CSV's founder rows
(ticker + episode_start_date == entry_date) -- still pure post-processing,
no re-derivation of anything episode_builder.py didn't already compute.
"""
import sys
sys.path.insert(0, ".")

import pandas as pd

from backtesting.backtest_runner import _group_stats
from backtesting.episode_builder import build_episodes

CORRECTED_PATH = "data/backtest_results_run2_corrected.csv"
SCORE_THRESHOLD = 65.0

GATE_ORDER = [
    "1_regime_ceiling", "2_sector_ceiling", "3_rr_floor",
    "4_pattern_requirement", "5_execute",
]


def _classify_gate(row) -> str:
    if row["category"] == "EXECUTE":
        return "5_execute"
    if row["category"] == "MONITOR":
        return "4_pattern_requirement"
    # ALERT_WATCHLIST, score >= 65 -- mutually exclusive per categorize()'s
    # real control flow: RR floor only ever fires on a pre-floor EXECUTE,
    # i.e. exactly the population the ceiling did NOT already block.
    caps = str(row.get("caps_applied") or "")
    if "RR_BELOW_FLOOR" in caps:
        return "3_rr_floor"
    if row["market_regime_verdict"] == "UNFAVORABLE":
        return "1_regime_ceiling"
    return "2_sector_ceiling"


def main():
    trades = pd.read_csv(CORRECTED_PATH)
    trades["entry_date"] = pd.to_datetime(trades["entry_date"])

    episodes = build_episodes(trades)

    # Re-attach founder-level fields episode_builder.py's own schema
    # doesn't carry (caps_applied, needed for the RR-floor split) by
    # joining back on (ticker, entry_date == episode_start_date) -- exact
    # match by construction, since episode_start_date IS the founder's
    # own entry_date (episode_builder.py's _flush()).
    founder_fields = trades[["ticker", "entry_date", "caps_applied"]].rename(
        columns={"entry_date": "episode_start_date"}
    )
    episodes = episodes.merge(founder_fields, on=["ticker", "episode_start_date"], how="left")

    qualifying = episodes[episodes["confidence_score"] >= SCORE_THRESHOLD].copy()
    print(f"Episodes with founder confidence_score >= {SCORE_THRESHOLD}: {len(qualifying)} "
          f"(of {len(episodes)} total episodes)")

    unexpected_categories = set(qualifying["category"]) - {"MONITOR", "ALERT_WATCHLIST", "EXECUTE"}
    if unexpected_categories:
        print(f"WARNING: unexpected categories in score>=65 population: {unexpected_categories}")

    qualifying["gate"] = qualifying.apply(_classify_gate, axis=1)

    print("\n" + "=" * 78)
    print("  EXTENDED CHOKE-POINT DECOMPOSITION (score >= 65, episode level)")
    print("=" * 78)
    print(f"\nscored >= 65 total: N = {len(qualifying)}\n")

    for gate in GATE_ORDER:
        sub = qualifying[qualifying["gate"] == gate]
        if sub.empty:
            print(f"  {gate}: N = 0")
            continue
        gross = _group_stats(gate, sub, "gross_return_pct")
        net = _group_stats(gate, sub, "net_return_pct")
        flag = "  [LOW SAMPLE SIZE]" if gross["sample_size"] < 20 else ""
        print(
            f"  {gate}: N = {gross['sample_size']}, win_rate={gross['win_rate_pct']}%, "
            f"gross_expectancy={gross['expectancy_pct']}%, net_expectancy={net['expectancy_pct']}%{flag}"
        )

    print("\n" + "=" * 78)
    qualifying.to_csv("data/gate2_chokepoint_episodes.csv", index=False)
    print("Per-episode detail saved -> data/gate2_chokepoint_episodes.csv")


if __name__ == "__main__":
    main()
