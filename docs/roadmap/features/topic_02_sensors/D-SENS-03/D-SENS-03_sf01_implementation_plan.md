# D-SENS-03 SF-01 — AST Base Class Refactoring

**Status**: APPROVED · **Feature ID**: 3.32e · **FRs owned**: FR-1 · **Depends on**: — ·
Design: [D-SENS-03_design.md](D-SENS-03_design.md) §Why a shared base class first

## Goal

Extract `BaseTreeSitterParser` from `PythonCodeStructure`, `JavaCodeStructure`,
`TypeScriptCodeStructure`, `RustCodeStructure`, `KotlinCodeStructure` and `MarkdownCodeStructure`,
removing ~2000 lines of duplicated byte-level Tree-sitter manipulation.

## Changes

1. **New** `src/specweaver/workspace/ast/parsers/base.py` — `BaseTreeSitterParser` implements
   `CodeStructureInterface`:
   - `language` and `parser` are initialized by subclasses;
   - subclasses provide `SCM_SKELETON_QUERY`, `SCM_SYMBOL_QUERY`, `SCM_IMPORT_QUERY`,
     `SCM_COMMENT_QUERY`;
   - generic `extract_skeleton`, `extract_symbol`, `extract_symbol_body`, `extract_imports`,
     `list_symbols`, `extract_traceability_tags` move here;
   - `replace_symbol`, `replace_symbol_body`, `add_symbol`, `delete_symbol` resolve Tree-sitter
     bounds generically and delegate string formatting to subclass hooks
     `_format_replacement(self, new_code: str, margin: int) -> bytes` and
     `_format_body_injection(self, new_code: str, margin: int) -> bytes`.
2. **Inherit from `BaseTreeSitterParser`** instead of `CodeStructureInterface`; delete the duplicated
   `extract_*` methods; define the SCM query constants and formatting hooks:
   - `src/specweaver/workspace/ast/parsers/python/codestructure.py`
   - `src/specweaver/workspace/ast/parsers/java/codestructure.py`
   - `src/specweaver/workspace/ast/parsers/typescript/codestructure.py`
   - `src/specweaver/workspace/ast/parsers/rust/codestructure.py`
   - `src/specweaver/workspace/ast/parsers/kotlin/codestructure.py`
   - `src/specweaver/workspace/ast/parsers/markdown/codestructure.py`
3. Markdown's `extract_skeleton` outputs strings, not JSON.

Why hooks: Python uses whitespace indentation, Java/Rust/TS use curly braces `{}`, so
`replace_symbol_body` cannot inject strings without the language's block rules.

## Tests

No new tests. Success = the existing polyglot suite passes with 100% parity:
- `pytest tests/unit/workspace/ast/parsers/`
- `pytest tests/e2e/` (context condensation and macro evaluator integrations stay stable).

## Decisions (audit)

- **Markdown in SF-01** (HITL): included and migrated to standard string return types. Research had
  proposed excluding it (its `extract_skeleton` returned JSON, not a raw text skeleton) and handling
  it in SF-02; SF-02 then completes the rest of the Markdown parser.
