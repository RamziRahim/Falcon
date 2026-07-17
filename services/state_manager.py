"""
===============================================================================
Falcon AI Swing Trading Platform
Module : state_manager.py
Package: services

Purpose:
Centralized application state management for Falcon.

All UI components interact with application state exclusively through this
module. Direct access to st.session_state outside this class is discouraged.

Author : Falcon
===============================================================================
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st


class StateManager:
    """
    Centralized manager for Falcon application state.

    This class abstracts Streamlit's session_state and provides a stable API
    for the rest of the application.
    """

    _DEFAULT_STATE = {

        # Candidate Selection
        "selected_symbol": None,

        # Screener Results
        "scan_result": None,
        "candidates_df": pd.DataFrame(),

        # Chart Data
        "technical_df": pd.DataFrame(),

        # AI Cache
        "ai_cache": {},

        # Scan Metadata
        "last_scan_time": None,

        # Market Snapshot
        "market_snapshot": {},

    }

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    @classmethod
    def initialize(cls) -> None:
        """
        Initialize Falcon session state.
        Safe to call multiple times.
        """

        for key, value in cls._DEFAULT_STATE.items():

            if key not in st.session_state:

                # Prevent mutable defaults from being shared
                if isinstance(value, dict):
                    st.session_state[key] = {}

                elif isinstance(value, pd.DataFrame):
                    st.session_state[key] = pd.DataFrame()

                else:
                    st.session_state[key] = value

    # ------------------------------------------------------------------
    # Generic Helpers
    # ------------------------------------------------------------------

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        return st.session_state.get(key, default)

    @classmethod
    def set(cls, key: str, value: Any) -> None:
        st.session_state[key] = value

    # ------------------------------------------------------------------
    # Candidate Selection
    # ------------------------------------------------------------------

    @classmethod
    def get_selected_symbol(cls) -> str | None:
        return cls.get("selected_symbol")

    @classmethod
    def set_selected_symbol(cls, symbol: str) -> None:
        cls.set("selected_symbol", symbol)

    # ------------------------------------------------------------------
    # Candidate Data
    # ------------------------------------------------------------------

    @classmethod
    def get_candidates(cls) -> pd.DataFrame:
        return cls.get("candidates_df")

    @classmethod
    def set_candidates(cls, dataframe: pd.DataFrame) -> None:
        cls.set("candidates_df", dataframe)

    # ------------------------------------------------------------------
    # Technical Data
    # ------------------------------------------------------------------

    @classmethod
    def get_technical_data(cls) -> pd.DataFrame:
        return cls.get("technical_df")

    @classmethod
    def set_technical_data(cls, dataframe: pd.DataFrame) -> None:
        cls.set("technical_df", dataframe)

    # ------------------------------------------------------------------
    # AI Cache
    # ------------------------------------------------------------------

    @classmethod
    def get_ai_cache(cls) -> dict:
        return cls.get("ai_cache")

    @classmethod
    def get_ai_result(cls, symbol: str):

        cache = cls.get_ai_cache()

        return cache.get(symbol)

    @classmethod
    def save_ai_result(cls, symbol: str, result: dict) -> None:

        cache = cls.get_ai_cache()

        cache[symbol] = {

            "generated_at": datetime.now(),

            "result": result,

        }

        cls.set("ai_cache", cache)

    # ------------------------------------------------------------------
    # Scan Metadata
    # ------------------------------------------------------------------

    @classmethod
    def set_last_scan_time(cls) -> None:
        cls.set("last_scan_time", datetime.now())

    @classmethod
    def get_last_scan_time(cls):

        return cls.get("last_scan_time")

    # ------------------------------------------------------------------
    # Market Snapshot
    # ------------------------------------------------------------------

    @classmethod
    def set_market_snapshot(cls, snapshot: dict) -> None:
        cls.set("market_snapshot", snapshot)

    @classmethod
    def get_market_snapshot(cls) -> dict:
        return cls.get("market_snapshot")

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    @classmethod
    def clear(cls) -> None:
        """
        Reset Falcon state.
        Useful when starting a fresh scan.
        """

        for key in list(cls._DEFAULT_STATE.keys()):

            st.session_state.pop(key, None)

        cls.initialize()