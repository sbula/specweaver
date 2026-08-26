# Implementation Plan: AST Semantic Chunking [SF-06: Every chunk is labelled]

- **Feature ID**: B-SENS-03
- **Sub-Feature**: SF-06 — Every chunk is labelled
- **Design Document**: docs/roadmap/features/topic_02_sensors/B-SENS-03/B-SENS-03_design.md
- **Design Section**: §Sub-Feature Breakdown → Group B → SF-06
- **Implementation Plan**: docs/roadmap/features/topic_02_sensors/B-SENS-03/B-SENS-03_sf06_implementation_plan.md
- **Status**: DRAFT
- **FRs**: FR-12, FR-13, FR-14 · **Depends on**: SF-01, SF-02, SF-03, SF-04 — all ✅

## Research Notes

### Measured, and one number decided a requirement

921 symbols across 120 files in this repository:

| | median | mean | max | over the 4,000 budget |
|---|---|---|---|---|
| **skeleton** (`extract_symbol_signature`) | **99** non-ws chars | 148 | 1,563 | **0** |
| body (`extract_symbol`) | 357 | 714 | 15,607 | some |

**The skeleton layer never splits.** And a 4,000 budget would hold **~40 median skeletons** if they
merged — which is why they do not: 40 signatures in one chunk matches everything, the exact
low-discrimination problem that made `FR-6` per-symbol instead of per-file `[agreed 2026-08-26]`.

### What `Chunk` already carries, and what is left

`text · path · symbol · language · part · parts · symbols · is_line_window`

`FR-13`'s *contained names* and *scoped name when exactly one symbol is inside* landed in SF-04 CB-4,
because `FR-9` could not be honest without them. What remains is the **content hash**.

### `FR-17`'s second half needs the same qualifier its first half got

The design says `FR-12` narrows *totality* to the body layer. **It does not narrow verbatim-ness,
and it must**: a skeleton chunk is a doc and a signature **concatenated**, so it is not a slice of
the file at all. `test_every_chunk_is_a_verbatim_slice_of_the_file` asserts over every chunk today
and will fail on the first skeleton emitted.

That is the same forward-reference problem SF-05 fixed for the other clause, one clause over.
**Both halves of `FR-17` bind the body layer**, and the design says so before this is built.

### The preamble is in both layers, and it costs duplication

`[agreed 2026-08-26]`. It has no body to elide, so its skeleton is the same text. Duplicating it is
deliberate: skeletons are ranked first, and *"what is this file for"* would otherwise live only in
the layer read second. The cost is one repeated chunk per file, and it is the only text that appears
twice **within** the corpus rather than across layers by design.

### `unit` with no markers

`chunk_source` is pure and has no caller, so `markers` is optional. Absent, `unit` is `""` — *not
known* `[agreed 2026-08-26]`. Falling back to `package` would make every chunk claim a boundary the
caller never established, and a query asking *"is this outside my service?"* would be answered from
a guess. Same reasoning as `unknown` visibility.

## Commit boundaries

### CB-1 — A chunk knows its scope (`FR-14`)

| Task | |
|---|---|
| 1 | `visibility`, `package`, `unit` on `Chunk` |
| 2 | `package` = the chunk's directory, from `path`. Pure |
| 3 | `unit` = the longest supplied marker directory that is a prefix of `path`, else `""` |
| 4 | `visibility` from `_levels`; `unknown` for gaps, the preamble, line windows, and whenever `_levels` could not answer |
| 5 | `chunk_source(..., markers: frozenset[str] = frozenset())` |

**Tier**: unit. **Red first**: none of the three fields exists.

> **Expected mutants**: `unit` falls back to `package` → the no-markers assertion objects; a merged
> chunk takes the first member's visibility rather than the shared one → the guard's own test still
> passes, so this needs its own assertion on a merged chunk's `visibility`.

### CB-2 — Two layers (`FR-12`)

| Task | |
|---|---|
| 1 | `layer: "skeleton" \| "body"` |
| 2 | One skeleton chunk per symbol, from `extract_symbol_signature`. **Never merged, never split** — measured max 1,563 against 4,000, and the pathological case still goes through `_emit` |
| 3 | The preamble appears in **both** layers `[agreed 2026-08-26]` |
| 4 | `FR-17` binds the **body** layer — both halves. The existing totality and verbatim tests are narrowed, with the reason inline |
| 5 | The parser contract grows a fourth call shape; the minimal stub says so, as SF-04's did |

**Tier**: unit.

> **Expected mutants**: skeletons merge → the per-symbol assertion objects; the layer is never set →
> the body-only totality assertion objects, because it would then bind skeletons too.

### CB-3 — A chunk can be identified (`FR-13`)

| Task | |
|---|---|
| 1 | `content_hash`: sha256 over the text **and every other label** |
| 2 | Every label, so a corrected visibility invalidates the row rather than leaving a stale one |
| 3 | The hash is not part of its own input, and that is asserted |

**Tier**: unit.

> **Expected mutants**: the hash covers text only → the label-change assertion objects; the hash is
> constant → the different-text assertion objects. Both required: a constant hash satisfies "same
> input, same hash" on its own.

## Risks

| Risk | Mitigation |
|---|---|
| The verbatim test fails on the first skeleton | Named above and fixed in the design **before** CB-2 rather than during it |
| Chunk count roughly doubles | Skeletons are 99 median characters. Measured, not estimated |
| A merged chunk's visibility is taken from one member | Its own assertion in CB-1, because `FR-9`'s guard test passes either way |
| `package` from `path` on Windows | `PurePosixPath` is wrong and `Path` is platform-dependent. Asserted on a POSIX and a Windows-style path |

## Not in this sub-feature

- Anything that reads a chunk. `A-SENS-02` and `B-FLOW-04`
- `NFR-8` — one parse per symbol, measured at 359 ms for 200 symbols. A batch parser accessor, in no FR
