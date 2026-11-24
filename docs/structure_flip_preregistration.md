# Weekly and monthly structure flip (downtrend → higher high → higher low) — pre-registration

**Status: FROZEN on 2026-11-24 23:27 IST**

## Question

IA (2026-11-23): a stock in a downtrend makes lower highs and lower lows, then breaks that structure with a higher high followed by a higher low. Is buying that turn a profitable strategy?
- On **weekly** bars and on **monthly** bars.
- With entry **(a)** at the higher low and **(b)** on the break of the new high.
- With several risk:reward exits.

Daily-swing versions of break-of-structure have already failed (`docs/wyckoff_swing_preregistration.md`, `docs/structure_pullback_preregistration.md`). Weekly and monthly structure is untested.

## Bars and swing points

- **Bars:** built from the adjusted daily data.
  - Weekly bars run Monday to Friday.
  - Monthly bars are calendar months.
  - A bar is complete at its last session's close.
- **Swing high:** a bar whose high is above the highs of the *k* bars on each side. Swing low likewise, with lows. k = 2 on weekly bars and k = 1 on monthly bars.
- **Confirmation:** a swing point is known only *k* bars later, at that bar's close. Nothing uses an unconfirmed point.

## Setup (known at a completed bar's close)

1. **Downtrend:** the last two confirmed swing highs are falling (H1 > H2), and so are the last two confirmed swing lows (L1 > L2).
2. **Break:** a bar closes above H2, the last lower high. The highest high from that break onward is HH.
3. **Higher low:** a swing low is confirmed after the break, above L2. This is HL.
4. **Universe:** the stock must be in that month's point-in-time top-500 universe when HL is confirmed.

**Cancelled if:**
- a bar closes below HL before entry; or
- no entry within 13 weekly bars (weekly) or 6 monthly bars (monthly) after HL.

## Entries (the session after HL is confirmed onward)

- **(a) Higher-low entry:** buy at the next session's open.
- **(b) Breakout entry:** a buy-stop at HH.
  - It fills on the first session whose high exceeds HH, at max(open, HH).
  - It is valid until the setup is cancelled.

## Stop and exits

- **Initial stop:** 1% below HL, checked daily against daily lows. A gap through the stop fills at the open.
- Each variant uses one of three exits:
  - **STR (structure exit):** the stop is raised to 1% below each newly confirmed higher swing low on the same timeframe. It never lowers. The position is held until stopped, with no target.
  - **R2:** fixed stop at the initial level; target = entry + 2 × (entry − stop).
  - **R3:** the same with 3 × the risk.

## Portfolio

- 20 slots, each 1/20 of equity at entry, limited by cash. No resizing.
- Costs use the standard CostModel and Ledger (brokerage, STT, slippage).
- A delisted stock is exited at its last close − 5%, as in A10.
- When more fills arrive on one day than there are free slots, the deepest prior fall goes first, measured as (H1 − lowest low before the break) ÷ H1. Ties go by entity_id.

## Variants

There are 12 variants: {W = weekly, M = monthly} × {a, b} × {STR, R2, R3}, named for example `SF_W_a_STR`.

**Judged (four primaries):** `SF_W_a_STR`, `SF_W_b_STR`, `SF_M_a_STR`, `SF_M_b_STR`.

**Reported:**
- the eight R2 and R3 variants;
- each primary combined 50/50 with A10 (`combine(..., "FA", True)` with the flip variant as F), against A10 alone.

**Reference:** A10 must reproduce `data/buystop_mix_result.txt` within 0.05pp on all stocks, half A and half B, in every window present. Otherwise the run stops.

## Runs

- Windows: H0 2001-01-01 → 2006-12-31, W2 2008-01-01 → 2017-12-31, W1 2019-01-01 → 2026-10-30.
- Samples: all stocks, half A and half B. Data `data/pit_v2`, no ethical filter, `PYTHONHASHSEED=0`.
- Bars and swing points use data from before each window's start, so setups already forming are recognised. Trades start only within the window.

## Adoption bar (each primary separately)

A primary passes only if all three conditions hold:

1. **All stocks, W1 and W2:** CAGR at least 3.0 percentage points a year above the Nifty 50's in the same window.
2. **Half B, W1 and W2:** CAGR above the Nifty 50's.
3. **H0 2001–06, all stocks:** CAGR above the Nifty 50's.

Four primaries are judged, so the chance that one passes by luck is higher than for a single test. The verdict will state how many of the four passed.

A pass means "candidate for paper trading, alone or beside A10" — IA decides. No re-tuning, no extra variants.

## Output

- `data/structure_flip_result.txt`
- Module: `backtesting/structure_flip.py`
- Runner: `tests/run_structure_flip.py`
- Dated Results section here; scorecard rows.

## Results (2026-11-24, run once after freeze)

**References.** Passed: A10 reproduced `data/buystop_mix_result.txt` exactly on all stocks, half A and half B, in H0, W2 and W1 (9 checks). Output: `data/structure_flip_result.txt`.

Nifty 50 CAGR: H0 21.19%, W2 5.54%, W1 10.03%.

**Verdict: 2 of the 4 primaries passed. Both monthly versions passed; both weekly versions failed.**

| Primary | All W2 (≥ 8.54) | All W1 (≥ 13.03) | Half B W2 (> 5.54) | Half B W1 (> 10.03) | All H0 (> 21.19) | |
|---|---|---|---|---|---|---|
| SF_M_a_STR (monthly, higher-low entry) | 17.98 | 17.01 | 18.67 | 13.10 | 21.93 | **PASSES** |
| SF_M_b_STR (monthly, breakout entry) | 23.73 | 14.84 | 18.78 | 13.32 | 26.23 | **PASSES** |
| SF_W_a_STR (weekly, higher-low entry) | 10.87 | **8.61** | 10.44 | 10.75 | **8.95** | FAILS |
| SF_W_b_STR (weekly, breakout entry) | 13.94 | **7.41** | 12.20 | **8.00** | **14.91** | FAILS |

Four primaries were judged, so one pass in four could be luck. Two passed, both monthly, and both cleared every sample and window. That is stronger than a single lucky cell, but the H0 margins are thin: +0.7 and +5.0 points over the Nifty.

**All stocks, CAGR % (max DD %)**

| Version | H0 2001–06 | W2 2008–17 | W1 2019–26 |
|---|---|---|---|
| A10 (reference) | 37.52 (−38.0) | 13.17 (−59.0) | 26.36 (−39.4) |
| **Monthly (a), structure exit** | 21.93 (−31.4) | 17.98 (−33.7) | 17.01 (−26.3) |
| **Monthly (b), structure exit** | 26.23 (−31.8) | 23.73 (−29.3) | 14.84 (−23.8) |
| Monthly (a), 1:2 / 1:3 | 14.68 / 18.66 | 5.44 / 3.38 | 8.61 / 10.12 |
| Monthly (b), 1:2 / 1:3 | 23.12 / 25.86 | 11.36 / 11.39 | 5.66 / 8.60 |
| Weekly (a), structure / 1:2 / 1:3 | 8.95 / 11.89 / 12.79 | 10.87 / 6.15 / 8.77 | 8.61 / 5.92 / 8.82 |
| Weekly (b), structure / 1:2 / 1:3 | 14.91 / 22.33 / 18.71 | 13.94 / 13.20 / 17.56 | 7.41 / 11.64 / 11.35 |
| 50/50 A10 + monthly (a) | 30.28 (−34.1) | 15.94 (−46.7) | 22.15 (−28.7) |
| 50/50 A10 + monthly (b) | 32.58 (−34.5) | 18.88 (−36.1) | 20.95 (−27.8) |

**How the monthly versions trade** (all stocks, W2 / W1):

| | Monthly (a) | Monthly (b) |
|---|---|---|
| Entries | 247 / 210 | 145 / 152 |
| Signals skipped for lack of a slot | 655 / 453 | 402 / 258 |
| Average initial risk to the stop | 19.9% / 16.8% | 29.1% / 26.5% |
| Win rate | 28% / 29% | 51% / 36% |
| Net per trade | +29.0% / +16.7% | +53.9% / +15.8% |
| Top-3 share of profit, W1 | 0.56 | 0.43 |
| Average invested | 86% | 83% |

**What it means, in plain English:**

**The monthly structure flip works on this data.** Buying a stock whose monthly chart turns from lower highs and lower lows into a higher high and higher low, and holding while each new monthly low is higher, beat the Nifty in every period and on both halves. It also beat A10 in 2008–17 (18–24% vs 13%) with far smaller falls:
- **Worst fall:** about −24% to −34%, against −39% to −59% for A10.

**It is not better than A10 overall.** A10 is still well ahead in 2001–06 and 2019–26 (37.5 / 26.4 vs 15–26%). What makes the flip interesting is that it makes money *differently*:
- It catches turnarounds that A10 cannot rank.
- **Mixed 50/50 with A10:** about 21–22% a year in 2019–26 and 16–19% in 2008–17, with the worst fall cut to −28% to −47% from A10's −39% to −59%.

**The weekly version does not work.** Weekly structure flips too often and fails too often: 2,000+ signals a period, roughly 28% winners. Like the daily versions tested earlier, it ends up near or below the Nifty in 2019–26.

**Fixed 1:2 / 1:3 targets hurt the monthly version.** They cost 6–15 points a year in 2008–17, for the same reason as with momentum: the profit comes from the few turnarounds that keep running.

**Things to know before trusting it:**
- **The stops are very wide:** on average 17–20% below entry for (a) and 26–29% for (b). Each loss can be large even though the portfolio's falls were smaller than A10's.
- **There are few trades:** about 15–25 entries a year. Results lean on a handful of big winners (top 3 trades = 43–56% of profit in 2019–26).
- **Signals far exceed the 20 slots.** Which turnarounds get bought depends on the "deepest prior fall" tie-break.
- **2001–06 was barely above the Nifty for (a):** +0.7 points.

**Next step (IA decides):** paper-trade the monthly flip, alone or as a 50/50 partner to A10. It would need IA's decision to add a track; the frozen plan is otherwise unchanged.
