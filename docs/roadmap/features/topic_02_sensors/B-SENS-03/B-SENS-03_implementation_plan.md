# B-SENS-03 — AST Semantic Chunking

**FRs owned: FR-1, FR-2, FR-3, FR-4, FR-5.** Proof and mutants are tabulated in
`B-SENS-03_design.md`.

## Approach

One pure module, `workspace/analyzers/chunking.py`. It walks the symbols a parser reports,
partitions the source around each symbol's text, and emits what is left over as preamble and
remainder chunks. `workspace.analyzers` already depends on `workspace.ast.parsers`, so no
boundary moves.

The parser is passed in rather than resolved, so the module needs no factory, no file access and
no language table — and a stub parser can drive the branches a real one cannot reach.

## Order

Tests first, red before the code, per `ADR-005`.

1. `tests/unit/workspace/analyzers/test_semantic_chunking.py` against the real Python parser.
2. `chunking.py`.
3. Mutation pass — where three guards survived, and the tests were fixed rather than the mutants
   waved through. Stub parsers were added for hostile symbol ordering and for a parser that
   raises; the dead empty-input guard was deleted.

## Non-Goals

- Embeddings, storage, retrieval scoring.
- A language-specific chunking rule. If one is ever needed it belongs behind the parser interface,
  not in this module.
