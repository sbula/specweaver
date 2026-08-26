# task.md — B-SENS-03 SF-02, CB-1: `extract_symbol_doc`

**Plan**: `docs/roadmap/features/topic_02_sensors/B-SENS-03/B-SENS-03_sf02_implementation_plan.md`
**Boundary**: CB-1 of 2 · **FR-5** · **Tier**: unit (one module, no seam)

## Test matrix

| Bucket | Story |
|---|---|
| **Happy path** | One documented symbol per language, all ten · a **stacked** doc block (`///` ×2, `//` ×2) returned whole, in source order |
| **Boundary/edge** | A symbol with no doc → `""` · an empty file · an empty doc comment `/** */` → `""` · a doc whose text contains `*` and `/` survives stripping · C and C++ at depth 1 |
| **Graceful degradation** | Unparseable source → `""`, never a raise · SQL (empty comment query) → `""` · markdown (`html_block`, which does not contain the word `comment`) → `""` |
| **Hostile** | **A comment separated by a blank line must NOT attach** · a name not in the file · an empty name · a doc that is only markers |

**Used in sequence?** Not yet — `FR-6` composes it in CB-2, and that is where the pair is asserted.
**Anything else doing this job?** `extract_traceability_tags` reads comments, but by whole-file
query with no attachment. Different claim, and it must keep working: it is in the regression set.

## Tasks

- [x] **T1** — Red. `tests/unit/workspace/ast/parsers/test_symbol_docs.py`, every bucket above.
- [x] **T2** — `_docs.py`: collect consecutive preceding comment siblings (type contains `comment`),
      reject on a line gap, strip leading markers per line.
- [x] **T3** — `extract_symbol_doc` on the mixin → hook `_doc_of(name_node)`; `_DOC_DEPTH = 0`.
- [x] **T4** — `_DOC_DEPTH = 1` on C and C++. **Python overrides the hook**, not the depth.
- [x] **T5** — Abstract method on `CodeStructureInterface` + the `CompleteParser` stub
      (`test_parsers_interfaces.py`). SF-01 CB-2 was broken by exactly this and found it via a red
      suite; here it is a task.
- [x] **T6** — Mutants. Both required:
      | # | Neutralised | Must be objected to by |
      |---|---|---|
      | M1 | the line-gap check always passes | the blank-line case |
      | M2 | the marker stripping is skipped | the marker-free assertions |

## Pre-commit phases

- [x] P1 architecture · [ ] P2 test gap (HITL) · [ ] P3 implement (HITL)
- [x] P4 suite · [ ] P5 quality · [ ] P6 docs · [ ] P7 walkthrough · [ ] P7.5 red/blue (HITL)

## CB-1 done — and the plan's design was wrong

`_DOC_DEPTH` (a per-language depth) passed every method-level test and failed four of eight
type-level ones the moment the Phase 2 gap analysis added them. Replaced by: **climb to the
outermost ancestor starting on the same row.** C needs one extra level for a function and none for
a struct, which no fixed depth can express.

6 mutants, 6 kills. M4 (Python's docstring reader) has a single point of protection.
Record: `B-SENS-03_sf02_cb1_walkthrough.md`
