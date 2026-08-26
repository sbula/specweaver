# task.md — B-SENS-03 SF-01, CB-1: the net

**Plan**: `docs/roadmap/features/topic_02_sensors/B-SENS-03/B-SENS-03_sf01_implementation_plan.md`
**Boundary**: CB-1 of 3 · **FRs**: none directly — this boundary serves **NFR-5**
**Goal**: capture what all ten parsers return **today**, so CB-3's change is a readable diff.

## Why this boundary has no red

`NFR-5` is a **must-not-change** requirement. The only way to prove "did not change" is to capture
before and compare after, so these tests are green on their first run **by design**. That is not a
vacuous test — it is a regression net, and its ability to fail is proved by **probe**, not by red
(dev skill 3.2b). **CB-1 is not finished until every probe kills it.**

## Test matrix

| Bucket | Story |
|---|---|
| **Happy path** | Each of the ten parsers, a real fixture: exact `list_symbols(code)` and exact `list_symbols(code, visibility=["public"])` |
| **Boundary/edge** | Empty string · whitespace only · a file with imports and no symbols · `visibility=[]` (falsy — today means *no filter*) |
| **Graceful degradation** | Source tree-sitter cannot parse · a parser whose `supported_parameters()` omits `visibility` (C, SQL, markdown) |
| **Hostile** | `visibility=["nonsense"]` — **today returns the whole file**, which is the fail-open itself · `["public","nonsense"]` · a symbol whose `name_node` is `None` |

**Used in sequence?** Yes — `list_symbols` → `extract_public_symbols` → `ContextInferrer` → the
`exposes:` list in a generated `context.yaml`. A unit test of either end is not a test of the pair,
so **T2 is integration**.

**Does anything else do this job?** Yes — four parsers carry their own filter. Asserting they
*agree* is CB-3's job (the structural invariant widens from four parsers to ten); CB-1 captures each
separately so the diff shows which one moved.

## Tasks

- [x] **T1** — Characterization, all ten parsers.
  - test: `tests/unit/workspace/ast/parsers/test_visibility_vocabulary.py` (new)
  - src: none
  - Each fixture **must carry the shape whose delta this plan predicts**, or the net cannot show it:
    Python `__dunder__` + `__mangled` + `_leading` · Java `interface` · Rust `pub trait` (required
    **and** defaulted method) · TypeScript exported class with `private`/`protected` members · Go
    lowercase · C `static` · C++ class vs struct defaults · SQL `schema.table` · markdown headings.

- [x] **T2** — The seam, pinned exactly.
  - test: `tests/integration/workspace/context/test_exposes_seam.py` (new)
  - src: none
  - `tests/integration/workspace/context/test_scan_and_infer.py:50` already walks this seam, but
    asserts with `in` / `not in`, so it cannot see a set change. T2 asserts the **exact** `exposes`
    list, over its **own `tmp_path` project** — the shared `sample_project` fixture is left alone so
    nothing else moves under it.

- [x] **T3** — Probes. **One per filter path, not one in total.**
  - `_reading.py` covers only the four shared parsers. C, C++, Go and Python each carry their own.
  - | # | File | `--old` | `--new` |
    |---|---|---|---|
    | P1 | `_reading.py` | `and "public" in visibility` | `and False` |
    | P2 | `python/codestructure.py` | `and "public" in visibility` | `and False` |
    | P3 | `go/codestructure.py` | `if visibility and "public" in visibility:` | `if False:` |
    | P4 | `c/codestructure.py` | `return visibility is None` | `return True` |
    | P5 | `cpp/codestructure.py` | *(its `_is_symbol_valid` visibility branch)* | neutralised |
  - **Done when**: T1 (and T2 for P2) appear in the objectors list for **every** probe. A probe
    nothing kills means the net has a hole over that parser, and CB-1 is not finished.

## Pre-commit phases

- [x] Phase 1 architecture · [ ] Phase 2 test gap (HITL) · [ ] Phase 3 implement (HITL)
- [x] Phase 4 suite · [ ] Phase 5 quality · [ ] Phase 6 docs · [ ] Phase 7 walkthrough · [ ] Phase 7.5 red/blue (HITL)

## T3 results — 2026-08-26, all five killed

| Probe | File | Objections | Named this net |
|---|---|---|---|
| P1 | `_reading.py` | 52 | `test_public_only_listing[java\|kotlin\|rust\|typescript]` |
| P2 | `python/codestructure.py` | 53 | `test_public_only_listing[python]` **and 3 of `test_exposes_seam.py`** |
| P3 | `go/codestructure.py` | 48 | `test_public_only_listing[go]` |
| P4 | `c/codestructure.py` | 52 | 5 tests, including all three `FailsOpen` rows for C |
| P5 | `cpp/codestructure.py` | 54 | 6 tests, including all four `CppAlreadyDoesItRight` rows |

**P1 does not name markdown or SQL, and that is correct** — neither hides anything, so the shared
filter's branch cannot change their answer. There is no behaviour there to protect.

**P2 is the one that mattered.** It is the only probe that reaches the integration test, which is
the proof that the seam into `context.yaml` is genuinely covered rather than assumed.

## CB-1 complete. CB-2 below.

## Phase 2 gap, closed — 2026-08-26

`_is_symbol_valid` answers **two** questions, and CB-3 deletes four copies of it. The decorator half
was pinned nowhere. Added 21 assertions and three probes:

| Probe | Neutralised | Objections | Named |
|---|---|---|---|
| P6 | Go's `return False  # Go does not have decorators` | 48 | 2 |
| P7 | C's `raise CodeStructureError(...)` | 48 | 1 |
| P8 | `if not any(decorator_filter in d ...)` in `_reading.py` | 67 | 7 |

**Eight probes, eight kills.** Every branch of `_is_symbol_valid` that CB-3 touches is now held.

---

# CB-2 — visibility becomes a value  ✅

- [x] `VISIBILITY` + `Visibility` in `interfaces.py`
- [x] static `_get_symbol_visibility` hook on the mixin, default `unknown`
- [x] per-language `_visibility_of`, all ten
- [x] C++ returns checked against the vocabulary
- [x] 6 mutants, 6 kills (M3, M4 single point of protection)
- [x] class-health regression caught and fixed by restructure, NOT by re-freezing

Record: `B-SENS-03_sf01_cb2_walkthrough.md`

---

# CB-3 — the filter consumes the value  ✅  SF-01 COMPLETE

- [x] one filter for all ten; **nine** copies removed, not eight (the declarative tier had a ninth)
- [x] C's raise and Go's declared `False` preserved via a `_matches_decorator` hook
- [x] dedup moved before the filter — Rust reported `Circle` as both public and private
- [x] CB-1's net updated: five agreed deltas + two `FR-2` consequences, each with its decision
- [x] `test_symbol_filtering.py` widened from four parsers to ten
- [x] dev guide's false security claim corrected
- [x] corpus: FR-1 and FR-3 retired with reasons; FR-1/FR-2 campaigns added — 9 protected, 0 stale
