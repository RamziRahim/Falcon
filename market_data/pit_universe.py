"""
===============================================================================
Falcon AI Swing Trading Platform — Point-in-Time Universe from NSE Bhavcopies
===============================================================================
Script      : pit_universe.py
Package     : Market Data

Survivorship-bias-free history for research on 2019-2024. data/technical/
only holds stocks that are in TODAY's Nifty 500, so a test on an older window
silently drops every company that later collapsed, merged or was delisted.
This module rebuilds, from NSE's whole-market daily bhavcopies
(tests/download_bhavcopies.py):

1. ENTITIES. A company is followed across symbol renames (same ISIN, new
   symbol) and ISIN changes (face-value splits issue a new ISIN under the
   same symbol) by linking every (symbol, ISIN) pair seen on the same day
   into one connected component.

2. ADJUSTED PRICES. NSE publishes each day's PrevClose already adjusted for
   that day's corporate actions (split, bonus, rights). So
   factor_t = PrevClose_t / Close_(t-1) is the exact adjustment factor, with
   no need to parse corporate-action text. Prices before t are multiplied by
   it (volume divided), latest first. Factors within ADJUST_TOLERANCE of 1
   are rounding noise and ignored.

3. MONTHLY UNIVERSE. At each month end, the 500 most liquid stocks, ranked
   by median daily traded value over the previous LOOKBACK_DAYS sessions.
   Only stocks trading in the normal EQ series on that date, and that traded
   on at least MIN_ACTIVE_SHARE of those sessions, are eligible. This is a
   rule-based stand-in for the Nifty 500 (which also ranks by size and
   liquidity), built only from data available on that date.

4. EXIT DATES. last_date per entity: a stock that stops appearing has
   delisted, merged or been suspended. A backtest must exit it at its last
   close rather than silently dropping it.
===============================================================================
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SERIES_PRIORITY = {"EQ": 0, "BE": 1, "BZ": 2, "BL": 3, "SM": 4, "ST": 5}
ADJUST_TOLERANCE = 0.001
LOOKBACK_DAYS = 126
MIN_ACTIVE_SHARE = 0.8
UNIVERSE_SIZE = 500


def link_entities(bhav: pd.DataFrame) -> pd.Series:
    """entity_id for each row: connected components of symbols and ISINs
    that appear together on any day. Returns a Series aligned to bhav."""
    parent: dict[str, str] = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    pairs = bhav[["Symbol", "ISIN"]].drop_duplicates()
    for sym, isin in pairs.itertuples(index=False):
        s = f"S:{sym}"
        find(s)
        if isinstance(isin, str) and isin.strip():
            union(s, f"I:{isin.strip()}")
    roots = {sym: find(f"S:{sym}") for sym in pairs["Symbol"].unique()}
    return bhav["Symbol"].map(roots)


def primary_rows(bhav: pd.DataFrame) -> pd.DataFrame:
    """One row per (entity, Date): the most liquid-normal series wins
    (EQ before BE before BZ ...), then the higher traded value."""
    df = bhav.copy()
    df["entity_id"] = link_entities(df)
    df["_prio"] = df["Series"].map(SERIES_PRIORITY).fillna(99)
    df = df.sort_values(["entity_id", "Date", "_prio", "Turnover"], ascending=[True, True, True, False])
    return df.drop_duplicates(["entity_id", "Date"]).drop(columns="_prio").reset_index(drop=True)


def adjust_entity(rows: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Backward-adjust one entity's rows (sorted by Date) using NSE's own
    PrevClose. Returns (adjusted rows, list of applied adjustments)."""
    rows = rows.sort_values("Date").reset_index(drop=True).copy()
    prev_close = rows["Close"].shift(1)
    factor = (rows["PrevClose"] / prev_close).where(prev_close > 0)
    events = []
    cumulative = np.ones(len(rows))
    running = 1.0
    for i in range(len(rows) - 1, 0, -1):
        f = factor.iloc[i]
        if pd.notna(f) and f > 0 and abs(f - 1) > ADJUST_TOLERANCE:
            running *= f
            events.append({"Date": rows.at[i, "Date"], "factor": float(f)})
        cumulative[i - 1] = running
    for col in ("Open", "High", "Low", "Close", "PrevClose"):
        rows[col] = rows[col] * cumulative
    rows["Volume"] = rows["Volume"] / cumulative
    rows["adj_factor"] = cumulative
    return rows, events[::-1]


def build_adjusted_prices(bhav: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(adjusted daily prices for every entity, log of adjustments)."""
    base = primary_rows(bhav)
    out, log = [], []
    for entity, rows in base.groupby("entity_id", sort=False):
        adjusted, events = adjust_entity(rows)
        out.append(adjusted)
        log.extend({"entity_id": entity, **e} for e in events)
    prices = pd.concat(out, ignore_index=True)
    latest = prices.sort_values("Date").groupby("entity_id")["Symbol"].last()
    prices["current_symbol"] = prices["entity_id"].map(latest)
    return prices, pd.DataFrame(log, columns=["entity_id", "Date", "factor"])


def monthly_universe(prices: pd.DataFrame, size: int = UNIVERSE_SIZE, lookback: int = LOOKBACK_DAYS,
                     min_active_share: float = MIN_ACTIVE_SHARE) -> pd.DataFrame:
    """Top-`size` stocks by median daily traded value at each month end,
    using only the `lookback` sessions up to and including that date."""
    sessions = np.sort(prices["Date"].unique())
    month_ends = pd.Series(sessions).groupby(pd.Series(sessions).dt.to_period("M")).max().to_numpy()
    turnover = prices.pivot_table(index="Date", columns="entity_id", values="Turnover", aggfunc="first")
    series_today = prices.pivot_table(index="Date", columns="entity_id", values="Series", aggfunc="first")
    rows = []
    for me in month_ends:
        pos = int(np.searchsorted(sessions, me))
        if pos + 1 < lookback:
            continue
        window = turnover.iloc[pos + 1 - lookback: pos + 1]
        active = window.notna().mean()
        median_tv = window.median()
        eq_today = series_today.iloc[pos] == "EQ"
        eligible = median_tv[(active >= min_active_share) & eq_today.reindex(median_tv.index, fill_value=False)]
        top = eligible.sort_values(ascending=False).head(size)
        rows.append(pd.DataFrame({"month_end": pd.Timestamp(me), "entity_id": top.index,
                                  "rank": np.arange(1, len(top) + 1), "median_turnover": top.values}))
    universe = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(
        columns=["month_end", "entity_id", "rank", "median_turnover"])
    symbols = prices.drop_duplicates(["entity_id", "Date"]).set_index(["entity_id", "Date"])["Symbol"]
    universe["symbol_then"] = [symbols.get((e, m)) for e, m in zip(universe["entity_id"], universe["month_end"])]
    return universe


def last_trading_dates(prices: pd.DataFrame) -> pd.Series:
    return prices.groupby("entity_id")["Date"].max()
