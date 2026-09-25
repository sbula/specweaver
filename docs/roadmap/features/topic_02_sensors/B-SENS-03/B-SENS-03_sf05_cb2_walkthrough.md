# B-SENS-03 SF-05 CB-2 — Walkthrough

**Commit boundary:** CB-2 of 2 · **DAL-B** · 2026-08-26 · **Proves**: `FR-16`, `FR-17`. Closes
SF-05 · Plan: [sf05](B-SENS-03_sf05_implementation_plan.md)

## Delivered

`Chunk.is_line_window` — true when text was cut by lines rather than at a boundary the code has: an
unreadable file, **and** `FR-10`'s last resort (a symbol sliced at line 400 is no more a whole unit
than a blob). `_Cut.unreadable` carries the unreadable case; `len(pieces) > 1` cannot see a small
file no grammar handles.

**`FR-17` is two claims**: totality (non-whitespace) and verbatim-ness. The first does not imply the
second — a merge that dropped a blank run satisfied it while producing `... return 1clas s Beta:`.
Both are now stated **once per path** — preamble, merge, structure split, line fallback,
no-symbols, unparseable — at three budgets each. The `FR-17` tag moved off the two totality-only
files onto the one that states both (a tag is exhaustive).

## Proof

Three mutants were corrected before counting:

| Mutant | Verdict | What it was |
|---|---|---|
| `parser-failure-drops-file` | `UNMEASURED [symbol-drifted]` | anchored on `order = []`, rewritten here |
| `preamble-dropped` | `UNMEASURED [run-failed]` | the replacement was **not valid Python** |
| `the-trailing-remainder-is-dropped` | `UNPROTECTED [no-killer]` | **equivalent** — `if True:` makes every gap join the buffer and the final flush still emits it. Replaced with one where the final `run.flush()` never happens |

Four more anchors re-hashed.

| Check | Result |
|---|---|
| Full suite | **8,926 passed, 11 skipped** |
| `quality.py cb` | 15/15 · duplication none new |
| Corpus | **37 judged, 37 protected, 0 unprotected, 0 stale** |
| Ledger | `FR-15`, `FR-16`, `FR-17` carry a test file. Only `FR-12`, `FR-13`, `FR-14` remain — all SF-06 |
