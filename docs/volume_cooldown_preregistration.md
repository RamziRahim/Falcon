# Pre-registration: volume exit with a 20-session cool-down

**Status: FROZEN on 2026-11-08 ~22:30 IST,** before any run. This follows
`docs/volume_exit_preregistration.md`. There, the volume exit failed because sold stocks
were re-bought again and again. IA approved adding a cool-down. Never edit; add dated
notes.

## Rules

All rules of `docs/volume_exit_preregistration.md`:
- the breakout buy-stop entry;
- the optional 10% range check before the fill;
- sell at the close of the fill day if its volume is below 1.5× the 50-session average.

Plus one new rule:
- **Cool-down.** After a volume exit on session i, no new buy order is placed for that
  stock until after session i + 20. For FM, the stock's trigger is ignored while it is
  blocked, even if it is on the watch list.

Everything else is unchanged.

## Versions

Same eight codes as before, with a C prefix:

| | Volume exit only | Volume exit + 10% range |
|---|---|---|
| **#3** | CS3_VX3, CS3_VX2 | CS3_RX3, CS3_RX2 |
| **FM** | CFM_VX3, CFM_VX2 | CFM_RX3, CFM_RX2 |

## References

| Reference | W1 | W2 | 2018 |
|---|---|---|---|
| #3 + Nifty 1:3 | 17.3% | 5.5% | −14.3% |
| #3 + Nifty 1:2 | 15.4% | 5.1% | −12.6% |
| FM H3 | 9.4% | 9.7% | −19.6% |
| FM H2 | 9.0% | 12.2% | −22.8% |

## Windows and outputs

- **Windows:** W1, W2 and 2018, with the six checks.
- **All windows are in-sample.**
- **Output:** `data/volume_cooldown_result.txt`.
