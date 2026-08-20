# Design: AST Semantic Chunking

- **Feature ID**: B-SENS-03
- **Epic**: Topic 02 (Sensors)
- **Status**: 🔧 IN WORK — built and proven, **not approved**. The `specweaver-design`
  Phase 6 gate was never run for this capability. Status returns to ✅ only after that
  review and any corrections it produces.
- **DAL**: B (Severe failure)

## What shipped

`workspace/analyzers/chunking.py` splits a source file into units a developer would recognise —
one per top-level symbol, plus whatever belongs to no symbol — each carrying the file, symbol and
language it came from.

This is one of the two open items in `US-11`'s Core MVS (the other is `A-SENS-02`). The story's
benefit is recalling exact context from twenty interacting services without blowing up the context
window, and the unit of recall is what decides whether that works.

## Why not fixed-size windows

A fixed-size window cuts a function in half. Whichever half is retrieved is missing its signature
or its return, so the model is asked to reason about a fragment that never existed as code. AST
boundaries make every unit whole.

Origin metadata is the other half of the job. A retrieved fragment that cannot name its file and
symbol cannot be cited, and an agent that cannot cite cannot be checked.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | A chunk is a whole unit | System | Splits on symbol boundaries taken from the AST, and skips a symbol whose text has already been consumed by an enclosing one | Retrieval returns a function or class entire, never half of one, and never the same lines twice under two names |
| FR-2 | A chunk can be cited | System | Records path, symbol and language on every chunk | A hit names where it came from, so a claim built on it can be checked |
| FR-3 | An oversized symbol is split, not truncated | System | Breaks on line boundaries into numbered `part`/`parts` | A 2000-line function is still indexed in full, and a reader given part 2 of 3 can tell the unit continues |
| FR-4 | An unreadable file is still indexed | System | Falls back to line windows when the parser raises, under an empty symbol name | A missing grammar or a binary file does not silently vanish from the index, which a reader cannot tell apart from *this code does not exist* |
| FR-5 | Nothing is dropped | System | Emits the preamble and any trailing remainder as their own chunks | Imports and the module docstring — the part that says what the file depends on — reach the index with everything else |

Proof is by citation in the test files, read by `check_fr_coverage.py`.

## What the mutation pass corrected

Three guards survived their first mutants, meaning three tests were decoration:

- **Nested-symbol filtering** looked redundant, because Python's parser happens to list a class
  before its methods, and the remainder logic then skips the method anyway. It is not redundant:
  a parser listing `Beta.go` first would consume the method's text and cause the whole enclosing
  class to be skipped. A stub parser with hostile ordering now proves it.
- **The parser-failure fallback** was never reached. Tree-sitter is error-tolerant — handed
  nonsense it returns no symbols rather than raising — so the "unparseable source" test exercised
  the remainder path, not the `except`. Only a stub that genuinely raises reaches it.
- **The empty-input early return** was genuinely dead and was deleted rather than tested.

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface | Verified how |
|---|---|---|---|
| FR-1 | The symbols in a file | `B-SENS-02` · `CodeStructureInterface.list_symbols(code)` | read `src/specweaver/workspace/ast/parsers/_reading.py:222` — returns scoped names, so `Beta.go` arrives beside `Beta` |
| FR-1 | Each symbol's exact source | `B-SENS-02` · `CodeStructureInterface.extract_symbol(code, name)` | read `src/specweaver/workspace/ast/parsers/interfaces.py:52` |

Both are inside `workspace`, which `workspace.analyzers` already depends on, so no boundary moves.
The parser is passed in rather than resolved, so this feature consumes no factory and no language
table — which is what `NFR-1` asserts and a stub parser proves.

## Non-Functional Requirements

| # | NFR | Requirement |
|---|-----|-------------|
| NFR-1 | Polyglot | Depends only on `list_symbols` / `extract_symbol`, so every installed language tier is chunkable without per-language code |
| NFR-2 | Total | Every non-blank character of a file lands in some chunk |
| NFR-3 | Pure | Text in, chunks out — no I/O, no embedding, no storage |

## Non-Goals

- Embedding or vector storage. That is `A-SENS-02`, the other open item in `US-11`'s Core MVS.
- Retrieval scoring — `B-FLOW-04`.
- Choosing a chunk size for a specific model. `max_chars` is a parameter with a working default.
