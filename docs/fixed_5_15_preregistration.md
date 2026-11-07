# Pre-registration: fixed −5% stop / +15% target (1:3) on FM and #3

**Status: FROZEN on 2026-11-07 ~22:40 IST,** before any run. IA asked: "how about 5% SL
and 15% target". This goes straight to full portfolio backtests, after the −5%/+10%
per-trade check proved misleading. Never edit; add dated notes.

## Versions

- **FM-F515:** FM as frozen (weekly rank, sector check, crash protection, rank exit,
  40-session time stop), with stop = fill × 0.95 and target = fill × 1.15.
- **S3-F515:** #3 + Nifty filter (S+ "market filter only": breakout buy-stop, Nifty above
  its 50-SMA, 20-session limit), with stop = fill × 0.95 and target = fill × 1.15.

## Both

- **Sizing:** 1% risk per trade, so about 20% positions, capped at 25% of equity; 10
  slots, cash-limited.
- **Fill rules:** the stop wins a same-day tie, including on the fill day; after the
  fill day, gaps fill at the open.
- **Same costs.**
- **Windows:** W1, W2 and 2018, with the six checks.
- **Compared with:** FM 1:3 (11.2 / 8.6 / −26.7%) and #3 + Nifty filter (17.3 / 5.5 /
  −14.3%).
- **All windows are in-sample.**

## Output

`data/fixed_5_15_result.txt`
