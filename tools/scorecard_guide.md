## How to read this scorecard

### What one row is
Each row is one complete trading strategy, simulated day by day on past NSE prices with real costs, starting with ₹10 lakh. A strategy is a fixed set of rules:
- which stocks qualify;
- when to buy (entry);
- where to sell at a loss (stop);
- where to take profit (target);
- when the whole market is too weak to buy (market filter);
- the longest a trade is held.

Variants of one idea share a family and differ in one or two rules. Every rule was written down and frozen before the test ran (the test-document column names the file), and each result was judged mechanically against that rule.

- **Data:** daily NSE prices 2007–2026 for every stock, including those later delisted (no survivorship bias), adjusted for splits, bonuses and demergers. The stock list each month is the 500 most-traded stocks by value at that time. Fundamentals were not used, because only today's figures exist. Falcon's ethical filters (debt-to-equity below 0.33; no financial-services or alcohol companies) were not applied for the same reason; a live version must apply them.
- **Costs:** brokerage and statutory charges, bid-ask spread and price impact on every buy and sell.
- **Sizing, unless the row says otherwise:** each trade risks 1% of capital, so position size = 1% of capital ÷ (buy price − stop) × buy price. No position above 25% of capital, and at most 10 positions. Monthly momentum instead holds 20 stocks in equal amounts.

### Periods
- **2019–26:** 1 Jan 2019 to 30 Oct 2026 (7.8 years). Mostly a bull market, with the 2020 crash.
- **2008–17:** 1 Jan 2008 to 31 Dec 2017 (10 years). Includes the 2008 crash and the 2011 and 2013 slumps.
- **2018:** one year on its own, when mid- and small-caps fell sharply while the Nifty 50 rose 4%. A stress test.

### Samples
- **All stocks:** the full monthly top-500 list. Used for most tests up to 8 Nov 2026.
- **Half A:** from 9 Nov 2026 the stocks were split at random (by a hash of their ID) into two halves. Half A (828 stocks) was used for all later tuning. Each month's list is half as long, so half-A figures are lower than all-stock figures; compare half-A rows only with other half-A rows.
- **Half B:** the other 794 stocks, untouched until one final run of the shortlist after tuning ended. The best evidence of what holds on stocks the rules were never tuned on.
- **Screener list:** Falcon's original stock list from the Screener.in "Leadership" query.

### Columns
- **Strategy:** plain name of the rule set.
- **Code:** the label for the run in the result files and test documents.
- **Family:** the idea it belongs to (see Families).
- **Sample:** All stocks, Half A or Half B.
- **Entry, Stop, Target, Market filter, Max hold:** the rules (see Building blocks).
- **2019–26, 2008–17:** yearly return (CAGR) of the whole account after all costs. **2018:** the return for that year.
- **₹10 L →:** what ₹10 lakh grew to by the end of the period.
- **Drop:** worst drop, the deepest fall of the whole account from its previous high at any point in the period. −40% means ₹10 lakh at a peak fell to ₹6 lakh before recovering.
- **Win:** share of closed trades that made money after costs.
- **Avg/trade:** average profit or loss per closed trade, as % of the money put in, after costs.
- **Trades:** positions bought and closed. For monthly momentum each holding counts as one trade.
- **Checks:** how many of the six checks were passed, out of 6.
- **Verdict:** the outcome against the rule frozen before the test.
  - "Rejected" means it failed that rule.
  - "Reference run" means an existing strategy re-run on the same sample for a fair comparison.
- **Notes:** caveats.
- **Test document:** the frozen rule file in the Falcon repository, which also holds the written-up results.
- **—:** not measured for that period, or not applicable.

### The six checks (per period)
1. Yearly return beats the Nifty 50 by at least 5 points.
2. Yearly return beats owning every stock in the list in equal amounts.
3. Luck test: the monthly excess return over the Nifty is statistically significant (Newey-West t ≥ 2, 3 lags).
4. Beats the Nifty in at least 4 calendar years.
5. Worst drop no more than 10 points deeper than the Nifty's.
6. The 3 most profitable stocks make under half of all profit.

The early mean-reversion (MR) tests used their own six trade-level checks; their notes say so. Every period has been used to make decisions, so all results describe the past. Only paper trading can confirm them.

### Families
- **Monthly momentum:** at each month end, rank the list by 12-month return excluding the last month (from 252 to 21 trading days ago). Hold the top 20 in equal amounts and rebalance at the next open. "+ 10% stop" sells a holding 10% below its buy price. Variants change the number held, the ranking period or the holding rule.
- **#3 Momentum breakout:**
  - **Candidates:** top 20% by 6-month return; the stock's peer group (its 20 most similar stocks) in the top third; price above the 50- and 200-day averages.
  - **Entry:** a buy-stop at the 20-day intraday high, valid for the next day, skipped if the stock opens more than 3% above it.
  - **Exits:** stop at the last swing low; target a multiple of the risk; otherwise sold after 20 trading days.
  - **"S"** is its first version, with a 2 ATR stop and trend exits.
- **Falcon Momentum (FM):**
  - **Watch list:** every Friday, rank the list by 6- and 12-month return, each divided by volatility; the top 30 form the watch list.
  - **Sector check:** the stock's NSE sector index must beat the Nifty over 6 months and be above its 50-day average. A stock with no matching index needs a strong peer group instead.
  - **Crash protection:** no new buys while the Nifty is below its 200-day average; half risk while it is below its 50-day.
  - **Entry:** originally Monday's open. The best variant, "clean close", buys at the close of a day the stock closes above its 20-day high on a clean candle.
  - **Exits:** stop at the higher of the swing low and 3 ATR below the buy; target 1:3; sold if the rank falls below 100, or after 40 trading days.
- **Portfolio combination:** two or three of the strategies above run side by side, each with its own share of capital, reset to equal shares every month (no rebalancing cost charged).
- **Other:**
  - **F:** Falcon's original chart-pattern setups (VCP, ascending triangle, flat base, bull flag), bought with a buy-stop at the pattern's pivot.
  - **B:** 52-week-high breakout.
  - **MR:** RSI-2 short-term mean reversion in the top 100 stocks.
  - **C:** buying a 3-day dip in a strong stock.
  - **Leader pullback:** buying a quiet 3–8 day dip in a momentum leader when it closes above the previous day's high.
  - **ML model:** Falcon's machine-learning-scored pattern breakouts.

### Building blocks
- **Buy-stop:** an order to buy if the price rises to a level during the day. It fills at that level, or at the open if the stock opens above it.
- **Next open:** buy at the next day's opening price after the signal.
- **Clean close:** buy at the day's close (decided about 3:20 pm), only if all of these hold:
  - the stock traded above the level and closed above it;
  - it closed above its open;
  - the upper wick is under half the day's range.
- **Range breakout:** a sideways range of at least 10 days, at most 12% from high to low, formed after the stock broke an earlier swing high. Buy at a close above the range on volume of at least 1.5× the 50-day average.
- **Retest / limit / dip to 20 EMA or SMA:** after a breakout, wait up to 10 days to buy lower: at the breakout level, the breakout candle's low, or the 20-day average.
- **Swing low stop:** just below the most recent swing low (a low with 3 higher lows on each side), minus 0.25 ATR. Trades whose stop is more than 15% away are skipped.
- **ATR:** average true range, the stock's average daily price range over 14 days.
- **1:3, 1:2 (R multiples):** risk R = buy price − stop. A 1:3 target is 3R above the buy price.
- **Fixed −5% / +10% etc.:** stop and target at fixed percentages from the buy price.
- **Stop to cost / break-even:** once the trade is up a set amount, the stop moves to the buy price.
- **Half at +5% or 1R:** sell half the position at that level; the rest runs to the stop or target.
- **Volume exit / wick exit:** sell at the entry day's close if its volume was below 1.5× average, or if it closed back below the breakout level.
- **Cool-down:** after such an exit, no re-buying that stock for 20 days.
- **Nifty filters:** no new buys while the Nifty 50 is below its 50-day (or 200-day) average.
- **Sector check:** the stock's NSE sector index must be strong (above its 50-day average, or beating the Nifty).
- **Disaster stop:** a wide stop meant only for crashes, at 15% below the buy price or 3 ATR.

