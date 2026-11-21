
---

# Update, 2026-11-07 → 2026-11-09

Every test below is pre-registered in `docs/`. Each doc has its results section.

## Full-universe tests (2026-11-07/08)

| Test | 2019-26 (W1) | 2008-17 (W2) | 2018 | Verdict |
|---|---|---|---|---|
| **A10**: monthly 12-1 momentum, top 20, 10% stop (`a_stop`) | **26.4%** (DD −39%), 5/6 | **13.2%** (DD −59%), 5/6 | −38.9% | Best raw return; deep drawdowns |
| A, top 10 / top 15 (`a_topn`) | top 15 + stop 25.8% | 11.6% | | No better than top 20 |
| FM exit variants R2, break-even (`fm_variants`) | R2 10.0% | 8.0% | −19.0% | R3 stays best |
| Fixed −5%/+10% and −5%/+15% brackets, #3 and FM (`fixed_5_15`) | −7% to −10% | −10% | | Fail. The descriptive per-trade check misled; gaps and re-entries broke it |
| FM 20-day-high buy-stop entry (`fm_high20`) | 9.0-9.5% | 9.7-12.2% | −20 to −23% | Mixed |
| #3 quality breakout, 4 checks (`s_quality`) | 1.5% | 0.6% | | Fail |
| Range + volume, buy the next open (`range_volume`) | #3 5.4%, FM 5.5% | #3 −0.8%, FM 9.0% | | Fail |
| Volume exit at the close, with and without a cool-down (`volume_exit`, `volume_cooldown`) | 0.7% to 5.5% | −8% to 5.4% | | Fail: churn |
| Portfolio combinations (`portfolio_combo`) | A10 + #3 + FM 18.9% (DD −22%) | 9.7% (−34%) | −26.9% | Smoother, but missed the frozen bar |

Descriptive finding: breakout-day volume ≥ 1.5× separates better #3 trades (+2.6%
against +0.8% per trade in W1; +1.9% against −0.2% in W2). But the volume is known only
at the close, and every way of acting on it lost money.

## Hold-out split (2026-11-09)

The stocks were split by hash into half A (828 stocks, used for all tuning) and half B
(794, used once). Half-A numbers are only comparable with each other.

| Half-A test | Result |
|---|---|
| **FM, clean-candle close entry, FM_C3** (`close_entry`) | **14.5% / 12.7%** against FM's 9.1% / 8.7%; DD −18% / −23%. Candidate |
| #3 clean-close / + volume | Worse than the buy-stop: the day-one gain is lost |
| #3 retest at the breakout candle low / 20-EMA / 20-SMA (`retest_depth`) | None beats the buy-stop in both decades |
| #3 true range breakout: ≥ 10-day range, ≤ 12% wide, after a swing-high break, close on 1.5× volume (`range_breakout`) | Better trades (57% wins, +2.2% per trade, half the DD) but a third as many; 6.9% / 3.6% |
| Range breakout at 2% risk (`rb_risk_combo`) | 9.8% / 6.7%, DD −22% |
| IA's leader pullback rules (`pullback`) | About 1% / 0%. Fail: 9-20 trades a year, no edge |
| Pullback diagnostics (`pullback_diagnostics`) | No dip set has an edge. Plain momentum leaders (+1.35% 20-day excess, t 3.0) beat every dip variant. Momentum + 5-day dip adds about 0.2pp in W1 and nothing in W2 |
| Falcon pattern audit + salvage (`falcon_salvage`) | 55% of pivot buy-stop fills are wick fakeouts: −1.3% against +2.6% per trade. 70% of detections fail a sanity check: triangle pivot = average of 2 highs; VCP pivot below the base top; 32% not above a rising 200-DMA. Momentum filter + clean close + wider stop still reaches only 5.1% / 1.4%. The patterns add nothing |
| Wick exit at the close (`wick_exit`) | Worse for every strategy: the win rate halves |
| **FM_C3 + A10 pair, C_F_A** (`wick_exit`) | **20.7% / 12.6%**, DD −21% / −36%; 5/6 checks in both. Missed the frozen bar by 0.09pp |

## One-time half-B confirmation (`halfB_confirmation`)

| Strategy | Half B W1 | Half B W2 | Checks | Half A for comparison |
|---|---|---|---|---|
| A10 | **23.2%** (DD −41%) | **12.2%** (−59%) | 5 / 5 | 25.9% / 11.3% |
| **C_F_A** | **16.1%** (−31%) | **12.4%** (−36%) | 5 / 5 | 20.7% / 12.6% |
| FM_C3 | 8.4% (−26%) | 11.3% (−24%) | 2 / 5 | 14.5% / 12.7% |
| FM, original | 8.3% | 4.1% | 2 / 3 | 9.1% / 8.7% |
| #3 + Nifty | 6.2% | 0.5% | 2 / 2 | 9.9% / 3.4% |
| Range breakout 2% | −2.9% | 4.1% | 1 / 3 | 9.8% / 6.7% |

Nifty: 10.0% / 5.5%.

**Verdicts under the frozen rules:**
- **FM_C3 is not confirmed.** It trails the Nifty in W1 on half B.
- **C_F_A is not confirmed,** missing by 0.06pp. Its W1 drawdown was 9.94pp shallower
  than A10's, against the 10pp required. It held up in substance: it beats the Nifty by
  6-7pp a year in both decades, with 5 of 6 checks on both halves.

## What the evidence now says

1. **The one edge that survives every sample is momentum stock selection.** A10 makes
   23-26% in W1 and 11-13% in W2 on all stocks, half A and half B.
2. **Entry timing tricks, chart patterns and dip-buying add nothing reliable on top of
   it.** Several results looked good on half A, then failed on half B: #3 and the range
   breakout.
3. **Momentum's cost is its drawdowns:** −33% to −41% in 2019-26, −59% in 2008-17, and
   about −36% in 2018. Pairing it with FM_C3 roughly halves the 2008-17 drawdown and keeps
   about 75-80% of the return.
4. **Candidate for paper trading:** C_F_A (FM clean-close + A10, half each), or A10 alone
   if the drawdowns are acceptable. Live results should be expected below the backtest.
