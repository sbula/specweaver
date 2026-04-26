# Implementation Plan: Polyglot Expansion [SF-2: Markdown Parser Completion]
- **Feature ID**: 3.32e
- **Sub-Feature**: SF-2 — Markdown Parser Completion
- **Design Document**: docs/roadmap/features/topic_02_sensors/D-SENS-03/D-SENS-03_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-2
- **Implementation Plan**: docs/roadmap/features/topic_02_sensors/D-SENS-03/D-SENS-03_sf2_implementation_plan.md
- **Status**: COMPLETED

## 1. Goal Description
The objective of this sub-feature (SF-2) is to complete the existing `MarkdownCodeStructure` stub, ensuring it fully implements the `CodeStructureInterface` (including traceability tag extraction, skeleton generation, and symbol mutation) using the new `BaseTreeSitterParser` extracted in SF-1. The primary architectural goal is to delete the custom `extract_*` overrides currently present in the markdown parser and map its operations dynamically to `BaseTreeSitterParser` via `.scm` queries, satisfying FR-5.

## 2. Context & Boundary Rules
- **Archetype**: `pure-logic`.
- **Location**: `src/specweaver/workspace/parsers/markdown/codestructure.py`.
- **Boundaries**: Strictly NO `loom/*` execution, no file I/O, no networking. Everything must be processed in memory using the `tree_sitter_markdown` dependency.

## 3. Proposed Changes

### `src/specweaver/workspace/parsers/markdown/codestructure.py`
We will rewrite `MarkdownCodeStructure` to lean entirely on `BaseTreeSitterParser`.
1. **Remove the manual overrides**: Delete the custom `extract_skeleton`, `extract_symbol`, `extract_symbol_body`, `replace_symbol`, `replace_symbol_body`, `add_symbol`, and `delete_symbol` functions. Let the `BaseTreeSitterParser` handle these automatically.
2. **Define SCM Queries**:
   - `SCM_SKELETON_QUERY`: Capture `(paragraph) @block`, `(list) @block`, `(fenced_code_block) @block`, `(indented_code_block) @block`, `(block_quote) @block`, and `(html_block) @block`. Because `extract_skeleton` blanks all nodes labeled `@block`, this perfectly isolates the headers.
   - `SCM_SYMBOL_QUERY`: `(section (atx_heading heading_content: (inline) @name)) @block`
   - `SCM_COMMENT_QUERY`: `(html_block) @comment`
3. **Implement Formatting & Query Hooks**:
   - `_is_symbol_valid`: For Markdown, always return `True` (visibility and decorators don't apply).
   - `_find_symbol_node`: Query `SCM_SYMBOL_QUERY`. Walk the cursor matches; if the `@name` inline text matches `symbol_name`, return the `@block` (the `section` node).
   - `_find_target_block`: Since Tree-Sitter's Markdown grammar doesn't wrap the "body" of a section in a discrete AST node (it's a flat list of siblings after `atx_heading`), you **must** build a duck-typed `MarkdownBodyBlock` object with `start_byte`, `end_byte`, and `text` properties. Calculate this from the end of the `atx_heading` to the end of the `section` node.
   - `_format_replacement`: Standard byte-slicing replacement.
   - `_format_body_injection`: Splice `new_code` into the `target_block` bounds identified above.
4. **Implement Other Overrides**:
   - `extract_framework_markers`: Return empty dict.
   - `extract_imports`: Return empty list.
   - `get_binary_ignore_patterns`: Return empty list.
   - `get_default_directory_ignores`: Return empty list.

### `tests/integration/core/loom/test_polyglot_ast_markdown.py`
1. **Update Skeleton Test**: Modify `test_markdown_extract_skeleton` to expect the base class output format (where paragraphs are replaced with `...` instead of clean header lists).
2. **Rewrite Exception Tests**: Update `test_markdown_unsupported_symbol_extraction` and `test_markdown_unsupported_mutators` from testing for `CodeStructureError` to asserting correct string replacements and symbol extractions. Ensure coverage of `replace_symbol_body` mutating a paragraph inside a section.

## 4. Open Questions & HITL Gate Review (Resolved)
- **Question**: Should we override `extract_skeleton` to preserve its current string output format, or use the `BaseTreeSitterParser` implementation and update the tests to expect the `...` format?
- **HITL Decision**: We will strictly utilize the `BaseTreeSitterParser` implementation and update the tests. This satisfies FR-5 and maintains 100% uniformity.

## 5. Session Handoff (For the Next Agent)
This sub-feature has been fully implemented, tested, and validated by the pre-commit quality gate. 
Next Step: The Feature lifecycle should proceed to the next Sub-Feature (SF-3: C/C++ Parser Implementation).
