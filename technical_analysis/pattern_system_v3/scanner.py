import pandas as pd
from technical_analysis.pattern_system_v3.engine import classify_nse_stock


def scan_nse_universe(
    stock_dfs: dict[str, pd.DataFrame],
    min_avg_turnover_inr: float = 5e7,  # ₹5 Cr minimum 20-day average turnover
    atr_mult: float = 2.2,
) -> pd.DataFrame:
    rows = []
    for symbol, df in stock_dfs.items():
        if len(df) < 220:
            continue

        avg_turnover = float((df["Close"].iloc[-20:] * df["Volume"].iloc[-20:]).mean())
        if avg_turnover < min_avg_turnover_inr:
            continue

        sig = classify_nse_stock(df, atr_mult=atr_mult)
        if sig.verdict in ("REAL_PATTERN", "UNSURE"):
            rows.append(
                {
                    "Symbol": symbol,
                    "Verdict": sig.verdict,
                    "Pattern": sig.pattern_type,
                    "Score": sig.score,
                    "Breakout": sig.breakout_level,
                    "Stop": sig.stop_loss,
                    "Risk_%": sig.risk_pct,
                    "Dist_to_Pivot_%": sig.dist_to_pivot_pct,
                    "Vol_DryUp": sig.vol_dryup_ratio,
                    "Diagnostics": " | ".join(sig.notes),
                }
            )

    res = pd.DataFrame(rows)
    if not res.empty:
        res = res.sort_values(["Verdict", "Score"], ascending=[True, False]).reset_index(drop=True)
    return res