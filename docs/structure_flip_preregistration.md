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
