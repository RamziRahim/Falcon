# Pre-registration: a true range breakout for #3 (half A)

**Status: FROZEN on 2026-11-09 ~16:50 IST,** before any run. IA pointed out that the
20-day high is not a range, and that my "range low" was not a real range low. This test
replaces #3's 20-day-high breakout with IA's definition: break an earlier swing high,
consolidate in a range, break out of the range on volume. IA set the swing-high rule
(any earlier swing high) and the stop (a few points below the swing low, which is #3's
stop), and left the range parameters to me. Never edit; add dated notes.

## Range (`find_range`), evaluated at the signal close, session i

- Grow back from session i while (highest high / lowest low − 1) ≤ **12%**, up to 60
  sessions.
- The range must be at least **10 sessions** long.
- **Range high / range low** = the highest high / lowest low of that stretch.
- **Range start** s = its first session.

## Earlier swing high broken (`pivot_highs`, fractal 3)

- p = the most recent swing high confirmed before the range start (p + 3 < s).
- Require a close above High[p] at some session from p + 1 to i.

## Candidates, entry, stop and exits

- **Candidates:** #3's (`entries_s` on session i): top 20% 6-month momentum, peer group,
  close above the 50/200-SMA. Nifty above its 50-day SMA (`market_filter`).
- **Entry,** on session i + 1, at the close (known around 3:20 pm), if:
  - Close > the range high;
  - Volume ≥ 1.5 × the 50-session average;
  - **K versions only:** also a clean candle (Close ≥ Open, upper wick < 50% of range).
- **Stop:** #3's swing-low stop (fractal-3 pivot low − 0.25 ATR, from session i).
  Skipped if wider than 15%.
- **Exits:** 1% risk, 10 slots, 20-session time stop. No exit checks on the entry
  session.

## Versions (half A only)

| Code | Target | Clean candle |
|---|---|---|
| RB3 | 1:3 | no |
| RB2 | 1:2 | no |
| RBK3 | 1:3 | yes |
| RBK2 | 1:2 | yes |

## Comparison

- **References:** half-A S3_REF3 (9.9% / 3.4% / −14.8%) and S3_REF2 (7.0% / 5.9% /
  −12.5%).
- **Adoption rule:** beat the same-target reference on CAGR in **both** W1 and W2.

## Also reported: paths with the true range low

Over 20 and 40 sessions after the entry:
- direct to target (never back to the buy);
- back to the range low before the stop, and what happened next;
- back to the 20-SMA before the stop, and what happened next;
- hit the stop first.

## Windows and outputs

- **Windows:** W1, W2 and 2018.
- **All windows are in-sample.**
- **Outputs:**
  - `data/range_breakout_result.txt`
  - `data/range_breakout_paths.txt`

---

## Results, 2026-11-09 (`data/range_breakout_result.txt`, `data/range_breakout_paths.txt`), half A

| Version | W1 2019-26 | W2 2008-17 | 2018 | Trades W1 / W2 | Win % W1 / W2 | Net per trade W1 / W2 | ₹10 L grew to (W1 / W2) |
|---|---|---|---|---|---|---|---|
| *S3_REF3 (20-day high)* | *9.9% (DD −26%)* | *3.4% (−33%)* | *−14.8%* | *708 / 748* | *48.4 / 46.9* | *+1.35 / +0.60%* | *20.9 / 14.0 L* |
| **RB3** | 6.9% (**−13%**) | 3.6% (**−16%**) | **−7.2%** | 243 / 237 | **56.8 / 52.7** | **+2.16 / +1.81%** | 16.8 / 14.2 L |
| RB2 | 6.6% (−12%) | 3.8% (−15%) | −8.8% | 244 / 239 | 57.0 / 52.7 | +2.10 / +1.86% | 16.5 / 14.5 L |
| RBK3 | 6.4% (−12%) | 2.6% (−15%) | −4.6% | 220 / 212 | 55.9 / 51.9 | +2.19 / +1.49% | 16.3 / 12.9 L |
| RBK2 | 5.5% (−13%) | 3.0% (−15%) | −6.3% | 221 / 213 | 55.7 / 51.6 | +1.91 / +1.67% | 15.2 / 13.4 L |

**Verdict against the adoption rule:** not adopted. RB3 / RB2 beat the reference in W2
(3.6% / 3.8% against 3.4% and 5.9%) only for RB3, and lose in W1 (6.9% against 9.9%).

**But the trade quality is clearly higher:**
- win rate 53-57% against 47-48%;
- net per trade +1.8-2.2% against +0.6-1.4%;
- drawdowns halved, and the 2018 loss halved.

The lower CAGR comes from about a third as many trades, with cash idle most of the time.
Return per unit of drawdown, W1: RB3 0.53 against 0.38.

**Paths, RB3:**

| | W1, 40 days | W2, 40 days |
|---|---|---|
| Direct to target | 2% | 2% |
| Back to the range low before the stop | 18% | 15% |
| — of which then stopped | 84% | 89% |
| Back to the 20-SMA | 93% | 93% |
| — of which then stopped | 38% | 37% |

In about 55% of trades the swing-low stop sits above the range low, inside the range.

**Idea for a follow-up (not run):** these trades are better but fewer. A higher risk per
trade, or combining with another sleeve, would use the idle cash.
