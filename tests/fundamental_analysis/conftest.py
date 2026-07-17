"""
Shared fixtures for fundamental_analysis/ engine tests.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def isolated_fundamental_cache(monkeypatch, tmp_path):
    """
    A FundamentalCache instance pointed at a temp cache file instead of the
    real project path, so tests never touch real data/fundamentals_cache.json.
    """
    import fundamental_analysis.fundamental_cache as fc

    monkeypatch.setattr(fc, "CACHE_PATH", tmp_path / "fundamentals_cache_test.json")
    return fc.FundamentalCache()
