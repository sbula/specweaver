# Walkthrough: `B-SENS-03` SF-05 CB-2 — a chunk says whether it is a whole unit

- **Story**: `B-SENS-03` SF-05, commit boundary 2 of 2 · **DAL-B** · 2026-08-26
- **Proves**: `FR-16`, `FR-17`. Closes SF-05.

## What shipped

`Chunk.is_line_window` — true when the text was cut by lines rather than at a boundary the code
has. A binary blob and a module preamble both carry no symbol, so without it a consumer cannot rank
one below the other.

**`FR-10`'s last resort sets it too**, which the design's `FR-16` does not say. A symbol sliced at
line 400 is no more a whole unit than a blob is, and a consumer ranking by *"is this a whole unit"*
needs both marked. Stated in the plan rather than discovered in review.

**And the unreadable file is tracked, not inferred.** `len(pieces) > 1` cannot see it: a *small*
file no grammar handles arrives in one piece, so nothing about the cut says it was never understood.
`_Cut.unreadable` carries that from the one place that knows.

## `FR-17` is two claims and the second is not implied by the first

Totality compares **non-whitespace** characters. A merge that dropped the blank run between two
symbols satisfied it while producing `... return 1clas s Beta:` — a chunk whose content never
existed in the file and which no reader could locate in it. That was found in SF-04 CB-4 by mutating
the fix and getting SILENT back.

So `FR-17` now says both, and this boundary states them **once per path** — preamble, merge,
structure split, line fallback, no-symbols, unparseable — at three budgets each. A rule that only
holds where it was tested is not a rule.

## The tag moved, because a tag is exhaustive

`FR-17` was carried by two files that assert **totality only**. Its claim grew a second half neither
of them makes, and a `Proves:` tag is exhaustive for the story it names — so leaving it would have
credited a half-claim as whole. It now sits on the file that states both.

## Three mutants of mine were wrong, and the runner said which kind of wrong

| Mutant | Verdict | What it actually was |
|---|---|---|
| `parser-failure-drops-file` | `UNMEASURED [symbol-drifted]` | anchored on `order = []`, which this boundary rewrote |
| `preamble-dropped` | `UNMEASURED [run-failed]` | the replacement was **not valid Python** |
| `the-trailing-remainder-is-dropped` | `UNPROTECTED [no-killer]` | **equivalent** — `if True:` makes every gap join the buffer, and the final flush still emits it. Boundaries move; content does not |

The third is the one worth naming. `UNPROTECTED` reads as *a test is missing*, and here it meant
*the mutant was wrong*. Checked before acting, as the skill requires, and replaced with one that
genuinely drops the tail: the final `run.flush()` never happening. Recording a coverage gap that
was not there would have been worse than the mutant.

Four more anchors were re-hashed. **Every commit that touches a mutated line costs a re-anchor** —
six times now in this story — and the drift check is the only reason each has been a correction
rather than a silent pass.

## Results

| Check | Result |
|---|---|
| Full suite | **8,926 passed, 11 skipped** |
| `quality.py cb` | 15/15 · duplication none new |
| Corpus | **37 judged, 37 protected, 0 unprotected, 0 stale** |
| Ledger | `FR-15`, `FR-16`, `FR-17` all carry a test file. Only `FR-12`, `FR-13`, `FR-14` remain — all SF-06 |

## SF-05 is delivered

Nothing is lost on any path, every chunk is text the file actually has, and a chunk that is not a
whole unit says so.
