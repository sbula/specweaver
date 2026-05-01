# Ontology Mapping Guide

To prevent contextual handoff failures between agents, all language-specific parsers MUST map their raw AST nodes into the **Universal Ontology** using the `OntologyMapper`.

## The Universal Ontology

### Nodes
- `FILE`: Physical file entity.
- `DATA_STRUCTURE`: Classes, Structs, Interfaces, ORM models.
- `PROCEDURE`: Functions, Methods, Lambdas.
- `STATE`: Global variables, Enums.
- `API_CONTRACT`: Cross-language boundaries (e.g., REST endpoints).
- `GHOST`: Unresolved third-party dependencies.

### Edges
- `CONTAINS`: Structural ownership (e.g. FILE contains DATA_STRUCTURE).
- `IMPORTS`: File A depends on File B.
- `CALLS`: Procedure A invokes Procedure B.
- `IMPLEMENTS`: Data Structure A fulfills Data Structure B.
- `CONSUMES`: Service A calls an `API_CONTRACT`.
- `FULFILLS`: Service B implements an `API_CONTRACT`.

## Handling Edge Cases

1. **Syntax Errors:** If the underlying parser detects syntax errors, the `OntologyMapper` must gracefully drop `ERROR` blocks rather than crashing the ingestion pipeline.
2. **API Contracts:** Ensure HTTP endpoints (e.g., `@GET`, `/api/`) are mapped to `API_CONTRACT` at the `APPLICATION` granularity level.
3. **Lazy Polyglot Edges:** When extracting imports, you often don't know the `target_id`. Map edges with `target_id = -1` and supply the raw import string in the metadata. The Engine will lazily resolve these "Dangling Edges" later.
