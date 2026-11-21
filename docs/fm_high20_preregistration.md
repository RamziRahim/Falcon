# Pre-registration: Falcon Momentum with a 20-day-high breakout entry

**Status: FROZEN on 2026-11-07 ~23:10 IST,** before any run. IA asked: "for Falcon, what
if we try an entry point at the 20-day breakout instead of buying on Monday, for
different variations (1:2, 1:3, 5%:5%, 5% then stop to cost…)". Never edit; add dated
notes.

## Rules

**Watch list:** FM's, exactly as in `docs/falcon_momentum_entries_preregistration.md`.
- Weekly top 30 by FM rank, passing the sector check, while the Nifty is above its
  200-SMA.
- On the list for 10 sessions, renewed while the stock qualifies.
- Triggers are ignored while the Nifty is at or below its 200-SMA.

**Entry:** each session a stock is on the list, a one-session buy-stop at its 20-day high
(the highest high of the last 20 sessions, including today).
- Filled the next session if the high reaches the level, at the higher of the level and
  the open.
- Skipped if the open is more than 3% above the level.

## Exit variants

| Code | Stop | Target | Extra |
|---|---|---|---|
| H3 | FM's: the higher of the swing-low stop and fill − 3 ATR | 3R | — |
| H2 | FM's | 2R | — |
| H5 | fill × 0.95 | fill × 1.05 | — |
| H3BE | FM's | 3R | once the high reaches fill × 1.05, the stop moves to the fill from the next session |
| H2BE | FM's | 2R | same as H3BE |

## Unchanged from FM

- **Sizing:** 1% risk (0.5% while the Nifty is below its 50-SMA), positions ≤ 25%, at
  most 10 positions.
- **Skipped** if the stop is more than 15% away, or at or above the fill.
- **Exits:** the rank > 100 exit and the 40-session time stop.
- **Fill rules:** the stop wins a same-day tie, including on the fill day; after the
  fill day, gaps fill at the open.

## Windows and judgement

- **Windows:** W1, W2 and 2018, with the six checks.
- **Compared with:** FM's Monday-open versions (1:3 at 11.2 / 8.6 / −26.7%).
- **All windows are in-sample.**

## Output

`data/fm_high20_result.txt`

---

## Results, 2026-11-08 (`data/fm_high20_result.txt`)

| Version | W1 2019-26 | W2 2008-17 | 2018 | Max DD W1 / W2 | Win % W1 / W2 | Checks W1 / W2 |
|---|---|---|---|---|---|---|
| H3 (20-day-high entry, 1:3) | 9.5% | 9.7% | −19.6% | −28 / −36% | 42.0 / 44.9 | 3/6 / 4/6 |
| **H2 (1:2)** | 9.0% | **12.2%** | −22.8% | −31 / **−24%** | 44.7 / 48.2 | 3/6 / **5/6** |
| H5 (±5%) | −27.1% | −38.5% | −20.3% | −92 / −99% | 44.0 / 42.2 | 0/6 / 0/6 |
| H3BE | 11.2% | 2.6% | −18.2% | −25 / −39% | 22.2 / 20.7 | 3/6 / 3/6 |
| H2BE | 7.2% | 2.4% | −17.6% | −21 / −34% | 24.9 / 23.9 | 2/6 / 2/6 |
| *FM 1:3, Monday open* | *11.2%* | *8.6%* | *−26.7%* | *−26 / −27%* | *39.8 / 43.7* | *2/6 / 4/6* |
| *FM 1:2, Monday open* | *10.0%* | *8.0%* | *−19.0%* | *−22 / −24%* | *44.4 / 47.2* | *3/6 / 4/6* |

**Verdict:** no version passes both windows.

**Reading:**
- The 20-day-high entry is about level with the Monday open: 1-2 pp lower on W1,
  1-4 pp higher on W2.
- **H2 is the best version on W2:** 12.2%, a −24% drawdown, and 5/6 checks. On W1 it
  makes 9.0%, below the Nifty's 10.0%.
- ±5% is ruinous here too.
- Moving the stop to cost at +5% gives up most of the W2 return.
