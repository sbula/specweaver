# Walkthrough: `B-SENS-03` SF-04 CB-4 — small neighbours merge

- **Story**: `B-SENS-03` SF-04, commit boundary 4 of 4 · **DAL-B** · 2026-08-26
- **Proves**: `FR-9`. Closes SF-04.

## What shipped

Consecutive small symbols are combined up to the budget, **within one visibility level**, carrying
whatever sits between them. Twelve three-line getters stop being twelve chunks of near-identical
shape that match everything and discriminate nothing.

**`Chunk.symbols` arrives here rather than in SF-06, and that was said before it was written.**
`FR-9` cannot be honest without it: a merged chunk holds several symbols, so `symbol` cannot name
it, and merging twelve getters into three *anonymous* chunks loses more than it gains. The rest of
`FR-13` — content hash, package, unit — is still SF-06's.

## Three defects the mutants found in my own tests

**1. The visibility test was vacuous.** `test_a_public_getter_is_not_merged_with_a_private_helper`
passed, and deleting the guard changed nothing — **SILENT, 0 objections**. At `max_chars=90` the
class fitted whole: nothing split, nothing merged, and the loop iterated one chunk named `Bag`.
At 60 it splits and two methods would merge without the guard. The fixture now asserts it split
before asserting anything about what it split into.

**2. Merging spliced text that never existed.** A chunk read `... return 1clas s Beta:`. `_walk`
dropped whitespace-only gaps — harmless when every symbol was its own chunk, and not harmless once
a merged chunk concatenates what it covers.

**3. Totality does not catch that, and did not.** `FR-17` compares *non-whitespace* characters, so
losing a blank run passes it. The assertion that catches it is **containment**: every chunk's text
must be a verbatim slice of the file. Found by mutating the fix and getting SILENT back a second
time.

## Split-then-merge does not undo itself

It looks as though it should — the split makes small siblings, and merging combines small siblings.
Both obey the **same budget**, so the class that was over it cannot have all its methods merge back.
Asserted directly: an oversized class yields more than one chunk after both passes, and no chunk
exceeds the budget.

## Complexity and cohesion pushed the shape, and the shape is better

`check_complexity` put `_merge` at **19** against a ceiling of 15, and every branch it counted was
one question — *may this piece join the run?* — asked of one piece of state. That is a class, and
`_Run` is it: three methods, all touching all of its state, `check_class_health` clean.

## Visibility is asked five times per file, not once per symbol

`extract_symbol_visibility` re-parses on every call. `_levels` asks `list_symbols(visibility=[…])`
once per level instead, and `VISIBILITY` is closed, so the bound is a constant rather than a guess.
A test asserts the call count directly.

**And the parser contract grew, which is now stated rather than swallowed.** The chunker's minimal
stub needed a third call shape. A stub that did not accept it fell into `except Exception` and
reported every symbol `unknown`, merging everything — a degradation silent enough to be worth a
stub that says so.

## Mutants — three, all killed

| # | Neutralised | Objections |
|---|---|---|
| M1 | the visibility guard | **1** |
| M2 | merging entirely | 3 |
| M3 | the between-text | 2 |

M1 has a single point of protection, and it is the one that matters most.

**Three anchors drifted** and were re-pointed. `FR-17`'s `preamble-dropped` had anchored on
`if head.strip():` — a line that now belongs to `FR-9`'s between-text mutant, one requirement over.
Two claims would have shared one line, which is the conflation this story has now hit four times.

## Results

| Check | Result |
|---|---|
| Full suite | **8,892 passed, 11 skipped** |
| `quality.py cb` | 15/15 · duplication none new · complexity clean · class health clean |
| Corpus | **30 judged, 30 protected, 0 unprotected, 0 stale** |
| Ledger | `FR-8`–`FR-11` all carry a test file. `FR-12`–`FR-15` remain SF-05 and SF-06 |

## SF-04 is delivered

Code is cut where it has a seam, sized by what is actually there, and small neighbours travel
together without a private symbol ever riding along.
