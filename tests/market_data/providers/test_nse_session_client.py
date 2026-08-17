"""
Tests for market_data/providers/nse_session_client.py -- the vendored,
session-reusing replacement for nselib's own price_volume_and_
deliverable_position_data(), which creates a brand-new requests.Session()
and re-fetches cookies on every single call. The whole point of this
module is fewer redundant round-trips per scan, so these tests are
mostly about call COUNTS (how many origin-cookie fetches / data fetches
happen for N logical requests), not really about NSE response parsing
(that logic is unchanged, copied verbatim from nselib).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from market_data.providers.nse_session_client import NseSessionClient


def _csv_response(status_code: int = 200, symbol: str = "DEMO") -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.text = (
        "Symbol ,Series ,Date ,PrevClose ,OpenPrice ,HighPrice ,LowPrice ,LastPrice ,"
        "ClosePrice ,AveragePrice ,TotalTradedQuantity ,TurnoverInRs ,No.ofTrades ,"
        "DeliverableQty ,%DlyQttoTradedQty \n"
        f"{symbol} ,EQ ,01-Jan-2024 ,100.00 ,100.50 ,105.00 ,99.50 ,104.00 ,104.50 ,102.00 ,"
        "1000000 ,500000 ,1000 ,600000 ,60.00\n"
    )
    return response


@pytest.fixture
def mock_requests_session():
    with patch("market_data.providers.nse_session_client.requests.session") as mock_session_factory:
        session = MagicMock()
        mock_session_factory.return_value = session
        yield mock_session_factory, session


class TestCookiesFetchedOnceNotPerCall:

    def test_multiple_data_requests_share_one_cookie_fetch(self, mock_requests_session):
        _, session = mock_requests_session
        session.get.return_value = _csv_response()

        client = NseSessionClient()
        client._get_price_volume_and_deliverable_position_data("DEMO", "01-01-2024", "02-01-2024")
        client._get_price_volume_and_deliverable_position_data("DEMO", "01-01-2024", "02-01-2024")
        client._get_price_volume_and_deliverable_position_data("DEMO", "01-01-2024", "02-01-2024")

        # 1 cookie fetch (origin URL) + 3 real data fetches = 4 total,
        # not 3 cookie fetches + 3 data fetches = 6 -- the whole point of
        # this module vs. nselib's own fresh-session-per-call behavior.
        assert session.get.call_count == 4

    def test_only_one_requests_session_is_ever_created(self, mock_requests_session):
        mock_session_factory, session = mock_requests_session
        session.get.return_value = _csv_response()

        client = NseSessionClient()
        client._get_price_volume_and_deliverable_position_data("DEMO", "01-01-2024", "02-01-2024")
        client._get_price_volume_and_deliverable_position_data("DEMO", "01-01-2024", "02-01-2024")

        mock_session_factory.assert_called_once()


class TestNon200TriggersOneRetryWithFreshCookies:

    def test_non_200_response_reprimes_cookies_and_retries_once(self, mock_requests_session):
        _, session = mock_requests_session
        # 1st call: cookie fetch (200). 2nd call: data fetch, but stale
        # cookies -> 403. 3rd call: cookie re-fetch (200). 4th call: data
        # fetch retried, succeeds.
        session.get.side_effect = [
            _csv_response(200),  # initial cookie priming
            _csv_response(403),  # stale-cookie data fetch failure
            _csv_response(200),  # cookie re-priming
            _csv_response(200),  # retried data fetch succeeds
        ]

        client = NseSessionClient()
        df = client._get_price_volume_and_deliverable_position_data("DEMO", "01-01-2024", "02-01-2024")

        assert session.get.call_count == 4
        assert not df.empty


class TestPriceVolumeAndDeliverablePositionDataChunking:
    """Same >365-day year-chunking logic as nselib's own
    price_volume_and_deliverable_position_data() -- copied verbatim, so
    this is a regression test confirming the copy still behaves
    identically, not new logic being introduced."""

    def test_short_range_makes_a_single_fetch(self, mock_requests_session):
        _, session = mock_requests_session
        session.get.return_value = _csv_response()

        client = NseSessionClient()
        df = client.price_volume_and_deliverable_position_data(
            symbol="DEMO", from_date="01-01-2024", to_date="10-01-2024",
        )

        # 1 cookie fetch + 1 data fetch for a range well under 365 days.
        assert session.get.call_count == 2
        assert not df.empty

    def test_multi_year_range_chunks_into_multiple_fetches(self, mock_requests_session):
        _, session = mock_requests_session
        session.get.return_value = _csv_response()

        client = NseSessionClient()
        client.price_volume_and_deliverable_position_data(
            symbol="DEMO", from_date="01-01-2020", to_date="01-01-2024",
        )

        # 1 cookie fetch + N data fetches (N > 1 for a >4-year range) --
        # still only ONE cookie fetch across all of them.
        assert session.get.call_count > 2

    def test_numeric_columns_are_cleaned_and_typed(self, mock_requests_session):
        _, session = mock_requests_session
        session.get.return_value = _csv_response()

        client = NseSessionClient()
        df = client.price_volume_and_deliverable_position_data(
            symbol="DEMO", from_date="01-01-2024", to_date="02-01-2024",
        )

        assert pd.api.types.is_numeric_dtype(df["TotalTradedQuantity"])
        assert df["TotalTradedQuantity"].iloc[0] == 1_000_000
