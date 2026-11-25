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

## Results (2026-11-25, run once after freeze)

**References.** Passed (27 checks): A10 reproduced `data/buystop_mix_result.txt`; `WF_a_STR` and `WF_b_STR` reproduced `SF_W_a_STR` and `SF_W_b_STR` of `data/structure_flip_result.txt` exactly, on all stocks and both halves, in every window. Output: `data/weekly_flip_exits_result.txt`.

The second-flip rule cut weekly signals from 13,955 to 5,776 (all stocks, all history).

**Verdict: 0 of 4 primaries passed.** The second-flip half-target versions all failed:

| Primary | All W2 (≥ 8.54) | All W1 (≥ 13.03) | Half B W2 (> 5.54) | Half B W1 (> 10.03) | All H0 (> 21.19) |
|---|---|---|---|---|---|
| WF_a2_H2 | 1.55 | 2.28 | 2.78 | 2.74 | 8.73 |
| WF_a2_H3 | 2.41 | 4.36 | 4.86 | 5.41 | 13.10 |
| WF_b2_H2 | 6.51 | 9.14 | 6.23 ✓ | 5.85 | 10.64 |
| WF_b2_H3 | 10.63 ✓ | 8.51 | 7.93 ✓ | 6.81 | 19.15 |

**All stocks, CAGR % for every entry × exit (H0 / W2 / W1).** Nifty 50: 21.19 / 5.54 / 10.03.

| Exit | (a) first HL | (b) first breakout | (a2) second HL | (b2) second breakout |
|---|---|---|---|---|
| STR trailing | 9.0 / 10.9 / 8.6 | 14.9 / 13.9 / 7.4 | 14.8 / 8.7 / 7.9 | 16.9 / 9.1 / 11.7 |
| R2 | 11.9 / 6.2 / 5.9 | 22.3 / 13.2 / 11.6 | 11.4 / 2.2 / 7.8 | 21.0 / 10.1 / 13.2 |
| R3 | 12.8 / 8.8 / 8.8 | 18.7 / 17.6 / 11.4 | 14.9 / 5.2 / 9.0 | 25.8 / 14.9 / 10.6 |
| T26 time exit | 9.9 / 12.0 / 9.9 | 22.1 / 14.5 / 14.1 | 15.0 / 8.3 / 9.9 | 19.1 / 10.7 / 13.5 |
| **LL lower-low exit** | 23.8 / 11.9 / 11.0 | **32.8 / 17.2 / 12.5** | 33.6 / 8.7 / 11.3 | **35.0 / 12.1 / 17.0** |
| H2 half at 1R, stop to cost | 4.9 / 1.5 / 4.7 | 20.1 / 9.4 / 9.1 | 8.7 / 1.6 / 2.3 | 10.6 / 6.5 / 9.1 |
| H3 half at 1.5R, stop to cost | 8.5 / 5.3 / 6.1 | 14.2 / 12.5 / 9.1 | 13.1 / 2.4 / 4.4 | 19.2 / 10.6 / 8.5 |

The year-by-year returns for every variant are in the result file.

**What it means, in plain English:**

**Half-target exits made the weekly flip worse, not better.**
- Selling half at 1R or 1.5R and moving the stop to cost leaves the rest of the trade to be stopped at cost by ordinary weekly noise.
- So the trade earns a small gain on half, while every full loss stays a full loss.
- With the higher-low entries ((a)/(a2)), only about 42% of trades made money, and the result was 1.5–6% a year in 2008–26, below the Nifty.

**The second higher low did cut false signals, but it did not make the strategy profitable on its own.**
- Waiting for the second higher low cut signals by 59%.
- But the second-flip entries are later and higher, so the remaining moves are shorter.

**The one exit that worked well is LL: fixed stop, sold when a week closes below the latest weekly swing low.**
- It cuts trades as soon as the uptrend's structure breaks on a *close*, instead of waiting for an intraday stop under a low that keeps rising.
- **Second breakout + lower-low exit (`WF_b2_LL`):**
  - All stocks 35.0 / 12.1 / 17.0, half B 34.7 / 7.5 / 17.2. It would clear this test's bar, but it was **reported, not judged**, so it does not pass here.
  - Its stops are wide: on average 18–19% below entry.
  - About 270 trades per period (about 30 a year), with roughly 40% winners.
- First breakout + lower-low exit (`WF_b_LL`) was strong in 2001–06 and 2008–17 (32.8 / 17.2) but below the bar in 2019–26 (12.5).

**Stops under 5%** (IA's question):
- Only the higher-low entries ever have them: 8–19% of (a)/(a2) entries risk less than 5%, 25–37% risk 5–10%, and about half risk 10% or more.
- The breakout entries (b)/(b2) almost never do: 0–1% under 5%, and 89–98% risk 10% or more. The buy-stop sits at the new high, far above the higher low the stop is placed under.

A10 stays as it is. Nothing in the frozen paper-trading plan changes. Testing `WF_b2_LL` properly would need its own frozen test; IA decides.
