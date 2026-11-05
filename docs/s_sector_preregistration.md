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

---

## Results, 2026-11-06 (`data/s_sector_result.txt`)

CAGR, with max drawdown in brackets. Nifty: W1 10.0% / W2 5.5% / 2018 +4.1%.

| Variant (sector filter) | W1 2019-26 | W2 2008-17 | 2018 | Win % W1 / W2 | Net per trade W1 / W2 |
|---|---|---|---|---|---|
| R3 | 11.1% (−37%) | 0.2% (−46%) | −9.2% | 47.9 / 43.2 | +1.19 / +0.31% |
| R2 | 5.8% (−40%) | −0.8% (−45%) | −8.9% | 46.0 / 44.1 | +0.76 / +0.16% |
| F5 (±5%) | −47.5% (−99%) | −61.9% (−100%) | −37.1% | 43.6 / 39.3 | −1.03 / −1.77% |
| R3H | 3.9% (−31%) | −5.2% (−49%) | −10.1% | **65.7 / 61.7** | +0.44 / −0.49% |
| R2H | 0.1% (−37%) | −6.0% (−52%) | −13.5% | 64.0 / 62.0 | +0.13 / −0.56% |
| *Reference: #3 + Nifty filter (S+)* | *17.3% (−24%)* | *5.5% (−34%)* | *−14.3%* | | |
| *Reference: original #3* | *20.4% (−23%)* | *−0.2% (−57%)* | *−21.4%* | | |

**Verdict:** no variant passes. The best is R3, at 3/6 checks on W1 and 1/6 on W2.

**Reading:**
- **The sector filter did worse than the plain Nifty filter in both decades,** with
  deeper drawdowns. It was better only in 2018: −9% vs −14% for the Nifty-filtered
  version.
- Most stocks (about 3 in 4) are judged by the mid- or small-cap bucket index. The
  filter blocks good momentum stocks when that bucket dips. It also lets trades through
  when the broad market is falling but a sector index is still above its 50-SMA, which is
  why the W2 drawdown is −46% vs −34%.
- **±5% 1:1 is ruinous as a portfolio.** At 1% risk, a 5% stop means about 20% positions.
  At about 450 trades a year, losing −1 to −1.8% per trade compounds to near-total loss.
- **Half at +5% then break-even** raises the win rate to 55-66%, but lowers net per
  trade and CAGR in every window. The same pattern was seen with the half exit on
  2026-11-04.
