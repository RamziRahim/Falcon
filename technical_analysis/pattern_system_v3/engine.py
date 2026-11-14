"""
===============================================================================
Falcon AI Swing Trading Platform — Pattern engine v3 (Stage 2 + ATR-zigzag geometry)
===============================================================================
Source: PATTERN_ENGINE_SPEC.md (supplied by IA, 2026-11-14, generated with Gemini),
reference implementation kept as written except for these changes (see
docs/falcon_pattern_audit.md, "v3 engine"):
  1. VCP depths used Pivot objects in arithmetic and crashed; uses .price now.
  2. Ascending triangle needs at least 3 swing highs on the ceiling (spec allowed 2,
     its own acceptance test describes 3 touches).
  3. Detector order is cup -> triangle -> VCP -> bull flag -> flat base (spec: VCP first).
     With VCP first, the spec's own triangle and cup fixtures are labelled VCP, because
     a 3-touch triangle with rising lows and a cup with a shallow handle both satisfy
     the VCP rules. Specific shapes are checked before the general one.
  5. A triangle also needs its rising lows to form a straight support line: the
     smaller step between successive lows is at least 0.6 x the larger. Lows that
     rise in shrinking steps (each pullback about half the last) are left to the VCP
     rules. This only decides the label between two shapes the spec cannot separate.
  4. detect_pattern() returns the pattern, breakout level and stop without the
     right-edge timing verdict, so Falcon's own entry rules can decide timing.
     classify_nse_stock() keeps the spec's verdict logic unchanged.
Dependencies: numpy, pandas, standard library only. Only data up to the last row of
the frame is used; callers must pass history up to the scan day.
===============================================================================
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import numpy as np
import pandas as pd


@dataclass
class Pivot:
    idx: int
    price: float
    kind: str          # "HIGH" or "LOW"
    confirmed: bool    # False for live right-edge extreme


@dataclass
class PatternSignal:
    verdict: str               # "REAL_PATTERN", "UNSURE", "NOT_A_PATTERN"
    pattern_type: str          # "VCP", "ASCENDING_TRIANGLE", "FLAT_BASE", "BULL_FLAG", "CUP_WITH_HANDLE", "NONE"
    breakout_level: float
    stop_loss: float
    risk_pct: float
    dist_to_pivot_pct: float
    vol_dryup_ratio: float
    score: int                 # 0 to 100 quality score
    notes: List[str] = field(default_factory=list)


def prepare_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["SMA_50"] = out["Close"].rolling(50).mean()
    out["SMA_150"] = out["Close"].rolling(150).mean()
    out["SMA_200"] = out["Close"].rolling(200).mean()

    prev_close = out["Close"].shift(1)
    tr = pd.concat(
        [
            out["High"] - out["Low"],
            (out["High"] - prev_close).abs(),
            (out["Low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    out["ATR_14"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    out["Vol_SMA_50"] = out["Volume"].rolling(50).mean()

    out["SMA_50_Slope"] = out["SMA_50"].diff(20)
    out["SMA_200_Slope"] = out["SMA_200"].diff(20)
    return out


def check_stage2_regime(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    if len(df) < 220:
        return False, ["Insufficient history (< 220 sessions)"]

    last = df.iloc[-1]
    if pd.isna(last["SMA_200"]) or pd.isna(last["ATR_14"]):
        return False, ["Indicators not warmed up"]

    reasons = []
    if not (last["Close"] > last["SMA_50"] > last["SMA_150"] > last["SMA_200"]):
        reasons.append("Failed MA stack (Close > SMA50 > SMA150 > SMA200)")

    if last["SMA_200_Slope"] <= 0:
        reasons.append("200-day SMA is flat or declining")

    if last["SMA_50_Slope"] < -0.5 * last["ATR_14"]:
        reasons.append("50-day SMA is sloping downward")

    lookback_252 = df.iloc[-min(len(df), 252):]
    high_52w = lookback_252["High"].max()
    low_52w = lookback_252["Low"].min()

    if last["Close"] < 0.75 * high_52w:
        reasons.append("Price is >25% below 52-week high")

    if high_52w < 1.25 * low_52w:
        reasons.append("Prior 52-week advance < 25%")

    return len(reasons) == 0, reasons


def detect_atr_zigzag(df: pd.DataFrame, atr_mult: float = 2.2) -> List[Pivot]:
    highs = df["High"].to_numpy()
    lows = df["Low"].to_numpy()
    atrs = df["ATR_14"].to_numpy()
    n = len(df)

    start = 50
    pivots: List[Pivot] = []

    init_high_idx = start + int(np.argmax(highs[start : start + 10]))
    init_low_idx = start + int(np.argmin(lows[start : start + 10]))

    if init_low_idx < init_high_idx:
        direction = 1
        ext_idx, ext_price = init_high_idx, highs[init_high_idx]
    else:
        direction = -1
        ext_idx, ext_price = init_low_idx, lows[init_low_idx]

    for i in range(max(init_high_idx, init_low_idx) + 1, n):
        atr = atrs[i]
        if np.isnan(atr) or atr <= 0:
            continue

        if direction == 1:
            if highs[i] >= ext_price:
                ext_price = highs[i]
                ext_idx = i
            if lows[i] <= ext_price - atr_mult * atr:
                pivots.append(Pivot(idx=ext_idx, price=float(ext_price), kind="HIGH", confirmed=True))
                direction = -1
                ext_idx, ext_price = i, lows[i]
        else:
            if lows[i] <= ext_price:
                ext_price = lows[i]
                ext_idx = i
            if highs[i] >= ext_price + atr_mult * atr:
                pivots.append(Pivot(idx=ext_idx, price=float(ext_price), kind="LOW", confirmed=True))
                direction = 1
                ext_idx, ext_price = i, highs[i]

    pivots.append(
        Pivot(
            idx=ext_idx,
            price=float(ext_price),
            kind="HIGH" if direction == 1 else "LOW",
            confirmed=False,
        )
    )
    return pivots


def _detect_vcp(df: pd.DataFrame, pivots: List[Pivot]) -> Optional[dict]:
    n = len(df)
    recent = [p for p in pivots if p.idx >= n - 80]

    pairs: List[Tuple[Pivot, Pivot]] = []
    for i in range(len(recent) - 1):
        if recent[i].kind == "HIGH" and recent[i + 1].kind == "LOW":
            pairs.append((recent[i], recent[i + 1]))

    if len(pairs) < 2:
        return None

    pairs = pairs[-4:]
    highs = [h.price for h, _ in pairs]
    lows = [l.price for _, l in pairs]

    ceiling = max(highs)
    if (ceiling - min(highs)) / ceiling > 0.035:
        return None

    depths = [(h.price - l.price) / h.price for h, l in pairs]  # change 1: spec subtracted Pivot objects
    if depths[0] > 0.28 or depths[-1] > 0.10:
        return None

    for i in range(1, len(depths)):
        if depths[i] > depths[i - 1] * 0.88:
            return None
        if lows[i] < lows[i - 1] * 0.995:
            return None

    atr_last = float(df["ATR_14"].iloc[-1])
    return {
        "pattern_type": "VCP",
        "breakout_level": ceiling,
        "stop_loss": lows[-1] - 0.5 * atr_last,
        "notes": [
            f"{len(pairs)} contractions: " + " -> ".join(f"-{d*100:.1f}%" for d in depths),
            "Higher lows & flat overhead supply confirmed",
        ],
    }


def _detect_ascending_triangle(df: pd.DataFrame, pivots: List[Pivot]) -> Optional[dict]:
    n = len(df)
    recent = [p for p in pivots if p.idx >= n - 70]

    highs = [p for p in recent if p.kind == "HIGH"]
    lows = [p for p in recent if p.kind == "LOW"]

    if len(highs) < 3 or len(lows) < 2:          # change 2: 3 ceiling touches
        return None

    highs = highs[-3:]
    lows = lows[-3:]

    if lows[-1].idx < highs[0].idx:
        return None

    h_prices = [p.price for p in highs]
    l_prices = [p.price for p in lows]
    ceiling = max(h_prices)

    if (ceiling - min(h_prices)) / ceiling > 0.020:
        return None

    atr_last = float(df["ATR_14"].iloc[-1])
    for i in range(1, len(l_prices)):
        if l_prices[i] <= l_prices[i - 1] + 0.5 * atr_last:
            return None

    steps = np.diff(l_prices)
    if len(steps) >= 2 and steps.min() < 0.6 * steps.max():   # change 5: straight support line
        return None

    initial_depth = (ceiling - l_prices[0]) / ceiling
    final_depth = (ceiling - l_prices[-1]) / ceiling
    if not (0.05 <= initial_depth <= 0.25 and final_depth <= 0.095):
        return None

    return {
        "pattern_type": "ASCENDING_TRIANGLE",
        "breakout_level": ceiling,
        "stop_loss": l_prices[-1] - 0.5 * atr_last,
        "notes": [
            f"Flat ceiling at {ceiling:.2f} ({len(highs)} touches within 2%)",
            f"Rising lows ({len(lows)} troughs) narrowing depth from -{initial_depth*100:.1f}% to -{final_depth*100:.1f}%",
        ],
    }


def _detect_flat_base(df: pd.DataFrame) -> Optional[dict]:
    if len(df) < 80:
        return None

    for base_len in (18, 25, 35):
        base = df.iloc[-base_len:]
        prior = df.iloc[-(base_len + 45) : -base_len]
        if len(prior) < 20:
            continue

        base_high = float(base["High"].max())
        base_low = float(base["Low"].min())
        box_depth = (base_high - base_low) / base_high

        bars_since_peak = base_len - 1 - int(np.argmax(base["High"].to_numpy()))
        if bars_since_peak < 5 or box_depth > 0.11:
            continue

        prior_low = float(prior["Low"].min())
        if (base_high - prior_low) / prior_low < 0.20:
            continue

        if base_low < float(base["SMA_50"].iloc[-1]) * 0.97:
            continue

        atr_last = float(df["ATR_14"].iloc[-1])
        return {
            "pattern_type": "FLAT_BASE",
            "breakout_level": base_high,
            "stop_loss": base_low - 0.5 * atr_last,
            "notes": [
                f"{base_len}-session Flat Base with -{box_depth*100:.1f}% total box depth",
                "Held above rising 50-day SMA throughout consolidation",
            ],
        }
    return None


def _detect_bull_flag(df: pd.DataFrame) -> Optional[dict]:
    for flag_len in (5, 8, 12):
        for pole_len in (6, 10, 14):
            if len(df) < flag_len + pole_len + 5:
                continue

            flag = df.iloc[-flag_len:]
            pole = df.iloc[-(flag_len + pole_len) : -flag_len]

            pole_low = float(pole["Low"].min())
            pole_high = float(pole["High"].max())
            pole_gain = (pole_high - pole_low) / pole_low

            if pole_gain < 0.15:
                continue

            if pole["Volume"].max() < 1.5 * float(pole["Vol_SMA_50"].max()):
                continue

            flag_high = float(flag["High"].max())
            flag_low = float(flag["Low"].min())
            flag_depth = (pole_high - flag_low) / pole_high
            retrace_ratio = (pole_high - flag_low) / (pole_high - pole_low)

            if flag_high > pole_high * 1.005 or flag_depth > 0.085 or retrace_ratio > 0.382:
                continue

            if flag["Volume"].mean() > 0.85 * float(df["Vol_SMA_50"].iloc[-1]):
                continue

            atr_last = float(df["ATR_14"].iloc[-1])
            return {
                "pattern_type": "BULL_FLAG",
                "breakout_level": pole_high,
                "stop_loss": flag_low - 0.5 * atr_last,
                "notes": [
                    f"+{pole_gain*100:.1f}% flagpole followed by {flag_len}-bar flag (-{flag_depth*100:.1f}% depth)",
                    f"Flag retraced {retrace_ratio*100:.0f}% of pole on contracting volume",
                ],
            }
    return None


def _detect_cup_with_handle(df: pd.DataFrame) -> Optional[dict]:
    if len(df) < 90:
        return None

    window = df.iloc[-80:]
    handle = window.iloc[-10:]
    cup = window.iloc[:-10]

    left_lip = float(cup["High"].iloc[:20].max())
    right_lip = float(cup["High"].iloc[-15:].max())
    cup_bottom = float(cup["Low"].iloc[15:-10].min())

    cup_depth = (left_lip - cup_bottom) / left_lip
    if not (0.12 <= cup_depth <= 0.30):
        return None

    if abs(left_lip - right_lip) / left_lip > 0.035:
        return None

    midpoint = cup_bottom + 0.5 * (left_lip - cup_bottom)
    lower_half_share = (cup["Close"] < midpoint).mean()
    if lower_half_share < 0.35:
        return None

    pivot = max(left_lip, right_lip)
    handle_low = float(handle["Low"].min())
    handle_depth = (pivot - handle_low) / pivot

    if handle_depth > 0.085 or handle_low < midpoint:
        return None

    atr_last = float(df["ATR_14"].iloc[-1])
    return {
        "pattern_type": "CUP_WITH_HANDLE",
        "breakout_level": pivot,
        "stop_loss": handle_low - 0.5 * atr_last,
        "notes": [
            f"Rounded cup (-{cup_depth*100:.1f}% depth) with -{handle_depth*100:.1f}% upper-rim handle",
            f"U-shape symmetry score: {lower_half_share*100:.0f}% bars in lower basin",
        ],
    }


def _match(df: pd.DataFrame, atr_mult: float) -> Optional[dict]:
    """First valid geometry in change-3 order (df must already have indicators)."""
    pivots = detect_atr_zigzag(df, atr_mult=atr_mult)
    for fn in (lambda: _detect_cup_with_handle(df), lambda: _detect_ascending_triangle(df, pivots),
               lambda: _detect_vcp(df, pivots), lambda: _detect_bull_flag(df), lambda: _detect_flat_base(df)):
        m = fn()
        if m is not None:
            return m
    return None


@dataclass
class Detection:
    stage2: bool
    pattern_type: str          # as PatternSignal.pattern_type
    breakout_level: float
    stop_loss: float
    risk_pct: float            # (breakout - stop) / breakout, as a fraction
    risk_ok: bool              # inside the spec's [2%, 11.5%] stop window
    notes: List[str] = field(default_factory=list)


def detect_pattern(df: pd.DataFrame, atr_mult: float = 2.2) -> Detection:
    """Change 4: pattern geometry only, no right-edge timing verdict."""
    df = prepare_indicators(df)
    ok, notes = check_stage2_regime(df)
    if not ok:
        return Detection(False, "NONE", 0.0, 0.0, 0.0, False, notes)
    m = _match(df, atr_mult)
    if m is None:
        return Detection(True, "NONE", 0.0, 0.0, 0.0, False, ["No valid base geometry"])
    pv, sp = float(m["breakout_level"]), float(m["stop_loss"])
    risk = (pv - sp) / pv
    return Detection(True, m["pattern_type"], pv, sp, risk, 0.02 <= risk <= 0.115, list(m["notes"]))


def detect_at(df: pd.DataFrame, t: int, atr_mult: float = 2.2, history: int = 400) -> Detection:
    """Detection on the scan day at row t, using only rows up to t."""
    return detect_pattern(df.iloc[max(0, t - history + 1): t + 1].reset_index(drop=True), atr_mult)


def classify_nse_stock(df: pd.DataFrame, atr_mult: float = 2.2) -> PatternSignal:
    df = prepare_indicators(df)
    is_stage2, stage2_notes = check_stage2_regime(df)

    last = df.iloc[-1]
    close_last = float(last["Close"])
    vol_sma = float(last["Vol_SMA_50"]) if last["Vol_SMA_50"] > 0 else 1.0
    vol_dryup = float(df["Volume"].iloc[-5:].mean() / vol_sma)

    if not is_stage2:
        return PatternSignal(
            verdict="NOT_A_PATTERN",
            pattern_type="NONE",
            breakout_level=0.0,
            stop_loss=0.0,
            risk_pct=0.0,
            dist_to_pivot_pct=0.0,
            vol_dryup_ratio=round(vol_dryup, 2),
            score=0,
            notes=stage2_notes,
        )

    matched = _match(df, atr_mult)

    if matched is None:
        return PatternSignal(
            verdict="NOT_A_PATTERN",
            pattern_type="NONE",
            breakout_level=0.0,
            stop_loss=0.0,
            risk_pct=0.0,
            dist_to_pivot_pct=0.0,
            vol_dryup_ratio=round(vol_dryup, 2),
            score=20,
            notes=["Passed Stage 2 uptrend, but no valid contraction/base geometry found"],
        )

    pivot = float(matched["breakout_level"])
    stop = float(matched["stop_loss"])
    risk_pct = (pivot - stop) / pivot
    dist_pct = (pivot - close_last) / pivot
    notes = list(matched["notes"])

    if risk_pct > 0.115 or risk_pct < 0.02:
        notes.append(f"Rejected: stop distance {risk_pct*100:.1f}% outside [2.0%, 11.5%] risk window")
        return PatternSignal(
            verdict="NOT_A_PATTERN",
            pattern_type=matched["pattern_type"],
            breakout_level=round(pivot, 2),
            stop_loss=round(stop, 2),
            risk_pct=round(risk_pct * 100, 2),
            dist_to_pivot_pct=round(dist_pct * 100, 2),
            vol_dryup_ratio=round(vol_dryup, 2),
            score=35,
            notes=notes,
        )

    bar_range = float(last["High"] - last["Low"])
    upper_wick = float(last["High"] - max(last["Open"], last["Close"]))
    is_heavy_rejection = (
        last["Close"] < last["Open"]
        and last["Volume"] > 1.3 * vol_sma
        and bar_range > 0
        and (upper_wick / bar_range) > 0.45
        and abs(dist_pct) <= 0.03
    )

    one_day_jump = (close_last - float(df["Close"].iloc[-2])) / float(df["Close"].iloc[-2])
    if one_day_jump > 0.075 and dist_pct >= 0:
        notes.append(f"Downgraded: raw +{one_day_jump*100:.1f}% 1-day surge needs handle digestion")
        return PatternSignal(
            verdict="UNSURE",
            pattern_type=matched["pattern_type"],
            breakout_level=round(pivot, 2),
            stop_loss=round(stop, 2),
            risk_pct=round(risk_pct * 100, 2),
            dist_to_pivot_pct=round(dist_pct * 100, 2),
            vol_dryup_ratio=round(vol_dryup, 2),
            score=55,
            notes=notes,
        )

    score = 60
    if vol_dryup <= 0.75:
        score += 20
        notes.append(f"Strong right-side volume dry-up ({vol_dryup:.2f}x 50D avg)")
    elif vol_dryup <= 0.95:
        score += 10
        notes.append(f"Acceptable volume contraction ({vol_dryup:.2f}x 50D avg)")
    else:
        notes.append(f"Elevated right-side volume ({vol_dryup:.2f}x 50D avg)")

    if risk_pct <= 0.075:
        score += 10

    if is_heavy_rejection:
        notes.append("Downgraded to UNSURE: heavy red distribution/rejection candle at pivot")
        verdict = "UNSURE"
        score -= 20
    elif -0.03 <= dist_pct <= 0.045 and vol_dryup <= 1.05:
        verdict = "REAL_PATTERN"
        score += 10
        notes.append(f"Actionable right edge ({dist_pct*100:.1f}% from breakout pivot)")
    elif 0.045 < dist_pct <= 0.095:
        verdict = "UNSURE"
        notes.append(f"Developing base: price is still {dist_pct*100:.1f}% below pivot")
    else:
        verdict = "NOT_A_PATTERN"
        notes.append(f"Out of position ({dist_pct*100:.1f}% from pivot)")

    return PatternSignal(
        verdict=verdict,
        pattern_type=matched["pattern_type"],
        breakout_level=round(pivot, 2),
        stop_loss=round(stop, 2),
        risk_pct=round(risk_pct * 100, 2),
        dist_to_pivot_pct=round(dist_pct * 100, 2),
        vol_dryup_ratio=round(vol_dryup, 2),
        score=max(0, min(100, score)),
        notes=notes,
    )