"""
Price-series integrity checks and repair for Falcon's cached OHLCV history.

Two distinct failure modes have been found in data/technical (2026-10-20),
and they need different repairs:

SERIES_FLIP
    The close alternates between two price levels on consecutive days
    (SBIN: ~Rs 245 <-> ~Rs 11,700). Cause: NSE returns several trading
    series per symbol (EQ plus bonds/rights etc.) and the old ingestion kept
    an arbitrary row per date. Not recoverable from the cached file -- the
    history must be re-downloaded (NSEProvider now selects the equity
    series), then split-adjusted.

UNADJUSTED_STEP
    One or a few sustained one-way jumps (NAUKRI: 5.29x). Cause: a real
    split/bonus that was never (or no longer is) adjusted. Recoverable from
    the cached file by running confirm_and_adjust() against NSE's
    corporate-action records.

Genuine large single-day moves also exist (a real crash). Classification is
therefore a TRIAGE signal, not a verdict: STEP findings are only repaired
when a matching corporate-action record confirms them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from market_data.corporate_actions import confirm_and_adjust, merge_and_adjust

CLEAN = "CLEAN"
SERIES_FLIP = "SERIES_FLIP"
UNADJUSTED_STEP = "UNADJUSTED_STEP"

JUMP_THRESHOLD = 0.40          # same bar corporate_actions.DISCONTINUITY_THRESHOLD uses
FLIP_WINDOW_DAYS = 3           # a jump reversed within this many rows is a "flip"
MIN_FLIPS_FOR_SERIES_FLIP = 3  # one reversed spike can be a bad print; 3+ is a pattern


@dataclass
class IntegrityReport:
    symbol: str
    status: str
    rows: int
    jumps: int
    flips: int
    jump_dates: list[pd.Timestamp] = field(default_factory=list)


def classify_price_series(symbol: str, df: pd.DataFrame) -> IntegrityReport:
    ordered = df.sort_values("Date").reset_index(drop=True)
    close = ordered["Close"].astype(float)
    ratio = close / close.shift(1)
    jump = ((ratio > 1 + JUMP_THRESHOLD) | (ratio < 1 - JUMP_THRESHOLD)).to_numpy()

    flips = 0
    up = (ratio > 1 + JUMP_THRESHOLD).to_numpy()
    down = (ratio < 1 - JUMP_THRESHOLD).to_numpy()
    n = len(ordered)
    for i in range(1, n):
        if not jump[i]:
            continue
        for j in range(i + 1, min(i + 1 + FLIP_WINDOW_DAYS, n)):
            if (up[i] and down[j]) or (down[i] and up[j]):
                flips += 1
                break

    jump_dates = [pd.Timestamp(d) for d in ordered.loc[jump, "Date"]]
    if flips >= MIN_FLIPS_FOR_SERIES_FLIP:
        status = SERIES_FLIP
    elif jump.any():
        status = UNADJUSTED_STEP
    else:
        status = CLEAN

    return IntegrityReport(symbol, status, n, int(jump.sum()), flips, jump_dates)


@dataclass
class RepairOutcome:
    symbol: str
    action: str              # "REFETCHED", "ADJUSTED", "UNRESOLVED", "UNCHANGED"
    before: IntegrityReport
    after: IntegrityReport | None
    detail: str = ""


def repair_series(
    symbol: str,
    cached: pd.DataFrame,
    corporate_actions: pd.DataFrame | None,
    fetch_full_history: Callable[[str], pd.DataFrame],
) -> tuple[pd.DataFrame | None, RepairOutcome]:
    """Return (repaired_df or None, outcome). Never returns a frame that is
    still SERIES_FLIP -- a failed repair leaves the caller's file untouched.

    `fetch_full_history(symbol)` must return RAW (unadjusted, equity-series
    only) daily history; it is injected so this logic is testable offline.
    """
    before = classify_price_series(symbol, cached)

    if before.status == CLEAN:
        return None, RepairOutcome(symbol, "UNCHANGED", before, None)

    if before.status == SERIES_FLIP:
        try:
            raw = fetch_full_history(symbol)
        except Exception as ex:  # noqa: BLE001
            return None, RepairOutcome(symbol, "UNRESOLVED", before, None, f"re-download failed: {ex}")
        if raw is None or raw.empty:
            return None, RepairOutcome(symbol, "UNRESOLVED", before, None, "re-download returned no data")
        repaired, _ = merge_and_adjust(symbol, None, raw, corporate_actions)
        after = classify_price_series(symbol, repaired)
        if after.status == SERIES_FLIP:
            return None, RepairOutcome(symbol, "UNRESOLVED", before, after, "still alternating after re-download")
        return repaired, RepairOutcome(symbol, "REFETCHED", before, after)

    # UNADJUSTED_STEP
    repaired, events = merge_and_adjust(symbol, cached, cached.iloc[0:0], corporate_actions)
    if not events:
        return None, RepairOutcome(
            symbol, "UNRESOLVED", before, None,
            "jump(s) have no matching NSE corporate-action record -- possibly a genuine move",
        )
    after = classify_price_series(symbol, repaired)
    return repaired, RepairOutcome(symbol, "ADJUSTED", before, after, f"{len(events)} event(s) applied")


def process_directory(
    technical_dir,
    corporate_actions: pd.DataFrame | None,
    fetch_full_history: Callable[[str], pd.DataFrame],
    save: Callable[[str, pd.DataFrame], None],
    apply: bool = False,
    backup_dir=None,
    pause: Callable[[], None] | None = None,
) -> list[RepairOutcome]:
    """Scan every `*.parquet` in `technical_dir`; with apply=True also
    repair and persist the fixable ones.

    Safety properties (tested): scan mode writes nothing; apply mode copies
    the original file to `backup_dir` BEFORE `save()` is called; a ticker
    whose repair does not verify clean is left exactly as it was.
    """
    import shutil
    from pathlib import Path

    technical_dir = Path(technical_dir)
    outcomes: list[RepairOutcome] = []

    for path in sorted(technical_dir.glob("*.parquet")):
        symbol = path.stem
        cached = pd.read_parquet(path)
        if "Close" not in cached.columns or len(cached) < 30:
            continue
        cached["Date"] = pd.to_datetime(cached["Date"])

        if not apply:
            report = classify_price_series(symbol, cached)
            outcomes.append(RepairOutcome(symbol, "UNCHANGED" if report.status == CLEAN else report.status, report, None))
            continue

        repaired, outcome = repair_series(symbol, cached, corporate_actions, fetch_full_history)
        outcomes.append(outcome)

        if repaired is not None:
            if backup_dir is not None:
                Path(backup_dir).mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, Path(backup_dir) / path.name)
            save(symbol, repaired)

        if pause is not None and outcome.before.status == SERIES_FLIP:
            pause()   # be polite to NSE between re-downloads

    return outcomes
