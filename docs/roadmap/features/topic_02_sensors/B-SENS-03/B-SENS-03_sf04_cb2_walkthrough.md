# B-SENS-03 SF-04 CB-2 — Walkthrough

**Commit boundary:** CB-2 of 4 · **DAL-B** · 2026-08-26 · **Proves**: `FR-11` · Plan:
[sf04](B-SENS-03_sf04_implementation_plan.md)

## Delivered

The budget counts **non-whitespace** characters, as cAST does. Replaces a count of every character,
under which the same code indented differently was judged differently and **reformatting a file
moved its chunk boundaries** — a whole-repository re-index once anything is embedded.

**`FR-11` changes the unit, not the number.** `4000` stays a guess agreed to stay one; a test asserts
the default did not move. Limit (`NFR-3`): raw chunk length is unbounded — deeply indented source
gives physically larger chunks; clamping for a hard input cap is `A-SENS-02`'s.

## Proof

The one assertion that tells the measures apart: **the same code at two indentation depths yields
the same number of chunks**. The mutant — `_weight` reverting to `len(text)` — is objected to by
that test and one other, and nothing else in a suite of 8,868.

`test_non_whitespace_over_the_budget_does_split` guards its own fixture with
`assert len("".join(code.split())) > 2000` — a fixture about a measure must cross the threshold in
that measure (`x = 0` is three non-whitespace characters; 400 lines reach only 1,900).

| Check | Result |
|---|---|
| Full suite | **8,868 passed, 11 skipped** |
| `quality.py cb` | 15/15 · duplication none new |
| Ledger | `FR-11` carries one test file |
| Corpus | `FR-11` campaign added |
