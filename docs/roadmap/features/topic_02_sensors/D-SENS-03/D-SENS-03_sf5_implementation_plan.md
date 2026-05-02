# Implementation Plan: Polyglot Expansion [SF-5: SQL Parser Implementation]
- **Feature ID**: 3.32e
- **Sub-Feature**: SF-5 — SQL Parser Implementation
- **Design Document**: docs/roadmap/features/topic_02_sensors/D-SENS-03/D-SENS-03_design.md
- **Design Section**: §5 Sub-Feature Breakdown → SF-5
- **Implementation Plan**: docs/roadmap/features/topic_02_sensors/D-SENS-03/D-SENS-03_sf5_implementation_plan.md
- **Status**: COMPLETED

## Goal Description
Implement the `CodeStructureInterface` for Standard SQL by leveraging the unified `BaseTreeSitterParser`. This enables SpecWeaver to structurally parse SQL schemas (tables/views) and functions, providing critical context for data-centric AI agent tasks.

> **Implementation Note:** Added `test_polyglot_ast_sql.py` in Phase 2 to ensure full Integration test coverage parity with other supported languages.

## Research Notes
- **tree-sitter-sql limitations**: The standard `tree-sitter-sql` grammar (v0.3.11) natively supports `create_table`, `create_view`, and `create_function`, but fails to parse ANSI `CREATE PROCEDURE`, returning an `ERROR` node. Per HITL decision (Phase 4), we will adhere strictly to NFR-3 (Dialect Agnosticism) and drop support for `procedure` extraction, documenting it as a known limitation.
- **Framework markers & Visibility**: SQL does not support code-level decorators or typical OOP visibility modifiers. Per HITL decision (Phase 4), `extract_framework_markers` will return `{}`. `supported_parameters` will return `[]`.
- **Dependencies**: We will install `tree-sitter-sql>=0.3.11` via `pyproject.toml`.

## Proposed Changes

### Configuration and Registries
#### [MODIFY] pyproject.toml
- Append `"tree-sitter-sql>=0.3.11"` to the `dependencies` array.

#### [MODIFY] src/specweaver/workspace/ast/parsers/context.yaml
- Add `- sql/codestructure` to the `exposes:` list to ensure architectural compliance with the `pure-logic` boundary.

#### [MODIFY] src/specweaver/workspace/ast/parsers/factory.py
- Import `from specweaver.workspace.ast.parsers.sql.codestructure import SqlCodeStructure`
- Map the tuple `(".sql",)` to `SqlCodeStructure()` inside `get_default_parsers()`.

---

### SQL Parser Implementation

#### [NEW] src/specweaver/workspace/ast/parsers/sql/__init__.py
- Empty initialization file.

#### [NEW] src/specweaver/workspace/ast/parsers/sql/codestructure.py
- Create `SqlCodeStructure(BaseTreeSitterParser)`.
- Initialize `Language(tree_sitter_sql.language())` and `Parser`.
- **`SCM_SKELETON_QUERY`**: Target `create_table`, `create_view`, `create_function`.
- **`SCM_SYMBOL_QUERY`**: Capture `identifier` inside the `object_reference` node of `create_table`, `create_view`, and `create_function`.
- **`SCM_COMMENT_QUERY`**: Target `(comment) @comment` or `(--) @comment`.
- **`_is_symbol_valid`**: Always return `True` (visibility and decorator parameters ignored).
- **`supported_intents`**: Return `["skeleton", "symbol", "symbol_body", "list", "replace", "replace_body", "add", "delete", "traceability"]`.
- **`supported_parameters`**: Return `[]`.
- **`extract_framework_markers`**: Return `{}`.
- **`extract_imports`**: Return `[]` (SQL imports/includes are dialect-specific and non-standard).
- **`get_binary_ignore_patterns`**: Return `["*.sqlite", "*.db", "*.mdf", "*.ldf"]`.
- **`get_default_directory_ignores`**: Return `["data/", "migrations/"]`.

---

### Verification Plan

#### Automated Tests
#### [NEW] tests/unit/workspace/ast/parsers/sql/test_sql_code_structure.py
- Test `list_symbols` correctly identifies tables, views, and functions.
- Test `extract_skeleton` blanks out function bodies and column definitions appropriately.
- Test `extract_symbol` and `replace_symbol` for exact SQL schema extraction.
- Verify `extract_framework_markers` returns an empty dictionary.
- Verify robust handling of syntax errors per standard parser error mitigation.

**Commands to run**:
- `uv run pytest tests/unit/workspace/ast/parsers/sql/test_sql_code_structure.py -v`
- `uv run ruff check src tests`
- `uv run mypy src tests`

#### Manual Verification
- Not required; purely logical unit tests provide sufficient coverage.
