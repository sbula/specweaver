# D-SENS-03 SF-05 — SQL Parser Implementation

**Status**: COMPLETED · **Feature ID**: 3.32e · **FRs owned**: FR-4 · **Depends on**: SF-01 ·
Design: [D-SENS-03_design.md](D-SENS-03_design.md) §Sub-features and Progress Tracker

## Goal

`CodeStructureInterface` for Standard SQL on `BaseTreeSitterParser`: parse schemas (tables/views)
and functions, as context for data-centric agent tasks.

## Where it plugs in

- `tree-sitter-sql` (v0.3.11) parses `create_table`, `create_view`, `create_function`, but returns an
  `ERROR` node for ANSI `CREATE PROCEDURE`.
- SQL has no code-level decorators or OOP visibility modifiers.
- Install `tree-sitter-sql>=0.3.11` via `pyproject.toml`.

## Changes

1. pyproject.toml — append `"tree-sitter-sql>=0.3.11"` to `dependencies`.
2. src/specweaver/workspace/ast/parsers/context.yaml — add `- sql/codestructure` to `exposes:`
   (`pure-logic` boundary compliance).
3. src/specweaver/workspace/ast/parsers/factory.py —
   `from specweaver.workspace.ast.parsers.sql.codestructure import SqlCodeStructure`; map `(".sql",)`
   to `SqlCodeStructure()` in `get_default_parsers()`.
4. `[NEW]` src/specweaver/workspace/ast/parsers/sql/__init__.py — empty.
5. `[NEW]` src/specweaver/workspace/ast/parsers/sql/codestructure.py — `SqlCodeStructure(BaseTreeSitterParser)`:
   - `Language(tree_sitter_sql.language())` and `Parser`;
   - **`SCM_SKELETON_QUERY`**: `create_table`, `create_view`, `create_function`;
   - **`SCM_SYMBOL_QUERY`**: the `identifier` inside `object_reference` of those three;
   - **`SCM_COMMENT_QUERY`**: `(comment) @comment` or `(--) @comment`;
   - **`_is_symbol_valid`**: always `True` (visibility and decorator parameters ignored);
   - **`supported_intents`**: `["skeleton", "symbol", "symbol_body", "list", "replace", "replace_body", "add", "delete", "traceability"]`;
   - **`supported_parameters`**: `[]`; **`extract_framework_markers`**: `{}`;
   - **`extract_imports`**: `[]` (SQL imports/includes are dialect-specific);
   - **`get_binary_ignore_patterns`**: `["*.sqlite", "*.db", "*.mdf", "*.ldf"]`;
   - **`get_default_directory_ignores`**: `["data/", "migrations/"]`.

## Tests

`[NEW]` tests/unit/workspace/ast/parsers/sql/test_sql_code_structure.py:
- `list_symbols` finds tables, views and functions;
- `extract_skeleton` blanks function bodies and column definitions;
- `extract_symbol` and `replace_symbol` extract SQL schema exactly;
- `extract_framework_markers` returns an empty dictionary;
- syntax errors handled per standard parser error mitigation.

Also `test_polyglot_ast_sql.py` (integration), for parity with the other languages.

Commands:
- `uv run pytest tests/unit/workspace/ast/parsers/sql/test_sql_code_structure.py -v`
- `uv run ruff check src tests`
- `uv run mypy src tests`

No manual verification — pure-logic unit tests suffice.

## Decisions (audit)

1. **`CREATE PROCEDURE`**: HITL — keep to NFR-3 (Dialect Agnosticism); `procedure` extraction is
   dropped and documented as a known limitation.
2. **Markers and visibility**: HITL — `extract_framework_markers` returns `{}`; `supported_parameters`
   returns `[]`.

## As built

**Since changed** (`B-SENS-03` SF-03, noted 2026-09-25): `SCM_SYMBOL_QUERY` now captures the
`object_reference` itself. Capturing the `identifier` inside it reported `CREATE TABLE public.orders`
as two symbols, `public` and `orders`. `SCM_COMMENT_QUERY` is now empty.
