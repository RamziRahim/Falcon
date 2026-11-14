# Falcon pattern detector: blind chart audit (2026-11-14)

**What was done.** 50 charts were drawn by `tools/pattern_audit_charts.py` (seed 20261113):
40 Falcon v2 detections (10 per pattern, one per stock, 2008-2026) and 10 uptrending
stocks Falcon did not flag (above a rising 200-DMA, 50-DMA above 200-DMA, no detection
within 10 sessions). Each chart showed 180 sessions up to the scan day, the 50/200-day
averages, volume, the breakout level and the stop; no names, dates or later prices. IA
marked each chart "real pattern", "not a pattern" or "unsure", and named the pattern
when real, on the blind audit page, without knowing which charts were detections.
Files: `data/pattern_audit/` (answer key, IA's answers, joined table).

## Results

| Charts | Real | Unsure | Not | Named the same pattern as Falcon |
|---|---|---|---|---|
| Bull flag (10) | 8 | 2 | 0 | 6 of 8 |
| Flat base (10) | 7 | 2 | 1 | 1 of 7 (3 VCP, 2 bull flag, 1 triangle) |
| Ascending triangle (10) | 5 | 2 | 3 | 0 of 5 (4 flat base, 1 VCP) |
| VCP (10) | 4 | 0 | 6 | 2 of 4 (1 triangle, 1 bull flag) |
| **All detections (40)** | **24 (60%)** | 6 | 10 | **9 of 24 (38%)** |
| Not detected (10) | 2 (both VCP) | 4 | 4 | — |

- Precision: 60% of Falcon's detections were judged real patterns, against the 80% bar
  proposed on 2026-11-13. The detector **fails** the audit.
- It does carry information: 60% of detections were real against 20% of comparable
  uptrending charts it did not flag.
- Labels are mostly wrong. Even when the chart was real, Falcon named the same pattern
  only 38% of the time. No "ascending triangle" was seen as a triangle; most were flat
  bases. "Flat base" catches whatever is sideways for 25 days.
- By pattern: bull flag is good (8 of 10 real, labels mostly right); flat base finds
  real setups but mislabels them; triangle is weak; VCP is the worst (6 of 10 rejected).
- It missed real setups: 2 of the 10 non-detections were VCPs.

### What happened next (anecdotal: 21 of the 50 charts traded through the level within 5 sessions)

| IA's verdict | Charts | Broke the level | Hit stop | Hit 1:3 target | Mean 40-session return after breaking out |
|---|---|---|---|---|---|
| Real | 26 | 11 | 5 | 3 | +4.0% |
| Unsure | 10 | 4 | 0 | 2 | +20.5% |
| Not | 14 | 6 | 4 | 1 | −5.0% |

Too few trades to conclude anything; the rejected charts did worse, as one would hope.

## What it means

The detector is a real weakness, and it confirms the concern raised on 2026-11-13: the
pattern backtests tested Falcon's detectors, not chart patterns as IA reads them. Priority
for a rebuild: VCP, then ascending triangle, then flat base (labels); bull flag can stay.
Any rebuilt detector should be re-audited blind (target: at least 80% judged real) before
a backtest is pre-registered. Both halves of the stocks have already been used for
pattern tests, so a later backtest would be in-sample.
