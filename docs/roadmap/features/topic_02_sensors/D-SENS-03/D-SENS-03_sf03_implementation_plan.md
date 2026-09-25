# D-SENS-03 SF-03 — C/C++ Parser Implementation

**Status**: COMPLETED · **Feature ID**: 3.32e · **FRs owned**: FR-2 · **Depends on**: SF-01 ·
Design: [D-SENS-03_design.md](D-SENS-03_design.md) §Sub-features and Progress Tracker

## Where it plugs in

- `pyproject.toml` needs `tree-sitter-c` and `tree-sitter-cpp`; `get_default_parsers()` in
  `factory.py` registers `.c, .h, .cpp, .hpp, .cc, .cxx`.
- Grammar: C uses `function_definition` and `struct_specifier`; C++ adds `class_specifier` and
  `namespace_definition`, and `access_specifier` (public/private) for visibility, checked in
  `_is_symbol_valid`.

## Changes

All `[x]` done.

1. `pyproject.toml` — add `"tree-sitter-c>=0.23.0"` and `"tree-sitter-cpp>=0.23.0"` to `dependencies`.
2. `[NEW]` src/specweaver/workspace/ast/parsers/c/codestructure.py — `CCodeStructure` inherits
   `BaseTreeSitterParser`; `.scm` queries for `function_definition` and `struct_specifier`;
   `_is_symbol_valid`, `_find_target_block`, `_format_replacement`, `_format_body_injection`; binary
   ignores `*.o`, `*.so`, `*.dll`, `*.a`.
3. `[NEW]` src/specweaver/workspace/ast/parsers/cpp/codestructure.py — `CppCodeStructure` inherits
   `BaseTreeSitterParser`; queries add `class_specifier` and `namespace_definition`; custom
   `_is_symbol_valid` for `access_specifier`; `decorator_filter` supported (Option C, see Decisions).
4. src/specweaver/workspace/ast/parsers/factory.py — import `CCodeStructure` and `CppCodeStructure`;
   `.c`, `.h` → `CCodeStructure`; `.cpp`, `.hpp`, `.cc`, `.cxx` → `CppCodeStructure`.

## Tests

| File | Covers |
|---|---|
| `[NEW]` tests/unit/workspace/ast/parsers/c/test_codestructure.py | extraction bounds (read_skeleton, read_symbol, replace_body) |
| `[NEW]` tests/unit/workspace/ast/parsers/cpp/test_codestructure.py | same, C++ |
| `[NEW]` tests/integration/core/loom/test_polyglot_ast_cpp.py | via `CodeStructureAtom` on sample `.cpp` and `.h` fixtures |

Run: `pytest tests/unit/workspace/ast/parsers/c/` · `pytest tests/unit/workspace/ast/parsers/cpp/` ·
`pytest tests/integration/core/loom/test_polyglot_ast_cpp.py` · `ruff check src/specweaver/workspace/ast/parsers/` ·
`mypy src/specweaver/workspace/ast/parsers/` · `tach check`.

## Decisions (audit)

- **C++ `decorator_filter`** — HITL Decision: Option C. Query
  `(attribute_declaration (attribute name: (identifier)))` and `(attribute_specifier)`; with a
  filter, return only symbols carrying a matching attribute.
