# B-SENS-03 SF-05 — Nothing is lost

**Status**: DRAFT · **FRs owned**: FR-15, FR-16, FR-17 · **Depends on**: SF-04 ✅ · Design:
[B-SENS-03_design.md](B-SENS-03_design.md) §Sub-features → SF-05

## Goal

The preamble gets a name, an unreadable file's line windows say so, and every chunk on every path is
both total and a verbatim slice of the file.

## Where it plugs in

| Fact | Where |
|---|---|
| A gap and a line window are indistinguishable: `"""Doc."""\nimport os\n\nCONST = 1` before the first `def` → `symbol='' symbols=()`; `<<<< %%% not code >>>>` (nothing parses) → `symbol='' symbols=()`. Measured 2026-08-26 | `chunk_source` |
| `FR-17` totality already tagged since SF-04 CB-1: `test_every_non_blank_character_survives`, `test_a_split_symbol_loses_no_lines`; `preamble-dropped` pins it in the corpus | tests |
| `FR-17`'s second half — **containment** (every chunk a verbatim slice) — lives only in `test_chunking_merge.py`, where it was found | tests |
| `Chunk` gains `is_line_window: bool = False` — a bool, not a `kind` string: `FR-12` adds `layer` in SF-06, and a second free-text axis invites two fields that disagree | `chunking.py` |

The design's `FR-16` (*"visibility `unknown`"*) and `FR-17` (*"body-layer chunk"*) clauses moved to
`FR-14` and `FR-12`, which create those fields in SF-06 `[agreed 2026-08-26]` — so each requirement
is finishable by its own sub-feature.

## Changes

### CB-1 — The preamble has a name (`FR-15`)

| Task | |
|---|---|
| 1 | The run of text **before the first symbol** is emitted with `symbol="<module>"` |
| 2 | Text **between** symbols stays unnamed `[agreed 2026-08-26]` — a stray mid-file comment is not the module's description |
| 3 | The preamble's `symbols` stays empty: `<module>` is a name, not a reported symbol |

Required mutants, both directions: the preamble loses its name; **every** gap gains it.

### CB-2 — A line window says so, nothing is lost anywhere (`FR-16`, `FR-17`)

| Task | |
|---|---|
| 1 | `Chunk.is_line_window`, set on the parser-failure path **and** on `FR-10`'s last-resort cut — the same fallback for a different reason; a consumer ranking by *"is this a whole unit"* needs both marked (the design's `FR-16` names only the unreadable file) |
| 2 | Totality **and** verbatim-ness asserted across every path: structure split, merge, line fallback, preamble, unparseable |
| 3 | The `FR-17` tag moves onto the file that states the whole claim |

Required mutants: the flag never set; the flag always set.

## Tests

| Tier | File | Covers |
|---|---|---|
| Unit | `tests/unit/workspace/analyzers/test_chunking_preamble.py` | `FR-15` |
| Unit | `tests/unit/workspace/analyzers/test_chunking_totality.py` | `FR-16`, `FR-17` — every path, three budgets each |

## Decisions (audit)

| Risk | Mitigation |
|---|---|
| `<module>` collides with a real symbol | Angle brackets are not a legal identifier in any of the eight languages; asserted |
| The flag is set on the wrong path | Two mutants, both directions, plus an assertion on an ordinary chunk |
| `FR-17` reads as proven while only the merge path is covered | CB-2 task 2: every path |

Not here: layers, content hash, visibility and scope on a chunk (SF-06); the `unknown` visibility a
line window carries (`FR-14`).

## As built (2026-08-26)

| Where | What |
|---|---|
| preamble | split out of `_walk`'s call; a file that does not parse has no first symbol, so no `<module>` — it gets `FR-16`'s line window |
| `_Cut.unreadable` | tracks an unreadable file from the one place that knows. `len(pieces) > 1` cannot: a small file no grammar handles arrives in one piece |
| tail | the final `run.flush()` emits the trailing remainder |

Walkthroughs: [cb1](B-SENS-03_sf05_cb1_walkthrough.md) · [cb2](B-SENS-03_sf05_cb2_walkthrough.md).
