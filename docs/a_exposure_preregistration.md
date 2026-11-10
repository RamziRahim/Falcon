# Pre-registration: monthly momentum with exposure scaled by the stock list's own trend

**Status: FROZEN on 2026-11-10 15:10 IST.** Frozen by IA before any code was written or run. Never edit;
add dated notes.

**Samples and hold-out.** Half B was used once on 2026-11-09, so it is no longer unseen.
To keep it meaningful, nothing in this test is tuned: every parameter below is fixed
here, before any run, from common practice and not from a search. Each variant runs once
on all stocks, half A and half B (`data/holdout_split.csv`), on W1 2019-01-01 →
2026-10-30, W2 2008-01-01 → 2017-12-31 and 2018, with the same six checks, costs and
data. One variant is named **primary**; only it can be adopted. The others are reported
for information. All windows are in-sample. Paper trading is still the real test.

## Why

- A10 (monthly 12-1 momentum, top 20, 10% stop) has no market filter. Its worst drops are
  −39% (W1), −59% (W2) and −39% in 2018 (`data/a_stop_result.txt`).
- On the later window 2024-08 → 2026-10, test A fell 35.6% against the Nifty's 15.8%
  (`docs/momentum_confirmation_preregistration.md`).
- In three paired tests on other strategies, a Nifty filter cost 3-7 points a year in W1,
  added 5.6-6.7 in W2 and cut the W2 drawdown by about 22 points (`s_plus`,
  `pullback_diagnostics`).
- The Nifty 50 is the wrong gauge for this list: in 2018 it rose 4.1% while the
  equal-weight list fell 24.4%.

## Rules

A10 exactly as frozen in `docs/a_stop_preregistration.md`, plus an exposure level set at
each month end.

**Gauge (EW):** the equal-weight index of the sample's own monthly list
(`pit_strategies.equal_weight_universe`, cumulated from the first session in the data).
At each month-end close it is "up" if it is above its own 200-session average, else
"down". With fewer than 200 sessions of history the gauge is "up".

**Exposure:** each of the 20 slots is equity × level ÷ 20.
- "up": level 1.0 (A10 unchanged).
- "down": level as per the variant below. The rest stays in cash, earning nothing.
- When the level changes, existing holdings are resized to the new slot at the next
  open, with normal costs. Stops are unchanged.

| Code | Gauge | Level when "down" | Role |
|---|---|---|---|
| A10 | none | 1.0 | reference |
| **A10_E50** | EW | 0.5 | **primary** |
| A10_E0 | EW | 0.0 (all cash) | reported |
| A10_N50 | Nifty 50 above its 200-session average | 0.5 | reported, to compare gauges |

## Implementation notes (confirmed by IA before the freeze)

1. **Resizing direction.** When the level changes, every holding is set to exactly the new
   slot value (equity × level ÷ 20): trimmed if above, topped up if below, in both
   directions.
2. **Months with no level change.** Existing holdings are not touched (they drift, as in
   A10). Only new buys use the current slot size.
3. **Order at the rebalance open.** Sell the names leaving the top 20, then resize the
   survivors, then buy the new names. If cash is short, A10's rule applies: cash is split
   evenly across the buys.
4. **Trade accounting.** A trim or top-up is not a separate trade. Its cash flows and
   costs are folded into that position's single trade record.

## Adoption bar (A10_E50 against A10, same sample)

Adopted only if **all** hold on **both** half A and half B:
1. max drawdown at least 10pp shallower than A10's in **both** W1 and W2;
2. CAGR no more than 3pp below A10's in W1, and not below A10's in W2;
3. 2018 return better than A10's;
4. at least 5 of the 6 checks in both decades.

Also reported: months spent "down", number of level changes, and the all-stocks run.

## Expected, stated before the run

A shallower W2 and 2018 drop, paid for with a few points of W1 return. If the W1 cost is
more than 3pp, the filter is not worth it and A10 stays as it is.

## Output

`data/a_exposure_result.txt`

---

## Dated note, 2026-11-10 15:20 IST, before any variant run

The A10 reference cannot be reproduced to the last digit. `run_momentum` keeps each
month's buy list in an unordered set, so the order of the buys, and with it the cash
split, changes from one Python process to the next. The noise is about 0.01pp. With the
ordering fixed, the code before and after this change gives identical equity (checked on
all stocks, W2, seeds 0 and 1).

Decision by IA:
- every run in this series uses `PYTHONHASHSEED=0`;
- the reference counts as reproduced if CAGR and max drawdown are within 0.05pp of the
  stored result file.

Variants and their reference run in the same process.

---

## Results, 2026-11-10 (`data/a_exposure_result.txt`)

Run with `PYTHONHASHSEED=0`. The A10 reference matched the stored files within 0.01pp on
all nine sample × window cells. Nifty: W1 10.0%, W2 5.5%, 2018 +4.1%.

Each cell is CAGR (max drawdown); checks are out of 6.

| Sample | Version | W1 2019-26 | W2 2008-17 | 2018 | Checks W1 / W2 | ₹10 L grew to (W1 / W2) |
|---|---|---|---|---|---|---|
| Half A | A10 (reference) | 25.9% (−32.5%) | 11.3% (−58.9%) | −36.1% | 6 / 5 | 60.8 / 29.1 L |
| Half A | **A10_E50** | 22.4% (−29.6%) | 9.7% (−44.2%) | −29.2% | 5 / 4 | 48.5 / 25.2 L |
| Half A | A10_E0 | 16.6% (−28.9%) | 7.3% (−47.0%) | −20.1% | 5 / 3 | 33.2 / 20.3 L |
| Half A | A10_N50 | 24.2% (−23.1%) | 11.2% (−46.4%) | −37.8% | 6 / 5 | 54.5 / 29.0 L |
| Half B | A10 (reference) | 23.2% (−41.4%) | 12.2% (−58.6%) | −36.0% | 5 / 5 | 51.3 / 31.5 L |
| Half B | **A10_E50** | 18.5% (−37.2%) | 10.5% (−41.8%) | −31.0% | 5 / 4 | 37.9 / 27.0 L |
| Half B | A10_E0 | 14.7% (−35.1%) | 7.2% (−43.0%) | −23.0% | 4 / 4 | 29.2 / 20.0 L |
| Half B | A10_N50 | 19.7% (−29.1%) | 11.2% (−42.9%) | −37.8% | 5 / 5 | 40.9 / 28.9 L |
| All stocks | A10 (reference) | 26.4% (−39.4%) | 13.2% (−59.1%) | −38.9% | 5 / 5 | 62.4 / 34.4 L |
| All stocks | **A10_E50** | 20.9% (−34.0%) | 12.5% (−43.0%) | −31.6% | 5 / 5 | 44.3 / 32.6 L |
| All stocks | A10_E0 | 15.8% (−33.9%) | 10.0% (−42.4%) | −19.9% | 5 / 4 | 31.4 / 26.0 L |
| All stocks | A10_N50 | 22.0% (−30.5%) | 13.6% (−45.4%) | −39.1% | 5 / 5 | 47.3 / 35.8 L |

**Months "down" and level changes:**

| Gauge | Sample | W1 months down / changes | W2 months down / changes | 2018 months down / changes |
|---|---|---|---|---|
| EW | Half A | 28 of 93 / 20 | 46 of 120 / 14 | 8 of 11 / 3 |
| EW | Half B | 31 of 93 / 20 | 46 of 120 / 20 | 8 of 11 / 3 |
| Nifty | either half | 27 of 93 / 15 | 39 of 120 / 20 | 2 of 11 / 4 |

### Verdict on the primary, A10_E50, against the frozen bar: **FAILS. Not adopted.**

| Rule | Half A | Half B |
|---|---|---|
| 1. Drawdown ≥ 10pp shallower in both decades | W1 3.0pp: **fail**; W2 14.7pp: pass | W1 4.2pp: **fail**; W2 16.8pp: pass |
| 2. CAGR ≤ 3pp below A10 in W1; not below in W2 | W1 −3.6pp: **fail**; W2 −1.6pp: **fail** | W1 −4.7pp: **fail**; W2 −1.7pp: **fail** |
| 3. 2018 better than A10 | −29.2% against −36.1%: pass | −31.0% against −36.0%: pass |
| 4. ≥ 5 of 6 checks in both decades | 5 / 4: **fail** | 5 / 4: **fail** |

As expected before the run, the W2 and 2018 drops are shallower. But the W1 cost is more
than 3pp on both halves, the W1 drawdown barely improves, and W2 return also falls. A10
stays as it is.

**For information (not judged):**
- A10_E0 (all cash) cuts 2018 to about −20% to −23%, but loses 9pp a year in W1 and 4-5pp
  in W2.
- A10_N50 (Nifty gauge) costs less return: −1.7 to −3.5pp in W1, −0.1 to −1.0pp in W2. It
  cuts both decades' drawdowns by 9-16pp, but makes 2018 slightly worse, because the
  Nifty was "down" in only 2 of 11 months. It was not the primary and cannot be adopted
  from this test.

**Trade accounting.** Trims and top-ups are folded into each position's single trade
record, so the trade counts equal A10's. The "net per trade" of the scaled versions is
not comparable with A10's, because a top-up adds to the cost basis of a position.
