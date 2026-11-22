# Falcon paper trading

Plan: `docs/paper_trading_plan.md` (frozen 2026-11-22 18:22 IST). Engine: tag `paper-v1`.

| File | What |
|---|---|
| `paper/data_update.py` | Brings `data/pit_v2` to the latest NSE session (needs NSE access: laptop or Indian-region server) |
| `paper/engine.py` | Replays every track from day one with the backtest functions; writes the ledger, orders and the daily report |
| `paper/check_engine.py` | Dry-run check on past data: engine (history from 2022) vs the same functions on full history must match exactly |
| `paper/nse_holidays.csv` | NSE trading holidays (add 2027 when NSE publishes its circular) |
| `paper/manual/track8_orders.csv` | IA's discretionary orders (track 8): date, action, symbol, limit, stop, target, note |
| `paper/manual/new_listings_cleared.csv` | New listings IA has reviewed: entity_id, excluded (true/false), note |
| `paper/ledger/<track>/` | equity.csv, trades.csv (closed), positions.csv (open) |
| `paper/orders/<date>.csv` | Month-end momentum orders for the next open |
| `paper/reports/<date>.md` | Daily summary |

Daily: `python paper/data_update.py && python paper/engine.py`, then commit `paper/`.

Checks done before tagging `paper-v1` (2026-11-22), all on past data with a pretend day one of 2026-09-01:
- engine vs full-history backtest: all 10 automatic tracks identical to the paisa (`paper/check_engine.py 2026-08-31 2026-09-01 2026-11-20`);
- no look-ahead: a run cut at 2026-10-15 gives the same record to that date as a run to 2026-11-20;
- the 2026-10-30 evening orders equal the 2026-11-02 fills on tracks 1, 10 and 11.
