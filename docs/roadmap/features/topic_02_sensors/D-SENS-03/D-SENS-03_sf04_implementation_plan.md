# D-SENS-03 SF-04 — Go Parser Implementation

**Status**: COMPLETED · **Feature ID**: 3.32e · **FRs owned**: FR-3, FR-7 · **Depends on**: SF-01 ·
Design: [D-SENS-03_design.md](D-SENS-03_design.md) §Sub-features and Progress Tracker

## Goal

1. A Go parser on `tree-sitter-go` (Feature 3.32e SF-04).
2. **Dot-notation symbols in every parser** (Option B) — Go, Python, Java, C++, TypeScript, Rust,
   Kotlin, Markdown. `list_symbols` emits `Class.MethodName` (or `Receiver.MethodName`, or
   `Header.Section` for markdown); `extract_symbol` resolves it with `string.split(".", 1)`. The LLM
   copies whatever string it sees, in any language.

   Replaces bare method names, which collided (two `move` methods in different classes).
3. **Capability pruning** (FR-7): tools stop offering intents/parameters no active parser supports.

## Where it plugs in

- tree-sitter-go nodes: functions `function_declaration`; methods `method_declaration` with a
  `receiver` node; interfaces and structs `type_declaration` -> `type_spec` -> `struct_type` /
  `interface_type`.
- Go has no `public`/`private` keywords: visibility is `sym_name[0].isupper()` for "public".

## Changes

1. `pyproject.toml` — add `"tree-sitter-go>=0.23.0"` to core dependencies under the `tree-sitter`
   group.
2. `src/specweaver/workspace/ast/parsers/interfaces.py` — `CodeStructureInterface` gains `@classmethod`
   `supported_intents() -> set[str]` and `supported_parameters(intent: str) -> set[str]`, defaulting
   to everything (backward compatible). `extract_framework_markers` and `decorator_filter` are
   optional capabilities.
3. `src/specweaver/core/loom/tools/code_structure/definitions.py` —
   `get_code_structure_schema(supported_intents: set[str], supported_params: dict[str, set[str]])`
   drops `READ_UNROLLED_SYMBOL_SCHEMA` or `extract_framework_markers` (if added) when unsupported, and
   prunes `decorator_filter` from `LIST_SYMBOLS_SCHEMA` unless it is in
   `supported_params["list_symbols"]`.
4. `src/specweaver/core/loom/tools/code_structure/tool.py` — `definitions()` combines capabilities
   across the parsers in `CodeStructureAtom._parsers`; an intent/parameter no parser supports is
   pruned from the agent's schema.
5. `src/specweaver/workspace/ast/parsers/factory.py` — register `(".go",)` → `GoCodeStructure`.
6. `src/specweaver/workspace/ast/parsers/context.yaml` — `exposes` gains `factory`,
   `go/codestructure`, `c/codestructure`, `cpp/codestructure`, `markdown/codestructure` (the list was
   out of date).
7. **Existing parsers** (`python`, `cpp`, `java`, `kotlin`, `typescript`, `rust`, `markdown`):
   - `list_symbols` prepends the class/struct/receiver name (`Point.Move`, not `Move`); Markdown may
     nest headers.
   - `_find_symbol_node`: `if "." in symbol_name: scope, name = symbol_name.split(".", 1)`, then match
     the class/method pair by tree-sitter parent traversal or scope checks — no regex.
   - `CppCodeStructure`, `CCodeStructure`, `RustCodeStructure`, `MarkdownCodeStructure` override
     `supported_intents()` / `supported_parameters()` to exclude `decorator_filter` and
     `read_unrolled_symbol`/`extract_framework_markers` where meaningless.
8. `docs/dev_guides/code_structure_and_ast_editing.md` — document the Option B dot-notation API.
9. `[NEW]` `src/specweaver/workspace/ast/parsers/go/codestructure.py` — `GoCodeStructure(BaseTreeSitterParser)`:
   - `SCM_SKELETON_QUERY`, `SCM_SYMBOL_QUERY`, `SCM_COMMENT_QUERY` target `function_declaration`,
     `method_declaration` (captures `@receiver` and `@name`) and `type_declaration`;
   - `list_symbols` emits `Receiver.MethodName` (`Point.Move`); `_find_symbol_node` splits with
     `symbol_name.split(".", 1)`;
   - `supported_intents()` / `supported_parameters()` exclude `decorator_filter` and
     `extract_framework_markers`; a `decorator_filter` explicitly raises an error (Go has no
     decorators);
   - `_is_symbol_valid`: uppercase first letter = public, lowercase = private;
   - `extract_imports` targets `(import_declaration)` blocks.

> [!NOTE]
> **Deferred: AST Knowledge Tree filtering.** `CodeStructureAtom.get_supported_capabilities()`
> aggregates across *all* registered parsers. Hiding `decorator_filter` when an agent's grant area
> holds only Go files needs the upcoming **AST Knowledge Tree** (which languages live where). An
> architectural `TODO` in `CodeStructureAtom` marks it.

**Since moved** (noted 2026-09-25): `core/loom/tools/code_structure/` →
`sandbox/code_structure/interfaces/`.

## Tests

| File | Covers |
|---|---|
| `[NEW]` `tests/unit/workspace/ast/parsers/go/test_codestructure.py` | 100% parity with other parsers: symbols, skeleton, imports, `add_symbol`, visibility (capitalized vs lowercase) |
| `tests/unit/workspace/ast/parsers/*/test_codestructure.py` | `test_extract_symbol_dot_notation` in Python, C++, Java, Kotlin, TypeScript, Rust, Markdown |
| `[NEW]` `tests/integration/core/loom/test_polyglot_ast_go.py` | `GoCodeStructure` behaves like the C/C++ parsers under `BaseTreeSitterParser` |

The dot-notation tests prove `Class.Method` isolates identical method names across classes.

Run: `pytest tests/unit/workspace/ast/parsers/go/test_codestructure.py` ·
`pytest tests/integration/core/loom/test_polyglot_ast_go.py` · `tach check` ·
`ruff check src/specweaver/workspace/ast/parsers/go`.
