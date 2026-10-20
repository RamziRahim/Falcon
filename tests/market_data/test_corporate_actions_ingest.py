"""
Tests for ingestion-time split/bonus adjustment (merge_and_adjust,
load_corporate_actions) and its wiring in DataCollectionEngine.

Regression for the 2026-10-20 finding: adjustment used to be a one-off
manual script, so a ticker whose raw cache was rebuilt afterwards silently
reverted to unadjusted prices (NAUKRI: cached Close 5.29x run #4's own
entry_price).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from market_data import corporate_actions as ca
from market_data.corporate_actions import load_corporate_actions, merge_and_adjust
from market_data.data_collection_engine import DataCollectionEngine


def _history(start: str, closes: list[float], volume: int = 1000, deliverable: bool = False) -> pd.DataFrame:
    dates = pd.bdate_range(start, periods=len(closes))
    df = pd.DataFrame({
        "Date": dates, "Open": closes, "High": closes, "Low": closes, "Close": closes,
        "Volume": [volume] * len(closes),
    })
    if deliverable:
        df["Deliverable_Qty"] = [volume * 0.5] * len(closes)
    return df


def _actions(symbol: str, ex_date: str) -> pd.DataFrame:
    return pd.DataFrame({
        "symbol": [symbol], "exDate": [pd.Timestamp(ex_date)], "subject": ["Face Value Split From Rs 10 To Rs 2"],
    })


class TestMergeAndAdjust:

    def test_split_between_cache_and_new_rows_adjusts_old_history(self):
        existing = _history("2024-01-01", [1000.0] * 5)
        new_rows = _history("2024-01-08", [200.0] * 3)          # 5:1 split on 2024-01-08
        actions = _actions("ABC", "2024-01-08")

        full, events = merge_and_adjust("ABC.NS", existing, new_rows, actions)

        assert len(events) == 1
        assert full["Close"].round(6).tolist() == [200.0] * 8
        assert full["Volume"].tolist() == [5000] * 5 + [1000] * 3

    def test_full_raw_redownload_is_adjusted_when_no_cache_exists(self):
        raw = _history("2024-01-01", [1000.0] * 5 + [200.0] * 3)

        full, events = merge_and_adjust("ABC.NS", None, raw, _actions("ABC", "2024-01-08"))

        assert len(events) == 1
        assert full["Close"].round(6).tolist() == [200.0] * 8

    def test_deliverable_qty_scaled_with_volume(self):
        raw = _history("2024-01-01", [1000.0] * 5 + [200.0] * 3, deliverable=True)

        full, _ = merge_and_adjust("ABC.NS", None, raw, _actions("ABC", "2024-01-08"))

        assert full["Deliverable_Qty"].tolist() == [2500.0] * 5 + [500.0] * 3

    def test_big_move_without_a_corporate_action_record_is_left_alone(self):
        raw = _history("2024-01-01", [1000.0] * 5 + [200.0] * 3)

        full, events = merge_and_adjust("ABC.NS", None, raw, _actions("OTHER", "2024-01-08"))

        assert events == []
        assert full["Close"].tolist() == [1000.0] * 5 + [200.0] * 3

    def test_already_adjusted_history_is_not_adjusted_twice(self):
        adjusted = _history("2024-01-01", [200.0] * 8)

        full, events = merge_and_adjust("ABC.NS", adjusted, _history("2024-01-11", [200.0]), _actions("ABC", "2024-01-08"))

        assert events == []
        assert full["Close"].tolist() == [200.0] * 9

    def test_missing_actions_table_degrades_to_no_adjustment(self):
        new_rows = _history("2024-01-08", [200.0] * 3)

        full, events = merge_and_adjust("ABC.NS", None, new_rows, None)

        assert events == []
        assert full is new_rows


class TestLoadCorporateActions:

    def test_refresh_failure_falls_back_to_stale_cache(self, tmp_path, monkeypatch):
        cache = tmp_path / "corporate_actions_cache.parquet"
        stale = _actions("ABC", "2024-01-08")
        stale.to_parquet(cache, index=False)
        import os, time
        old = time.time() - 10 * 86400
        os.utime(cache, (old, old))
        monkeypatch.setattr(ca, "CORPORATE_ACTIONS_CACHE_PATH", cache)

        calls = []

        def fake_fetch(from_date, to_date, force_refresh=False):
            calls.append(force_refresh)
            if force_refresh:
                raise ConnectionError("NSE unreachable")
            return pd.read_parquet(cache)

        monkeypatch.setattr(ca, "fetch_all_corporate_actions", fake_fetch)

        result = load_corporate_actions()

        assert result is not None and len(result) == 1
        assert calls == [True, False]

    def test_no_cache_and_no_network_returns_none_not_a_crash(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ca, "CORPORATE_ACTIONS_CACHE_PATH", tmp_path / "missing.parquet")
        monkeypatch.setattr(
            ca, "fetch_all_corporate_actions",
            MagicMock(side_effect=ConnectionError("NSE unreachable")),
        )

        assert load_corporate_actions() is None


class TestEngineWiring:

    def _run(self, existing, new_rows, actions):
        engine = DataCollectionEngine()
        with patch("market_data.data_collection_engine.cache_synchronizer") as sync, \
             patch("market_data.data_collection_engine.downloader") as dl, \
             patch("market_data.data_collection_engine.market_data_validator") as validator, \
             patch("market_data.data_collection_engine.cache_manager") as cache, \
             patch("market_data.data_collection_engine.load_corporate_actions", return_value=actions):
            sync.synchronize.return_value = MagicMock(added=[], retained=["ABC.NS"], added_count=0, retained_count=1, removed_count=0)
            dl.download.return_value = {"ABC.NS": new_rows}
            validator.validate_history.return_value = MagicMock(valid=True, warnings=[])
            cache.exists.return_value = existing is not None
            cache.load.return_value = existing
            engine.run(symbols=["ABC.NS"])
            return cache

    def test_confirmed_split_replaces_cached_history(self):
        cache = self._run(
            _history("2024-01-01", [1000.0] * 5), _history("2024-01-08", [200.0] * 3), _actions("ABC", "2024-01-08"),
        )

        cache.save.assert_called_once()
        saved = cache.save.call_args[0][1]
        assert saved["Close"].round(6).tolist() == [200.0] * 8
        cache.update.assert_not_called()

    def test_no_split_keeps_cheap_append_update(self):
        cache = self._run(
            _history("2024-01-01", [100.0] * 5), _history("2024-01-08", [101.0] * 3), _actions("ABC", "2020-01-01"),
        )

        cache.update.assert_called_once()
        cache.save.assert_not_called()
