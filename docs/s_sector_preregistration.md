# Pre-registration: #3 with a sector filter, and five exit variants

**Status: FROZEN on 2026-11-05 ~23:45 IST,** before any run. Requested by IA:
- replace "Nifty above its 50-day average" with "the stock's **sector** above its 50-day
  average", falling back to the matching mid- or small-cap index if no sector index
  applies;
- then redo 1:3, 1:2 and a 5% 1:1 bracket;
- and, for 1:3 and 1:2, book half at +5%, move the stop to cost, and take the rest at
  the target.

Never edit; add dated notes.

## Honest framing

- **All windows are now in-sample.** W1 2019-26 and W2 2008-17 shaped earlier designs.
- **2018 was used once,** as the S+ hold-out, and its result is known. It is reported
  again here but is no longer unseen.
- These results describe the past. Only paper trading can confirm them.

## Entry (unchanged #3)

The S signals (`backtesting/fixed_bracket.entries_s`), with the same rules:
- the stock's 6-month return is in the top 20% of the universe;
- its peer group of 20 correlated stocks is in the top third (top 10% when the Nifty is
  below its 200-SMA);
- the close is above its 50- and 200-SMA;
- a buy-stop at the 20-day high for the next session.

1% risk per trade, positions ≤ 25% of equity, at most 10 positions, a 20-session time
limit.

## New filter: sector above its 50-day average

At the signal close, a stock may be ordered only if **its index** closes above that
index's 50-session SMA:
1. **Its NSE sector index,** if one fits: the best 252-session daily-return correlation
   ≥ 0.5 among Auto, Bank, Energy, Financial Services, FMCG, IT, Media, Metal, Pharma,
   PSU Bank and Realty. The mapping is refreshed monthly, as in FM.
2. **Otherwise, its size bucket's index,** by that month's universe rank:
   - ranks 1-100: Nifty 50;
   - ranks 101-250: **our equal-weight mid-cap index**;
   - ranks 251-500: **our equal-weight small-cap index**.

   The official Nifty Midcap 100 and Smallcap 100 histories start only in Nov 2015 and
   Apr 2016. Our indices are built from the point-in-time universe (each month's members,
   equal weight, daily) and cover 2008-2026 consistently.

The Nifty-50-above-50-SMA filter from S+ is **not** used.

## Exit variants (5)

| Code | Stop | Target | Half exit |
|---|---|---|---|
| R3 | Swing low − 0.25 ATR (skip if > 15%) | 3R | — |
| R2 | Swing low − 0.25 ATR (skip if > 15%) | 2R | — |
| F5 | Entry × 0.95 | Entry × 1.05 (1:1) | — |
| R3H | Swing low − 0.25 ATR | 3R | Sell half at **+5%**, then the stop moves to the entry from the next session |
| R2H | Swing low − 0.25 ATR | 2R | Same as R3H |

**Same-day rules:**
- the stop wins a tie, including on the fill day;
- after the fill day, a gap through a level fills at the open;
- the half exit and the full target can both trade on the same day;
- break-even is not live on the day the half is sold.

## Windows and judgement

- **Windows:** W1, W2 and 2018, each with the six checks.
- **Compared with:** the original #3 (R3, no filter) and S+ "market filter only".
- **Reported:**
  - win rate, average win and loss, mean net per trade, exit mix;
  - how often the sector index vs the size-bucket index decided.
- No variant is called proven unless it passes both W1 and W2. Even then, the next step
  is paper trading.

## Outputs

- `data/s_sector_result.txt`
- trades in `data/s_sector_trades_*.csv`
