# Pre-registration: Wyckoff swing strategy (break of structure, demand zone, double MB)

**Status: DRAFT (2026-11-21). Not frozen. No test code written.**

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

11. **MB1.** After the tap, L1 = the lowest low since the tap (tap bar included); H1 = the
    latest confirmed swing high (rule 1) before L1's bar. H1's bar must be at least one bar
    before L1's bar (a leg of at least two bars).
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
