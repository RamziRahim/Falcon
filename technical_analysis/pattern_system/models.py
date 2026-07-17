"""
===============================================================================
Falcon AI Swing Trading Platform — Core Pattern System Models
===============================================================================
Script      : models.py
Package     : Technical Analysis / Pattern System
===============================================================================
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class SwingPoint:
    """Represents a validated fractal structural peak (High) or trough (Low) on a chart."""
    index: int
    date: str
    price: float
    type: Literal["HIGH", "LOW"]
    is_higher: bool  # True if Higher High (HH) or Higher Low (HL) relative to prior pivot


@dataclass(frozen=True)
class VCPContraction:
    """Tracks the dimensional metrics of a single volatility contraction wave."""
    wave_number: int
    swing_high_price: float
    swing_low_price: float
    depth_percentage: float  # (High - Low) / High * 100
    length_days: int         # Total bars taken to complete the contraction wave