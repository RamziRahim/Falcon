"""
Shared fixtures for fundamental_analysis/ engine tests.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def isolated_screener_fundamentals_store(monkeypatch, tmp_path):
    """
    Points fundamental_analysis.screener_fundamentals_store at a temp JSON
    file instead of the real project path, so tests never touch real
    data/screener_fundamentals_store.json.
    """
    import fundamental_analysis.screener_fundamentals_store as store

    monkeypatch.setattr(store, "STORE_PATH", tmp_path / "screener_fundamentals_store_test.json")
    return store
