"""
===============================================================================
Falcon AI Swing Trading Platform
Module  : chart_models.py
Package : chart

Purpose
-------
Core data models used by Falcon's charting engine.

This module defines the contracts shared by:

    • Chart Panel
    • Chart Renderer
    • Layer Manager
    • Individual Chart Layers

No rendering logic belongs here.
===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# =============================================================================
# Chart Modes
# =============================================================================

class ChartMode(str, Enum):
    """
    Display mode of the chart.
    """

    DASHBOARD = "dashboard"
    FOCUS = "focus"


# =============================================================================
# Time Frames
# =============================================================================

class TimeFrame(str, Enum):
    """
    Supported chart intervals.
    """

    DAILY = "1D"
    WEEKLY = "1W"
    MONTHLY = "1M"


# =============================================================================
# Theme
# =============================================================================

class ChartTheme(str, Enum):
    """
    Chart appearance.
    """

    DARK = "dark"
    LIGHT = "light"


# =============================================================================
# Layer Types
# =============================================================================

class LayerType(str, Enum):
    """
    Supported chart layers.

    New layers should be added here only.
    """

    CANDLESTICK = "candlestick"

    VOLUME = "volume"

    MA20 = "ma20"
    MA50 = "ma50"
    MA150 = "ma150"
    MA200 = "ma200"

    EMA21 = "ema21"
    EMA50 = "ema50"
    EMA200 = "ema200"

    VWAP = "vwap"

    ATR = "atr"

    RSI = "rsi"

    MACD = "macd"

    SUPPORT = "support"

    RESISTANCE = "resistance"

    BREAKOUT = "breakout"

    VCP = "vcp"

    LIQUIDITY_SWEEP = "liquidity_sweep"

    FAIR_VALUE_GAP = "fair_value_gap"

    TRADE_MARKERS = "trade_markers"

    AI_ANNOTATIONS = "ai_annotations"


# =============================================================================
# Individual Layer
# =============================================================================

@dataclass(slots=True)
class ChartLayer:
    """
    Represents one drawable chart layer.
    """

    layer: LayerType

    enabled: bool = False

    opacity: float = 1.0

    order: int = 100

    metadata: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Render Options
# =============================================================================

@dataclass(slots=True)
class ChartRenderOptions:
    """
    Controls how the renderer produces the figure.
    """

    mode: ChartMode = ChartMode.DASHBOARD

    timeframe: TimeFrame = TimeFrame.DAILY

    theme: ChartTheme = ChartTheme.DARK

    height: int = 650

    width: int | None = None

    show_toolbar: bool = True

    show_range_slider: bool = False

    show_legend: bool = False

    enable_zoom: bool = True

    enable_pan: bool = True

    enable_crosshair: bool = True

    responsive: bool = True


# =============================================================================
# Default Layer Configuration
# =============================================================================

DEFAULT_LAYERS = [

    ChartLayer(
        layer=LayerType.CANDLESTICK,
        enabled=True,
        order=1,
    ),

    ChartLayer(
        layer=LayerType.VOLUME,
        enabled=True,
        order=2,
    ),

    ChartLayer(
        layer=LayerType.MA20,
        enabled=True,
        order=10,
    ),

    ChartLayer(
        layer=LayerType.MA50,
        enabled=True,
        order=11,
    ),

    ChartLayer(
        layer=LayerType.MA150,
        enabled=False,
        order=12,
    ),

    ChartLayer(
        layer=LayerType.MA200,
        enabled=False,
        order=13,
    ),

    ChartLayer(
        layer=LayerType.BREAKOUT,
        enabled=False,
        order=30,
    ),

    ChartLayer(
        layer=LayerType.VCP,
        enabled=False,
        order=31,
    ),

    ChartLayer(
        layer=LayerType.SUPPORT,
        enabled=False,
        order=40,
    ),

    ChartLayer(
        layer=LayerType.RESISTANCE,
        enabled=False,
        order=41,
    ),

    ChartLayer(
        layer=LayerType.TRADE_MARKERS,
        enabled=False,
        order=50,
    ),

    ChartLayer(
        layer=LayerType.AI_ANNOTATIONS,
        enabled=False,
        order=60,
    ),
]