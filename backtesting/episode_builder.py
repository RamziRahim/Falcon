"""
===============================================================================
Falcon AI Swing Trading Platform — Episode Builder (Part I-1)
===============================================================================
Script      : episode_builder.py
Package     : Backtesting

Run #1's raw trade log (data/backtest_results.csv, produced by
tests/run_backtest.py -> backtesting.backtest_runner.run_backtest()) has one
row per *sampled signal*, not one row per *trade a real portfolio would have
taken*. Because replay samples every ticker every 5 trading days regardless
of whether a prior signal's position is still theoretically open, the same
underlying trade idea for one ticker routinely re-fires several times while
its own outcome window (entry_date -> exit_date) hasn't closed yet -- e.g.
ATHERENERG.NS produced 24 raw rows in run #1 that collapse to 16 real
episodes once overlapping windows are absorbed. This module does that
collapse. It is a pure post-processor: it reads the existing CSV/DataFrame
and never re-runs replay_decision_as_of() or categorize().

Run #1 raw schema (data/backtest_results.csv, verified via
`pd.read_csv(...).dtypes` against the actual 1076-row file -- see
backtesting/backtest_runner.py::run_backtest()'s trade_records.append(...)
for the source of truth):

    ticker                  object   NSE ticker, e.g. "AIAENG.NS"
    entry_date              object   "YYYY-MM-DD" string (parse with pd.to_datetime)
    entry_price             float64
    category                object   "EXECUTE" | "ALERT_WATCHLIST"
                                      (run_backtest() only records these two --
                                      AVOID/no-entry signals are filtered out
                                      before a trade_record is ever appended)
    pattern_used            object   pattern field name (e.g.
                                      "is_vcp_breakout") or NaN if no pattern
                                      fired for this signal
    market_regime_verdict   object   "FAVORABLE" | "CAUTION" | "UNFAVORABLE"
    sector_health_verdict   object   "STRONG" | "NEUTRAL" | "WEAK"
    exit_date               object   "YYYY-MM-DD" string
    exit_price              float64
    exit_reason             object   "TARGET_HIT" | "STOP_HIT" | "TIME_EXIT"
    return_pct              float64  % move from entry_price to exit_price
    days_held               int64
    target_pct              float64  planned distance to target, % of entry_price
    stop_pct                float64  planned distance to stop, % of entry_price
    confidence_score        float64  0-100, from categorize()'s compute_score()
    caps_applied            float64  NaN for every row in run #1 -- replay_engine.py
                                      always calls categorize() with
                                      disable_fundamental_signals=True, which
                                      skips INDEPENDENT_CAPS entirely (see
                                      leadership_decision_engine.py), so the
                                      comma-joined string this column holds
                                      in memory is always "" and round-trips
                                      through CSV as NaN. Never a real signal
                                      of a fundamentals-based cap in this
                                      dataset -- market_regime_verdict /
                                      sector_health_verdict are the only
                                      ceiling causes that can appear here.
===============================================================================
"""
from __future__ import annotations

import pandas as pd

from config import ROUND_TRIP_COST_PCT

EPISODE_COLUMNS = [
    "ticker",
    "episode_start_date",
    "episode_end_date",
    "category",
    "category_changes",
    "pattern_used",
    "market_regime_verdict",
    "sector_health_verdict",
    "confidence_score",
    "exit_reason",
    "days_held",
    "gross_return_pct",
    "net_return_pct",
    "r_multiple",
    "n_signals_absorbed",
]


def _build_ticker_episodes(ticker_trades: pd.DataFrame) -> list[dict]:
    """
    ticker_trades: every raw signal row for a single ticker, already sorted
    by entry_date ascending.

    An episode is founded by the first signal seen for this ticker (or the
    first signal after the previous episode's window closed). Every
    subsequent signal whose entry_date falls strictly before the founding
    signal's exit_date is "absorbed" -- it's a renewed/repeated signal on a
    position a real single-position-per-ticker portfolio would already be
    holding, not a separate trade. Absorption never extends the episode's
    own outcome window: the episode's return/exit_reason/days_held are
    always the FOUNDING signal's actual measured outcome (that's the trade
    that would genuinely have been taken), never the absorbed signals'.

    entry_date == founder's exit_date is treated as a NEW episode (not
    absorbed) -- by that date the founding position has already closed per
    its own measured outcome, so the ticker is flat and free to re-enter.
    """
    episodes = []
    founder = None
    absorbed_categories: set[str] = set()
    n_absorbed = 0

    def _flush():
        if founder is None:
            return
        gross = founder["return_pct"]
        net = gross - ROUND_TRIP_COST_PCT * 100
        stop_pct = founder["stop_pct"]
        r_multiple = (net / stop_pct) if stop_pct not in (0, None) and pd.notna(stop_pct) else float("nan")
        changes = sorted(absorbed_categories | {founder["category"]})
        episodes.append({
            "ticker": founder["ticker"],
            "episode_start_date": founder["entry_date"],
            "episode_end_date": founder["exit_date"],
            "category": founder["category"],
            "category_changes": ",".join(changes) if len(changes) > 1 else founder["category"],
            "pattern_used": founder["pattern_used"],
            "market_regime_verdict": founder["market_regime_verdict"],
            "sector_health_verdict": founder["sector_health_verdict"],
            "confidence_score": founder["confidence_score"],
            "exit_reason": founder["exit_reason"],
            "days_held": founder["days_held"],
            "gross_return_pct": gross,
            "net_return_pct": net,
            "r_multiple": r_multiple,
            "n_signals_absorbed": n_absorbed,
        })

    for _, row in ticker_trades.iterrows():
        if founder is None:
            founder = row
            n_absorbed = 1
            absorbed_categories = set()
            continue

        if row["entry_date"] < founder["exit_date"]:
            n_absorbed += 1
            absorbed_categories.add(row["category"])
        else:
            _flush()
            founder = row
            n_absorbed = 1
            absorbed_categories = set()

    _flush()
    return episodes


def build_episodes(trades: pd.DataFrame) -> pd.DataFrame:
    """
    Collapses run #1's raw per-signal trade log into one row per distinct
    trade episode per ticker (see module docstring / _build_ticker_episodes
    for the absorption rule). Post-processor only -- operates on the
    DataFrame already produced by run_backtest() / loaded from
    data/backtest_results.csv, never re-runs replay.
    """
    if trades.empty:
        return pd.DataFrame(columns=EPISODE_COLUMNS)

    working = trades.copy()
    working["entry_date"] = pd.to_datetime(working["entry_date"])
    working["exit_date"] = pd.to_datetime(working["exit_date"])
    working = working.sort_values(["ticker", "entry_date"])

    all_episodes = []
    for _, ticker_trades in working.groupby("ticker", sort=False):
        all_episodes.extend(_build_ticker_episodes(ticker_trades))

    episodes = pd.DataFrame(all_episodes, columns=EPISODE_COLUMNS)
    return episodes.sort_values("episode_start_date").reset_index(drop=True)
