# Implementation Plan: AST Semantic Chunking [SF-05: Nothing is lost]

- **Feature ID**: B-SENS-03
- **Sub-Feature**: SF-05 — Nothing is lost
- **Design Document**: docs/roadmap/features/topic_02_sensors/B-SENS-03/B-SENS-03_design.md
- **Design Section**: §Sub-Feature Breakdown → Group B → SF-05
- **Implementation Plan**: docs/roadmap/features/topic_02_sensors/B-SENS-03/B-SENS-03_sf05_implementation_plan.md
- **Status**: DRAFT
- **FRs**: FR-15, FR-16, FR-17 · **Depends on**: SF-04 ✅

## Research Notes

### Two forward references were removed from the design before planning

`FR-16` read *"flagged as a line window, **visibility `unknown`**"* and `FR-17` read *"lands in some
**body-layer** chunk"*. Neither field exists: visibility on a chunk is `FR-14` and layers are
`FR-12`, both in **SF-06**, which comes after this.

Tagging them as proven here would have meant a clause of each unbuilt — the conflation this story
has already hit four times, in the corpus twice, in the FR ledger, and in a mutant anchor. The
clauses moved to the FRs that create the fields `[agreed 2026-08-26]`, so each requirement is now
finishable by the sub-feature that owns it.

### A gap and a line window are indistinguishable today

Measured 2026-08-26:

| input | chunk |
|---|---|
| `"""Doc."""\nimport os\n\nCONST = 1` before the first `def` | `symbol='' symbols=()` |
| `<<<< %%% not code >>>>` — nothing parses | `symbol='' symbols=()` |

Identical. A consumer cannot rank a binary blob below real code, because nothing says which it is —
which is `FR-16`'s whole point.

### `FR-17` is largely delivered already, and its second half is the interesting one

`test_every_non_blank_character_survives` and `test_a_split_symbol_loses_no_lines` are tagged
`FR-17` since SF-04 CB-1, and `preamble-dropped` pins it in the corpus.

But SF-04 CB-4 found that **totality is not enough**: it compares non-whitespace characters, so a
merge that dropped the blank run between two symbols satisfied it while producing
`... return 1clas s Beta:` — a chunk whose content never existed in the file. The assertion that
catches that is **containment**, and it is now the second half of `FR-17` in the design.

That test lives in `test_chunking_merge.py`. This sub-feature owns the requirement, so it owns
stating the claim across **every** path — the structure split, the line fallback, the preamble —
not only the merge where it was found.

### What `Chunk` gains

`is_line_window: bool = False`. A bool rather than a `kind` string, deliberately: `FR-12` adds
`layer` in SF-06, and a second free-text axis invites two fields that disagree about the same chunk.

## Commit boundaries

### CB-1 — The preamble has a name (`FR-15`)

| Task | |
|---|---|
| 1 | The run of text **before the first symbol** is emitted with `symbol="<module>"` |
| 2 | Text **between** symbols stays unnamed `[agreed 2026-08-26]` — a stray mid-file comment is not the module's description |
| 3 | `symbols` for the preamble stays empty: `<module>` is a name, not a symbol the parser reported |

**Tier**: unit.

**Red first**: today the preamble is `symbol=''`, so it is indistinguishable from every other gap.

> **Expected mutants**: the preamble loses its name → the naming assertions object; **every** gap
> gains it → the mid-file assertion objects. Both are required, because one alone is satisfied by a
> rule that names everything or nothing.

### CB-2 — A line window says so, and nothing is lost anywhere (`FR-16`, `FR-17`)

| Task | |
|---|---|
| 1 | `Chunk.is_line_window`, set on the parser-failure path and on `FR-10`'s last-resort cut |
| 2 | Totality **and** verbatim-ness asserted across every path: structure split, merge, line fallback, preamble, unparseable |
| 3 | The `FR-17` tag moves onto the file that states the whole claim |

**Tier**: unit.

**Red first**: the flag does not exist, and no test asserts verbatim-ness outside the merge path.

> **Expected mutants**: the flag is never set → the parser-failure assertion objects; the flag is
> always set → the ordinary-chunk assertion objects.

**Is `FR-10`'s line cut a line window too?** Yes — it is the same fallback reached for a different
reason, and a consumer ranking by *"is this a whole unit"* needs both marked. Stated here because
the design's `FR-16` names only the unreadable file, and a reader would otherwise have to guess.

## Risks

| Risk | Mitigation |
|---|---|
| `<module>` collides with a real symbol name | Angle brackets are not a legal identifier in any of the eight languages. Asserted rather than assumed |
| The flag is set on the wrong path | Two mutants, both directions, and an assertion on an ordinary chunk |
| `FR-17` reads as proven while only the merge path is covered | CB-2's task 2 is the requirement: every path, one test |

## Not in this sub-feature

- Layers, content hash, visibility and scope on a chunk — **SF-06**
- The `unknown` visibility a line window will carry — `FR-14`, moved there today
