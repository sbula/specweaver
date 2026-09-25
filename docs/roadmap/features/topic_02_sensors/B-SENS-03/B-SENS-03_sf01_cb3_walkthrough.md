# B-SENS-03 SF-01 CB-3 — Walkthrough

**Commit boundary:** CB-3 of 3 · **DAL-B** · 2026-08-26 · **Proves**: `FR-2`. Closes SF-01 · Plan:
[sf01](B-SENS-03_sf01_implementation_plan.md)

## Delivered

`_is_symbol_valid` reads the symbol's actual level and asks whether it was requested. It replaces a
`"public" in visibility` test under which `["private"]` returned the whole file — and one of the two
live callers passes whatever an agent typed.

**Nine copies of the filter became one**: the eight known overrides plus
`DeclarativeParser._is_symbol_valid`, which returned `True` unconditionally (*"Every declaration is
valid: there is no body whose shape could be wrong."*) and so disabled visibility and decorator
filtering for SQL and markdown.

Deltas, all measured:

| Language | Change |
|---|---|
| Python | `Store.__mangled` **left** the public set — and the `exposes:` list of every generated `context.yaml` |
| Java | `Shape.area`, `Shape.name` **joined** — interface members are implicitly public by the JLS |
| Rust | `name` (a trait member) **joined**; `Circle.crate_only` **left**, because `pub(crate)` is `internal` |
| TypeScript | `Circle.log` (protected) and `Circle.helper` (private) **left** |
| C | was **empty for every request**; now answers, because `unknown` counts as visible |
| SQL · markdown | a decorator filter returns nothing rather than everything |
| all ten | `["nonsense"]` → nothing · `[]` → no filter, where three different answers came from that one input |

The first five were agreed with the user. The last two are `FR-2` itself.

Kept: **C still raises** on a decorator filter (it refuses an answer it cannot give) and **Go still
answers `False`** (a claim about the language). Both moved to a `_matches_decorator` hook —
module-level functions bound with `staticmethod` — so no class gains a lone method or an LCOM4
component. `test_c_parser_raises_on_decorator_filter` guards it.

Rust dedup runs **before** the filter: `pub struct Circle` and `impl Circle` both yield a name node
and only the first carries visibility, so `Circle` had appeared under both `["public"]` and
`["private"]`. First occurrence wins — the rule `extract_symbol_visibility` and `_declared_names`
already use.

`code_structure_and_ast_editing.md` now says the tool checks the **path** only, and visibility is a
**relevance filter for information hiding, not a security boundary** — anyone who can read the file
can read its private symbols.

## Proof

`mutation.py --corpus`: **9 judged, 9 protected, 0 unprotected, 0 stale.** Old `FR-1` and `FR-3`
mutants **retired with a reason and a date** (design §Old FR numbers).

| Requirement | Mutants | Objections |
|---|---|---|
| `FR-1` | 4 — Go capitalisation, Java's container rule, Python's dunder column, Rust `pub(crate)` | 1–2 each |
| `FR-2` | 3 — admits everything, rejects everything, `unknown` stops counting | 88 · 93 · 23 |

| Check | Result |
|---|---|
| Full suite | **8,723 passed, 11 skipped** |
| `quality.py cb` | 15 of 15 · `doc` 13/13 · `mypy` clean across 352 files |
| Mutation corpus | 9 protected, 0 unprotected, 0 stale |

Duplication re-frozen: five reported clones are pre-existing `SCM_COMMENT_QUERY`, `_get_symbol_scope`
and `supported_intents` blocks re-keyed by pure deletions (`+n,0` hunks) between them — verified by
hunk headers; read in the full `check_duplication` output, not a `grep -A6 FAILED` excerpt.
