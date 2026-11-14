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

---

## v3 engine from PATTERN_ENGINE_SPEC.md (2026-11-14)

IA supplied a spec (generated with Gemini) for a rule-based engine: Minervini Stage 2
gate, ATR-adaptive zigzag pivots, VCP / ascending triangle / bull flag / cup with handle /
flat base geometry, a 2-11.5% stop window and a right-edge verdict.

**Run as written on the round-1 charts** (`data/pattern_audit/v3_engine_on_round1.csv`):
it called 5 charts real, and IA had judged all 5 real; it rejected all 14 that IA rejected,
but it missed 21 of IA's 26 real setups (5 failed its strict 50 > 150 > 200-day stack,
the rest its shape rules). Its VCP and triangle rules fired on about 1 in 1,500 random
stock-days.

**Defects found in the spec:**
1. The reference VCP code crashed (subtracted Pivot objects); it had never been run.
2. The triangle accepted 2 touches, though its own test describes 3.
3. With VCP checked first, the spec's own triangle and cup examples come out as VCP: a
   3-touch triangle with rising lows and a cup with a shallow handle both meet the VCP
   rules. Its VCP and triangle examples (lows 82/91/96 vs 85/91/95 under 100) are the
   same shape.
4. A 20%-deep, 70-session cup fails its own Stage 2 stack (the 50-day average falls
   below the 150-day), so deep cups can never qualify.
5. The anti-V filter (35% of closes below the cup midpoint) passes a straight-line V,
   which has half its closes below the midpoint; it only rejects a spike bottom.
6. The verdict mixes "is it a pattern" with entry timing (distance to pivot, volume).

**Built as `technical_analysis/pattern_system_v3/`** with changes 1-5 listed in
`engine.py`: VCP fix, 3 triangle touches, order cup -> triangle -> VCP -> flag -> flat
base, a straight-support-line rule to label triangles vs VCPs, and `detect_pattern()`
without the timing verdict. `tests/test_pattern_engine_v3.py`: the spec's five tests
plus a no-future-data test, 10 passing. Defects 4 and 5 are left as specified and noted.

**Frequency** (60,000 random top-500 stock-days, 2008-2026; `data/pattern_audit2/scan_counts.json`):
1.3% were "real pattern" (flat base 458, bull flag 155, cup 122, VCP 26, triangle 19),
about 6-7 a day across 500 stocks.

**Round 2 audit** (`tools/pattern_audit2_charts.py`, seed 20261114): 40 v3 "real pattern"
picks (8 per pattern) and 10 Stage-2 stocks with no pattern, none from round-1 stocks.
Answer key held back until IA finishes.

## Round 2 results (2026-11-14): v3 engine

IA marked all 50 charts blind (`data/pattern_audit2/`).

| v3 label | Real | Unsure | Not | IA named the same pattern |
|---|---|---|---|---|
| VCP (8) | 6 | 2 | 0 | 4 of 6 (2 flat base) |
| Ascending triangle (8) | 6 | 1 | 1 | 1 of 6 (4 VCP, 1 flat base) |
| Bull flag (8) | 8 | 0 | 0 | 2 of 8 (3 VCP, 3 flat base) |
| Cup with handle (8) | 4 | 4 | 0 | 0 of 4 (2 triangle, 2 VCP) |
| Flat base (8) | 8 | 0 | 0 | 3 of 8 (3 VCP, 2 bull flag) |
| **All v3 picks (40)** | **32 (80%)** | 7 | **1** | **10 of 32 (31%)** |
| Stage-2 stocks with no v3 pattern (10) | 2 | 2 | 6 | — |

- **Detection passes the 80% bar** (round 1, Falcon v2: 60%). Only 1 of 40 picks was
  judged not a pattern (round 1: 10 of 40). Picks were judged real 80% of the time
  against 20% for comparable Stage-2 stocks it did not flag.
- **Labels still fail**: IA named the same pattern 31% of the time (round 1: 38%). IA
  most often saw a VCP. Cups were never seen as cups. Labels do not change any trading
  rule; they matter only for what the dashboard shows.
- Cups are the weakest pick (4 of 8 real, 4 unsure).
