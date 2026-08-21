# Design: The Knowledge Graph Emits One of Its Nine Declared Edge Kinds

- **Feature ID**: TECH-068
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: 2026-08-21 benefit-chain follow-up. Measured while wiring graph consumers
  (`ADR-006`): `EdgeKind` declares nine kinds; the mapper writes one.

## Problem Statement

`B-SENS-02` is delivered as a "deep class/function-level semantic Knowledge Graph". Measured
2026-08-21, the delivered graph is a containment inventory:

- `graph/core/engine/ontology.py` declares nine edge kinds: `CONTAINS`, `IMPORTS`, `CALLS`,
  `IMPLEMENTS`, `EXTENDS`, `CONSUMES`, `FULFILLS`, `PUBLISHES`, `SUBSCRIBES`.
- `graph/core/builder/mapper.py:112` is the only `GraphEdge` construction site. It emits
  `CONTAINS` (file → symbol). No other kind is ever written.

Every planned reader of the graph needs dependency edges, not containment: blast radius needs
`CALLS`/`IMPORTS` closure (`B-EXEC-03`, `A-FLOW-04`, `C-FLOW-03` upgrade), context packing needs
caller/callee traversal (`B-SENS-09`), post-generation verification needs `CALLS`/`IMPLEMENTS`/
`EXTENDS` to detect broken dependents (`B-VAL-07`). With one edge kind, each traversal returns an
empty or trivial result and every consumer built on it would be green and useless.

This is a defect in delivered work: the registry claim ("semantic Knowledge Graph") is ahead of
the mechanism. Per `finished-stories-immutable`, the gap becomes this ticket, not an edit to
`B-SENS-02`'s closed scope.

## Candidate Approaches (not yet designed)

1. Extend the mapper to emit the **syntactic** kinds the AST can prove: `IMPORTS` (import
   statements), `CALLS` (call expressions resolved within the parsed set), `EXTENDS`/`IMPLEMENTS`
   (declaration clauses). Tree-sitter queries already exist per language in
   `workspace/ast/parsers/*/`; the work is resolution (symbol reference → node hash), not parsing.
2. Emit unresolved references as edges to `GHOST` nodes (the ontology already declares `GHOST`),
   so an unresolved callee is visible instead of silently dropped. A traversal can then tell
   "no callers" from "callers unknown".
3. Python-first with the polyglot seam explicit, following `TECH-061`'s shape.

## Non-Goals (proposed, pending design)

- Framework-semantic edges (`INJECTS`, routes, listeners) — `B-SENS-08`, sequenced behind this.
- `CONSUMES`/`FULFILLS`/`PUBLISHES`/`SUBSCRIBES` dataflow kinds — they need framework or dataflow
  analysis (`B-SENS-08`, `B-SENS-05`), not AST syntax.
- Any consumer of the edges. Readers are `B-SENS-09`, `B-VAL-07`, and the blast-radius seam
  owners. This ticket makes the graph true; it does not make it used.
- Dynamic dispatch resolution. A `CALLS` edge asserts a syntactic call site, nothing more —
  `ADR-006` records the graph-checked-not-guaranteed calibration for dynamic languages.

## Next Step

Run `specweaver-design` for TECH-068. Its first test: build the graph over a fixture package
where module A imports and calls module B; assert `IMPORTS` and `CALLS` edges exist with correct
direction — red today, because the mapper cannot emit them.
