# B-SENS-03 SF-06 — Every chunk is labelled

**Status**: DRAFT · **FRs owned**: FR-12, FR-13, FR-14 · **Depends on**: SF-01, SF-02, SF-03, SF-04
— all ✅ · Design: [B-SENS-03_design.md](B-SENS-03_design.md) §Sub-features → SF-06

## Goal

Every chunk carries what a consumer needs to place and filter a hit: scope (visibility, package,
unit), a layer (skeleton or body), and a content hash.

## Where it plugs in

| Fact | Where |
|---|---|
| `Chunk` carries `text · path · symbol · language · part · parts · symbols · is_line_window`. `FR-13`'s contained names and single scoped name landed in SF-04 CB-4; the **content hash** remains | `chunking.py` |
| `test_every_chunk_is_a_verbatim_slice_of_the_file` asserts over every chunk and fails on the first skeleton — a skeleton is doc + signature **concatenated**. So **both halves of `FR-17` bind the body layer**, written into the design before building | tests |
| `chunk_source` is pure and has no caller, so `markers` is optional | `chunking.py` |

921 symbols across 120 files in this repository:

| | median | mean | max | over the 4,000 budget |
|---|---|---|---|---|
| **skeleton** (`extract_symbol_signature`) | **99** non-ws chars | 148 | 1,563 | **0** |
| body (`extract_symbol`) | 357 | 714 | 15,607 | some |

**The skeleton layer never splits**, and a 4,000 budget would hold **~40 median skeletons** if they
merged — so they do not: 40 signatures in one chunk matches everything, the low-discrimination
problem that made `FR-6` per-symbol `[agreed 2026-08-26]`.

## Changes

### CB-1 — A chunk knows its scope (`FR-14`)

| Task | |
|---|---|
| 1 | `visibility`, `package`, `unit` on `Chunk` |
| 2 | `package` = the chunk's directory, from `path`. Pure |
| 3 | `unit` = the longest supplied marker directory that is a prefix of `path`, else `""` |
| 4 | `visibility` from `_levels`; `unknown` for gaps, the preamble, line windows, and whenever `_levels` cannot answer |
| 5 | `chunk_source(..., markers: frozenset[str] = frozenset())` |

Mutants: `unit` falls back to `package`; a merged chunk takes the first member's visibility rather
than the shared one (`FR-9`'s guard test passes either way, so it needs its own assertion).

### CB-2 — Two layers (`FR-12`)

| Task | |
|---|---|
| 1 | `layer: "skeleton" \| "body"` |
| 2 | One skeleton chunk per symbol, from `extract_symbol_signature`. **Never merged, never split** — max 1,563 against 4,000; the pathological case still goes through `_emit` |
| 3 | The preamble appears in **both** layers `[agreed 2026-08-26]` |
| 4 | `FR-17` binds the **body** layer, both halves; existing totality and verbatim tests narrowed with the reason inline |
| 5 | The parser contract grows a fourth call shape; the minimal stub says so |

Mutants: skeletons merge; the layer is never set (totality would then bind skeletons).

### CB-3 — A chunk can be identified (`FR-13`)

| Task | |
|---|---|
| 1 | `content_hash`: sha256 over the text **and every other label** |
| 2 | Every label, so a corrected visibility invalidates the row |
| 3 | The hash is not part of its own input — asserted |

Mutants, both required: the hash covers text only; the hash is constant (satisfies "same input,
same hash" alone).

## Tests

| Tier | File | Covers |
|---|---|---|
| Unit | `tests/unit/workspace/analyzers/test_chunking_scope.py` | `FR-14` |
| Unit | `tests/unit/workspace/analyzers/test_chunking_layers.py` | `FR-12`, `NFR-6` |
| Unit | `tests/unit/workspace/analyzers/test_chunking_identity.py` | `FR-13` |

## Decisions (audit)

| Decision | Why |
|---|---|
| The preamble is in both layers `[agreed 2026-08-26]` | It has no body to elide, so its skeleton is the same text. Skeletons rank first, and *"what is this file for"* would otherwise live only in the layer read second. Cost: one repeated chunk per file — the only text twice **within** the corpus rather than across layers by design |
| `unit` is `""` with no markers `[agreed 2026-08-26]` | Falling back to `package` claims a boundary the caller never established; *"is this outside my service?"* would be answered from a guess. Same reasoning as `unknown` visibility |

| Risk | Mitigation |
|---|---|
| The verbatim test fails on the first skeleton | Fixed in the design **before** CB-2 |
| Chunk count roughly doubles | Skeletons are 99 median characters, measured |
| A merged chunk's visibility taken from one member | Its own assertion in CB-1 |
| `package` from `path` on Windows | `PurePosixPath` is wrong and `Path` is platform-dependent; asserted on a POSIX and a Windows-style path |

Not here: anything that reads a chunk (`A-SENS-02`, `B-FLOW-04`); `NFR-8` — one parse per symbol,
359 ms for 200 symbols, a batch parser accessor in no FR.

## As built (2026-08-26/27)

| Where | What |
|---|---|
| `_unit_of` (since moved: `unit_of` in `_scope.py`) | iterates the marker paths **sorted** — frozenset order is hash-based, stable within a process but not across runs (`NFR-4`), and ties of equal length must resolve the same every day. The marker paths are sorted, not the directories |
| skeleton layer | one skeleton per **reported** symbol, not per body chunk: a class that fits is one body chunk and its methods none, but the skeleton layer holds every method |
| `analyzers/` split | `chunking.py` passed the 600-line RED limit (617), and became three files on its seams: `_sizing.py` (*how much is this, and cut it here*), `_scope.py` (*which boundary is this inside, and what may see it*), `chunking.py` (where the cuts fall, 498 lines). `_weight` → `weight` |
| `content_hash` | sha256 over all twelve other fields (text and every label), excluding itself; chunks are sealed on emit (`_sealed`) |

Walkthroughs: [cb1](B-SENS-03_sf06_cb1_walkthrough.md) · [cb2](B-SENS-03_sf06_cb2_walkthrough.md) ·
[cb3](B-SENS-03_sf06_cb3_walkthrough.md).
