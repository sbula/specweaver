# Implementation Plan: Polyglot Expansion [SF-3: C/C++ Parser Implementation]
- **Feature ID**: 3.32e
- **Sub-Feature**: SF-3 — C/C++ Parser Implementation
- **Design Document**: docs/roadmap/features/topic_02_sensors/D-SENS-03/D-SENS-03_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-3
- **Implementation Plan**: docs/roadmap/features/topic_02_sensors/D-SENS-03/D-SENS-03_sf3_implementation_plan.md
- **Status**: COMPLETED

## Research Notes
- **Track A (Codebase):** `pyproject.toml` requires explicit additions for `tree-sitter-c` and `tree-sitter-cpp`. `get_default_parsers()` in `factory.py` needs registering `.c, .h, .cpp, .hpp, .cc, .cxx`.
- **Track B (Grammar):** C AST uses `function_definition` and `struct_specifier`. C++ AST extends this with `class_specifier` and `namespace_definition`. C++ uses `access_specifier` (public/private) for visibility, which can be evaluated during `_is_symbol_valid`.

## Proposed Changes

### `pyproject.toml`
#### [x] [MODIFY] pyproject.toml
- Add `"tree-sitter-c>=0.23.0"` and `"tree-sitter-cpp>=0.23.0"` to the `dependencies` array.

### Workspace Parsers (C and C++)
#### [x] [NEW] src/specweaver/workspace/parsers/c/codestructure.py
- Define `CCodeStructure` inheriting from `BaseTreeSitterParser`.
- Implement declarative `.scm` queries for `function_definition` and `struct_specifier`.
- Implement `_is_symbol_valid`, `_find_target_block`, `_format_replacement`, `_format_body_injection`.
- Return explicit C binary ignore patterns (`*.o`, `*.so`, `*.dll`, `*.a`).

#### [x] [NEW] src/specweaver/workspace/parsers/cpp/codestructure.py
- Define `CppCodeStructure` inheriting from `BaseTreeSitterParser`.
- Implement declarative `.scm` queries expanding C definitions to include `class_specifier` and `namespace_definition`.
- Implement custom `_is_symbol_valid` to support C++ `access_specifier` bounding.
- **[HITL Decision: Option C]**: Implement support for `decorator_filter` by querying `(attribute_declaration (attribute name: (identifier)))` and `(attribute_specifier)`. If a filter is provided, only return symbols possessing matching attributes.

### Parser Factory
#### [x] [MODIFY] src/specweaver/workspace/parsers/factory.py
- Import `CCodeStructure` and `CppCodeStructure`.
- Map `.c`, `.h` to `CCodeStructure`.
- Map `.cpp`, `.hpp`, `.cc`, `.cxx` to `CppCodeStructure`.

### Tests
#### [x] [NEW] tests/unit/workspace/parsers/c/test_codestructure.py
#### [x] [NEW] tests/unit/workspace/parsers/cpp/test_codestructure.py
- Unit tests mapping extraction bounds (read_skeleton, read_symbol, replace_body).
#### [x] [NEW] tests/integration/core/loom/test_polyglot_ast_cpp.py
- Full integration tests via `CodeStructureAtom` mapped against sample `.cpp` and `.h` fixtures.

## Verification Plan
### Automated Tests
1. `pytest tests/unit/workspace/parsers/c/`
2. `pytest tests/unit/workspace/parsers/cpp/`
3. `pytest tests/integration/core/loom/test_polyglot_ast_cpp.py`

### Quality Gates
1. `ruff check src/specweaver/workspace/parsers/`
2. `mypy src/specweaver/workspace/parsers/`
3. `tach check`
