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
