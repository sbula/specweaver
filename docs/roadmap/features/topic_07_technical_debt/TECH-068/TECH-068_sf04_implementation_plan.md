# Implementation Plan: The Knowledge Graph Emits One of Its Nine Declared Edge Kinds [SF-04: CALLS where the grammar already ships the query]

- **Feature ID**: TECH-068
- **Sub-Feature**: SF-04 — `CALLS` where the grammar already ships the query
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-068/TECH-068_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-04
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-068/TECH-068_sf04_implementation_plan.md
- **Status**: APPROVED (2026-08-22)

## Scope

`FR-1` (`extract_call_sites` on the contract), `FR-2` (from the grammar's `TAGS_QUERY`), `FR-7` (the
seam carries call sites), `FR-11` (`CALLS` edges) and `FR-13` (ambiguity becomes one ghost).
Depends on `SF-03`, which is committed.

## Research Notes

### The mechanism works, and works identically across all four languages

`TAGS_QUERY` is a module constant on each grammar package, so reading it is an import rather than
file I/O and `ast.parsers` stays `pure-logic`. Spiked against the real grammars:

```
python   calls found: ['helper']
rust     calls found: ['helper']
java     calls found: ['helper']
go       calls found: ['helper']
```

One generic implementation covers all four.

**`captures()` is the wrong API here.** The `name` capture is shared between the `@definition.*`
and `@reference.call` patterns, so `captures()` returns definition names mixed with call names and
nothing distinguishes them. `QueryCursor.matches()` keeps the per-match grouping, so a `name` can be
taken only from a match that also carries `reference.call`.

### The caller must be qualified, and the walk gives a bare name

Walking up from a call node to the enclosing `function_definition` yields `go`, while `list_symbols`
names the same symbol `Impl.go` — and the node hash is `hash_node(filepath, "Impl.go")`. Every
enclosing declaration name must be collected and joined, not just the nearest one, or a method's
calls attach to a node that does not exist.

### The index `SF-03` built holds types only

`_index_types` filters on `child.get("type") != "class_definition"` (`orchestrator.py:19`). A callee
is a procedure, so the index must grow to cover them.

### Bare-name resolution is better than it looks, and its failures are the right ones

Measured over this repository's own `src/`: **351 files, 2,677 symbols, 1,821 distinct bare names,
of which 1,588 (87%) are declared exactly once** and therefore resolve uniquely.

The collisions concentrate exactly where a guess would be worst:

| name | declarations |
|---|---|
| `__init__` | 131 |
| `name` | 28 |
| `check` | 26 |
| `execute` | 25 |
| `run` | 14 |

Under `FR-13` each of those becomes one ghost. **Every constructor call will ghost**, which is a
consequence of the ambiguity rule rather than a gap in it — special-casing `__init__` would mean
guessing which class was constructed, which is the guess `ADR-006` forbids of a truth store.

### Surfaces this plan touches

| Symbol | Signature as it exists | File |
|---|---|---|
| `_index_types` | `(parsed: dict[str, dict[str, Any]]) -> dict[str, set[str]]` | `graph/core/builder/orchestrator.py` |
| `_supertype_target` | `(self, name: str, symbol_index) -> str` — the shape a callee resolver mirrors | `graph/core/builder/mapper.py` |
| `_map_supertypes` | `(self, filepath, child, symbol_index, edges) -> None` | same |
| `extract_supertypes` | `(self, code: str) -> dict[str, dict[str, list[str]]]` — the contract shape a call extractor mirrors | `workspace/ast/parsers/interfaces.py` |
| `TAGS_QUERY` | module constant, `str` | each grammar package |

## Decision taken with the user at the Phase 4 gate

**Two indexes, one per kind.** A supertype resolves against types, a callee against procedures.
Symmetrical with what `SF-03` built, and more precise: a class named `run` never makes a method
named `run` ambiguous, so neither ghosts for the other's sake.

## Red/Blue findings, merged

- **A call outside any function belongs to the FILE.** Module-level code — a decorator argument, a
  constant built by calling something — has no enclosing declaration, so the walk returns nothing.
  The edge runs from the file's node rather than being dropped, or a whole class of real
  dependencies disappears.
- **A recursive call is a self-edge**, and must be emitted rather than filtered. A function calling
  itself is a real dependency and a traversal that silently drops it is wrong about the graph.
- **The procedure index needs the qualified name, not just the file.** A callee is written bare —
  `helper()` — but the node hash is `hash_node(filepath, "Impl.go")`. So the index maps a bare name
  to the set of `(file, qualified name)` pairs that declare it. The type index needs no such thing,
  which is a second reason not to share one structure.
- **Unresolved callees need their own ghost namespace.** `SF-03` separated modules from types after
  a mutant showed one prefix serving both; a procedure is a third kind of unknown, and reusing
  either prefix would report a missing function as a missing type.
- **The tags query is a second pass over each file.** Currently 4.7 ms/file; a rough doubling of the
  query work would put the reference workload near 18 s against `NFR-1`'s 60 s. Within budget, and
  `CB-4` re-measures rather than assuming.

## Commit Boundaries

### CB-1 — A parser reports call sites, attributed to their caller

**Proves**: `FR-1`, `FR-2`. **Tier**: unit per language, plus one integration test that every shipped
parser answers the contract — the set-level claim `SF-03` CB-1 found missing.

1. Red first: `extract_call_sites` does not exist. It must return each caller's qualified name mapped
   to the bare names it invokes, taking `name` only from matches carrying `reference.call`.
2. Enclosing declarations are collected and joined, so a method's calls attach to `Impl.go` rather
   than `go`. A call with no enclosing declaration is attributed to the file.

**Done when**: green, and mutants go red for `captures()` in place of `matches()`, and for the
nearest enclosing name used unqualified.

### CB-2 — The index covers procedures, beside the types

**Proves**: the prerequisite `FR-11` rests on. **Tier**: integration.

1. Red first: a procedure declared anywhere in the tree is findable before any edge is built, and a
   type of the same name does not make it ambiguous.

**Done when**: green, and mutants go red for the procedure index dropped, and for the two kinds
merged into one namespace.

### CB-3 — The seam carries call sites

**Proves**: `FR-7`. **Tier**: integration. Fills the `calls` field `SF-02` declared, so this fills
rather than reshapes.

**Done when**: green, and a mutant emptying the field goes red.

### CB-4 — `CALLS` edges, with ambiguity ghosted

**Proves**: `FR-11`, `FR-13`. **Tier**: integration.

1. Red first: a call to a uniquely-named procedure yields a `CALLS` edge to it; a call to a name
   declared twice yields exactly one ghost; a recursive call yields a self-edge; a module-level call
   runs from the file node.
2. `NFR-1` and `NFR-2` re-measured on a real build.

**Done when**: green, and mutants go red for no edges, the ghost fallback removed, ambiguity
resolved to a guess, and a self-edge filtered out.

## Test Plan

| Test | Tier | Proves | Goes red because |
|---|---|---|---|
| a call is attributed to its caller | unit | FR-1 | `extract_call_sites` does not exist |
| the caller is qualified | unit | FR-1 | the walk yields the nearest name only |
| all four languages report calls | unit | FR-2 | same |
| every shipped parser answers the contract | integration | FR-1 | the set is not covered by any one language's tests |
| a procedure is indexed | integration | CB-2 | the index holds types only |
| a type and a procedure of one name do not collide | integration | CB-2 | one namespace would ghost both |
| the seam carries calls | integration | FR-7 | the field is declared and empty |
| a unique callee becomes an edge | integration | FR-11 | nothing emits `CALLS` |
| a callee declared twice becomes one ghost | integration | FR-13 | a heuristic would pick one |
| a recursive call is a self-edge | integration | FR-11 | it would be dropped |
| a module-level call runs from the file | integration | FR-11 | it has no enclosing declaration |

Four buckets: happy path (a unique callee), boundary (recursion, module-level, a file with no calls),
graceful degradation (a callee outside the parsed set), hostile input (an ambiguous callee, an empty
callee name).

## Non-Goals

- `typescript`, `c`, `cpp`, `kotlin`. `SF-05` owns them, because their grammars ship no call query.
- Resolving a call through its receiver's type. A `CALLS` edge asserts a syntactic call site and
  nothing more, as the design's Non-Goals already record.
- Special-casing constructors so `__init__` resolves. Measured at 131 declarations here, it is the
  ambiguity rule working rather than a gap in it.
