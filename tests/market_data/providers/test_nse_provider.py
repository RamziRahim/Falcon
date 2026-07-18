"""
Tests for market_data/providers/nse_provider.py -- delivery % / deliverable
quantity unlock. NSE_provider.get_history() already fetched these columns
via capital_market.price_volume_and_deliverable_position_data() but silently
dropped them in the OHLCV-only column filter. Real column names (confirmed
via nselib/constants.py, not guessed): 'DeliverableQty', '%DlyQttoTradedQty'.
"""
from __future__ import annotations

import datetime
from unittest.mock import patch

import pandas as pd
import pytest

from market_data.exceptions import DownloadError, ProviderError
from market_data.providers.nse_provider import NSEProvider


def _raw_payload_with_delivery() -> pd.DataFrame:
    """Real column names/shape per nselib/constants.py's
    price_volume_and_deliverable_position_data_columns."""
    return pd.DataFrame({
        "Symbol": ["MARKSANS", "MARKSANS"],
        "Series": ["EQ", "EQ"],
        "Date": ["01-Jan-2024", "02-Jan-2024"],
        "PrevClose": ["100.00", "101.00"],
        "OpenPrice": ["100.50", "101.50"],
        "HighPrice": ["105.00", "106.00"],
        "LowPrice": ["99.50", "100.50"],
        "LastPrice": ["104.00", "105.00"],
        "ClosePrice": ["104.50", "105.50"],
        "AveragePrice": ["102.00", "103.00"],
        "TotalTradedQuantity": ["1,000,000", "2,000,000"],
        "TurnoverInRs": ["500000", "600000"],
        "No.ofTrades": ["1000", "1200"],
        "DeliverableQty": ["600,000", "1,200,000"],
        "%DlyQttoTradedQty": ["60.00", "60.00"],
    })


def _raw_payload_without_delivery() -> pd.DataFrame:
    """Simulates an older NSE payload shape / a different nselib function
    that doesn't include delivery columns at all."""
    return pd.DataFrame({
        "Symbol": ["MARKSANS", "MARKSANS"],
        "Date": ["01-Jan-2024", "02-Jan-2024"],
        "OpenPrice": ["100.50", "101.50"],
        "HighPrice": ["105.00", "106.00"],
        "LowPrice": ["99.50", "100.50"],
        "ClosePrice": ["104.50", "105.50"],
        "TotalTradedQuantity": ["1,000,000", "2,000,000"],
    })


@pytest.fixture
def provider() -> NSEProvider:
    return NSEProvider()


class TestDeliveryColumnsUnlocked:

    def test_deliverable_qty_and_delivery_pct_mapped_and_cleaned(self, provider):
        with patch(
            "market_data.providers.nse_provider.capital_market.price_volume_and_deliverable_position_data",
            return_value=_raw_payload_with_delivery(),
        ):
            df = provider.get_history(
                "MARKSANS.NS",
                datetime.date(2024, 1, 1),
                datetime.date(2024, 1, 2),
            )

        assert "Deliverable_Qty" in df.columns
        assert "Delivery_Pct" in df.columns
        assert list(df["Deliverable_Qty"]) == [600_000, 1_200_000]
        assert list(df["Delivery_Pct"]) == [60.0, 60.0]

    def test_deliverable_qty_is_numeric_dtype(self, provider):
        with patch(
            "market_data.providers.nse_provider.capital_market.price_volume_and_deliverable_position_data",
            return_value=_raw_payload_with_delivery(),
        ):
            df = provider.get_history(
                "MARKSANS.NS",
                datetime.date(2024, 1, 1),
                datetime.date(2024, 1, 2),
            )

        assert pd.api.types.is_numeric_dtype(df["Deliverable_Qty"])
        assert pd.api.types.is_numeric_dtype(df["Delivery_Pct"])

    def test_core_ohlcv_contract_unchanged(self, provider):
        """Existing callers that only read OHLCV must be unaffected."""
        with patch(
            "market_data.providers.nse_provider.capital_market.price_volume_and_deliverable_position_data",
            return_value=_raw_payload_with_delivery(),
        ):
            df = provider.get_history(
                "MARKSANS.NS",
                datetime.date(2024, 1, 1),
                datetime.date(2024, 1, 2),
            )

        for col in ["Date", "Open", "High", "Low", "Close", "Volume"]:
            assert col in df.columns
        assert df["Close"].iloc[0] == pytest.approx(104.50)
        assert df["Volume"].iloc[0] == 1_000_000


class TestGracefulDegradationWithoutDeliveryColumns:

    def test_get_history_succeeds_with_ohlcv_only(self, provider):
        """An older NSE payload shape (or a different nselib function)
        without delivery columns must not raise -- only Date/OHLCV are
        required."""
        with patch(
            "market_data.providers.nse_provider.capital_market.price_volume_and_deliverable_position_data",
            return_value=_raw_payload_without_delivery(),
        ):
            df = provider.get_history(
                "MARKSANS.NS",
                datetime.date(2024, 1, 1),
                datetime.date(2024, 1, 2),
            )

        for col in ["Date", "Open", "High", "Low", "Close", "Volume"]:
            assert col in df.columns

    def test_delivery_columns_absent_not_null(self, provider):
        with patch(
            "market_data.providers.nse_provider.capital_market.price_volume_and_deliverable_position_data",
            return_value=_raw_payload_without_delivery(),
        ):
            df = provider.get_history(
                "MARKSANS.NS",
                datetime.date(2024, 1, 1),
                datetime.date(2024, 1, 2),
            )

        assert "Deliverable_Qty" not in df.columns
        assert "Delivery_Pct" not in df.columns

    def test_missing_required_ohlcv_column_still_raises(self, provider):
        """Confirms the required-columns gate still protects against a
        genuinely broken payload (missing Close), unaffected by making
        delivery columns optional."""
        broken = _raw_payload_without_delivery().drop(columns=["ClosePrice"])
        with patch(
            "market_data.providers.nse_provider.capital_market.price_volume_and_deliverable_position_data",
            return_value=broken,
        ):
            with pytest.raises(ProviderError):
                provider.get_history(
                    "MARKSANS.NS",
                    datetime.date(2024, 1, 1),
                    datetime.date(2024, 1, 2),
                )
