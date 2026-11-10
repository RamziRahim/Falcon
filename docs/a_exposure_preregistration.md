# Pre-registration: monthly momentum with exposure scaled by the stock list's own trend

**Status: DRAFT, written 2026-11-10. NOT FROZEN.** No code written, nothing run. IA to
confirm or change the variants and the adoption bar, then replace this line with
"FROZEN on <date, time>" before any run. After that: never edit; add dated notes.

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
