# Pre-registration: Wyckoff swing strategy (break of structure, demand zone, double MB)

**Status: FROZEN on 2026-11-21 11:33 IST.** Frozen on IA's instruction ("try for 0.5% 1% risk and 2% risk
separately and lets run this strategy"), with the risk versions IA asked for and the rule 11
clarification below both added before freezing, and before any test code was written or run.
Never edit; add dated notes.

Source: IA's doc "Wyckoff Swing Strategy for NSE Equities" (claude.ai artifact
WcCRv6ywWJ3e9jr261LfTZ, 2026-11-14, rev 52), drawn from the Mentfx course. Where that doc
leaves a rule open or proposes a parameter sweep, this file fixes one value; those places
are marked **(fixed here)**. IA's decisions of 2026-11-21: test both universes and both
sizings; long only.

**Samples.** Each version runs once on half A, half B and all stocks, on W1 2019-01-01 →
2026-10-30, W2 2008-01-01 → 2017-12-31 and 2018, with the same six checks, costs and data,
and `PYTHONHASHSEED=0`. All windows are in-sample: both halves have been used for earlier
tests, including breakout and retest tests close to this one. A pass would mean "paper
trade it", not "proven".

**No parameter sweep.** The source doc proposes sweeping seven parameters in two bias
modes. With no untouched data left, the best of dozens of variants would look good by
chance, so this test runs the course defaults as one primary version and reports a fixed,
short list of other versions.

## Why

The doc's three-box method (structure, zone, confirmation) is a codeable pullback entry
with its own controls: it must beat buying the break of structure with no zone, and buying
the zone tap with no confirmation. Earlier dip and retest entries on this data trailed
breakout entries (`docs/structure_pullback_preregistration.md` and those it cites); this
test asks whether the Wyckoff confirmation changes that.

## Rules

Daily bars, decided after the close; all prices adjusted; long only.

### 1. Swing points (fixed here, from the doc's pullback rule)

A per-stock state machine, run over the stock's full history, with a mode, up or down.
1. **Up mode.** When a bar trades below the previous bar's low, a pullback has started:
   the highest high since the last confirmed swing low becomes a confirmed **swing high**
   (on that bar). The lowest low of the pullback becomes a confirmed **swing low** on the
   first later bar that closes above that swing high. That close is a **break of structure
   up** (continuation).
2. **Down mode.** Mirror: when a bar trades above the previous bar's high, the lowest low
   since the last confirmed swing high becomes a confirmed swing low; the highest high of
   that rally becomes a confirmed swing high on the first later bar that closes below that
   swing low (a break of structure down).
3. **Mode changes.** In up mode, a close below the latest confirmed swing low is a break of
   structure down and the mode becomes down. In down mode, a close above the latest
   confirmed swing high is a break of structure up (reversal) and the mode becomes up.
4. On any session only swing points confirmed on or before it are used.

### 2. Bias

5. **Break of structure up (BOS):** rule 1 or rule 3 above. **Protected low:** the lowest
   low between the broken swing high's bar and the breaking bar.
6. **Bias mode.** `double` (primary, the course's "double MB" bias): bias is up after two
   breaks of structure up in a row with no break down between them. `single` (reported):
   after one.
7. A daily close below the protected low ends the bias and cancels any pending order.

### 3. Demand zone

8. The zone belongs to the break that completed the bias (in `double`, the second break).
   It is the last down-closing bar (Close < Open) at or before the protected low's bar and
   after the broken swing high's bar, if any; else the protected low's bar itself.
   Zone top = that bar's High; zone bottom = the lower of its Low and the next bar's Low.
9. Each new break of structure up replaces the zone with the one behind the new break.
10. **Tap:** the first bar after the break whose Low is at or below the zone top
    (reaction level: top edge, **fixed here**; the doc's 50% line is not tested). One trade
    attempt per zone. The setup expires if there is no tap within 60 sessions of the break
    **(fixed here; the doc sets no limit)**.

### 4. Confirmation (double MB)

11. **MB1.** After the tap, L1 = the lowest low since the tap (tap bar included). H1 = the
    starting high of the down-leg that made L1, by the doc's own rule that a rally starts when
    a bar trades above the previous bar's high: k = the last bar before L1's bar (and not
    before the break) whose High is above the previous bar's High, and H1 = the highest High
    from k to the bar before L1 (from the break, if there is no such k). The leg is therefore
    at least two bars **(fixed here; the draft used the larger rule-1 swing high, which would
    have demanded a new high before validation)**.
12. **Validation:** a later bar's High exceeds H1. If a bar trades below L1 first, L1 and H1
    are updated per rule 11.
13. **MB2.** After validation, a bar trades below the previous bar's low (pullback start);
    H2 = the highest high from validation to that bar; L2 = the lowest low of the pullback,
    which must stay above L1.
14. **Armed:** a buy-stop at H2, valid on the next session and renewed each session until it
    fills or is cancelled; protective stop at L2 − 0.25 × ATR(14) (Wilder), using ATR on the
    bar before the fill. If the pullback makes a lower low that is still above L1, L2 and
    the stop move to it. A trade below L1 before the fill returns to step 11. Rule 7 cancels.

### 5. Entry

15. The buy-stop fills at max(H2, Open). Skip the trade if Open > H2 + 0.5 × (H2 − stop).
16. **Filters on the fill day:** (a) the stock is in that month's universe; (b) the Nifty
    50's own swing machine (rules 1-3) is in up mode; (c) the stock's weekly swing machine
    (rules 1-3 on weekly bars, Friday closes) is not in down mode. The doc also skips stocks
    at an untested weekly supply zone; that part is not coded **(fixed here)**.
17. Skip if the stop is not below the fill or more than 15% below it.

### 6. Exits (course)

18. **First target** T1 = max(the highest high from the break of structure to the tap,
    fill + 2.5 × (fill − stop)). Sell 80% of the shares there.
19. **Breakeven:** once a swing low (rule 1) above the fill is confirmed, the stop on the
    whole position moves to the fill.
20. **Runner (20%):** after T1, the stop is the latest confirmed swing low − 0.25 × ATR(14),
    never lowered. The doc's "bearish double MB" exit is not coded **(fixed here)**.
21. A time stop of 120 sessions sells the rest at the next open **(fixed here)**. No exit
    checks on the fill day except the stop; the stop wins ties; gaps fill at the open.

### 7. Universe and sizing (both tested, per IA)

| Code | Universe | Sizing |
|---|---|---|
| U200 | the 200 highest-turnover stocks of that month's point-in-time list (`rank` ≤ 200) | |
| U500 | the full monthly top-500 list | |
| SD (the doc's) | | 0.5% risk per trade; total open risk at most 4% of equity (defined below); at most 2 open positions per sector; ≤ 25% of equity per position |
| SF (Falcon standard) | | 1% risk per trade; 10 slots; ≤ 25% of equity per position |

- For WY_R1 and WY_R2 the open-risk cap scales with the risk per trade (8 × risk, as the
  doc's 4% is 8 × 0.5%), so each allows the same number of full-risk positions.
- Open risk for SD = Σ over open positions of shares × max(0, last close − current stop),
  as a share of equity, checked before each buy; a buy that would take it above 4% is
  skipped.
- Sector for SD = the NSE sector index the stock's daily returns correlate with most over
  the past year, as in Falcon Momentum (`sector_maps`, correlation ≥ its threshold);
  stocks with no matching index count as their own sector.
- When more orders fill on one session than there is room for, the higher 126-session
  return rank goes first.

## Versions

| Code | What | Role |
|---|---|---|
| P3 | v3 patterns, as stored | reference; must reproduce `data/falcon_v3_patterns_result.txt` within 0.05pp (all samples, W1 and W2) |
| **WY** | rules 1-21, `double` bias, U200, SD | **primary** |
| WY_U500 | as WY, U500 | reported |
| WY_SF | as WY, SF | reported |
| WY_U500_SF | as WY, U500 and SF | reported |
| WY_1 | as WY, `single` bias | reported |
| WY_R1 | as WY, 1% risk per trade (open-risk cap 8%) | reported (IA, 2026-11-21) |
| WY_R2 | as WY, 2% risk per trade (open-risk cap 16%) | reported (IA, 2026-11-21) |
| BASE_BOS | as WY, but buy at the close of the bar that completes the bias (no zone, no confirmation); stop at protected low − 0.25 ATR | baseline |
| BASE_TAP | as WY, but buy on the tap at min(zone top, Open) (no confirmation); stop at min(zone bottom, protected low) − 0.25 ATR | baseline |

Both baselines use WY's filters, exits, universe and sizing.

## Adoption bar (WY; all must hold on both half A and half B, in both W1 and W2)

1. CAGR above the Nifty's;
2. at least 4 of the 6 checks;
3. max drawdown no deeper than −25.00%;
4. mean net per trade at least +1.00% (no win-rate rule: the doc expects 25-50% wins);
5. CAGR higher than both BASE_BOS and BASE_TAP on the same sample and window (the
   confirmation must add something, as the source doc itself requires).

Figures are compared as printed in the result file. Also reported, per version: trades per
year, win rate, profit factor, average holding days, the share of trades that reached T1,
average capital invested, and 2018.

## What adoption would mean

WY would join the paper-trading tracks as a separate strategy. Running it beside monthly
momentum would be a separate registered test.

## Expected, stated before the run

Few trades, especially in U200 with `double` bias (perhaps 10-30 a year per half). Win rate
25-40%. With 0.5% risk and few trades, capital use will be low, so WY's CAGR is likely
below the Nifty's: rule 1 is the likeliest to fail, then rule 5. BASE_BOS (buying the break)
is likely to beat BASE_TAP, as breakouts beat retests in every earlier test.

## Output

`data/wyckoff_swing_result.txt`; code `backtesting/wyckoff_swing.py` with unit tests
`tests/test_wyckoff_swing.py`; runner `tests/run_wyckoff_swing.py`. Nothing existing changes.

---

## Results — 2026-11-21 (added after the run; nothing above was changed)

**Run notes.** `tests/run_wyckoff_swing.py`, one run, `PYTHONHASHSEED=0`; unit tests
`tests/test_wyckoff_swing.py` (3 pass: a simple break of structure, no later data used in
any candidate, candidate levels obey rules 15-18). **Reference check:** P3 reproduced
`data/falcon_v3_patterns_result.txt` exactly on half A, half B and all stocks, W1 and W2.
**Implementation notes, settled before the run:** a fill that the portfolio cannot take
(no room, sector cap, filters) is lost, not kept for a later session; filters use the Nifty
and weekly state known before the fill (the previous close for buy-stops and taps).
**Candidates 2007-2026, before filters:** half A 4,727 double-bias WY entries (6,709 with
single bias), half B 4,503; about 250 a year per half, of which the top-200 universe keeps
roughly a tenth.

### Primary WY against the frozen bar

| Sample, window | CAGR (Nifty) | Checks | Max DD | Net/trade | CAGR vs BASE_BOS / BASE_TAP | Bar |
|---|---|---|---|---|---|---|
| Half A, W1 | 0.03% (10.03%) ✗ | 1/6 ✗ | −13.59% ✓ | −0.12% ✗ | 0.03 < 4.08 ✗ / > −1.38 | **FAIL** |
| Half A, W2 | 0.61% (5.54%) ✗ | 1/6 ✗ | −13.87% ✓ | +1.27% ✓ | 0.61 < 3.54 ✗ / < 3.91 ✗ | **FAIL** |
| Half B, W1 | −0.94% (10.03%) ✗ | 1/6 ✗ | −12.42% ✓ | −0.60% ✗ | −0.94 < −0.48 ✗ / < 2.21 ✗ | **FAIL** |
| Half B, W2 | 1.12% (5.54%) ✗ | 1/6 ✗ | −12.95% ✓ | +0.93% ✗ | > 0.84 / 1.12 < 1.52 ✗ | **FAIL** |

**Verdict: WY FAILED its bar in all four cells. Not adopted.** It made almost nothing (−0.9%
to +1.1% a year) and did not beat both baselines in any cell, so on this data the Wyckoff
confirmation adds nothing. Only rule 3 (drawdown) held.

### All versions (CAGR / max DD / win / net per trade / closed trades / checks)

| Code | Half A W1 | Half A W2 | Half B W1 | Half B W2 | 2018 A / B |
|---|---|---|---|---|---|
| **WY** (top 200, 0.5%) | 0.03 / −13.59 / 27.4 / −0.12 / 186 / 1 | 0.61 / −13.87 / 32.1 / +1.27 / 209 / 1 | −0.94 / −12.42 / 23.8 / −0.60 / 181 / 1 | 1.12 / −12.95 / 31.8 / +0.93 / 214 / 1 | 0.23 / −4.85 |
| WY_R1 (1%) | 0.28 / −20.61 / 27.4 / +0.05 / 201 / 1 | 1.49 / −25.18 / 31.2 / +1.04 / 215 / 1 | −2.53 / −25.40 / 24.1 / −0.41 / 187 / 1 | 1.46 / −22.65 / 31.8 / +0.95 / 220 / 1 | −3.03 / −9.82 |
| WY_R2 (2%) | 0.28 / −23.21 / 28.4 / +0.26 / 208 / 1 | 4.84 / −24.60 / 30.9 / +0.94 / 246 / 4 | −2.67 / −38.12 / 25.4 / −0.28 / 197 / 1 | 2.70 / −32.93 / 31.0 / +0.81 / 242 / 2 | −3.50 / −13.79 |
| WY_U500 | 1.29 / −17.68 / 29.7 / +0.78 / 283 / 1 | 1.48 / −18.56 / 34.3 / +1.52 / 309 / 1 | 1.74 / −13.71 / 30.2 / +0.96 / 285 / 1 | 2.09 / −15.93 / 33.6 / +1.42 / 307 / 2 | −4.61 / −8.41 |
| WY_SF (1%, 10 slots) | 0.04 / −23.47 / 28.3 / +0.12 / 205 / 1 | 0.71 / −28.25 / 30.5 / +1.04 / 246 / 1 | −2.97 / −26.42 / 23.9 / −0.52 / 197 / 1 | 0.76 / −25.78 / 31.1 / +0.82 / 241 / 1 | −3.03 / −9.82 |
| WY_U500_SF | 3.37 / −22.94 / 28.2 / +0.49 / 354 / 1 | 4.55 / −32.88 / 33.8 / +1.50 / 361 / 3 | 1.93 / −27.05 / 27.2 / +0.47 / 335 / 1 | 1.98 / −31.84 / 31.0 / +0.62 / 374 / 1 | −13.24 / −15.32 |
| WY_1 (single bias) | 1.06 / −13.72 / 29.1 / +0.35 / 206 / 1 | 0.14 / −20.03 / 30.3 / +0.79 / 238 / 1 | 0.88 / −14.50 / 28.5 / +0.02 / 221 / 1 | 1.03 / −16.83 / 30.6 / +0.66 / 248 / 1 | −2.11 / −1.84 |
| BASE_BOS | 4.08 / −10.34 / 32.9 / +2.15 / 283 / 2 | 3.54 / −16.79 / 32.9 / +2.21 / 298 / 4 | −0.48 / −15.07 / 24.8 / +0.39 / 298 / 1 | 0.84 / −20.92 / 28.6 / +0.38 / 332 / 1 | −2.96 / 0.70 |
| BASE_TAP | −1.38 / −16.17 / 26.1 / −0.22 / 379 / 1 | 3.91 / −16.94 / 34.3 / +0.89 / 397 / 3 | 2.21 / −21.63 / 31.0 / +0.75 / 364 / 1 | 1.52 / −25.52 / 31.5 / +0.63 / 461 / 1 | −12.42 / −7.87 |
| P3 (reference) | 6.34 / −23.34 / 51.3 / +2.62 / 277 / 2 | 7.47 / −14.89 / 51.9 / +2.48 / 297 / 4 | 13.12 / −15.77 / 56.2 / +4.52 / 240 / 3 | 6.45 / −19.15 / 52.1 / +3.03 / 265 / 3 | −17.00 / −6.95 |

WY also reported: 21-24 trades a year per half; profit factor 0.89-1.14; 24-32% of trades
reached the first target; average holding 25-29 sessions; capital invested 14-19%.

### Reading (information only; no decision rests on it)

- The win rate (24-32%) was in the range the course itself expects, but the winners were not
  large enough: on daily bars, with 80% sold at about 2.5R, the strategy roughly broke even
  before costs, as the source doc warned ("roughly one win in three, after costs, just to
  break even").
- Higher risk did not rescue it. At 1% and 2% per trade the return stayed near zero on half B
  in 2019-26 while the drawdown deepened to −25% and −38%.
- The confirmation step did not add value: in three of four cells simply buying the break
  (BASE_BOS) or the zone tap (BASE_TAP) did better.
- This is the fifth pullback or retest family to trail breakout entries on this data.
- Expectation check: few trades (held, about 22 a year per half); win rate 25-40% (held,
  24-32%); low capital use and CAGR below the Nifty (held); rule 5 failing (held); BASE_BOS
  beating BASE_TAP (held on half A in 2019-26 only; mixed elsewhere).
