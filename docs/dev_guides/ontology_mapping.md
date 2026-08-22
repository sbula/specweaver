# Ontology Mapping Guide

To prevent contextual handoff failures between agents, all language-specific parsers MUST map their raw AST nodes into the **Universal Ontology** using the `OntologyMapper`.

## The Universal Ontology

### Nodes
- `FILE`: Physical file entity.
- `DATA_STRUCTURE`: Classes, Structs, Interfaces, ORM models.
- `PROCEDURE`: Functions, Methods, Lambdas.
- `STATE`: Global variables, Enums.
- `API_CONTRACT`: Cross-language boundaries (e.g., REST endpoints).
- `MESSAGE_QUEUE`: A topic or queue a service publishes to or subscribes from.
- `GHOST`: A target outside what the build parsed — a third-party dependency, an unresolved name,
  or an ambiguous one. See "Unresolved targets" below.

`SYSTEM`, `MICROSERVICE`, `MODULE` and `NAMESPACE` complete the eleven `NodeKind` declares.

### Edges
- `CONTAINS`: Structural ownership (e.g. FILE contains DATA_STRUCTURE).
- `IMPORTS`: File A depends on File B.
- `CALLS`: Procedure A invokes Procedure B.
- `IMPLEMENTS`: Data Structure A fulfills Data Structure B.
- `EXTENDS`: Data Structure A is built from Data Structure B (class extension).
- `CONSUMES`: Service A calls an `API_CONTRACT`.
- `FULFILLS`: Service B implements an `API_CONTRACT`.
- `PUBLISHES`: Service A writes to a `MESSAGE_QUEUE`.
- `SUBSCRIBES`: Service A reads from a `MESSAGE_QUEUE`.

All nine are declared in `graph/core/engine/ontology.py`, which is the source of truth; this list
mirrors it. `TECH-068` builds the first five from AST syntax. The last four need framework or
dataflow analysis and are `B-SENS-08`/`B-SENS-05`'s work.

**Every edge carries its kind explicitly.** `SqliteGraphRepository` refuses an edge that does not —
it does not supply one. It used to default a kindless edge to `CALLS`, and because the engine wrote
the attribute under one name while the store read another, that default fired on **every edge ever
persisted**: measured on a real build, 108 rows stored as `CALLS`, every one of them a `CONTAINS`.
The attribute has one name now, `EDGE_KIND_ATTR`, imported by both sides and by the loader.

## Handling Edge Cases

1. **Syntax Errors:** If the underlying parser detects syntax errors, the `OntologyMapper` must gracefully drop `ERROR` blocks rather than crashing the ingestion pipeline.
2. **API Contracts:** Ensure HTTP endpoints (e.g., `@GET`, `/api/`) are mapped to `API_CONTRACT` at the `APPLICATION` granularity level.
3. **Unresolved targets:** When extracting imports, supertypes or calls, the target often names
   nothing the build collected. Emit the edge anyway, to a `GHOST` node.

   **This replaces the `target_id = -1` "Dangling Edges" guidance that stood here** (`TECH-068`
   `AD-4`). That mechanism describes something the model cannot express: `GraphEdge` has no integer
   ids and no lazy-resolution pass exists. `GHOST` is already a declared `NodeKind`, and the store
   materialises a ghost automatically for any edge whose target hash is not a known node.

   Resolution happens **before** any edge is built, not after: `ingest_target` parses every
   collected file first, then indexes the symbols, so a name resolves the same way whichever file
   the build reaches first. Resolution never reads the filesystem (`NFR-4`).

   **Ambiguous is unresolved.** A name declared in two files is not one thing, so it becomes a
   ghost rather than a guess — `ADR-006` makes the graph the truth store, and a reader following an
   invented dependency is worse served than one seeing a visible unknown.

   **Ghost namespaces are separate per kind.** A module named `Foo`, a type named `Foo` and a
   procedure named `Foo` are three different unknowns; one ghost for all three would report a
   file's missing dependency as a type's missing parent.

   > **Known gap.** `FR-12` says the ghost edge carries the unresolved raw name in its metadata.
   > It does not — the name survives only inside the target hash, which is one-way, so a reader can
   > see *that* a target is unresolved but not *what* it was. `graph_edges` already has a metadata
   > column, so this is wiring rather than design. Found by the `TECH-068` retrospective
   > pre-commit gate on 2026-08-22 and left open for the user to schedule.
