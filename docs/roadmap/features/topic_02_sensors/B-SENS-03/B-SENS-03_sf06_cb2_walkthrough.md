# B-SENS-03 SF-06 CB-2 — Walkthrough

**Commit boundary:** CB-2 of 3 · **DAL-B** · 2026-08-27 · **Proves**: `FR-12` · Plan:
[sf06](B-SENS-03_sf06_implementation_plan.md)

## Delivered

A **skeleton** chunk per reported symbol — description and signature, body gone — beside the body
layer. A body hit says how something works; a signature hit says it exists and what it promises,
the question asked first.

- **Per reported symbol, not per body chunk**: a class that fits is one body chunk, but the skeleton
  layer holds every method. The layers split and merge separately.
- **Skeletons never merge**: median 99 non-whitespace characters, so a 4,000 budget would hold about
  **forty** — a chunk that matches everything.
- **`FR-17` binds the body layer**, both halves (a skeleton is concatenated, marker-stripped text,
  never a slice). Twenty-seven existing tests asserted over *every* chunk; each file's helper now
  filters to the body layer with the reason inline, and
  `test_a_skeleton_is_deliberately_not_a_slice` states the exception.
- `chunking.py` hit **617 lines against a RED limit of 600** in `check_file_sizes` and split on its
  three jobs:

| | |
|---|---|
| `_sizing.py` | *how much is this, and cut it here* — pure functions of a string |
| `_scope.py` | *which boundary is this inside, and what may see it* — about the file and the estate |
| `chunking.py` | where the cuts fall — 498 lines |

`_weight` became `weight`; the splitter's local of that name became `carried`.

## Proof

| # | Neutralised | Objections |
|---|---|---|
| L1 | skeletons merge | 39 |
| L2 | the skeleton layer is never emitted | 5 |
| L3 | every chunk claims the body layer | 35 |

L3 changes only the label — without it `FR-17`'s totality would silently bind the skeletons.

Six mutants re-pointed into the new modules (anchors for `FR-9`, `FR-10`, `FR-11`, `FR-14`), each
reported `symbol-drifted`.

| Check | Result |
|---|---|
| Full suite | **8,959 passed, 11 skipped** |
| `quality.py cb` | 15/15 · `doc` 13/13 |
| file sizes · mypy · ruff · complexity · class health · duplication · conventions · tach | all clean |
| Corpus | **47 judged, 47 protected, 0 unprotected, 0 stale** |
| Ledger | `FR-12` and `FR-14` carry a test file. Only `FR-13` remains |
