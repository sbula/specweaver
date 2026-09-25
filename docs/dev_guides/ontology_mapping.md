# Ontology Mapping

Use when: you write or change a language parser that feeds the graph. Every parser MUST map its raw
AST nodes into the **Universal Ontology** via `OntologyMapper`, so agents hand off context in one
vocabulary.

## Nodes

| Kind | Meaning |
|---|---|
| `FILE` | Physical file entity |
| `DATA_STRUCTURE` | Classes, Structs, Interfaces, ORM models |
| `PROCEDURE` | Functions, Methods, Lambdas |
| `STATE` | Global variables, Enums |
| `API_CONTRACT` | Cross-language boundaries (e.g. REST endpoints) |
| `MESSAGE_QUEUE` | A topic or queue a service publishes to or subscribes from |
| `GHOST` | A target outside what the build parsed: third-party dependency, unresolved or ambiguous name (see Unresolved targets) |

`SYSTEM`, `MICROSERVICE`, `MODULE` and `NAMESPACE` complete the eleven `NodeKind` declares.

## Edges

| Kind | Meaning |
|---|---|
| `CONTAINS` | Structural ownership (e.g. FILE contains DATA_STRUCTURE) |
| `IMPORTS` | File A depends on File B |
| `CALLS` | Procedure A invokes Procedure B |
| `IMPLEMENTS` | Data Structure A fulfills Data Structure B |
| `EXTENDS` | Data Structure A is built from Data Structure B (class extension) |
| `CONSUMES` | Service A calls an `API_CONTRACT` |
| `FULFILLS` | Service B implements an `API_CONTRACT` |
| `PUBLISHES` | Service A writes to a `MESSAGE_QUEUE` |
| `SUBSCRIBES` | Service A reads from a `MESSAGE_QUEUE` |

Source of truth: `graph/core/engine/ontology.py`; these tables mirror it. `TECH-068` builds the
first five from AST syntax. The last four need framework or dataflow analysis: `B-SENS-08`/`B-SENS-05`.

## Rules

1. **Every edge carries its kind explicitly.** `SqliteGraphRepository` refuses a kindless edge and
   never supplies one. The attribute has one name, `EDGE_KIND_ATTR`, imported by engine, store and
   loader. (Replaced: a silent `CALLS` default plus mismatched attribute names, which stored 108
   `CONTAINS` rows of a real build as `CALLS`.)
2. **Syntax errors:** `OntologyMapper` drops `ERROR` blocks; it never crashes the ingestion pipeline.
3. **API contracts:** map HTTP endpoints (e.g. `@GET`, `/api/`) to `API_CONTRACT` at the
   `APPLICATION` granularity level.

## Unresolved targets

An import, supertype or call often names nothing the build collected. Emit the edge anyway, to a
`GHOST` node. The store materialises a ghost for any edge whose target hash is not a known node.

Replaced: the `target_id = -1` "Dangling Edges" guidance (`TECH-068` `AD-4`). `GraphEdge` has no
integer ids and there is no lazy-resolution pass; `GHOST` is already a declared `NodeKind`.

- **Resolve before building edges.** `ingest_target` parses every collected file first, then indexes
  the symbols, so a name resolves the same whichever file the build reaches first. Resolution never
  reads the filesystem (`NFR-4`).
- **Ambiguous is unresolved.** A name declared in two files becomes a ghost, not a guess. `ADR-006`
  makes the graph the truth store; a visible unknown serves a reader better than an invented
  dependency.
- **One ghost namespace per kind.** A module `Foo`, a type `Foo` and a procedure `Foo` are three
  unknowns. One shared ghost would report a file's missing dependency as a type's missing parent.

## Known gap

`FR-12` says the ghost edge carries the unresolved raw name in its metadata. It does not: the name
survives only inside the one-way target hash, so a reader sees *that* a target is unresolved, not
*what* it was. `graph_edges` already has a metadata column; this is wiring, not design. Found by the
`TECH-068` retrospective pre-commit gate on 2026-08-22; open for the user to schedule.
