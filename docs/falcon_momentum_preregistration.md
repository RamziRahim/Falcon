# Pre-registration: FM, Falcon Momentum (momentum rank + sector confirmation + crash protection + 1:3 R:R)

**Status: FROZEN on 2026-11-04 ~16:40 IST,** before any run. IA asked for one approach
that combines Falcon's original idea:
- good stocks;
- a momentum ranking, compared with the market;
- confirmation that the stock's sector is also going up;
- crash protection;
- a risk-reward under which the strategy still makes money when 50% of trades fail.

Claude chose the details below, using published evidence where it exists: NSE's momentum
index method, and volatility- and regime-based crash protection. Never edit; add dated
notes.

## What cannot be tested: fundamentals

Falcon's fundamental data is a **current** Screener snapshot, with no history. Applying
today's fundamentals to past dates would select companies already known to have
survived, which is look-ahead bias. **FM is therefore tested without the fundamental
filter.** In live use the filter can only remove names, and its effect stays untested
until point-in-time quarterly data is collected.

## Universe and data

The point-in-time top 500 by traded value, the same as all earlier tests:
survivorship-free, adjusted, ETF-free, ≥ ₹5. Same costs and delisting rule.

## Rules

**1. Momentum rank, weekly.** Computed at the last session of each week, over that
month's universe.
- 6-month return (126 sessions) and 12-month return (252 sessions), each divided by the
  stock's annualised daily-return volatility over 252 sessions. This is the
  Nifty200 Momentum 30 method.
- Each is z-scored across the universe, and the two z-scores are averaged.
- Stocks without 252 sessions of history are skipped.
- **Candidates = the top 30.**

**2. Sector confirmation.** The stock's sector is "going up" if:
- **Sector index:** at each month end, the stock is mapped to the NSE sector index whose
  daily returns correlate most with its own over the previous 252 sessions:
  - indices: Auto, Bank, Energy, Financial Services, FMCG, IT, Media, Metal, Pharma,
    PSU Bank, Realty;
  - the mapping is used only if that correlation is ≥ 0.5;
  - confirmed if the index's 126-session return > the Nifty 50's, and the index close
    > its 50-session SMA.
- **Otherwise, its peer group:** the stock's 20 most-correlated universe peers have an
  average 6-month return in the top third of the universe. This is the survivorship-free
  method already used in S.

**3. Crash protection.**
- **No new entries** while the Nifty 50 close is at or below its 200-session SMA.
- **Risk per trade:**
  - 1% of equity while the Nifty 50 is above its 50-session SMA;
  - 0.5% otherwise.

**4. Entry.**
- At the next session's open, buy candidates that pass rule 2, in rank order.
- Skipped if the open is more than 5% above the signal close.
- At most 10 positions; each position ≤ 25% of equity; no leverage.

**5. Stop: 1R.** The tighter, meaning higher, of:
- the last confirmed swing low − 0.25 × ATR(14), the swing-low rule already tested;
- the fill − 3 × ATR(14). This keeps the stop sensible when the last swing low is far
  below the price.

The trade is skipped if the fill is at or below the stop.

**6. Exits.**
- **Target** = fill + 3 × (fill − stop), so R:R is 1:3. Break-even before costs is a
  25% win rate, so the strategy can lose on half its trades and still profit.
- **Stop:** wins a same-day tie; after the fill day, gaps fill at the open.
- **Momentum exit:** at a weekly ranking, a holding ranked below 100 is sold at the next
  open.
- **Time stop: 40 sessions,** about 8 weeks. Momentum is documented over weeks to
  months, and 20 sessions ended 60-75% of trades early in the swing-low test.
- **Secondary track, reported separately:** the same rules with a 20-session time stop,
  IA's 2-4 week horizon.

## Windows and judgement

- **W1** = 2019-01-01 → 2026-10-30; **W2** = 2008-01-01 → 2017-12-31.
- Judged by the same six checks.
- Passes only if both windows pass. That pass is still provisional, and the next step is
  paper trading.

## Reported

- Win rate, average win and loss, exit mix, exposure.
- The share of time the crash filter blocked entries.
- The Nifty and the equal-weight universe for comparison.

## Outputs

- `data/falcon_momentum_t40_result.txt` and `data/falcon_momentum_t20_result.txt`
- trades in `data/falcon_momentum_*_trades_*.csv`
