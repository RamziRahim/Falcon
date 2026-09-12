"""
Shared fixtures for tests/ui/ -- keeps unit tests deterministic and
network-free.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def no_live_nse_holiday_calendar_calls(monkeypatch):
    """format_stale_data_notice() (ui/dashboard_data.py) calls
    market_data.holiday_calendar.get_nse_holidays() to find the most
    recent real trading day. That function is disk-cached in production,
    but a test run must never depend on that cache's on-disk state (a
    fresh checkout, CI, or a stale/missing cache file would otherwise
    trigger a live nselib fetch). Empty set here means every test date
    behaves purely by weekday -- exactly what the existing (all-weekday)
    test fixtures were already written assuming. A test that specifically
    needs a holiday in the mix overrides this locally with its own
    monkeypatch.setattr call, applied after this one."""
    monkeypatch.setattr("market_data.holiday_calendar.get_nse_holidays", lambda: set())
