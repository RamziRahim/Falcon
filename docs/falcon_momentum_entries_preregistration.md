# Pre-registration: FM with entry triggers (E1 range breakout, E2 liquidity sweep, E3 fair value gap)

**Status: FROZEN on 2026-11-04 ~16:45 IST,** before any run. IA approved the design
("Go") after seeing the definitions below. Never edit; add dated notes.

## Question

Within the stocks FM already selects (`docs/falcon_momentum_preregistration.md`), does
waiting for a defined entry point beat buying at the next open (E0)? The baseline is FM
with a 40-session time stop (W1 +11.2%/yr, W2 +8.6%/yr).

## Watch list (unchanged FM selection)

- At each week's last session, while the Nifty 50 is above its 200-SMA: the top 30 by
  FM's momentum rank, passing FM's sector confirmation, go on a watch list for **10
  sessions**. A stock still qualifying the next week has its window renewed.
- Each stock is bought **only when its trigger appears** within the window. No trigger
  means no trade.
- A trigger is ignored while the Nifty is at or below its 200-SMA.

## Entry triggers (one track each)

**E1: range breakout, IA's definition** (`tests/analyse_ia_breakout.py`)
- **Setup:** a close above the previous swing high, then a 5–30 session range at most
  10% wide.
- **Trigger:** a close above the range top on volume > 1.5× the 50-session average.
- **Buy:** at the next open; skipped if the open is > 5% above the close.
- **Stop:** the range low − 0.25 × ATR(14).

**E2: liquidity sweep**
- **Trigger:** the low trades below the most recent confirmed swing low (a Falcon
  fractal, 3 bars each side, within the last 60 sessions), and the close is back above
  it.
- **Buy:** at the next open; skipped if the open is > 5% above the close.
- **Stop:** that day's low − 0.25 × ATR(14).

**E3: fair value gap retest** (Falcon's `fvg_detector` definition)
- **The gap:** a bullish gap exists when candle 1's high < candle 3's low; the gap is
  candle 1's high to candle 3's low.
- **Which gap:** the most recent gap formed within the last 20 sessions that is not yet
  mitigated, meaning no later low has reached the gap bottom, and whose top is below the
  current close, so the price must come back down into it.
- **Buy:** a limit order at the gap top for the next session, filled if the low reaches
  it, at the lower of the open and the gap top. It is re-placed daily while the stock is
  on the watch list.
- **Stop:** the gap bottom − 0.25 × ATR(14).

## Identical to FM

- **Sizing and limits:**
  - 1% risk per trade, 0.5% while the Nifty is at or below its 50-SMA;
  - each position ≤ 25% of equity;
  - at most 10 positions; when slots are full, the best momentum rank goes first.
- **Exits:**
  - target 3R;
  - the momentum exit (rank > 100 at a weekly ranking);
  - a 40-session time stop.
- **Fill rules:** the stop wins a same-day tie, including on the fill day; after the
  fill day, gaps fill at the open. A trade is skipped if the stop is > 15% below the
  fill or at or above it.
- **Same costs, universe and windows** (W1 2019-01-01 → 2026-10-30, W2 2008-01-01 →
  2017-12-31), and the same six checks.

## Judgement

Each trigger is judged by the six checks, and must pass both windows. It is also
compared with E0: CAGR, drawdown, win rate, mean net per trade. Three tracks are tested,
so any pass is provisional, and the next step is paper trading.

## Outputs

- `data/fm_entries_{breakout,sweep,fvg}_result.txt`
- trades in `data/fm_entries_*_trades_*.csv`

---

## Results, 2026-11-04

Full output: `data/fm_entries_{breakout,sweep,fvg}_result.txt`. **All three fail**, and
none beats E0 (FM's next-open entry) on CAGR in either window.

| Entry | CAGR W1 / W2 | Max DD W1 / W2 | Win % W1 / W2 | Mean net/trade W1 / W2 | Trades W1 / W2 | Avg exposure W1 / W2 |
|---|---|---|---|---|---|---|
| E0 next open (FM) | **11.2 / 8.6** | −25.6 / −27.0 | 39.8 / 43.7 | +1.56 / +1.81 | 610 / 691 | 53 / 47 |
| E1 range breakout | 2.4 / 5.7 | **−14.3 / −8.0** | 40.4 / **51.7** | +0.66 / **+4.25** | 156 / 143 | 20 / 16 |
| E2 liquidity sweep | 4.8 / 5.2 | −32.1 / −27.2 | 32.5 / 37.6 | +0.83 / +0.93 | 793 / 814 | 43 / 38 |
| E3 FVG retest | −4.9 / −8.7 | −37.1 / −79.0 | 30.0 / 31.1 | +0.07 / −0.09 | 1831 / 2039 | 55 / 47 |

*Nifty: 10.0 / 5.5% CAGR, −38 / −60% drawdown.*

**Reading:**
- **E3:** FVGs are mostly narrow, so the stop is very close and is hit by noise (about
  70% of trades). Many small losses plus costs.
- **E2:** a tighter stop (about 5% average loss vs 9%) but a lower win rate. Positive
  per trade in both windows, but below E0.
- **E1:** the best per trade on W2 (+4.2%, a 52% win rate) and the smallest drawdowns,
  but it triggers rarely: about 15-20 trades a year and 16-20% capital in use. So its
  CAGR is low. It is not consistent: per trade on W1 (+0.66%) is below E0.
- No re-tuning on these windows.
