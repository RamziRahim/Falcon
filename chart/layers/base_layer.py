"""
===============================================================================
Falcon AI Swing Trading Platform
Module  : base_layer.py
Package : chart.layers

Purpose
-------
Defines the abstract base class for all chart layers.

Every drawable chart layer must inherit from BaseLayer.

Responsibilities
----------------
• Standardize the drawing interface
• Provide layer metadata
• Validate incoming data
===============================================================================
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd
import plotly.graph_objects as go

from chart.chart_models import LayerType


class BaseLayer(ABC):
    """
    Abstract base class for all Falcon chart layers.
    """

    def __init__(self, layer_type: LayerType):
        self.layer_type = layer_type

    @abstractmethod
    def draw(
        self,
        fig: go.Figure,
        dataframe: pd.DataFrame,
        row: int = 1,
        col: int = 1,
    ) -> None:
        """
        Draw the layer on the supplied figure.
        """
        raise NotImplementedError

    @staticmethod
    def validate_columns(
        dataframe: pd.DataFrame,
        required_columns: list[str],
    ) -> None:
        """
        Validate required dataframe columns.
        """
        missing = [
            column
            for column in required_columns
            if column not in dataframe.columns
        ]

        if missing:
            raise ValueError(
                f"Missing dataframe columns: {missing}"
            )