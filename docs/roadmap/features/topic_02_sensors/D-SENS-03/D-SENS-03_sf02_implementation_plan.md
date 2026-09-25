# D-SENS-03 SF-02 — Markdown Parser Completion

**Status**: COMPLETED · **Feature ID**: 3.32e · **FRs owned**: FR-5 · **Depends on**: SF-01 ·
Design: [D-SENS-03_design.md](D-SENS-03_design.md) §Sub-features and Progress Tracker

## Goal

Complete the `MarkdownCodeStructure` stub so it implements all of `CodeStructureInterface`
(traceability tags, skeleton, symbol mutation) through `BaseTreeSitterParser`: delete its custom
`extract_*` overrides and express it as `.scm` queries.

## Where it plugs in

`src/specweaver/workspace/ast/parsers/markdown/codestructure.py` · archetype `pure-logic` · NO
`loom/*` execution, no file I/O, no networking — all in memory via `tree_sitter_markdown`.

## Changes

**`src/specweaver/workspace/ast/parsers/markdown/codestructure.py`**

1. **Remove overrides**: custom `extract_skeleton`, `extract_symbol`, `extract_symbol_body`,
   `replace_symbol`, `replace_symbol_body`, `add_symbol`, `delete_symbol` — the base class handles them.
2. **SCM queries**:
   - `SCM_SKELETON_QUERY`: `(paragraph) @block`, `(list) @block`, `(fenced_code_block) @block`,
     `(indented_code_block) @block`, `(block_quote) @block`, `(html_block) @block`.
     `extract_skeleton` blanks every `@block`, which leaves the headers.
   - `SCM_SYMBOL_QUERY`: `(section (atx_heading heading_content: (inline) @name)) @block`
   - `SCM_COMMENT_QUERY`: `(html_block) @comment`
3. **Hooks**:
   - `_is_symbol_valid`: always `True` (no visibility or decorators).
   - `_find_symbol_node`: query `SCM_SYMBOL_QUERY`; if the `@name` inline text matches `symbol_name`,
     return the `@block` (the `section` node).
   - `_find_target_block`: the grammar has no body node for a section (a flat list of siblings after
     `atx_heading`), so build a duck-typed `MarkdownBodyBlock` with `start_byte`, `end_byte`, `text`,
     spanning the end of the `atx_heading` to the end of the `section` node.
   - `_format_replacement`: standard byte-slicing replacement.
   - `_format_body_injection`: splice `new_code` into those `target_block` bounds.
4. **Other overrides**: `extract_framework_markers` → empty dict; `extract_imports`,
   `get_binary_ignore_patterns`, `get_default_directory_ignores` → empty list.

**`tests/integration/core/loom/test_polyglot_ast_markdown.py`**

5. `test_markdown_extract_skeleton` expects the base-class format (paragraphs replaced with `...`,
   not clean header lists).
6. `test_markdown_unsupported_symbol_extraction` and `test_markdown_unsupported_mutators` assert
   correct replacements and extractions instead of `CodeStructureError`; cover `replace_symbol_body`
   mutating a paragraph inside a section.

## Decisions (audit)

- **Keep the old `extract_skeleton` string format, or use the base class and update tests?** HITL:
  use the `BaseTreeSitterParser` implementation and update the tests — satisfies FR-5, 100% uniform.

## As built

Implemented, tested, passed the pre-commit quality gate.
