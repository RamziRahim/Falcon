# Strategy research summary (as of 2026-11-03)

Every test below was pre-registered: rules fixed before the result was seen, then judged
mechanically. Data:
- survivorship-free NSE bhavcopies 2007 → 2026-10-30, every listed stock including
  delisted ones;
- adjusted for splits, bonuses and demergers from NSE records;
- 1,079 symbol renames linked;
- ETFs and sub-₹5 stocks excluded;
- universe = the top 500 by traded value each month;
- costs: Indian delivery charges plus liquidity spread and impact;
- benchmark: NSE NIFTY 50.

Full output: `data/final_results_2026-11-03.txt`.

| Strategy | 2019 → 2026 (W1) | 2008 → 2017 (W2, unseen) | Verdict |
|---|---|---|---|
| Falcon breakout model (runs #5, #6, refit) | 6-13 trades in 2 years; no edge; refit not estimable | — | No edge |
| **A** monthly 12-1 momentum, top 20 | 2019-24: **42.0%/yr vs Nifty 16.1%** (passes 6/6). 2024-26: 14.8% vs −3.6%, but −35.5% drawdown vs −15.8% and one stock carries the profit, so not confirmed | 8.4%/yr vs 5.5%, but **−80% drawdown** (2008) vs −60%; t 0.51 | No demonstrated edge (bull-market only, crashes hard) |
| **B** 52-week-high breakout | 18.2% vs 16.1% (2019-24), loses to equal-weight 23.4% | — | No edge |
| **C** dip in a momentum leader, 20-day hold | 8.8% vs 16.1% (2019-24) | — | No edge |
| **MR** RSI-2 mean reversion, top 100 | −0.5%/yr vs 10.0%; 60% win rate; +0.00% net per trade | 3.1%/yr vs 5.5%; 62% win rate; +0.22% net per trade (t 1.71); drawdown −27% vs −60% | No edge (fails both) |
| **S** strong stock + strong peer group, 20-day-high buy-stop | −3.8%/yr, −62% drawdown, 33% wins | −11.5%/yr, −81% drawdown | No edge |
| **Fixed brackets** (stop −2%/+6% and −3%/+6%, 5 × 20%) on F, S, B, MR entries | All 8 lose: −10% to −85%/yr; best win rate 33.5% (MR −3/+6) | All 8 lose: −12% to −88%/yr | No edge (16/16 fail; tight stops sit inside daily noise, 6% cap removes big winners) |
| **F** Falcon's own setups, pivot buy-stop on breakout day | −5.8%/yr, 0/8 years beat Nifty | 1.8%/yr vs 5.5%, drawdown −40% vs −60% | No edge |

## What the evidence says

1. **Rule-based swing entries had no edge after Indian costs, on either decade.** That
   covers chart-pattern breakouts (Falcon F, S, B), dip-buying (C) and short-term mean
   reversion (MR). Entering on the breakout day (S, F) instead of a day late did not
   rescue them.
2. **Momentum is the one real effect, and it is regime-dependent.** It made big money
   in the 2019-24 small/mid-cap bull market. It fell 80% in 2008, more than the Nifty,
   and 36% in 2024-25.
3. **Mean reversion's edge exists before costs and is about the size of the costs.**
   Gross ≈ +0.33% per trade on W1. It did somewhat better on W2, and its drawdowns were
   far smaller than the Nifty's, but it lost on risk-adjusted return in both windows.
4. **Data quality mattered enormously.** Survivorship, unadjusted bonuses, penny ticks,
   renames and ETFs each changed individual results. That is why every result here was
   rebuilt on the corrected data before being recorded.

## Data-quality notes recorded during the work

- Of the remaining one-day moves over 40% while a stock was in the universe, 47 remain
  over 2007-2026, nearly all genuine:
  - 2008-09 crash and rebound;
  - Satyam, Yes Bank, DHFL and Jet Airways.
- Known leftovers:
  - SUVEN's 2020 demerger (a 95% drop, outside the 5-90% demerger rule);
  - MAJESCO's 2020 special dividend (−99% in price, but paid in cash);
  - GBN and KNL in 2008 (unrecorded).
- Re-running on the corrected data changed no verdict. Small number changes from the
  earlier runs:
  - A 2019-24: 42.31 → 41.98%;
  - B 2019-24: 14.65 → 18.16%;
  - S W1: −2.9 → −3.8%;
  - F W1: −6.3 → −5.8%;
  - MR W1: −0.4 → −0.5%.
