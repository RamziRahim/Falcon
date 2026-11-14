# Pre-registration: #3 with a sector filter and a Nifty 50 fallback

**Status: FROZEN on 2026-11-05 ~23:45 IST,** before any run. IA asked on 2026-11-05:
"sector index above 50ma, if not, check nifty index". Never edit; add dated notes.

## Rule

Everything is as in `docs/s_sector_preregistration.md`, except for one thing. When no
NSE sector index fits a stock (best 252-session correlation < 0.5), the filter checks
the **Nifty 50 close against its 50-session SMA**, instead of the stock's size-bucket
index.

- A stock **with** a mapped sector index needs that index above its 50-SMA.
- A stock **without** one needs the Nifty 50 above its 50-SMA.

"If not" is read as "if no sector index applies". It is not read as "if the sector is
below its 50-SMA, try the Nifty instead".

## Variants and windows

- **R3:** swing-low stop, 3R.
- **R2:** swing-low stop, 2R.
- ±5% 1:1 and the half-at-5% variants are not re-run. They were far worse under both
  earlier filters.
- **Windows:** W1, W2 and 2018, with the same six checks.
- **Compared with:** #3 + Nifty filter (S+), and #3 + sector/size-bucket filter.
- **All windows are in-sample.** Confirmation can only come from paper trading.

## Outputs

- `data/s_sector_nifty_result.txt`
- trades in `data/s_sector_nifty_trades_*.csv`

---

## Dated addendum, 2026-11-05 ~23:45 IST, before any result of these two variants existed (R3/R2 runs were in progress)

IA added: "no need to take half profit; instead, if it reaches 5%, trail the stop to
the entry price". Two more variants, under the same sector-or-Nifty filter:

- **R3BE:** swing-low stop and 3R target. Once the high reaches entry × 1.05, the stop
  moves to the entry from the next session. Nothing is sold at +5%; the full position
  goes for the target.
- **R2BE:** the same with a 2R target.

If the 3R or 2R target is at or below +5%, the break-even rule does not apply.
Everything else is as above. Results are appended to `data/s_sector_nifty_result.txt`.

## Results, 2026-11-06 (`data/s_sector_nifty_result.txt`)

| Variant (sector index, else Nifty 50) | W1 2019-26 | W2 2008-17 | 2018 | Win % W1 / W2 | Net per trade W1 / W2 | Checks W1 / W2 |
|---|---|---|---|---|---|---|
| **R3** | **18.0%** (DD −26%) | 5.2% (DD −43%) | −18.8% | 49.8 / 46.1 | +2.01 / +0.91% | **5/6 / 4/6** |
| R2 | 12.3% (−33%) | 2.8% (−39%) | −17.1% | 48.1 / 46.9 | +1.36 / +0.52% | 3/6 / 3/6 |
| R3BE (stop to entry at +5%) | 8.8% (−36%) | −0.5% (−51%) | −14.7% | 30.2 / 27.5 | +0.98 / −0.05% | 3/6 / 1/6 |
| R2BE | 5.0% (−36%) | −2.7% (−46%) | −17.3% | 30.7 / 28.0 | +0.64 / −0.24% | 3/6 / 1/6 |
| *#3 + Nifty filter (S+)* | *17.3% (−24%)* | *5.5% (−34%)* | *−14.3%* | | | *5/6 / 4/6* |

**Verdict:** no variant passes both windows.
- R3 under the sector-or-Nifty filter is about level with the Nifty-only filter: +0.7 pp on
  W1, −0.3 pp on W2, deeper W2 and 2018 drawdowns.
- About 3 in 4 filter decisions fell back to the Nifty.
- **Moving the stop to entry at +5% hurts in every window.**
  - On W1, 358 of 1,016 R3BE trades ended at break-even. They had been shaken out on a
    normal pullback after +5%, and many would otherwise have gone on to a time-stop gain
    or the target.
  - CAGR falls from 18.0% to 8.8% on W1, and from 5.2% to −0.5% on W2.
