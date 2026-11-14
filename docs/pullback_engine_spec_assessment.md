# Assessment: PULLBACK_ENGINE_SPEC.md (2026-11-14)

IA supplied a spec (with `nse_pullback_scanner.py`) for a Stage 2 pullback engine: ATR
zigzag swings (1.8 ATR), a +12% impulse leg on a volume surge, a 23.6-65% retracement on
dry volume, support confluence (broken prior high, rising 20-EMA / 50-SMA, or a prior
swing low), and a green reversal candle (TRIGGER_READY, buy-stop above its high) or a
resting dip (ARMED), with a 1.5-6.5% stop and at least 1.6R to the prior peak.

**Frequency, code as written** (20,000 random top-500 stock-days 2008-2026, last 400
sessions each; no errors): 5 TRIGGER_READY (4 polarity retest, 1 MA confluence) and 7
ARMED, i.e. 0.025% of stock-days, about one trigger every 8 sessions across 500 stocks
(roughly 30 a year). No returns were measured.

Where the stock-days were rejected: MA stack 11,133; below the 50-day 2,713; impulse
under 12% 1,679; no confirmed peak 2-16 sessions back 1,097; MA slope 895; retracement
outside 23.6-65% 600; already above the peak 596; undercut the origin low 324; no volume
surge 241; heavy pullback volume 221; low more than 2 sessions ago 94; risk outside
1.5-6.5% 50; R:R under 1.6 33; no support confluence 13.

**Defects and gaps.**
1. It is an entry scanner, not a strategy: the buy-stop's life, gap handling, how the
   two targets combine and any time stop are not defined.
2. The spec says a higher-low spring must hold above a rising 50-day SMA; the code does
   not check it.
3. "Highest win rate" and "high win-rate" are asserted, not shown.
4. Support confluence, presented as the key rule, rejects almost nothing (13 of 20,000);
   the impulse, peak-timing and retracement rules do the filtering.

**Prior evidence on this data.** Buying dips in leaders (`docs/pullback_preregistration.md`,
`docs/pullback_diagnostics_preregistration.md`) showed no edge beyond momentum, and every
retest entry (`docs/s_retest_preregistration.md`, `docs/retest_depth_preregistration.md`,
`docs/falcon_v2_retest_preregistration.md`) did worse than buying the breakout.
