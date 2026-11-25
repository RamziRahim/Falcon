# Weekly structure flip: second-flip entries and non-trailing exits — pre-registration

**Status: FROZEN on 2026-11-25 19:58 IST**

## Question

IA (2026-11-25), after the weekly flip failed (`docs/structure_flip_preregistration.md`): about half of weekly flips fall back through the higher low within about two weeks.
- Would waiting for a **second** higher low, a more confirmed uptrend, give fewer false flips?
- Do exits **without trailing** do better: fixed targets, a time exit, a lower-low exit, or selling half at half the target and moving the stop to cost?

The test is weekly only, and every rule not changed below is as frozen in `docs/structure_flip_preregistration.md`.

## Entries

The first two entries are the same as before; the second-flip entries are new.

- **(a):** buy at the next open once the first higher low (HL1) is confirmed.
- **(b):** a buy-stop at the high made after the break, while the setup is alive.
- **(a2), second higher low:**
  1. After HL1 is confirmed, wait for a weekly close above HH1, the highest high from the break to HL1's confirmation. This is the second higher high.
  2. Then wait for a weekly swing low confirmed after that close, above HL1. This is HL2.
  3. Buy at the next open.
  - **Reset** if a weekly close falls below HL1, if a confirmed swing low after the HH2 close is at or below HL1, or if no HH2 close comes within 26 weekly bars of HL1.
- **(b2):** after HL2, a buy-stop at HH2, the highest high from the HH2 close to HL2's confirmation.
  - It fills on the first session whose high exceeds HH2, at max(open, HH2).
  - **Cancelled** if a weekly close falls below HL2, or after 13 weekly bars.

**Stop:** 1% below the higher low the entry was based on: HL1 for (a)/(b), HL2 for (a2)/(b2), as IA chose.

## Exits (each entry is run with each exit)

| Code | Exit |
|---|---|
| STR | Trailing, as before: the stop rises to 1% below each newly confirmed higher weekly swing low |
| R2 / R3 | Fixed stop; target at 2 × / 3 × the risk |
| T26 | Fixed stop; otherwise sold at the open 130 sessions (about 26 weeks) after entry |
| LL | Fixed stop; also sold at the next open after a completed week closes below the latest confirmed weekly swing low (the entry's higher low, or a later confirmed swing low) |
| H2 | Half sold at 1 × risk; stop moves to the entry price for the rest; the rest exits at 2 × risk or at cost |
| H3 | Half sold at 1.5 × risk; stop to the entry price; the rest exits at 3 × risk or at cost |

Exit mechanics:
- The half sale uses `Ledger.trim`. If price gaps above the level, it fills at the open.
- A stop moved on a given session applies from the next session.
- Stops are checked before targets, as in all FM and A10 tests.

## Runs

- 4 entries × 7 exits = **28 variants**, named `WF_<entry>_<exit>`.
- **Windows:** H0 2001–06, W2 2008–17, W1 2019-01-01 → 2026-10-30.
- **Samples:** all stocks, half A and half B.
- Portfolio, universe, costs, slots and tie-break: as frozen for the structure flip. Data `data/pit_v2`, no ethical filter.
- **Reference:** A10 must reproduce `data/buystop_mix_result.txt`. Also, `WF_a_STR` and `WF_b_STR` must reproduce `SF_W_a_STR` and `SF_W_b_STR` in `data/structure_flip_result.txt`, within 0.05pp, in every window and sample. Otherwise the run stops.
- **Reported for every variant:**
  - CAGR, max DD, trades, win rate;
  - share of exits at the original stop and their median days held;
  - **year-by-year returns** for every year from 2001 to 2026 (all stocks), within each window's years.

## Adoption bar

**Judged: the four second-flip half-target versions:** `WF_a2_H2`, `WF_a2_H3`, `WF_b2_H2`, `WF_b2_H3`. Each must pass all three conditions:

1. **All stocks, W1 and W2:** CAGR at least 3.0 percentage points a year above the Nifty 50's.
2. **Half B, W1 and W2:** CAGR above the Nifty's.
3. **H0 2001–06, all stocks:** CAGR above the Nifty's.

This is the same bar as the structure-flip test. The verdict states how many of the four pass. The other 24 variants are reported only: a reported variant that clears the bar does not pass by itself.

A pass means "candidate for paper trading" — IA decides. No re-tuning, no extra variants.

## Output

- `data/weekly_flip_exits_result.txt`
- Code changes: optional `second=True` in `find_signals`, and exits T26 / LL / H2 / H3 in `run_flip`. Defaults are unchanged.
- Runner: `tests/run_weekly_flip_exits.py`
- Dated Results section here; scorecard rows.
