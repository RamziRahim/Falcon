# Falcon paper trading

Plan: `docs/paper_trading_plan.md` (frozen 2026-11-22 18:22 IST). Engine: `paper-v1` = commit `5f5eebf` on branch `claude/swing-low-risk` (a git tag of the same name exists locally; tags could not be pushed from the build environment).

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

## Oracle server (set up 2026-11-22/23)

- `falcon-paper`: Oracle Cloud Always Free Arm VM (2 OCPU, 12 GB, Ubuntu 24.04, 50 GB), region ap-hyderabad-1, tenancy ramzi_r, public IP 129.225.78.232, clock set to Asia/Kolkata.
- Login: the SSH key lives only in IA's Oracle Cloud Shell (`~/.ssh/falcon_vm`, user `ubuntu`).
- GitHub: the server has its own deploy key (`falcon-paper (Oracle)`, write access, this repository only).
- Code: `~/falcon` on branch `claude/swing-low-risk`; Python venv `~/venv` (requirements.txt).
- Seed data: branch `paper-data` (bhavcopy to 2026-11-20 in three parts, pit sources, ethical exclusions).
- The first full `tests/build_pit_v2.py` on the server (2026-11-23) took 1 min 52 s, peaking at 7.0 GB of RAM. It reproduced the laptop/cloud build:
  - `prices_adjusted.parquet` identical (content fingerprint);
  - `adjustments.csv` identical (1,932 rows);
  - `universe_monthly.parquet` identical except two stocks with equal median turnover in 2000-07 swapping ranks 460/461 (tie order; both in the universe, no effect).
- NSE archive downloads work from the server (bhavcopy for 2026-11-20 fetched, HTTP 200).
- Still to do: daily cron, email alerts (IA enters the app password on the server), missed-run watchdog, committing `paper/` outputs from the server.
