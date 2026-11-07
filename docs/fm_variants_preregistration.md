# Pre-registration: FM exit variants and trade-path breakdown

**Status: FROZEN on 2026-11-07 ~21:55 IST,** before any run. IA asked for the same table
as for #3 (direct / retest / stop then down / stop then up / neither, over 20 and 40 days)
for "the Falcon strategy": FM, `docs/falcon_momentum_preregistration.md`. Never edit; add
dated notes.

## Versions

FM exactly as frozen (40-session time stop), with the exit varied:

| Code | Target | Extra |
|---|---|---|
| R3 | 3R (FM as frozen) | — |
| R2 | 2R | — |
| R3BE | 3R | once the high reaches fill × 1.05, the stop moves to the fill from the next session; nothing is sold |
| R2BE | 2R | same as R3BE |

The stop stays FM's: the tighter of the swing-low stop and fill − 3 ATR. R3 must
reproduce the frozen FM result (W1 11.2%, W2 8.6%); that is the regression check.

## Windows and outputs

- **Windows:** W1, W2 and 2018, with the six checks for each run.
- **Trade-path breakdown:** every trade's path is followed for 20 and for 40 sessions
  from the fill, ignoring the actual exit. The classes are those of
  `tests/analyse_trade_paths.py`. The levels are the actual fill, stop and target logged
  at entry.
- **All windows are in-sample.** This is descriptive, plus a comparison of variants;
  confirmation can only come from paper trading.
- **Outputs:**
  - `data/fm_variants_result.txt`
  - `data/fm_trade_paths.txt`
  - trades and levels in `data/fm_variants_*`
