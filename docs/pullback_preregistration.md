# Pre-registration: leader pullback strategy (IA's rules), half A

**Status: FROZEN on 2026-11-09 ~17:05 IST,** before any run. These are IA's rules, as
given on 2026-11-09. Where the data cannot express a rule exactly, the substitute is
stated here, before any run. Never edit; add dated notes.

## Rules (`backtesting/pullback.py`)

**1. Market filter.**
- The Nifty 50 close is above its 200-DMA, and the 50-DMA is rising (above its value 5
  sessions earlier).
- **B versions** also require breadth: more than 50% of the universe closing above its
  own 200-DMA.

**2. Universe.**
- Half A of the point-in-time top-500-by-traded-value list. This stands in for the
  Nifty 500; index membership history is not available.
- Traded price above ₹100. The traded price is Turnover ÷ Volume, i.e. the unadjusted
  day's VWAP, because the stored prices are split-adjusted.
- 20-day average turnover above ₹10 cr.

**3. Leader filter, at session t.**
- **Momentum:** the 6-month return skipping the last 2 weeks (Close[t−10] / Close[t−126]
  − 1) is in the top 20% of the universe.
- **Near the high:** Close ≥ 85% of the 52-week high.
- **Trend:** Close is above the 50-DMA and the 200-DMA, and both are rising (above their
  values 10 sessions earlier).

**4. Pullback setup.**
- **Swing high:** the highest high of sessions t−12 to t−1, on session h.
- **Dip length:** 3-8 sessions, from h+1 to t−1.
- **Dip depth:** the pullback low (the lowest low from h+1 to t) is 5-12% below High[h].
- **Toward the averages:** the pullback low is at or within 1% above the 20-EMA or the
  50-DMA on its day.
- **Volume shrinks:** the mean volume from h+1 to t−1 is below the 50-day average volume
  before h.
- **RSI cools:** the minimum RSI(14), Wilder's, from h+1 to t−1 is between 35 and 50.
- **Not applied:** "no earnings within 7 days". There is no history of results dates in
  the data.

**5. Entry trigger.**
- Close[t] > High[t−1].
- The buy is at Close[t], an order near 3:20 pm.
- Priority: the highest momentum rank.

**6. Risk.**
- **Stop:** the pullback low − 0.5 × ATR(14). Skip the trade if the stop is more than 8%
  below the entry.
- **Sizing:** risk 1% of capital (**075 versions:** 0.75%), ≤ 25% per position.
- **Limits:** at most 6 positions, and at most 2 per sector. Sector = the NSE sector index
  a stock correlates with at ≥ 0.5 (`sector_maps`); stocks without one are uncapped.

**7. Exits.**
- **Stop:** intraday at the stop; a gap below it fills at the open.
- **Half off at +2R:** intraday at entry + 2R (a gap above fills at the open). The rest is
  trailed: sell at the next open after a close below the 20-EMA.
- **Day 8:** if the high has not reached +1R by the close of session 8 after entry, sell
  at the next open.
- **Day 20:** sell everything at the next open after session 20.

## Versions

| Code | Risk | Breadth filter |
|---|---|---|
| PB10 | 1% | no |
| PB075 | 0.75% | no |
| PBB10 | 1% | yes |
| PBB075 | 0.75% | yes |

## Comparison and adoption

- **References (half A):**
  - S3_REF3: 9.9% / 3.4% / −14.8%
  - FM_C3: 14.5% / 12.7% / −14.7%
  - RB3: 6.9% / 3.6% / −7.2%
- **Adoption rule:** a version is a candidate if, in both W1 and W2, it passes at least
  4 of the 6 checks and beats the Nifty on CAGR.

## Windows and outputs

- **Windows:** W1, W2 and 2018, with the six checks.
- **All windows are in-sample.**
- **Output:** `data/pullback_result.txt`.

---

## Results, 2026-11-09 (`data/pullback_result.txt`), half A

| Version | W1 2019-26 | W2 2008-17 | 2018 | Trades W1 / W2 | Win % W1 / W2 | Net per trade W1 / W2 | Checks W1 / W2 |
|---|---|---|---|---|---|---|---|
| PB10 | 1.0% (DD −13%) | 0.1% (−13%) | −2.7% | 158 / 89 | 43.7 / 40.4 | +0.28 / −0.06% | 1 / 1 |
| PB075 | 0.8% (−10%) | 0.0% (−10%) | −1.7% | 158 / 89 | 43.7 / 40.4 | +0.28 / −0.06% | 1 / 1 |
| PBB10 | 1.2% (−13%) | −0.2% (−15%) | +3.0% (2 trades) | 141 / 82 | 44.0 / 40.2 | +0.39 / −0.27% | 1 / 1 |
| PBB075 | 1.1% (−10%) | −0.2% (−12%) | +2.3% | 141 / 82 | 44.0 / 40.2 | +0.40 / −0.27% | 1 / 1 |

Nifty: 10.0% / 5.5%.

**Verdict:** all four fail; none beats the Nifty in either decade. Not adopted.

**Why:**
- **Few trades.** The full set of rules qualifies about 20 trades a year in W1 and 9 in
  W2, out of about 250 half-A stocks. Capital is idle almost all the time.
- **No edge per trade.** Net per trade is about 0%.
- **Exit mix, PB10 W1:**
  - 59 of 158 trades (37%) are cut at day 8 for not reaching +1R;
  - 51 (32%) are stopped;
  - only 30 (19%) reach the +2R half-exit.
  The day-8 rule and the stop below the pullback low catch most trades before they move.
