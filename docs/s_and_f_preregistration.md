# Pre-registration: S (strong stock in a strong peer group, buy-stop entry) and F (Falcon's own setups, pivot buy-stop entry)

**Status: FROZEN on 2026-11-02 ~20:10 IST.**

Written:
- before either strategy was run on any data;
- before the 2007-2017 data was usable (the combined bhavcopy file still covered only
  2018-2026, and `data/pit/` had not been rebuilt).

IA approved both tests in conversation. Never edit; add dated notes.

## Why these two

Everything tested so far entered **a day late**: the next open after a confirmed signal.
Run #4's own numbers show what that cost:
- +83% at the (impossible) pivot price;
- −3% at the next open;
- up to +20% with a buy-stop order at the pivot placed the evening before. That figure
  only counted stocks that did break out, so it is an optimistic bound.

Both tests below enter **on the breakout day** with a resting buy-stop order. They count
every triggered order, including false breakouts.

- **S** asks: do momentum leaders inside strong groups pay off when bought as they make
  new highs, with a market switch for corrections?
- **F** asks: does Falcon's own pattern engine have an edge once it is entered properly?

## Data and windows (both strategies)

- Data: `data/pit/` (survivorship-free, split/bonus/demerger-adjusted, ETF-free
  top-500-by-traded-value universe at each month end).
- **W1 = 2019-01-01 → 2026-10-30.** **W2 = 2008-01-01 → 2017-12-31**, unseen, including
  the 2008 crash. 2007 data is look-back only.
- Costs: `mtm_portfolio.CostModel`. Delisting: sold at the last close − 5%. Start ₹10
  lakh. No leverage.
- **Judgement:** the six checks of `docs/redesign_preregistration.md`, applied per
  window:
  1. CAGR beats Nifty by ≥ 5 pp/yr;
  2. beats the PIT equal-weight universe;
  3. monthly excess t (NW3) ≥ 2;
  4. beats Nifty in ≥ 4 calendar years (W1 has 8 calendar periods, W2 has 10; the
     threshold stays 4);
  5. drawdown no worse than Nifty's − 10 pp;
  6. top-3 positions < 50% of profit, open positions included.
- **A strategy passes only if it passes in BOTH windows.** Nothing is re-tuned after
  either result.

## Strategy S: strong stock, strong peer group, market switch, buy-stop at the 20-day high

### Why "peer group" instead of NSE sectors

Historical sector labels are not available for companies that no longer exist. In our
sector map, 0 of the 65 universe stocks that stopped trading after 2018 have a sector,
and only 57% of the 2019 universe is mapped. Using it would quietly bring survivorship
bias back.

So a stock's group is defined by co-movement, which is what a sector captures. At each
month end, a stock's **peer group** is the 20 universe stocks whose daily returns over
the previous 252 sessions are most correlated with its own. A stock needs ≥ 200 of those
sessions to be eligible. This uses only past data and covers every company.

### Definitions

All measured at a month end and used for the following month:
- **Peer strength:** the average 126-session return of the stock's 20 peers.
- **Strong group:** peer strength in the top third of universe stocks.
- **Top group:** peer strength in the top 10% of universe stocks.

### Signal at close t (stock in the current universe and not held)

- **Strong stock:**
  - the 126-session return is in the top 20% of the current universe;
  - close > 50-SMA, and close > 200-SMA.
- **Group and market switch:**
  - Nifty 50 close > its 200-SMA: the stock needs a strong group, and trades at full size;
  - otherwise: the stock needs a top group, and trades at half size.

### Entry

- A buy-stop at the 20-session high (the highest High of t−19..t), valid only for t+1.
- It fills if High(t+1) ≥ the trigger, at max(trigger, Open(t+1)).
- No fill if Open(t+1) > trigger × 1.03, because a gap above that is a chase.
- When more signals arrive than free slots, priority goes to the highest 126-session
  return.

### Exits, whichever comes first

- **Stop:** fill − 2 × ATR(14) at t. It is checked intraday; a gap through the stop fills
  at the open. It is checked on the fill day too.
- **Trend exit:** a close below the 20-SMA, sold at the next open.
- **Momentum exit:** the stock's 126-session return drops out of the universe's top 40%,
  sold at the next open.
- **Group exit:** at a month end, the stock's peer strength drops out of the top half,
  sold at the next open.
- **Time stop:** 30 sessions after entry, sold at the next open.

### Sizing

- 1% of equity at risk per trade (0.5% under the half-size rule);
- at most 10 positions;
- gross exposure ≤ 100%.

## Strategy F: Falcon's own setups, buy-stop at Falcon's pivot

### Scan

- Every 5 sessions (Falcon's backtest cadence), on each universe stock's adjusted daily
  history up to and including the scan day.
- Falcon's `technical_analysis.pattern_engine.analyze_ticker()` runs unchanged, with
  indicators and relative volume as in the live path. These are trailing indicators, so
  nothing reads past the scan day.

### A setup qualifies at scan day t if all of these hold

- One of Falcon's four scored continuation detectors (VCP, ascending triangle, flat
  base, bull flag) reports its *setup* flag. When several fire, priority follows Falcon's
  `PATTERN_WEIGHTS` in that order. Cup & handle is excluded: it is on probation in
  Falcon, with weight 0.
- That pattern has **not** confirmed a breakout, so the stock hasn't broken out yet.
- Close(t) < pivot and Close(t) ≥ 0.95 × pivot, meaning within 5% below the breakout
  level.

### Trade plan (Falcon's own)

- `get_entry_target_stop()` is given entry = pivot, with the pattern's own pivot,
  proximal low and structural low.
- That gives Falcon's two-low stop (with ATR clamps) and its measured-move target.
- Falcon's RR floor (`MIN_REWARD_RISK`) must hold at the pivot.

### Order

- A buy-stop at the pivot, valid for the next 5 sessions (until the next scan).
- It fills on the first day High ≥ pivot, at max(pivot, Open).
- No fill if that Open > pivot × 1.03.
- Cancelled if any day's Low reaches the stop before the order fills.

### Exits (Falcon's)

- stop, with the stop winning a same-day tie with the target;
- the measured-move target;
- a gap through either level fills at the open;
- `MAX_HOLDING_TRADING_DAYS` (40) sessions after the fill, sold at the next open.

### Sizing (Falcon's)

- 1% of equity at risk per trade;
- at most 5 positions;
- gross exposure ≤ 100%.
- When more fills arrive than free slots on a day, priority goes to the higher pattern
  weight, then to the setup closest below its pivot.

**No model, no regime ceiling, no fundamentals.** This is a test of the pattern engine
and Falcon's trade plan alone, which are what F is about.

## Outcomes

- **Passes both windows:** provisional edge, so forward paper trading next. For F, the
  next step is a Falcon change: surface "ready to break out" setups with the pivot as a
  buy-stop level.
- **Passes only one window, or none:** no demonstrated edge. Report plainly; no
  re-tuning.

---

## W1 results, 2026-11-02 (`data/s_and_f_result_W1.txt`)

| W1 2019-01-01 → 2026-10-30 | S | F | Nifty 50 | PIT equal-weight |
|---|---|---|---|---|
| CAGR | −2.9% | −6.3% | 10.1% | 15.2% |
| Max drawdown | −60.5% | −45.3% | −38.4% | |
| Monthly excess t | −1.20 | −4.63 | | |
| Years beating Nifty | 2/8 | 0/8 | | |
| Closed trades | 1,342 | 491 | | |
| Win rate | 33% | 40% | | |
| Average win / loss | +14.2% / −6.4% | +9.9% / −7.2% | | |
| Checks passed | 0/6 | 1/6 | | |

**S.** Trades that ran to the 30-session time stop averaged +30%, but:
- 677 trend exits averaged +0.6%;
- 472 stops averaged −8.2%.

**Sensitivity (does not change the verdict).** On 61 fill days the day's low was below
the stop. The frozen rule counts these as stopped out, because daily bars can't show
whether the low came before the breakout. Those trades lost ₹5.8 lakh. Treating them all
as neutral would leave S at about +4%/yr, still far below the Nifty.

**F.** Falcon's setups:

| Pattern | Setups found |
|---|---|
| ascending triangle | 7,621 |
| flat base | 5,805 |
| VCP | 966 |
| bull flag | 206 |
| **Total** | **14,598** |

- Median plan RR is 1.76.
- Entered with a pivot buy-stop, they averaged +0.16% gross and **−0.30% net** per trade.
- 260 stops (−7.5%) against 129 targets (+11.7%) and 96 time stops (+3.2%).
- Only 6 same-day exits, so the fill-day assumption doesn't matter here.

**Both fail W1.** A pass needs both windows, so **both are NO DEMONSTRATED EDGE**. W2 will
be run for the record when the 2007-2017 data is built. Nothing is re-tuned.
