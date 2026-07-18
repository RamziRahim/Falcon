"""
Tests for chart/layers/candlestick_layer.py -- Volume added to the hover
tooltip via customdata (Plotly's go.Candlestick has no native Volume
field), degrading gracefully rather than crashing when Volume is absent.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import pytest
from plotly.subplots import make_subplots

from chart.layers.candlestick_layer import CandlestickLayer


def _subplot_figure() -> go.Figure:
    """draw() adds traces by row/col -- requires a real subplot grid."""
    return make_subplots(rows=2, cols=1)


def _ohlc_df(with_volume: bool = True) -> pd.DataFrame:
    data = {
        "Open": [100.0, 101.0, 102.0],
        "High": [105.0, 106.0, 107.0],
        "Low": [99.0, 100.0, 101.0],
        "Close": [104.0, 105.0, 106.0],
    }
    if with_volume:
        data["Volume"] = [150_000, 160_000, 170_000]
    return pd.DataFrame(data, index=pd.date_range("2024-01-01", periods=3, freq="D"))


class TestVolumeInTooltip:

    def test_customdata_populated_when_volume_present(self):
        fig = _subplot_figure()
        CandlestickLayer().draw(fig, _ohlc_df(with_volume=True))

        trace = fig.data[0]
        assert trace.customdata is not None
        assert list(trace.customdata) == [150_000, 160_000, 170_000]
        assert "Volume" in trace.hovertemplate
        assert "%{customdata" in trace.hovertemplate

    def test_does_not_crash_when_volume_absent(self):
        fig = _subplot_figure()
        CandlestickLayer().draw(fig, _ohlc_df(with_volume=False))

        trace = fig.data[0]
        assert trace.customdata is None
        assert "Volume" not in trace.hovertemplate, (
            "Tooltip should omit the Volume line entirely when the column "
            "is missing, not show a broken 'Volume: nan'."
        )

    def test_price_fields_still_present_regardless_of_volume(self):
        for with_volume in (True, False):
            fig = _subplot_figure()
            CandlestickLayer().draw(fig, _ohlc_df(with_volume=with_volume))
            trace = fig.data[0]
            assert "Open" in trace.hovertemplate
            assert "High" in trace.hovertemplate
            assert "Low" in trace.hovertemplate
            assert "Close" in trace.hovertemplate

    def test_still_raises_on_missing_ohlc_columns(self):
        """Volume is optional; the actual OHLC price columns are not."""
        broken_df = pd.DataFrame({"Open": [100.0], "High": [105.0]})
        with pytest.raises(ValueError):
            CandlestickLayer().draw(_subplot_figure(), broken_df)
