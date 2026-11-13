# Pre-registration: Falcon v2 patterns at 2% risk per trade

**Status: FROZEN on 2026-11-13 18:20 IST.** Frozen on IA's instruction ("Try with 2% risk")
before any test code was written or run. Never edit; add dated notes.

**Samples.** Each variant runs once on half A, half B and all stocks, on W1 2019-01-01 →
2026-10-30, W2 2008-01-01 → 2017-12-31 and 2018, with the same six checks, costs and
data, and `PYTHONHASHSEED=0`. The stored v2 scans are reused. Neither half is clean
(half A shaped v2; half B was used for the v2 and retest tests), so a pass would mean
"paper trade it", not "proven". All windows are in-sample.

## Why

FV2 makes +1.5% to +2.6% per trade after costs, but with 1% risk per trade it kept only
47-61% of capital invested, so its yearly return only matched the Nifty. This test asks
whether doubling the risk per trade turns the per-trade edge into a return clearly above
the Nifty without an unacceptable drawdown.

## Rules

Everything is exactly FV2 (`docs/falcon_v2_preregistration.md`, rules 1-10) except the
risk per trade in rule 10:
- position value = min(risk × equity ÷ stop distance, 25% of equity, cash × 0.999);
- 10 slots and the 25% per-position cap are unchanged.

## Versions

| Code | Risk per trade | Role |
|---|---|---|
| FV2 | 1% | reference; must reproduce `data/falcon_v2_result.txt` within 0.05pp (all samples, W1 and W2) |
| **FV2_R2** | 2% | **primary** |
| FV2_R15 | 1.5% | reported |

## Adoption bar (FV2_R2; all must hold on both half A and half B, in both W1 and W2)

The same absolute bar as the v2 test:
1. CAGR above the Nifty's;
2. at least 4 of the 6 checks;
3. max drawdown no deeper than −25.00%;
4. win rate at least 45.0%, and mean net per trade at least +1.00%;

and:
5. CAGR higher than FV2's on the same sample and window.

Figures are compared as printed in the result file. Also reported: average capital
invested, how often the 25% cap or the cash limit sets the size, slots-full skips, and
2018.

## Expected, stated before the run

Return higher than FV2 in most cells, but the 25% cap will limit many positions (a 2%
risk with a stop more than 8% away is under the cap, nearer stops are capped), so the
gain is less than double. Drawdowns deeper, roughly 1.5×: likely to fail rule 3 in at
least one cell.

## Output

`data/falcon_v2_risk2_result.txt`, runner `tests/run_falcon_v2_risk2.py`. Implemented as
an optional `risk` parameter of `run_setups_v2` defaulting to 1%.

---

## Results — 2026-11-13 (added after the run; nothing above was changed)

**Run notes.** `run_setups_v2(..., risk=...)` (default 1% = FV2 unchanged), runner
`tests/run_falcon_v2_risk2.py`, one run, `PYTHONHASHSEED=0`. A `size_capped` counter was
added to the stats (how often the 25% cap or cash set the size); it changes no trade.
**Reference check:** FV2 reproduced `data/falcon_v2_result.txt` exactly on all three
samples, W1 and W2.

### Primary variant FV2_R2 against the frozen bar

| Sample, window | CAGR (Nifty) | Checks | Max DD | Win / net | CAGR vs FV2 | Bar |
|---|---|---|---|---|---|---|
| Half A, W1 | 10.57% (10.03%) ✓ | 3/6 ✗ | −33.25% ✗ | 44.7% / +1.58% ✗ | 10.57 > 9.50 ✓ | **FAIL** |
| Half A, W2 | 5.76% (5.54%) ✓ | 4/6 ✓ | −25.98% ✗ | 47.2% / +1.48% ✓ | 5.76 < 6.36 ✗ | **FAIL** |
| Half B, W1 | 12.61% (10.03%) ✓ | 3/6 ✗ | −26.40% ✗ | 46.1% / +2.69% ✓ | 12.61 > 11.64 ✓ | **FAIL** |
| Half B, W2 | 3.77% (5.54%) ✗ | 2/6 ✗ | −36.03% ✗ | 46.0% / +1.24% ✓ | 3.77 < 5.58 ✗ | **FAIL** |

**Verdict: FV2_R2 FAILED its bar in all four cells. Not adopted.** Rule 3 (drawdown no
deeper than −25%) failed in every cell; rule 5 (beat FV2) failed in 2008–17 on both
halves.

### All versions (CAGR / max DD / win / net per trade / closed trades / checks; average capital invested)

| Code | Sample | W1 2019–26 | W2 2008–17 | 2018 |
|---|---|---|---|---|
| FV2 (1%) | A | 9.50 / −29.59 / 45.7 / +1.79 / 431 / 3; 61% | 6.36 / −25.13 / 48.2 / +1.72 / 417 / 4; 49% | −7.55 / −15.07; 53% |
| **FV2_R2** | A | 10.57 / −33.25 / 44.7 / +1.58 / 427 / 3; 66% | 5.76 / −25.98 / 47.2 / +1.48 / 413 / 4; 56% | −5.98 / −21.17; 60% |
| FV2_R15 | A | 11.43 / −28.04 / 47.0 / +2.01 / 423 / 3; 65% | 5.75 / −27.51 / 47.7 / +1.61 / 415 / 4; 54% | −7.06 / −19.38; 55% |
| FV2 (1%) | B | 11.64 / −21.95 / 46.5 / +2.59 / 383 / 3; 56% | 5.58 / −28.34 / 46.4 / +1.50 / 403 / 4; 47% | −2.01 / −11.37; 52% |
| **FV2_R2** | B | 12.61 / −26.40 / 46.1 / +2.69 / 373 / 3; 64% | 3.77 / −36.03 / 46.0 / +1.24 / 396 / 2; 54% | +2.57 / −12.72; 57% |
| FV2_R15 | B | 12.32 / −25.65 / 46.1 / +2.76 / 375 / 3; 61% | 3.23 / −35.83 / 45.8 / +1.38 / 402 / 3; 52% | +1.77 / −12.19; 55% |
| FV2 (1%) | All | 12.20 / −24.63 / 44.6 / +1.88 / 491 / 3; 67% | 4.31 / −30.39 / 44.9 / +0.88 / 497 / 4; 57% | −1.19 / −15.67; 62% |
| **FV2_R2** | All | 11.41 / −44.23 / 43.8 / +1.82 / 475 / 2; 72% | 3.52 / −43.19 / 46.0 / +1.15 / 483 / 3; 62% | −9.41 / −17.84; 64% |
| FV2_R15 | All | 14.93 / −25.82 / 44.9 / +2.00 / 485 / 3; 70% | 2.01 / −42.84 / 45.6 / +1.16 / 493 / 2; 60% | −7.10 / −17.81; 64% |

How often the 25% cap or the cash limit set the size: at 1% risk about 25-30% of
buys; at 2% about 85-95%.

### Reading (information only; no decision rests on it)

- Doubling the risk raised average capital invested by only 5-8 points (to 54-72%). With
  2% risk most positions hit the 25% cap, so four or five fill the account and later
  signals find no cash; between clusters of signals the money still sits idle. Risk per
  trade is not what keeps v2 half in cash.
- Bigger positions made each losing streak hurt more: drawdowns deepened by 1-14
  points, and 2008-17 return fell on both halves. The per-trade edge does not scale
  with size because the largest positions land in the same clusters of breakouts that
  fail together.
- Expectation check: return higher than FV2 in most cells (held in W1 only, not W2);
  drawdowns deeper (held, and worse than expected on all stocks); failed rule 3 (held,
  in every cell).
