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
