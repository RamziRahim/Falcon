# Falcon paper trading — plan

**Status: DRAFT (2026-11-22). Not frozen. Freeze before day one; after that, changes only as dated notes.**

## Purpose

Run Falcon's candidate strategies forward on live NSE data for 12 months, automatically, with no real money, to find out:

1. **Does the system run cleanly every trading day without anyone tending it?**
2. **Do the forward trades match what the backtest code would have done on the same days?** They should match exactly.
3. **Is forward performance inside the range the 25-year history suggests?** This is not proof of an edge: one year cannot prove or disprove it.
4. **Is buying near the close worth the effort?** Tracks 3/4 vs 5/6 answer this.
5. **How do IA's own discretionary pullback trades compare?** Track 8.
6. **Does sector strength keep helping monthly momentum, as it did in 2019–26?** Track 10 vs track 1.
7. **How do smaller positions feel and fare in practice?** Track 11 vs track 1.

## Tracks

Each track has its own notional **₹10,00,000**. Rules are exactly as frozen in the docs named. No track changes rules during the run.

| # | Track | Rules | Entry fills |
|---|---|---|---|
| 1 | Monthly momentum (A10) | `docs/a_stop_preregistration.md`; `run_momentum(stop_pct=0.10)` | Month-end rank → next open; 10% stop |
| 2 | A10C (shadow) | `docs/a_stop_width_preregistration.md` | As 1; no re-buy after a stop that month |
| 3 | Current mix, close (C_F_A) | `docs/momentum_patterns_preregistration.md` | FM buys at the confirming day's **close** (stand-in for a 3:15 pm decision; IA 2026-11-22) |
| 4 | Three-way split, close (C_F_A_P3) | same | FM and P3 at the confirming close |
| 5 | Current mix, next open (C_F_A_O) | `docs/entry_realism_preregistration.md` | FM at the next open |
| 6 | Three-way split, next open (C_F_A_P3O) | same | FM and P3 at the next open |
| 7 | Current mix, FM buy-stop (C_F_A_H) | `docs/buystop_mix_preregistration.md`, **after that test runs**; IA decides if it fails | FM on a resting buy-stop at the 20-day high |
| 8 | IA discretionary pullbacks | Logged by IA (below) | As logged |
| 9 | Momentum, pullback add-on (A10P) | `docs/pullback_two_ways_preregistration.md` (failed its bar; included by IA's choice, 2026-11-22) | Half at the open, half at the weekly broken high, else next rebalance |
| 10 | Monthly momentum + sector strength (M_SEC_X10) | `docs/momentum_sector_exits_preregistration.md` (failed its bar: best in 2019–26, weaker in 2001–17; included by IA's choice, 2026-11-22) | As 1, but ranked only among stocks whose sector is strong (FM's sector rule, `backtesting/sector_strength.py`) |
| 11 | Monthly momentum at 70% size (A10_70) | `docs/half_at_1to1_preregistration.md` (comparison version, about 30% cash; included by IA's choice, 2026-11-22) | As 1, each position 70% of its normal size |

**Filters on every automatic track:**
- the ethical sector filter (`data/pit_v2/ethical_exclusions.csv`, refreshed monthly for new listings, which are unbuyable until classified);
- Falcon's quality gate (D/E < 0.33, ROCE > 10%), once `docs/quality_gate_history_preregistration.md` has run.

If that test has not run by day one, the gate is applied and its effect is reported separately.

**Track 8 logging:**
- IA sends a message (Telegram) such as `BUY SYMBOL` or `SELL SYMBOL`, optionally with a limit price, by 3:30 pm or after hours.
- A message without a price fills at the **next session's open**. A limit order fills the next session if the low reaches it, at min(open, limit).
- Stops and targets can be included and are then managed automatically.
- Track 8 uses the same ₹10 lakh, costs and filters. A filtered stock is refused, with a reply saying why.

## Daily cycle (automatic, about 7:00 pm IST on trading days)

1. Download the day's NSE bhavcopy, corporate actions and symbol changes, and update the data.
2. Fill orders placed for today's open at today's open.
3. Check every open position against today's high and low for stops and targets, using the same rules as the backtest code.
4. For close-fill tracks: evaluate today's close signals and buy at today's close.
5. Compute tomorrow's orders (momentum ranks at month end; FM, P3 and A10P orders daily) and apply the filters.
6. Write orders, fills, positions and equity per track, commit them to the GitHub repo, send the daily message, and ping the watchdog.

**The engine is the backtest code at a tagged version** (`paper-v1`). Every Sunday it re-runs the backtest over the paper period to date and checks that the trades match the paper ledger exactly. Any mismatch raises an alert.

## Where it runs

| Piece | Choice |
|---|---|
| Server | Oracle Cloud Always Free, Ampere A1 if available, home region Hyderabad or Mumbai. The account is converted to Pay As You Go so idle Always Free instances are not reclaimed, at no charge while only Always Free resources are used. |
| Record | GitHub repo `paper/` folder, committed daily (append-only ledger) |
| Watchdog | healthchecks.io (free): alert if no ping by 9:00 pm on a trading day |
| Alerts and reports | Telegram bot and/or email (IA to choose) |
| Backup runner | GitHub Actions: if the watchdog fires, a catch-up run uses Yahoo Finance prices marked "provisional", re-checked against NSE the next day |
| Claude | Not required. The engine, record and alerts run without it. Claude can read the weekly report if available. |

Before day one, a **one-week dry run** on the server must show reliable NSE downloads.

## Failure handling

| Event | Response |
|---|---|
| Missed run (server down) | Watchdog alert. The next run replays the missed days in order; results are identical because only daily data is used. |
| NSE file late or missing | Retry every 30 min until midnight. Then Yahoo Finance, marked provisional, re-checked next day. |
| NSE holiday | NSE holiday calendar; no alert. |
| Split or bonus on a holding | Shares and levels adjusted from the corporate-action feed. An unexplained jump of more than 30% raises an alert. |
| Symbol change, suspension or delisting | Followed via NSE's symbol-change list. A suspended stock is valued at its last price and flagged. Delisting is handled as in the backtest. |
| Circuit at the open | Fill recorded and flagged ("might not have been tradable"). |
| New listing not yet classified | Not buyable; added to IA's monthly review list. |
| Quality-gate data unavailable for a stock | Last known value kept and flagged. Never known = not buyable (live rule). |
| Replay mismatch | Alert. The track is marked "under investigation" until explained, with a dated note. |
| Credentials near expiry | Reminder 30 days ahead. A weekly self-test of each credential raises an alert on failure. |

**Credentials list** (kept in the server's secret store; renewal dates in `paper/credentials.md` with no secret values):
- GitHub deploy key;
- Telegram bot token / email app password;
- healthchecks.io ping URL;
- Screener login (for the gate data);
- Oracle account and card on file.

## Reports

- **Daily, about 7:30 pm:** OK or problem; fills, stops and tomorrow's orders; equity per track vs the Nifty. IA to choose: every day, or problems only plus weekly.
- **Weekly (Sunday):** replay-match result, health checks, each track vs the Nifty and its own backtest band, current drawdown.
- **Monthly:** the momentum picks and exclusions, the new-listing review list, quality-gate refresh status.

## Checkpoints: 3, 6 and 12 months

At each checkpoint, for each track:

1. **Integrity:** no unexplained missed days, and 100% replay match. Anything else must be explained before the track's results count.
2. **Performance band:** the track's return over the period, minus the Nifty's, placed in the distribution of all rolling windows of the same length in the 2008–2026 backtest (filtered).
   - Below the 5th percentile = **flag**.
   - Above the 95th = flag as unusually lucky.
3. **Drawdown:** a fall deeper than the track's worst historical drawdown = **review**.

**IA decides at every checkpoint:** continue, stop a track, or (at 12 months) move a track to small real money. Flags never act by themselves.

## Before day one (checklist)

- [ ] Buy-stop mix test run (track 7)
- [ ] Quality-gate test run, or the gate's untested status accepted by IA
- [ ] Oracle account (IA), converted to Pay As You Go
- [ ] Alerts channel and daily-message preference (IA)
- [ ] Engine built at tag `paper-v1`; replay test on the last 3 months matches the backtest exactly
- [ ] One-week dry run on the server
- [ ] This plan frozen
- [ ] Day one: **2027-01-01**, with the first momentum ranks taken at the 2026-12-31 close
