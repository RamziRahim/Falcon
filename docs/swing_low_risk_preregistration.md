# Pre-registration: swing-low stop, 1% risk per trade, 1:2 and 1:3 targets

**Status: FROZEN on 2026-11-03 ~20:10 IST,** before any run. Requested by IA:
- place the stop below the previous swing low;
- size each trade so it risks 1% of total capital;
- test R:R 1:2 and 1:3 separately.

The details IA didn't specify were fixed by Claude before any result, using Falcon's
existing conventions where one exists. Never edit; add dated notes.

## Entries: unchanged

Same four frozen signals and priorities as `docs/fixed_rr_preregistration.md`: F, S, B
and MR. They use the same generators (`backtesting/fixed_bracket.py`).

## Stop: below the previous swing low

- **Swing low:** a Falcon fractal pivot (`config.SWING_WINDOW = 3`), meaning no bar within
  3 sessions on either side has a strictly lower low. It must be **confirmed by the
  signal day**: the pivot is at least 3 sessions before it, so there is no look-ahead.
- **Which one:** the most recent confirmed swing low within the last 60 sessions whose
  low is below both the signal close and the order price.
- **Stop** = that low − 0.25 × ATR(14) on the signal day. This is Falcon's
  `STOP_BUFFER_ATR_MULTIPLE`, so the stop doesn't sit exactly on an obvious level.
- **No such swing low** → no order.

## Sizing: 1% of capital at risk

- Position value = 1% of current equity × fill / (fill − stop). If the stop is hit,
  the loss is about 1% of capital plus costs.
- **Limits:**
  - each position ≤ 25% of equity, so a stop closer than 4% risks less than 1%;
  - at most 10 positions;
  - no leverage (cash limits).
- **Skipped at the fill:**
  - the open is at or below the stop;
  - the stop is more than 15% below the fill, which is too wide for a 2–4 week trade.

## Target and exits

- **Target** = fill + R × (fill − stop).
  - **Track A:** R = 2 (1:2).
  - **Track B:** R = 3 (1:3).
  - The two tracks are reported separately.
- **Time stop:** 20 sessions, sold at the next open.
- **Same intraday rules as before:**
  - the stop and target are live from the fill day;
  - the stop wins a same-day tie;
  - after the fill day, a gap through either level fills at the open.
- **Break-even win rate before costs:** 33% for 1:2, 25% for 1:3. Costs push both up
  slightly; they matter less here than in the fixed bracket because stops are wider.

## Windows and judgement

- **W1** = 2019-01-01 → 2026-10-30; **W2** = 2008-01-01 → 2017-12-31.
- Judged by the six checks of `docs/redesign_preregistration.md`.
- A combination passes only if it passes both windows.
- **Reported:** win rate, average win/loss in R, exit mix, and skipped-signal counts.
- 8 combinations (4 entries × 2 targets), so any pass is provisional, and the next step
  is paper trading.
- Same costs, data, delisting rule and universe as all earlier tests.

---

## Results, 2026-11-04

Full output: `data/swing_risk_1to2_result.txt` and `data/swing_risk_1to3_result.txt`,
with trades in `data/swing_risk_1to{2,3}_trades_*.csv`.

**Process note:** the first 1:3 run was killed out of memory at load, because it was
started in parallel with 1:2. It was re-run alone with no changes.

**All 8 combinations fail** (each needs a pass in both windows):

| Entry | R | Win % W1 / W2 | CAGR W1 / W2 | Max drawdown W1 / W2 | Checks W1 |
|---|---|---|---|---|---|
| S | 1:2 | 48.5 / 42.9 | +14.2 / −3.6 | −22.9 / — | 2/6 |
| S | **1:3** | **49.5 / 42.8** | **+20.4 / −0.2** | −22.6 / −56.6 | **5/6** (t = 1.66 < 2) |
| B | 1:2 | 46.7 / 46.0 | +2.1 / −3.4 | −42.6 / — | 1/6 |
| B | 1:3 | 45.6 / 46.0 | −0.1 / −3.2 | −43.8 / −50.3 | |
| F | 1:2 | 44.8 / 43.1 | −3.3 / −8.7 | | |
| F | 1:3 | 44.2 / 41.3 | −0.4 / −7.7 | −36.5 / −68.8 | |
| MR | 1:2 | 38.5 / 39.1 | −2.2 / −2.2 | | |
| MR | 1:3 | 36.7 / 35.8 | −0.7 / −1.8 | −39.6 / −44.0 | |

*Nifty CAGR: +10.0% (W1) / +5.5% (W2). PIT equal-weight: +15.2% (W1) / +4.2% (W2).*

**Reading:**
- Exits based on swing-low stops and 1% risk are far better than the fixed brackets
  (whose CAGR ranged from −10% to −88%).
- **S with 1:3 on 2019–26 passes 5 of 6 checks:** +20.4% a year against the Nifty's
  +10.0%, a −22.6% drawdown against −38.4%, and 5 of 8 years ahead. Only the
  statistical-significance check fails (t = 1.66).
- **The same rules on 2008–17 make −0.2% a year.** That window is what decides the
  result: it is not confirmed.
- **Common to all eight:**
  - **60–75% of trades end at the 20-session time stop.** Swing-low stops are 5–10% away,
    so the targets (10–30%) are rarely reached in 4 weeks.
  - **S and B skip about 2,100–2,750 signals each,** because the last swing low is more
    than 15% below the price.
- **Verdict per the rules:** no demonstrated edge. Nothing is re-tuned on these windows.
