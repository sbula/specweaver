# Walkthrough: `B-SENS-03` SF-04 CB-2 — indentation stops deciding where code is cut

- **Story**: `B-SENS-03` SF-04, commit boundary 2 of 4 · **DAL-B** · 2026-08-26
- **Proves**: `FR-11`

## What changed, and why it is not cosmetic

The budget counted **every** character. So the same amount of code, indented differently, was judged
differently — deeply nested Java against flat Python — and **reformatting a file moved its chunk
boundaries without a line of it changing**. Once anything is embedded, that costs a re-index of the
whole repository.

Now: non-whitespace characters only, which is how cAST measures and for the same stated reason.
**`FR-11` changes the unit, not the number.** `4000` stays a guess agreed to stay one, and there is
a test asserting the default did not quietly move while the counting did.

## The one assertion that can tell the two measures apart

Every other test here passes under both. This is the boundary's whole proof:

> the same code at **two indentation depths** must yield the **same number of chunks**

Under a raw count the indented version is far larger and cuts into more pieces. The mutant —
`_weight` reverting to `len(text)` — is objected to by that test and one other, and by nothing else
in a suite of 8,868.

## The fixture's own guard caught a bad fixture

`test_non_whitespace_over_the_budget_does_split` carries
`assert len("".join(code.split())) > 2000` before its real assertion, and that guard **failed
first**. `x = 0` is three non-whitespace characters, so 400 lines of it reach 1,900 — the fixture
could not cross the budget in the unit being measured, and the test would have "passed" by never
splitting for the wrong reason.

Widened to a realistic statement. **A test about a measure needs a fixture that can cross the
threshold in that measure**, and saying so in the fixture is cheaper than rediscovering it.

## The honest limit, written down rather than found later

A non-whitespace budget leaves **raw** chunk length unbounded: deeply indented source produces
physically larger chunks. cAST accepts the same trade, `NFR-3` states it, and a model with a hard
input cap is `A-SENS-02`'s problem to clamp.

## Results

| Check | Result |
|---|---|
| Full suite | **8,868 passed, 11 skipped** |
| `quality.py cb` | 15/15 · duplication none new |
| Ledger | `FR-11` now carries one test file. `FR-8` still reads `NO TEST`, which is true |
| Corpus | `FR-11` campaign added |

## Not done here

- Splitting on structure — **CB-3**, and the reason line-cutting is about to become rare
- Merging — **CB-4**
