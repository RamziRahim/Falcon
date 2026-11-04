# Pre-registration: FM with a 4-week review (keep only winners still in momentum)

**Status: FROZEN on 2026-11-04 ~16:55 IST,** before any run. IA asked for this test
("Do the test") after the 4-week vs 8-week comparison. Never edit; add dated notes.

## Question

FM with a 40-session time stop made W1 11.2% / W2 8.6% a year. With a 20-session stop it
made 5.7% / 5.3%. Can IA's 2-4 week rhythm be kept without cutting the winners short:
review every position at 4 weeks, sell the weak ones, and let only the strong ones run
on?

## Rule

FM exactly as frozen (`docs/falcon_momentum_preregistration.md`, 40-session time stop),
plus one rule:

- **At the close of the 20th session held,** the position is **kept** only if both of
  these hold:
  - the close is at least **2% above the fill**, covering costs, so "flat" counts as
    weak;
  - the stock's **latest weekly momentum rank is 50 or better**, so it is still among
    the leaders. FM's normal exit is rank > 100.
- **Otherwise** it is sold at the next open (exit reason REVIEW_EXIT).
- **Kept positions** continue under FM's normal exits: the stop, the 3R target, the
  rank > 100 exit, and the 40-session time stop.

The 2% gain and the rank of 50 were chosen by Claude before any result. They are not
tuned; no other values will be tried on these windows.

## Judgement

- Same windows, costs and six checks.
- Compared side by side with FM t40 and FM t20.
- Passes only if both windows pass. That pass is provisional; the next step is paper
  trading.

## Output

- `data/fm_review_result.txt`
- trades in `data/fm_review_trades_*.csv`

---

## Result, 2026-11-04 (`data/fm_review_result.txt`)

| | W1 CAGR | W2 CAGR | Max DD W1 / W2 | Win % W1 / W2 | Mean net/trade W1 / W2 |
|---|---|---|---|---|---|
| FM t40 (no review) | **11.2%** | **8.6%** | −25.6 / −27.0 | 39.8 / 43.7 | +1.56 / +1.81 |
| **FM t40 + 4-week review** | 8.0% | 6.7% | −24.2 / −27.8 | 37.9 / 38.1 | +1.52 / +1.63 |
| FM t20 | 5.7% | 5.3% | −26.2 / −27.0 | 45.3 / 44.1 | +1.03 / +0.79 |

**Verdict:** no demonstrated edge, with 3/6 checks on W1 and 4/6 on W2.
- The review sits between t20 and t40, and is below t40 on both windows.
- 136 (W1) and 168 (W2) positions were sold at the review.
- **Reading:** in momentum trades, many positions that are flat at 4 weeks later go on
  to win. Cutting them lowers the win rate (40 → 38%, 44 → 38%) without making the
  losses meaningfully smaller.
