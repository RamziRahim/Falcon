"""
===============================================================================
Falcon AI Swing Trading Platform — MACD Divergence/Convergence Signal
===============================================================================
Script      : macd_signal.py
Package     : Technical Analysis / Pattern System

MACD_Line, MACD_Signal, MACD_Hist are already computed and persisted in
data/technical/ for every ticker (technical_analysis/indicators/momentum.py),
confirmed unused anywhere downstream until now -- no new computation
needed here, just reading what already exists.

Bidirectional by design, not negative-only: a VCP breakout where MACD is
also aligning upward is genuinely a higher-conviction setup than a
neutral MACD. Only penalizing the negative case (divergence) while never
crediting the positive case (alignment) would leave real signal on the
table in one direction for no principled reason.
===============================================================================
"""
from __future__ import annotations

import pandas as pd

MIN_ROWS_FOR_SIGNAL = 2  # need at least a "latest" and "prior" bar


def get_macd_signal(df: pd.DataFrame, lookback_bars: int = 10) -> str:
    """
    Checks the relationship between MACD_Hist and recent price action
    over the last `lookback_bars` bars.

    Returns one of:
      "BULLISH_ALIGNMENT"  -- MACD_Hist positive and rising vs. the prior
                              bar (momentum accelerating with the breakout)
      "BEARISH_DIVERGENCE" -- price near its recent high in the window,
                              but MACD_Hist has faded well off its own
                              recent peak and is still falling (price
                              extending, momentum not confirming)
      "NEUTRAL"            -- neither condition clearly fires

    NEUTRAL is the most common outcome and means no modifier applied --
    the absence of confirmation is different from active contradiction.
    """
    if "MACD_Hist" not in df.columns or df["MACD_Hist"].isna().all():
        return "NEUTRAL"

    if len(df) < MIN_ROWS_FOR_SIGNAL:
        return "NEUTRAL"

    recent = df.tail(lookback_bars)
    latest_hist = recent["MACD_Hist"].iloc[-1]
    prior_hist = recent["MACD_Hist"].iloc[-2]
    latest_close = recent["Close"].iloc[-1]

    # Bullish: histogram positive and increasing
    if latest_hist > 0 and latest_hist > prior_hist:
        return "BULLISH_ALIGNMENT"

    # Bearish divergence: price at or near recent high, histogram declining
    # well off its own recent peak -- momentum fading behind price strength.
    price_near_high = latest_close >= recent["Close"].quantile(0.85)
    hist_declining = latest_hist < recent["MACD_Hist"].max() * 0.7
    if price_near_high and hist_declining and latest_hist < prior_hist:
        return "BEARISH_DIVERGENCE"

    return "NEUTRAL"
