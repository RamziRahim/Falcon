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

2. ADJUSTED PRICES. Splits, bonuses and consolidations are taken from NSE's
   own corporate-action records (market_data/corporate_actions.py's cache):
   "Bonus A:B" -> factor B/(A+B); "Face Value Split ... From Rs X To Rs Y" ->
   factor Y/X (also covers consolidations). Prices before the ex-date are
   multiplied by the factor (volume divided). Bonus debentures/preference
   shares (NCRPS) are not equity dilution and are ignored. Demergers take
   their factor from the ex-date open / previous close (the drop is value
   moved to the new company, not a loss), only when that drop is 5-90%. (A first version
   used the bhavcopy's PrevClose column, assuming NSE adjusts it on ex-dates;
   it does not -- e.g. RELIANCE's 1:1 bonus on 2024-10-28 shows PrevClose
   2655.70 against a close of 1334.35 -- so that approach was dropped before
   any strategy was run.)

   Before 2016 the feed is thin, so for stocks ever in a universe an
   overnight gap matching a standard ratio (1/2, 1/3, 1/5, 1/10 ...) within
   2%, with no record within 10 days, is treated as an unrecorded
   split/bonus and logged as INFERRED.

3. MONTHLY UNIVERSE. At each month end, the 500 most liquid stocks, ranked
   by median daily traded value over the previous LOOKBACK_DAYS sessions.
   Only stocks trading in the normal EQ series on that date, and that traded
   on at least MIN_ACTIVE_SHARE of those sessions, are eligible. This is a
   rule-based stand-in for the Nifty 500; ETFs and fund units (ISIN
   prefix INF) and stocks closing below Rs 5 (raw) on the ranking date are
   excluded (which also ranks by size and
   liquidity), built only from data available on that date.

4. EXIT DATES. last_date per entity: a stock that stops appearing has
   delisted, merged or been suspended. A backtest must exit it at its last
   close rather than silently dropping it.
===============================================================================
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

SERIES_PRIORITY = {"EQ": 0, "BE": 1, "BZ": 2, "BL": 3, "SM": 4, "ST": 5}
LOOKBACK_DAYS = 126
MIN_ACTIVE_SHARE = 0.8
UNIVERSE_SIZE = 500
# Penny stocks: at a Rs 0.05 tick, a Rs 0.10-1 stock moves 5-50% per tick, which
# breaks split inference and isn't investable anyway. Raw (unadjusted) close.
MIN_PRICE = 5.0


def load_symbol_changes(path: str) -> list[tuple[str, str]]:
    """(old, new) symbol pairs from NSE's symbolchange.csv (columns: company
    name, old symbol, new symbol, date -- header text varies, so by position)."""
    df = pd.read_csv(path, header=None, dtype=str, encoding="latin-1")
    df = df[df[1].notna() & df[2].notna()]
    df = df[~df[1].str.strip().str.upper().str.contains("SYMBOL")]
    return [(a.strip().upper(), b.strip().upper()) for a, b in zip(df[1], df[2]) if a.strip() and b.strip()]


def link_entities(bhav: pd.DataFrame, symbol_changes: list[tuple[str, str]] | None = None) -> pd.Series:
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
    # NSE-documented renames (needed before 2011, when bhavcopies carry no ISIN)
    known = set(pairs["Symbol"].unique())
    for old_sym, new_sym in symbol_changes or []:
        if old_sym in known and new_sym in known:
            union(f"S:{old_sym}", f"S:{new_sym}")
    roots = {sym: find(f"S:{sym}") for sym in pairs["Symbol"].unique()}
    return bhav["Symbol"].map(roots)


def primary_rows(bhav: pd.DataFrame, symbol_changes: list[tuple[str, str]] | None = None) -> pd.DataFrame:
    """One row per (entity, Date): the most liquid-normal series wins
    (EQ before BE before BZ ...), then the higher traded value."""
    df = bhav.copy()
    df["entity_id"] = link_entities(df, symbol_changes)
    df["_prio"] = df["Series"].map(SERIES_PRIORITY).fillna(99)
    df = df.sort_values(["entity_id", "Date", "_prio", "Turnover"], ascending=[True, True, True, False])
    return df.drop_duplicates(["entity_id", "Date"]).drop(columns="_prio").reset_index(drop=True)


_BONUS = re.compile(r"bonus\s*(\d+)\s*:\s*(\d+)", re.I)
_SPLIT = re.compile(r"(?:rs|re)\.?\s*([\d.]+)\D*?to\s*(?:rs|re)\.?\s*([\d.]+)", re.I)   # "From Rs 10 To Rs 2", "Fv Split Rs.10/- To Re.2/"
SANITY_BAND = (0.6, 1.6)
DEMERGER = -1.0                    # marker: factor = ex-date open / previous close
# Overnight gaps that exactly match a common split/bonus ratio, on a date
# with no NSE record nearby, are treated as an unrecorded split/bonus
# (the corporate-action feed is thin before 2016). Standard factors only,
# within INFER_TOLERANCE; logged as "INFERRED" for review.
STANDARD_FACTORS = (1 / 2, 1 / 3, 2 / 3, 1 / 4, 1 / 5, 1 / 6, 2 / 5, 1 / 8, 1 / 10, 1 / 20)
INFER_TOLERANCE = 0.02
INFER_EXCLUSION_DAYS = 10          # observed / parsed factor outside this is logged as suspect


def parse_factor(subject: str) -> float | None:
    """Price multiplier for history before the ex-date, or None if the
    record isn't an equity split/bonus/consolidation."""
    text = str(subject)
    low = text.lower()
    factor = 1.0
    found = False
    for part in re.split(r"/(?!-)", text):          # "Rs 10/-" is not a separator
        p = part.lower()
        if "bonus" in p and not any(w in p for w in ("ncrps", "debenture", "preference", "pref ")):
            m = _BONUS.search(part)
            if m and int(m.group(1)) > 0:
                a, b = int(m.group(1)), int(m.group(2))
                factor *= b / (a + b)
                found = True
        elif "split" in p or "sub-division" in p or "subdivision" in p or "consolidat" in p:
            m = _SPLIT.search(part)
            if m and float(m.group(1)) > 0:
                factor *= float(m.group(2)) / float(m.group(1))
                found = True
    if not found and ("demerger" in low or "scheme of arrangement" in low or "scheme of arangement" in low):
        # value moved to a new company; taken from the ex-date drop (only when
        # that drop is 5-90%, see adjust_entity -- an amalgamation with no drop is ignored)
        return DEMERGER                       # value is taken from the ex-date price, see adjust_entity
    return factor if found and factor != 1.0 else None


def infer_actions(rows: pd.DataFrame, recorded: pd.Series) -> pd.DataFrame:
    """Unrecorded split/bonus candidates in one entity's raw rows: the
    opening gap Open_t / Close_(t-1) within INFER_TOLERANCE of a standard
    factor, with no recorded action within INFER_EXCLUSION_DAYS."""
    rows = rows.sort_values("Date").reset_index(drop=True)
    gap = rows["Open"] / rows["Close"].shift(1)
    out = []
    rec = pd.to_datetime(pd.Series(recorded)).to_numpy() if len(recorded) else np.array([], dtype="datetime64[ns]")
    prev_close = rows["Close"].shift(1)
    for i in np.flatnonzero(((gap < 0.7) & (prev_close >= MIN_PRICE)).to_numpy()):
        g = gap.iloc[i]
        f = min(STANDARD_FACTORS, key=lambda x: abs(g / x - 1))
        if abs(g / f - 1) > INFER_TOLERANCE:
            continue
        d = rows.at[i, "Date"]
        if len(rec) and (np.abs((rec - np.datetime64(d)) / np.timedelta64(1, "D")) <= INFER_EXCLUSION_DAYS).any():
            continue
        out.append({"exDate": d, "factor": f, "subject": f"INFERRED from opening gap {g:.4f}"})
    return pd.DataFrame(out, columns=["exDate", "factor", "subject"])


def adjust_entity(rows: pd.DataFrame, actions: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Backward-adjust one entity's rows (any order) for the corporate
    actions given (columns exDate, factor, subject). Latest first."""
    rows = rows.sort_values("Date").reset_index(drop=True).copy()
    cumulative = np.ones(len(rows))
    events = []
    dates = rows["Date"].to_numpy()
    # several records on one ex-date (e.g. bonus + split) combine into one factor
    for ex_date, same_day in sorted(actions.groupby("exDate"), key=lambda kv: kv[0], reverse=True):
        pos = int(np.searchsorted(dates, np.datetime64(ex_date)))
        if pos >= len(rows) or pos == 0:
            continue
        if (rows.at[pos, "Date"] - ex_date).days > 10:           # not traded near the ex-date
            continue
        observed = rows.at[pos, "Open"] / rows.at[pos - 1, "Close"] if rows.at[pos - 1, "Close"] > 0 else np.nan
        factors = same_day["factor"].to_numpy()
        if (factors == DEMERGER).any():
            # Demerger: shareholders receive the new company's shares, so the
            # ex-date drop is not a loss. Its size is only known from the
            # price; used only when it is a plausible drop (5-90%).
            if not (np.isfinite(observed) and 0.1 <= observed <= 0.95):
                continue
            factor = float(observed) * float(np.prod(factors[factors != DEMERGER]))
            suspect = False
        else:
            factor = float(np.prod(factors))
            ratio = observed / factor if np.isfinite(observed) else np.nan
            suspect = bool(not (SANITY_BAND[0] <= ratio <= SANITY_BAND[1])) if np.isfinite(ratio) else True
            if suspect and np.isfinite(observed) and 0.05 <= observed <= 0.95:
                # the record is incomplete (e.g. a second action on the same
                # day missing from the feed): the price shows the real factor
                factor = float(observed)
        cumulative[:pos] *= factor
        events.append({"Date": rows.at[pos, "Date"], "factor": factor, "subject": " + ".join(same_day["subject"]),
                       "observed_open_ratio": float(observed) if np.isfinite(observed) else None, "suspect": suspect})
    for col in ("Open", "High", "Low", "Close", "PrevClose"):
        rows[col] = rows[col] * cumulative
    rows["Volume"] = rows["Volume"] / cumulative
    rows["adj_factor"] = cumulative
    return rows, events[::-1]


def prepare_actions(corporate_actions: pd.DataFrame) -> pd.DataFrame:
    ca = corporate_actions.copy()
    ca["exDate"] = pd.to_datetime(ca["exDate"])
    ca["factor"] = ca["subject"].map(parse_factor)
    ca = ca[ca["factor"].notna()]
    ca["symbol"] = ca["symbol"].astype(str).str.strip().str.upper()
    return ca.drop_duplicates(["symbol", "exDate", "factor"])[["symbol", "isin", "exDate", "factor", "subject"]]


def build_adjusted_prices(bhav: pd.DataFrame, corporate_actions: pd.DataFrame | None = None,
                          infer_for: set | None = None, symbol_changes: list[tuple[str, str]] | None = None
                          ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(adjusted daily prices for every entity, log of adjustments). An
    action is matched to an entity by the symbol (or ISIN) the entity
    traded under around the ex-date."""
    base = primary_rows(bhav, symbol_changes)
    actions = prepare_actions(corporate_actions) if corporate_actions is not None else pd.DataFrame(
        columns=["symbol", "isin", "exDate", "factor", "subject"])
    sym_entity = base.groupby("Symbol")["entity_id"].first()
    isin_entity = base.dropna(subset=["ISIN"]).groupby("ISIN")["entity_id"].first()
    actions["entity_id"] = actions["symbol"].map(sym_entity)
    actions["entity_id"] = actions["entity_id"].fillna(actions["isin"].map(isin_entity))
    by_entity = {e: g for e, g in actions.dropna(subset=["entity_id"]).groupby("entity_id")}
    empty = actions.iloc[0:0]
    out, log = [], []
    for entity, rows in base.groupby("entity_id", sort=False):
        recorded = by_entity.get(entity, empty)
        # unrecorded splits are inferred only for stocks that matter for
        # backtests (ever in a universe): on thin small/SME stocks a 1/3
        # overnight gap is too often real
        inferred = (infer_actions(rows, recorded["exDate"]) if infer_for is not None and entity in infer_for
                    else empty.iloc[0:0])
        combined = pd.concat([recorded, inferred], ignore_index=True) if len(inferred) else recorded
        adjusted, events = adjust_entity(rows, combined)
        out.append(adjusted)
        log.extend({"entity_id": entity, **e} for e in events)
    prices = pd.concat(out, ignore_index=True)
    latest = prices.sort_values("Date").groupby("entity_id")["Symbol"].last()
    prices["current_symbol"] = prices["entity_id"].map(latest)
    return prices, pd.DataFrame(log, columns=["entity_id", "Date", "factor", "subject", "observed_open_ratio", "suspect"])


def monthly_universe(prices: pd.DataFrame, size: int = UNIVERSE_SIZE, lookback: int = LOOKBACK_DAYS,
                     min_active_share: float = MIN_ACTIVE_SHARE) -> pd.DataFrame:
    """Top-`size` stocks by median daily traded value at each month end,
    using only the `lookback` sessions up to and including that date."""
    sessions = np.sort(prices["Date"].unique())
    month_ends = pd.Series(sessions).groupby(pd.Series(sessions).dt.to_period("M")).max().to_numpy()
    turnover = prices.pivot_table(index="Date", columns="entity_id", values="Turnover", aggfunc="first")
    # ETFs and other fund units (ISIN prefix INF) trade in the EQ series but are not stocks
    funds = set(prices.loc[prices["ISIN"].astype(str).str.startswith("INF"), "entity_id"])
    series_today = prices.pivot_table(index="Date", columns="entity_id", values="Series", aggfunc="first")
    # raw close for the price floor: undo any backward adjustment if present
    raw_close = prices["Close"] / prices["adj_factor"] if "adj_factor" in prices.columns else prices["Close"]
    close_today = prices.assign(_raw=raw_close).pivot_table(index="Date", columns="entity_id", values="_raw", aggfunc="first")
    rows = []
    for me in month_ends:
        pos = int(np.searchsorted(sessions, me))
        if pos + 1 < lookback:
            continue
        window = turnover.iloc[pos + 1 - lookback: pos + 1]
        active = window.notna().mean()
        median_tv = window.median()
        eq_today = ((series_today.iloc[pos] == "EQ") & ~series_today.columns.isin(funds)
                    & (close_today.iloc[pos].reindex(series_today.columns) >= MIN_PRICE))
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
