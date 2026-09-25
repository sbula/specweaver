# D-SENS-03 — Polyglot Expansion

**Status**: **COMPLETED** (SF-01..SF-05 implemented; tracker below) · **Feature ID**: 3.32e

| | |
|---|---|
| Extends | `workspace/ast/parsers` (`CodeStructureInterface`, `factory.py` registry) |
| Used by | `CodeStructureAtom`; Phase 3.30 (Macro Evaluator); Phase 3.32a (Context Condensation) |
| Not touched | SQL dialects (pgSQL, T-SQL) |

## What it does

Adds Tree-sitter AST parsers for C/C++, Go and Standard SQL (systems, cloud-native, DB context) to
`workspace/ast/parsers`, each implementing `CodeStructureInterface` with a standard Tree-sitter
grammar. Registers them in `factory.py` for `CodeStructureAtom`. Constraints: Tree-sitter only,
standard grammars only, ANSI Standard SQL — no dialects.

## Why a shared base class first

SpecWeaver already supported Python, Java, Kotlin, TypeScript, Rust and Markdown, each implementing
`CodeStructureInterface` on its own. Their text manipulation (`extract_skeleton`, `extract_symbol`,
`replace_symbol`, `delete_symbol`, `list_symbols`) was nearly identical — `PythonCodeStructure` alone
was 432 lines. The real differences are the Tree-sitter `Language` binding and the `.scm` (Scheme)
query strings.

So SF-01 extracts `BaseTreeSitterParser(CodeStructureInterface)` before the 4 new parsers (C, C++,
Go, SQL). It owns byte-level encoding, `QueryCursor` matching, auto-indentation and AST mutation;
a language class defines `SCM_SKELETON_QUERY`, `SCM_SYMBOL_QUERY`, etc. and its `Language` object.

- Removes ~2000 lines of duplicated AST manipulation code.
- A new language is declarative `.scm` queries, not imperative Python byte manipulation.
- Fixes to node bounds or whitespace handling reach every language.
- Cost: every existing stable parser changes, so the full polyglot AST integration suite must pass.
- Fits the `pure-logic` archetype of `workspace/ast/parsers`.

## Functional Requirements

*   **FR-1:** The system SHALL provide a `BaseTreeSitterParser` that encapsulates all `CodeStructureInterface` generic AST mutation logic.
*   **FR-2:** The system SHALL parse C and C++ source files using `tree-sitter-c` and `tree-sitter-cpp` to extract skeletons, symbols, imports, and traceability tags via declarative `.scm` queries.
*   **FR-3:** The system SHALL parse Go source files (`.go`) using `tree-sitter-go` to extract skeletons, symbols, imports, and traceability tags.
*   **FR-4:** The system SHALL parse Standard SQL source files (`.sql`) using `tree-sitter-sql` to extract structural schemas (tables/views) and symbols (functions/procedures).
*   **FR-5:** The system SHALL complete the existing `MarkdownCodeStructure` stub, ensuring it
    implements the full `CodeStructureInterface` (including traceability tag extraction and symbol
    mutation) using the new `BaseTreeSitterParser`.
*   **FR-6:** The system SHALL register all new file extensions in `specweaver.workspace.ast.parsers.factory.get_default_parsers()`.
*   **FR-7:** The system SHALL dynamically prune `ToolDefinition` schemas (e.g. hiding
    `decorator_filter` or `extract_framework_markers`) if no active language parser supports them,
    ensuring agents never see useless capabilities.

## Non-Functional Requirements

*   **NFR-1 (Compatibility):** The new grammars must be fully compatible with `tree-sitter >= 0.25.2` as mandated by the current `pyproject.toml`.
*   **NFR-2 (Architecture Boundaries):** The implementations MUST reside strictly within
    `specweaver.workspace.ast.parsers` and implement the `CodeStructureInterface`. No sandbox I/O is
    permitted (`pure-logic`).
*   **NFR-3 (Dialect Agnosticism):** The SQL parser MUST stick to ANSI Standard SQL. It SHALL NOT
    attempt to polyfill proprietary pgSQL or T-SQL syntax unless it is natively supported by the
    standard `tree-sitter-sql` grammar.

## Risks and limits

- SQL `CREATE PROCEDURE` is not extracted: `tree-sitter-sql` returns an `ERROR` node for it (SF-05).
- FR-7 pruning is global across all registered parsers, not per grant area — waits for the AST
  Knowledge Tree (SF-04).

## Sub-features and Progress Tracker

| Sub-Feature | ID | Dependencies | Impl Plan | Dev | Pre-Commit | Committed |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **AST Base Class Refactoring** | SF-01 | None | ✅ | ✅ | ✅ | ✅ |
| **Markdown Parser Completion** | SF-02 | SF-01 | ✅ | ✅ | ✅ | ✅ |
| **C/C++ Parser Implementation** | SF-03 | SF-01 | ✅ | ✅ | ✅ | ✅ |
| **Go Parser Implementation** | SF-04 | SF-01 | ✅ | ✅ | ✅ | ✅ |
| **SQL Parser Implementation** | SF-05 | SF-01 | ✅ | ✅ | ✅ | ⬜ |

Plans: [sf01](D-SENS-03_sf01_implementation_plan.md) · [sf02](D-SENS-03_sf02_implementation_plan.md) ·
[sf03](D-SENS-03_sf03_implementation_plan.md) · [sf04](D-SENS-03_sf04_implementation_plan.md) ·
[sf05](D-SENS-03_sf05_implementation_plan.md)
