# Walkthrough: `B-SENS-03` SF-06 CB-2 — two views of the same file

- **Story**: `B-SENS-03` SF-06, commit boundary 2 of 3 · **DAL-B** · 2026-08-27
- **Proves**: `FR-12`

## What shipped

A **skeleton** chunk per reported symbol — its description and its signature, body gone — beside the
body layer that already existed. A hit on a body says how something works; a hit on a signature says
it exists and what it promises, and that is the question asked first.

**Per reported symbol, not per body chunk.** A class that fits is one body chunk and its methods are
none, but the skeleton layer still holds every method. That independence is what having two layers
is for, and `FR-12` says they split and merge separately.

**Skeletons never merge**, and a measurement decided it: 99 non-whitespace characters at the median,
so a 4,000 budget would hold about **forty**. Forty signatures in one chunk matches everything — the
low-discrimination problem that made `FR-6` per-symbol rather than per-file.

## `FR-17` binds the body layer, and 27 tests had to say so

A skeleton is a description and a signature **concatenated**, with the comment markers stripped. It
is not text the file contains and never could be. So both halves of `FR-17` — totality and
verbatim-ness — bind the body layer, which the design said **before** this was built rather than
after a red suite said it.

Twenty-seven existing tests asserted over *every* chunk. Each file's helper now filters to the body
layer with the reason inline, and one test says the exception out loud —
`test_a_skeleton_is_deliberately_not_a_slice` — so nobody later "fixes" it.

## The file grew past its ceiling, and the split was the honest fix

`check_file_sizes` blocked at **617 lines against a RED limit of 600**. `chunking.py` had grown three
jobs, so it became three files on those seams:

| | |
|---|---|
| `_sizing.py` | *how much is this, and cut it here* — pure functions of a string |
| `_scope.py` | *which boundary is this inside, and what may see it* — about the file and the estate |
| `chunking.py` | where the cuts fall |

498 lines now. **The gate found a real design smell rather than a formatting one**, and the seam it
forced is the one the module had grown anyway.

## A rename collided with a local, and mypy caught it

Renaming `_weight` to `weight` across the extracted file hit a **local variable** of the same name
inside the splitter — `weight = 0` then `weight(piece)`. mypy said `"int" not callable`; 115 tests
said it too. Renamed to `carried`.

## Mutants — three, all killed

| # | Neutralised | Objections |
|---|---|---|
| L1 | skeletons merge | 39 |
| L2 | the skeleton layer is never emitted | 5 |
| L3 | every chunk claims the body layer | 35 |

L3 is the subtle one: it changes **no content**, only the label — and without it `FR-17`'s totality
would silently bind the skeletons too.

**Six mutants were re-pointed into the new modules** and their hashes refreshed. The split moved
anchors for `FR-9`, `FR-10`, `FR-11` and `FR-14`; every one reported `symbol-drifted` rather than
passing on a stale anchor.

## Results

| Check | Result |
|---|---|
| Full suite | **8,959 passed, 11 skipped** |
| `quality.py cb` | 15/15 · `doc` 13/13 |
| file sizes · mypy · ruff · complexity · class health · duplication · conventions · tach | all clean |
| Corpus | **47 judged, 47 protected, 0 unprotected, 0 stale** |
| Ledger | `FR-12` and `FR-14` carry a test file. Only `FR-13` remains |

## Not done here

- The content hash — **CB-3**, and it must now cover `layer` as well
