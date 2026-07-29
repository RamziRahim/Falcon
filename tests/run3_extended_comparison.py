"""
Falcon — Run #3 Extended Comparison
Run from project root: python tests/run3_extended_comparison.py

Three follow-ups to run3_portfolio_simulation.py's first read, all pure
post-processing (no replay):

1. Corrected net-vs-net Falcon/NIFTY comparison. The prior report
   compared Falcon's r_multiple-based (already net-of-cost, see
   episode_builder.py's own docstring) portfolio return against NIFTY
   buy-and-hold's GROSS total_return_pct, not its net_return_pct --
   an inconsistent comparison, caught on direct question, not caught
   before reporting. Fixed here.

2. Naive momentum baseline (backtesting/baselines.py's
   naive_momentum_topdecile_baseline(): top-decile trailing 6-month
   return, above-50DMA trend filter) on the SAME 496-ticker universe and
   window, through the SAME portfolio simulator (5 slots). Sized flat
   (risk_fraction=1.0 always) since a scoreless momentum baseline has no
   MONITOR/EXECUTE/ceiling concept for make_unified_scaling_policy() to
   key off of -- r_multiple computed via the same REFERENCE_STOP_PCT
   convention tests/run_gate1_extension.py established (this run's own
   actual median stop_pct, not run #1's old 5.93 value), so a momentum
   trade is sized as if it carried a typical Falcon signal's stop
   distance, keeping the comparison apples-to-apples with Falcon's own
   r_multiple-based equity curve.

3. Slot-count sensitivity: same Falcon episode log at 7 and 8 concurrent
   slots (vs. 5), to see whether the 60-episodes-missed/65.7% slot
   utilization from the first read represents real left-on-the-table
   value or would have raised drawdown by admitting more concurrent,
   correlated positions.
"""
import sys
sys.path.insert(0, ".")

import glob
import os

import pandas as pd

from backtesting.backtest_runner import _sampled_dates_for_ticker
from backtesting.baselines import naive_momentum_topdecile_baseline, nifty_buy_hold
from backtesting.episode_builder import build_episodes
from backtesting.portfolio_simulator import make_unified_scaling_policy, simulate_portfolio
from scoring.benchmark import get_benchmark_history

RUN3_PATH = "data/backtest_results_run3_wide_universe.csv"
START_DATE = pd.Timestamp("2024-07-25")
END_DATE = pd.Timestamp("2026-07-25")
N_SLOTS = 5
BASE_RISK_PCT = 1.0


def _calmar(cagr_pct: float, max_drawdown_pct: float) -> float:
    return round(cagr_pct / abs(max_drawdown_pct), 2) if max_drawdown_pct != 0 else 0.0


def _load_universe_histories() -> dict[str, pd.DataFrame]:
    universe = {}
    for path in sorted(glob.glob("data/technical/*.parquet")):
        ticker = os.path.basename(path).replace(".parquet", "")
        df = pd.read_parquet(path)
        df["Date"] = pd.to_datetime(df["Date"])
        if df["Date"].dt.tz is not None:
            df["Date"] = df["Date"].dt.tz_localize(None)
        df = df.sort_values("Date").reset_index(drop=True)
        if len(df) >= 250:
            universe[ticker] = df
    return universe


def main():
    trades = pd.read_csv(RUN3_PATH, low_memory=False)
    trades["entry_date"] = pd.to_datetime(trades["entry_date"])
    episodes = build_episodes(trades)
    founder_fields = trades[["ticker", "entry_date", "caps_applied"]].rename(
        columns={"entry_date": "episode_start_date"}
    )
    episodes = episodes.merge(founder_fields, on=["ticker", "episode_start_date"], how="left")

    falcon_result = simulate_portfolio(
        episodes, make_unified_scaling_policy(0.5), n_slots=N_SLOTS, base_risk_pct=BASE_RISK_PCT,
    )
    falcon_total_return = round(falcon_result["final_equity"] - 100.0, 2)
    falcon_calmar = _calmar(falcon_result["cagr_pct"], falcon_result["max_drawdown_pct"])

    # ---------------------------------------------------------------------
    # 1. Corrected net-vs-net NIFTY comparison
    # ---------------------------------------------------------------------
    benchmark_history = get_benchmark_history()
    benchmark_history["Date"] = pd.to_datetime(
        benchmark_history["Date"] if "Date" in benchmark_history.columns else benchmark_history.index
    ).dt.tz_localize(None)
    nifty = nifty_buy_hold(benchmark_history, START_DATE, END_DATE)
    # nifty_buy_hold()'s own cagr_pct/calmar fields are computed from the
    # GROSS end/start price, not net_return_pct -- recompute a genuinely
    # net-of-cost CAGR/Calmar for the apples-to-apples comparison, rather
    # than mixing a net total return with a gross CAGR.
    nifty_years = (END_DATE - START_DATE).days / 365.25
    nifty_net_cagr = round(
        ((1 + nifty["net_return_pct"] / 100) ** (1 / nifty_years) - 1) * 100, 2
    ) if nifty_years > 0 else 0.0
    nifty_net_calmar = _calmar(nifty_net_cagr, nifty["max_drawdown_pct"])

    falcon_return_str = f"{falcon_total_return}%"
    falcon_dd_str = f"{falcon_result['max_drawdown_pct']}%"
    nifty_net_return_str = f"{nifty['net_return_pct']}%"
    nifty_dd_str = f"{nifty['max_drawdown_pct']}%"

    print("=" * 78)
    print("  1. CORRECTED NET-VS-NET COMPARISON (both figures net of round-trip cost)")
    print("=" * 78)
    print(f"{'metric':<20}{'Falcon (MONITOR@0.5)':<25}{'NIFTY buy-and-hold':<20}")
    print("-" * 65)
    print(f"{'Total return':<20}{falcon_return_str:<25}{nifty_net_return_str:<20}")
    print(f"{'Max drawdown':<20}{falcon_dd_str:<25}{nifty_dd_str:<20}")
    print(f"{'Calmar':<20}{falcon_calmar:<25}{nifty_net_calmar:<20}")
    print(
        f"\nConfirmed: Falcon's {falcon_total_return}% is already NET of the "
        f"{0.3}% round-trip cost -- episode_builder.py's r_multiple is built from "
        f"net_return_pct (gross - ROUND_TRIP_COST_PCT), and simulate_portfolio()'s "
        f"equity curve is built entirely from r_multiple. The prior report compared "
        f"this against NIFTY's GROSS total_return_pct ({nifty['total_return_pct']}%) "
        f"by mistake -- corrected NIFTY net figure is {nifty['net_return_pct']}%."
    )

    # ---------------------------------------------------------------------
    # 2. Momentum baseline through the same simulator
    # ---------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("  2. TOP-DECILE MOMENTUM BASELINE (126d lookback, above 50DMA) vs FALCON")
    print("=" * 78)

    universe_histories = _load_universe_histories()
    print(f"Universe loaded: {len(universe_histories)} tickers")

    ticker_sample_dates = {
        ticker: _sampled_dates_for_ticker(history, START_DATE, END_DATE, sample_every_n_days=5)
        for ticker, history in universe_histories.items()
    }
    sample_dates = sorted({d for dates in ticker_sample_dates.values() for d in dates})
    print(f"Sample dates: {len(sample_dates)} (same union-of-per-ticker-every-5-days convention as the replay)")

    momentum = naive_momentum_topdecile_baseline(
        universe_histories, sample_dates, lookback_days=126, max_holding_days=20, trend_filter_window=50,
    )
    print(f"Momentum raw signals generated: {len(momentum)}")

    # Data-integrity filter: data/technical/*.parquet's Close series has no
    # Adj Close at all -- confirmed directly (BAJFINANCE.NS: Rs 9,419 ->
    # Rs 938 overnight on 2025-06-16, a clean unadjusted stock split, not a
    # real -90% crash) that ~35% of the universe carries at least one
    # unadjusted-corporate-action discontinuity somewhere in its history.
    # Falcon's own real trades are barely exposed (2 of 459, ~0.4%, since a
    # real stop-loss exits before absorbing the full damage) and are NOT
    # refiltered here. This baseline has no stop at all, so it fully
    # absorbs whatever a >40%-single-day move does to it -- confirmed the
    # 197 exposed signals (1.9% of 10,504) averaged -64.3% return vs +0.9%
    # for the other 98.1%, i.e. the unfiltered result upstream of this
    # point is dominated by a data artifact, not real momentum performance.
    big_move_dates: dict[str, set] = {}
    for ticker, history in universe_histories.items():
        pct_change = history["Close"].pct_change().abs()
        hits = history.loc[pct_change[pct_change > 0.40].index, "Date"]
        if len(hits):
            big_move_dates[ticker] = set(pd.to_datetime(hits).dt.date)

    def _touches_big_move(row) -> bool:
        dates = big_move_dates.get(row["ticker"])
        if not dates:
            return False
        entry_d, exit_d = row["as_of_date"].date(), row["exit_date"].date()
        return any(entry_d <= d <= exit_d for d in dates)

    momentum["as_of_date"] = pd.to_datetime(momentum["as_of_date"])
    momentum["exit_date"] = pd.to_datetime(momentum["exit_date"])
    exposed_mask = momentum.apply(_touches_big_move, axis=1)
    print(f"Excluding {exposed_mask.sum()} signals ({exposed_mask.mean()*100:.1f}%) whose holding "
          f"window overlaps a suspected unadjusted corporate action")
    momentum = momentum[~exposed_mask].reset_index(drop=True)

    reference_stop_pct = trades["stop_pct"].median()
    print(f"REFERENCE_STOP_PCT (this run's own median stop_pct): {reference_stop_pct:.2f}%")

    # Same absorption episode_builder.build_episodes() applies to Falcon's
    # own raw signals: without it, a ticker whose momentum stays strong
    # across several consecutive 5-day-sampled dates gets re-picked over
    # and over, each re-pick landing as its OWN slot-contention candidate
    # -- not the single real position a portfolio would actually hold.
    # Caught by inspection before trusting the first (uncorrected) result:
    # 10,504 raw picks produced only 1.2% slot utilization at 5 slots,
    # meaning the vast majority were duplicate re-picks of positions
    # already open, not genuinely distinct opportunities competing for
    # capital the way Falcon's 115 real episodes do.
    momentum_trades = pd.DataFrame({
        "ticker": momentum["ticker"],
        "entry_date": pd.to_datetime(momentum["as_of_date"]),
        "exit_date": pd.to_datetime(momentum["exit_date"]),
        "category": "MOMENTUM",
        "pattern_used": None,
        "market_regime_verdict": "N/A",
        "sector_health_verdict": "N/A",
        "confidence_score": 100.0,
        "exit_reason": "TIME_EXIT",
        "days_held": (pd.to_datetime(momentum["exit_date"]) - pd.to_datetime(momentum["as_of_date"])).dt.days,
        "return_pct": momentum["return_pct"],  # gross -- build_episodes() subtracts cost itself
        "stop_pct": reference_stop_pct,
    })
    momentum_episodes = build_episodes(momentum_trades)
    print(f"Momentum episodes after absorption: {len(momentum_episodes)}")

    def _always_take_full_size(_episode) -> float:
        return 1.0

    momentum_result = simulate_portfolio(
        momentum_episodes, _always_take_full_size, n_slots=N_SLOTS, base_risk_pct=BASE_RISK_PCT,
    )
    momentum_total_return = round(momentum_result["final_equity"] - 100.0, 2)
    momentum_calmar = _calmar(momentum_result["cagr_pct"], momentum_result["max_drawdown_pct"])

    momentum_return_str = f"{momentum_total_return}%"
    momentum_dd_str = f"{momentum_result['max_drawdown_pct']}%"
    falcon_util_str = f"{falcon_result['slot_utilization_pct']}%"
    momentum_util_str = f"{momentum_result['slot_utilization_pct']}%"

    print(f"\n{'metric':<20}{'Falcon (MONITOR@0.5)':<25}{'Momentum (top-decile)':<20}")
    print("-" * 65)
    print(f"{'Total return':<20}{falcon_return_str:<25}{momentum_return_str:<20}")
    print(f"{'Max drawdown':<20}{falcon_dd_str:<25}{momentum_dd_str:<20}")
    print(f"{'Calmar':<20}{falcon_calmar:<25}{momentum_calmar:<20}")
    print(f"{'Episodes deployed':<20}{falcon_result['n_taken']:<25}{momentum_result['n_taken']:<20}")
    print(f"{'Slot utilization':<20}{falcon_util_str:<25}{momentum_util_str:<20}")

    # ---------------------------------------------------------------------
    # 3. Slot-count sensitivity (Falcon's own episode log, no replay needed)
    # ---------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("  3. SLOT-COUNT SENSITIVITY (Falcon MONITOR@0.5, same episode log)")
    print("=" * 78)
    print(f"{'n_slots':<10}{'n_taken':<10}{'missed':<10}{'utilization':<14}{'max_dd':<10}{'cagr':<10}{'calmar':<10}")
    for n_slots in (5, 7, 8):
        r = simulate_portfolio(episodes, make_unified_scaling_policy(0.5), n_slots=n_slots, base_risk_pct=BASE_RISK_PCT)
        c = _calmar(r["cagr_pct"], r["max_drawdown_pct"])
        util_str = f"{r['slot_utilization_pct']}%"
        dd_str = f"{r['max_drawdown_pct']}%"
        cagr_str = f"{r['cagr_pct']}%"
        print(f"{n_slots:<10}{r['n_taken']:<10}{r['n_missed_due_to_slots']:<10}"
              f"{util_str:<14}{dd_str:<10}{cagr_str:<10}{c:<10}")

    print("\n" + "=" * 78)

    comparison = pd.DataFrame([
        {"strategy": "Falcon (MONITOR@0.5)", "total_return_pct": falcon_total_return,
         "max_drawdown_pct": falcon_result["max_drawdown_pct"], "cagr_pct": falcon_result["cagr_pct"],
         "calmar": falcon_calmar, "n_taken": falcon_result["n_taken"]},
        {"strategy": "NIFTY buy-and-hold (net)", "total_return_pct": nifty["net_return_pct"],
         "max_drawdown_pct": nifty["max_drawdown_pct"], "cagr_pct": nifty_net_cagr,
         "calmar": nifty_net_calmar, "n_taken": None},
        {"strategy": "Momentum (top-decile, 126d, >50DMA)", "total_return_pct": momentum_total_return,
         "max_drawdown_pct": momentum_result["max_drawdown_pct"], "cagr_pct": momentum_result["cagr_pct"],
         "calmar": momentum_calmar, "n_taken": momentum_result["n_taken"]},
    ])
    comparison.to_csv("data/run3_extended_comparison.csv", index=False)
    print("Saved -> data/run3_extended_comparison.csv")


if __name__ == "__main__":
    main()
