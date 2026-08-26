# Walkthrough: `B-SENS-03` SF-01 CB-3 — the filter cannot fail open

- **Story**: `B-SENS-03` SF-01, commit boundary 3 of 3 · **DAL-B** · 2026-08-26
- **Proves**: `FR-2`. Closes SF-01.

## What changed

`_is_symbol_valid` now reads the symbol's actual level and asks whether it was requested. The
version it replaces tested `"public" in visibility` and let every other value fall through to
`True` — so a request for `["private"]`, the safest-sounding one there is, returned the whole file.
One of the two live callers passes whatever an agent typed.

**Nine copies of that filter became one.** Eight were known. The ninth was not:
`DeclarativeParser._is_symbol_valid` returned `True` unconditionally, with the docstring *"Every
declaration is valid: there is no body whose shape could be wrong."* That is a statement about
**body shape**, and it silently disabled visibility and decorator filtering for SQL and markdown
along with it. A default written for one question answering three.

## The deltas, all measured

| Language | Change |
|---|---|
| Python | `Store.__mangled` **left** the public set — and with it, the `exposes:` list of every generated `context.yaml` |
| Java | `Shape.area`, `Shape.name` **joined** — interface members are implicitly public by the JLS |
| Rust | `name` (a trait member) **joined**; `Circle.crate_only` **left**, because `pub(crate)` is `internal` |
| TypeScript | `Circle.log` (protected) and `Circle.helper` (private) **left** |
| C | was **empty for every request**; now answers, because `unknown` counts as visible |
| SQL · markdown | a decorator filter now returns nothing rather than everything |
| all ten | `["nonsense"]` → nothing · `[]` → no filter, where three different answers came from that one input |

The first five were agreed with the user. The last two are `FR-2` itself: a filter that ignores what
it was asked is the defect, not a contract.

## What was deliberately kept

**C still raises** on a decorator filter, and **Go still answers `False`**. Both sat inside the
functions this boundary deletes. Neither is an accident: C refuses rather than return an answer it
cannot give, and Go's `False` is a claim about the language rather than an empty marker table. They
moved to a `_matches_decorator` hook — module-level functions bound with `staticmethod`, the shape
CB-2 established — so the class gains no lone method and no LCOM4 component.

Both were pinned in CB-1 by the Phase 2 gap analysis. Without those tests they would have gone
silently, and `test_c_parser_raises_on_decorator_filter` is what caught the moment they did.

## One real bug the tests found

Rust reported `Circle` under **both** `["public"]` and `["private"]`. `pub struct Circle` and
`impl Circle` both yield a name node, and only the first carries visibility — so `list_symbols` and
`extract_symbol_visibility` disagreed about the same symbol. Deduplication moved **before** the
filter rather than after it: first occurrence wins, which is the same rule `extract_symbol_visibility`
already used. That is exactly the drift `_declared_names` was introduced to prevent, arriving by a
route neither the design nor the plan predicted.

## Nine mutants, nine protected

`mutation.py --corpus` on the rewritten file: **9 judged, 9 protected, 0 unprotected, 0 stale.**

The CRITICAL finding from the design review is discharged here. `FR-1` and `FR-3` are **retired
with a reason and a date** — those numbers now mean different requirements, and left alone the
nightly would have gone on printing `B-SENS-03 FR-1 PASSED` for a claim nobody makes. `FR-4` and
`FR-5` stay live; they are re-keyed to `FR-16`/`FR-17` when SF-05 changes the code they pin.

| Requirement | Mutants | Objections |
|---|---|---|
| `FR-1` | 4 — Go capitalisation, Java's container rule, Python's dunder column, Rust `pub(crate)` | 1–2 each |
| `FR-2` | 3 — admits everything, rejects everything, `unknown` stops counting | 88 · 93 · 23 |

## Two ratchets, two different answers

**Duplication: re-frozen.** Five clones reported as new. Verified by hunk headers that every one of
this boundary's edits to those files is a **pure deletion** (`+n,0`) and **none of the five clone
regions was touched**: they are pre-existing `SCM_COMMENT_QUERY`, `_get_symbol_scope` and
`supported_intents` blocks, re-keyed because code between them was removed — the caveat the tool
prints itself.

**And a process failure worth recording.** I read that verdict through `grep -A6 FAILED`, which cut
the output before the `NEW duplication` section, and nearly re-froze without seeing it. That is the
second time in this sub-feature that a **summary** hid what the **full output** said. In CB-2 it was
class-health reporting an improvement while four counts rose. Same shape, twice, one day apart:
**read the whole output, not the first lines of it.**

## Results

| Check | Result |
|---|---|
| Full suite | **8,723 passed, 11 skipped** |
| `quality.py cb` | 15 of 15 · `doc` 13/13 · `mypy` clean across 352 files |
| Mutation corpus | 9 protected, 0 unprotected, 0 stale |

`mypy` also caught a class attribute — `SCM_FRAMEWORK_QUERY` — that the line-based deletion took
with it. Nothing in the test suite would have.

## Documentation corrected

`code_structure_and_ast_editing.md` claimed the tool *"bounds-checks the request against the Role
`FolderGrant` and target `visibility`"*. It checks the **path** and nothing else. The line is now
explicit that visibility is a **relevance filter for information hiding, not a security boundary** —
anyone who can read the file can read its private symbols.
