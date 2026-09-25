# B-SENS-03 SF-01 CB-2 — Walkthrough

**Commit boundary:** CB-2 of 3 · **DAL-B** · 2026-08-26 · **Proves**: `FR-1` (the vocabulary),
`FR-3` (TypeScript's two axes), `FR-4` (Go has no private) · Plan:
[sf01](B-SENS-03_sf01_implementation_plan.md)

## Delivered

`extract_symbol_visibility(code, symbol_name) -> Visibility` on every parser, answering one of
`VISIBILITY = ("public", "protected", "internal", "private", "unknown")`, plus a `Literal` alias so
mypy rejects a typo. Behind it a per-language `_visibility_of(name_node)`; **nothing consumes it
yet** — `list_symbols` untouched, so CB-1's net stayed green.

The mapping is the plan's CB-2 table. The two rows that carry the reasoning:

- **Go has no `private`.** Lowercase is package-visible, so `internal`.
- **A member with no modifier takes its container's rule.** Java and Rust read "no modifier" as
  hidden — right for a class, wrong for an interface or trait. That one confusion was why every
  Java interface method and every Rust trait method was missing from the public set.

Rules are module-level functions in `_visibility.py` (a rule is a pure function of one AST node);
each parser binds `_get_symbol_visibility = staticmethod(_visibility_of)`, the shape
`grammar = staticmethod(...)` already used. All 22 classes within `check_class_health` limits, none
incohesive (LCOM4). A shared keyword scan brings TypeScript's mapping from 17 to under the ceiling
of 15 and removes the duplication.

Duplication re-frozen deliberately: five clones across sibling parser modules — four import
headers, one per-parser `supported_intents` declaration, one pre-existing code re-keyed by the
edit. Ten sibling modules importing the same infrastructure is the shape, not a defect.

## Proof

Red in three stages: **collection** (`VISIBILITY` did not exist), **125 errors** (a new abstract
method), **46 value assertions** once the base hook returned `unknown` — the stage that shows each
assertion discriminates.

| # | Neutralised | Objections |
|---|---|---|
| M1 | Go's capitalisation test | 2 |
| M2 | Java's interface rule | 2 |
| M3 | Rust's `pub(crate)` detection | **1** |
| M4 | Python's dunder-versus-mangled distinction | **1** |
| M5 | TypeScript's member accessibility | 2 |
| M6 | the shared keyword scan | 11 |

| Check | Result |
|---|---|
| Full suite | **8,652 passed, 11 skipped** in 84 s |
| `quality.py cb` | **15 of 15** |
| `mypy` | clean across 23 parser files |
| New tests | 137 |

## Findings still open

- **M3 and M4 have a single point of protection each** — one skipped or renamed test from none, on
  behaviours the user decided explicitly.
