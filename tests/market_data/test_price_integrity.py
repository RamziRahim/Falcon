"""Tests for market_data/price_integrity.py -- triage + repair of the two
cache-corruption modes found 2026-10-20 (series flips, unadjusted steps)."""
from __future__ import annotations

import pandas as pd

from market_data.price_integrity import (
    CLEAN, SERIES_FLIP, UNADJUSTED_STEP, classify_price_series, repair_series,
)


def _frame(closes, start="2024-01-01"):
    dates = pd.bdate_range(start, periods=len(closes))
    return pd.DataFrame({
        "Date": dates, "Open": closes, "High": closes, "Low": closes, "Close": [float(c) for c in closes],
        "Volume": [1000] * len(closes),
    })


def _actions(symbol, ex_date):
    return pd.DataFrame({"symbol": [symbol], "exDate": [pd.Timestamp(ex_date)], "subject": ["split"]})


FLIPPY = [250, 11700, 250, 11700, 250, 11700, 250, 11700, 250, 250]


class TestClassify:

    def test_smooth_series_is_clean(self):
        assert classify_price_series("A", _frame([100, 101, 99, 102])).status == CLEAN

    def test_alternating_levels_are_a_series_flip(self):
        report = classify_price_series("SBIN", _frame(FLIPPY))
        assert report.status == SERIES_FLIP
        assert report.flips >= 3

    def test_single_sustained_drop_is_an_unadjusted_step(self):
        report = classify_price_series("NAUKRI", _frame([1000] * 6 + [200] * 6))
        assert report.status == UNADJUSTED_STEP
        assert report.flips == 0

    def test_one_isolated_bad_print_is_not_called_a_series_flip(self):
        report = classify_price_series("A", _frame([100, 100, 5, 100, 100, 100]))
        assert report.status == UNADJUSTED_STEP   # triage only; below the flip-pattern bar
        assert report.flips == 1


class TestRepair:

    def test_series_flip_is_refetched_and_adjusted(self):
        clean_raw = _frame([1000] * 6 + [200] * 6)

        repaired, outcome = repair_series(
            "ABC.NS", _frame(FLIPPY * 2), _actions("ABC", "2024-01-09"),
            fetch_full_history=lambda s: clean_raw,
        )

        assert outcome.action == "REFETCHED"
        assert repaired["Close"].round(6).tolist() == [200.0] * 12
        assert outcome.after.status == CLEAN

    def test_series_flip_stays_untouched_if_refetch_is_still_corrupt(self):
        repaired, outcome = repair_series(
            "ABC.NS", _frame(FLIPPY * 2), None, fetch_full_history=lambda s: _frame(FLIPPY * 2),
        )

        assert repaired is None
        assert outcome.action == "UNRESOLVED"

    def test_refetch_failure_is_reported_not_raised(self):
        def boom(_):
            raise ConnectionError("NSE unreachable")

        repaired, outcome = repair_series("ABC.NS", _frame(FLIPPY * 2), None, fetch_full_history=boom)

        assert repaired is None
        assert outcome.action == "UNRESOLVED"
        assert "NSE unreachable" in outcome.detail

    def test_confirmed_step_is_adjusted_from_the_cached_file_alone(self):
        repaired, outcome = repair_series(
            "ABC.NS", _frame([1000] * 6 + [200] * 6), _actions("ABC", "2024-01-09"),
            fetch_full_history=lambda s: (_ for _ in ()).throw(AssertionError("must not re-download")),
        )

        assert outcome.action == "ADJUSTED"
        assert repaired["Close"].round(6).tolist() == [200.0] * 12

    def test_unconfirmed_step_is_left_for_a_human(self):
        repaired, outcome = repair_series(
            "ABC.NS", _frame([1000] * 6 + [200] * 6), _actions("OTHER", "2024-01-09"),
            fetch_full_history=lambda s: None,
        )

        assert repaired is None
        assert outcome.action == "UNRESOLVED"

    def test_clean_series_is_left_alone(self):
        repaired, outcome = repair_series("A", _frame([100, 101, 102]), None, lambda s: None)

        assert repaired is None
        assert outcome.action == "UNCHANGED"


class TestProcessDirectory:

    def _write(self, tmp_path, name, closes):
        d = tmp_path / "technical"
        d.mkdir(exist_ok=True)
        frame = _frame(closes)
        # classify/repair need >= 30 rows to be considered
        frame.to_parquet(d / f"{name}.parquet", index=False)
        return d

    def test_scan_mode_writes_nothing(self, tmp_path):
        from market_data.price_integrity import process_directory
        d = self._write(tmp_path, "AAA.NS", [100] * 20 + [20] * 20)
        saved = []

        outcomes = process_directory(d, _actions("AAA", "2024-01-29"), lambda s: None, lambda s, f: saved.append(s), apply=False)

        assert saved == []
        assert outcomes[0].action == UNADJUSTED_STEP

    def test_apply_backs_up_before_saving_and_skips_clean_files(self, tmp_path):
        from market_data.price_integrity import process_directory
        d = self._write(tmp_path, "AAA.NS", [100] * 20 + [20] * 20)
        self._write(tmp_path, "BBB.NS", [100 + i % 3 for i in range(40)])
        backup = tmp_path / "backup"
        saved = []

        def save(symbol, frame):
            assert (backup / "AAA.NS.parquet").exists(), "backup must exist before save()"
            saved.append(symbol)

        outcomes = process_directory(d, _actions("AAA", "2024-01-29"), lambda s: None, save, apply=True, backup_dir=backup)

        assert saved == ["AAA.NS"]
        assert {o.symbol: o.action for o in outcomes} == {"AAA.NS": "ADJUSTED", "BBB.NS": "UNCHANGED"}
        assert not (backup / "BBB.NS.parquet").exists()
