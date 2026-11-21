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

---

## Results, 2026-11-08 (`data/volume_cooldown_result.txt`)

| Version | W1 2019-26 | W2 2008-17 | 2018 | Trades W1 / W2 | ₹10 L grew to (W1 / W2) | Checks W1 / W2 |
|---|---|---|---|---|---|---|
| *#3 + Nifty 1:3 (reference)* | 17.3% | 5.5% | −14.3% | 820 / 895 | 34.8 / 17.0 L | 5 / 4 |
| CS3_VX3 | 2.0% (DD −35%) | −0.2% (−35%) | −24.1% | 1,449 / 1,519 | 11.7 / 9.8 L | 1 / 1 |
| CS3_VX2 | 1.5% | −0.5% | −21.8% | 1,511 / 1,579 | 11.2 / 9.5 L | 1 / 1 |
| CS3_RX3 | −4.1% | −1.9% | −25.8% | 1,399 / 1,416 | 7.2 / 8.3 L | 1 / 1 |
| CS3_RX2 | −3.4% | −2.6% | −18.7% | 1,434 / 1,477 | 7.7 / 7.7 L | 1 / 1 |
| *FM H3 (reference)* | 9.4% | 9.7% | −19.6% | 567 / 602 | — | 3 / 4 |
| CFM_VX3 | 5.5% (−22%) | 5.4% (−40%) | −17.6% | 938 / 949 | 15.2 / 17.0 L | 2 / 4 |
| CFM_VX2 | 2.2% | 2.1% | −16.8% | 1,024 / 1,036 | 11.9 / 12.3 L | 2 / 2 |
| CFM_RX3 | 5.1% | 4.5% | −16.1% | 908 / 887 | 14.7 / 15.5 L | 2 / 4 |
| CFM_RX2 | 1.0% | 4.9% (−30%) | −13.7% | 956 / 920 | 10.8 / 16.1 L | 1 / 4 |

**Verdict:** the cool-down helps compared with no cool-down, but every version is still far
below its reference in both decades. It softens 2018 for FM, by 2-6 pp. Not adopted.

**Why:** the slot freed by a volume exit is refilled by another breakout, which also
fails the volume check about 60% of the time. The trade count stays about 1.7× the
reference. Each early exit pays a round trip of costs and usually crystallises a
first-day loss: the buy is at the breakout level, and weak breakouts tend to close below
it. The low-volume trades the rule removes were not losers on average in W1
(+0.8% per trade), so removing them costs more than it saves.

**Conclusion across the three volume tests:** breakout-day volume separates better
trades from worse ones, but it is known only at the close. Every way of acting on it
loses more than it gains:
- buying the next open (range+vol);
- exiting at the close;
- exiting at the close with a cool-down.
