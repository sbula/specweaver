# Walkthrough: `B-SENS-03` SF-06 CB-1 — a chunk knows which boundary it sits inside

- **Story**: `B-SENS-03` SF-06, commit boundary 1 of 3 · **DAL-B** · 2026-08-26
- **Proves**: `FR-14`

## What shipped

`visibility`, `package` and `unit` on every chunk. The filter that matters is not *"is this
public"* but *"is this public **to me**"*, and that needs a level and **two radii** — a helper
shared inside one package is legitimately internal; another service's internals are a different
question at a different distance.

`unit` is `""` when the caller supplies no markers `[agreed 2026-08-26]`, never a fallback to
`package`. A chunk claiming a boundary the caller never established would answer *"is this outside
my service?"* from a guess.

`chunk_source` stays pure: markers arrive as data and no file is opened. There is a test that
patches `builtins.open` and asserts nothing was.

## Two mutants came back SILENT, and both were my fault in different ways

### The implementation could not be pinned

`_unit_of` iterated a **frozenset**. Its order is hash-based — stable inside one process, **not
across runs** — so two candidates of equal length would have tied differently on different days.
That is an `NFR-4` violation on its own, and it also means no deterministic test could ever kill an
order-dependent mutant. Fixed by sorting, and the sort is what made the mutant killable.

### The fixture gave the right answer by accident, twice

`test_a_marker_outside_this_path_is_ignored` used `src/apple` against `src/app/mod`. A bare-prefix
match fails there **anyway**, so removing the boundary check changed nothing. The case only bites
when the path is the **longer** of the two — `src/app` against `src/application` — and that test
now exists.

Then `test_the_nearest_marker_wins_not_the_first` used `src/app/pyproject.toml`, which sorts
**after** `src/app/mod/go.mod` — so first-match returned the correct answer. Swapped for
`src/app/build.gradle`, which sorts before it.

**A comment I wrote in `_unit_of` claimed the directories are sorted. They are not — the marker
paths are.** That comment is corrected, and it is the reason the second fixture was wrong: I
reasoned from my own wrong note instead of from the code.

## What the corpus asked for that the tests did not

`test_a_merged_chunk_carries_the_level_its_members_share` exists because `FR-9`'s guard test passes
either way. The guard proves two levels never merge; it does not prove the resulting chunk is
**labelled** with the level they share. Taking a member's level after the fact, or `unknown`, would
have satisfied every test that existed.

## Results

| Check | Result |
|---|---|
| Full suite | **8,947 passed, 11 skipped** |
| `quality.py cb` | 15/15 · `doc` 13/13 |
| ruff · ruff format · mypy · complexity · class health · duplication · conventions · tach | all clean |
| Corpus | **44 judged, 44 protected, 0 unprotected, 0 stale** |

Twelve anchors were re-hashed and two re-pointed — the preamble call gained its scope arguments.
**Six re-anchors in this story**, every one a correction the drift check forced.

## Not done here

- The two layers — **CB-2**
- The content hash — **CB-3**, and it must cover these three new labels
