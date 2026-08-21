# Implementation Plan: The Knowledge Graph Emits One of Its Nine Declared Edge Kinds [SF-02: The seam carries dependencies, and IMPORTS lands through it]

- **Feature ID**: TECH-068
- **Sub-Feature**: SF-02 — The seam carries dependencies, and `IMPORTS` lands through it
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-068/TECH-068_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-068/TECH-068_sf02_implementation_plan.md
- **Status**: APPROVED (2026-08-21)

## Scope

`FR-5` (the seam carries imports), `FR-8` (`IMPORTS` edges), `FR-12` (`GHOST` for unresolved) and
`FR-15` (unparsed files are visible). Depends on `SF-01`, which is committed.

## Research Notes

### The mapper sees one file, so resolution needs the collected set handed to it

`OntologyMapper.map_ast_to_nodes(filepath, ast_data)` receives a single path. It has no view of what
else was collected, so it cannot turn an imported module into a file node on its own.

`SemanticHasher.hash_file(filepath)` is a **pure function of the normalised path** —
`sha256(f"FILE:{norm_path}")` — so once a module resolves to a collected path, the target hash is
derivable with no filesystem access at all. `NFR-4` is satisfiable; what is missing is the set, not
the purity.

`GraphBuilder.collect_files(target_path)` already produces exactly that set.

### Six languages, six import shapes — measured, not assumed

| Language | Source | `extract_imports` returns |
|---|---|---|
| Python | `import a.b` / `from a.b import C` | `['a.b']` |
| Rust | `use crate::alpha::beta;` | `['crate::alpha::beta']` |
| Go | `import ("fmt" "github.com/x/y/z")` | `['fmt', 'github.com/x/y/z']` |
| TypeScript | `import {A} from "./local"` | `['./local']` |
| Kotlin / Java | `import com.acme.Thing` | `['com.acme.Thing']` |

Three separator conventions (`.`, `::`, `/`), a relative form (`./`), and identifiers that map to no
local file at all (`os`, `std::collections`, `fmt`, `github.com/x/y/z`). Java and Kotlin name the
**class**, not the module. The design's "every language uniformly" decision settled which edge
*kinds* are in scope; it never settled how a module string becomes a file, and these do not share
one rule.

### `extract_imports` is wrong for every Python relative import

Measured:

```
from . import sibling     -> ['sibling']   coincidentally the module
from .sibling import X    -> ['X']         WRONG — the module is .sibling
from ..pkg.mod import Y   -> ['Y']         WRONG — the module is ..pkg.mod
```

Absolute imports are correct. Relative ones return the imported **symbol** instead of the module,
because the query captures `import_from_statement` and the extraction takes the wrong child.

**This repo's own `src/` has 27 relative imports**, including
`sandbox/execution/executor.py`. It is a live defect, not a hypothetical one.

`FR-5` and `FR-8` rest directly on this: an import that reports a symbol name resolves to nothing and
becomes a `GHOST`, so a real dependency would read as an unknown one.

**It has consumers beyond this ticket.** `workspace/analyzers/factory.py` feeds
`workspace/context/inferrer.py` and `assurance/graph/hasher.py`, so topology inference has been
reading the same wrong values.

### Surfaces this plan touches

| Symbol | Signature as it exists | File |
|---|---|---|
| `map_ast_to_nodes` | `(self, filepath: str, ast_data: dict[str, Any])` | `graph/core/builder/mapper.py` |
| `collect_files` | `(self, target_path: Path) -> set[str]` | `graph/core/builder/orchestrator.py` |
| `hash_file` | `(self, filepath: str) -> str`, pure over the normalised path | `graph/core/engine/hashing.py` |
| `extract_ast_dict` | `(filepath: str) -> dict[str, Any]` | `workspace/ast/adapters/graph_adapter.py` |
| `extract_imports` | `(self, code: str) -> list[str]` | `workspace/ast/parsers/interfaces.py` |

## Decisions taken with the user at the Phase 4 gate

1. **Resolution is one language-agnostic rule.** Split an import on any of `.`, `::` or `/` and
   suffix-match the trailing segments against the collected file paths. No unique match becomes a
   `GHOST`. Works for python, kotlin, java and rust; go and typescript identifiers are module paths
   needing `go.mod` or `tsconfig.json`, which `graph/` may not read, so those `GHOST` — visibly
   rather than silently. Per-language resolvers are separate work.
2. **An import matching more than one collected file becomes a `GHOST`**, the same rule `FR-13`
   sets for calls. `ADR-006` makes the graph the truth store, and a wrong `IMPORTS` edge is worse
   than a visible unknown: a blast-radius reader would follow a dependency that does not exist.
3. **The relative-import defect is fixed here**, because `FR-5` and `FR-8` rest on it.

## Red/Blue findings, merged

- **A package resolves through its `__init__`.** Suffix-matching `a.b` against `a/b.<ext>` alone
  misses `a/b/__init__.<ext>`. This repo has only five such files, but a target project that uses
  packages conventionally is full of them. The rule tries both forms.
- **Matching is case-insensitive**, because `normalize_path` lowercases before hashing (RT-21) and
  `NFR-8` already records that two files differing only in case share a node. A case-sensitive match
  here would disagree with the hash it is about to compute.
- **`extract_ast_dict` has six paths that return an empty tree** — missing file, symlink, no parser,
  read failure, parser exception, and the ordinary end. `FR-15` must separate *could not read* from
  *read, nothing in it*, and the current shape cannot. Only the read failure and the parser
  exception are marked: `collect_files` filters to parseable suffixes, so "no parser" cannot occur
  on the normal path, and a skipped symlink is a deliberate exclusion rather than a failure.
- **A build that calls `ingest_file` outside `ingest_target` has no collected set**, so every import
  `GHOST`s. That is correct, and stated so nobody reads it as a bug later.

## Commit Boundaries

### CB-1 — A relative import reports its module

**Proves**: a correction `FR-5` depends on. **Tier**: unit for the parser, plus one integration test
at the `workspace/analyzers` seam, because topology inference consumes the same values.

1. Red first: `from .sibling import X` must report `.sibling`, and `from ..pkg.mod import Y` must
   report `..pkg.mod`. Both report the imported symbol today.
2. Take the module child of `import_from_statement` rather than the imported name.

**Done when**: green, and a mutant reverting to the imported name goes red at both tiers.

### CB-2 — The seam carries what the mapper needs

**Proves**: `FR-5`. **Tier**: integration — the claim spans `workspace/ast/adapters` and
`graph/core/builder`.

1. Red first: assert `extract_ast_dict` reports a file's imports. It reports none today.
2. Widen the returned structure once, declaring imports, supertypes and call sites together per
   `AD-1`, populating only imports here.

**Done when**: green, and a mutant dropping imports from the payload goes red.

### CB-3 — `IMPORTS` edges, and `GHOST` where the target is not ours

**Proves**: `FR-8`, `FR-12`. **Tier**: integration.

1. Red first: build over a fixture package where `a` imports `b`; assert an `IMPORTS` edge from
   `a`'s file node to `b`'s file node, that `import os` becomes a `GHOST`, and that an import
   matching two collected files becomes a `GHOST` rather than either of them.
2. Hand `collect_files`' output to the mapper; resolve by suffix, trying both `a/b.<ext>` and
   `a/b/__init__.<ext>`, case-insensitively; emit.

**Done when**: green, and three mutants go red — resolution disabled, the `GHOST` fallback removed,
and ambiguity resolved to the first match instead of a `GHOST`.

### CB-4 — An unparsed file is visible

**Proves**: `FR-15`. **Tier**: integration.

1. Red first: a file whose read or parse fails is marked on its node; today the adapter returns an
   empty tree and the build is silent, so "no symbols" and "never read" are indistinguishable.

**Done when**: green, and a mutant dropping the marking goes red.

## Test Plan

| Test | Tier | Proves | Goes red because |
|---|---|---|---|
| a relative import reports its module | unit | CB-1 | it reports the imported symbol |
| topology inference sees the corrected module | integration | CB-1 | same defect, one seam further out |
| the seam carries imports | integration | FR-5 | the payload has no imports field |
| `a` imports `b` yields an `IMPORTS` edge | integration | FR-8 | nothing emits `IMPORTS` |
| a package resolves through `__init__` | integration | FR-8 | the plain suffix would miss it |
| `import os` becomes a `GHOST` | integration | FR-12 | nothing emits `GHOST` for imports |
| an ambiguous import becomes one `GHOST` | integration | FR-12 | a heuristic would pick one |
| a file that cannot be read is marked | integration | FR-15 | the build is silent |

Four buckets: happy path (a resolves to b), boundary (package `__init__`, a file importing itself,
an empty import list), graceful degradation (unreadable file, no collected set), hostile input (an
import string that is empty, or one matching many files).

## Non-Goals

- Any edge kind but `IMPORTS`. `SF-03` and `SF-04` own the rest.
- Resolving an import to a **symbol** inside the target file. `IMPORTS` is file to file.
- Go module or TypeScript path-mapping resolution against `go.mod` / `tsconfig.json`.
- Per-language resolvers. Decision 1 records the single rule and what it does not reach.
