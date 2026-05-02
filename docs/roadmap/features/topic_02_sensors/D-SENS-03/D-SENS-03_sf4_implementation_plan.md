# Implementation Plan: Polyglot Expansion [SF-4: Go Parser Implementation]
- **Feature ID**: 3.32e
- **Sub-Feature**: SF-4 — Go Parser Implementation
- **Design Document**: docs/roadmap/features/topic_02_sensors/D-SENS-03/D-SENS-03_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-4
- **Implementation Plan**: docs/roadmap/features/topic_02_sensors/D-SENS-03/D-SENS-03_sf4_implementation_plan.md
- **Status**: COMPLETED

## Goal Description
Implement the Go language parser using `tree-sitter-go` (Feature 3.32e SF-4) and eliminate technical debt across all existing polyglot parsers by standardizing method resolution. 

Previously, AST parsers blindly returned method names, causing severe LLM context collision risks (e.g., identical `move` methods). This plan implements **Option B (Dot-Notation Resolution)** across Go, Python, Java, C++, TypeScript, Rust, Kotlin, and Markdown. `list_symbols` will dynamically emit `Class.MethodName` (or `Receiver.MethodName`, or `Header.Section` for markdown), and `extract_symbol` will resolve them perfectly using simple `string.split(".", 1)` logic, making the entire polyglot ecosystem robust, precise, and completely language-agnostic for the LLM.

> [!NOTE]
> **Deferred Feature: AST Knowledge Tree Filtering**
> The dynamic pruning of capabilities in `CodeStructureAtom.get_supported_capabilities()` currently aggregates across *all* registered parsers globally. True area-specific filtering (e.g., hiding `decorator_filter` when an agent only has access to Go files) requires the upcoming **AST Knowledge Tree** to identify which languages exist in which grant areas. We will add an architectural `TODO` in `CodeStructureAtom` to revisit this once the Knowledge Tree is implemented.

## Proposed Changes

### [MODIFY] `pyproject.toml`
- Add `"tree-sitter-go>=0.23.0"` to the core dependencies under the `tree-sitter` group.

### [MODIFY] `src/specweaver/workspace/ast/parsers/interfaces.py`
- **`CodeStructureInterface`**: Add `@classmethod` `supported_intents() -> set[str]` and `supported_parameters(intent: str) -> set[str]`. Default them to return all intents and parameters for backward compatibility.
- Ensure `extract_framework_markers` and `decorator_filter` are explicitly handled as optional capabilities.

### [MODIFY] `src/specweaver/core/loom/tools/code_structure/definitions.py`
- Modify `get_code_structure_schema(supported_intents: set[str], supported_params: dict[str, set[str]])` to dynamically filter out `READ_UNROLLED_SYMBOL_SCHEMA` or `extract_framework_markers` (if added) when not supported.
- Dynamically prune the `decorator_filter` parameter from `LIST_SYMBOLS_SCHEMA` if `decorator_filter` is not in `supported_params["list_symbols"]`.

### [MODIFY] `src/specweaver/core/loom/tools/code_structure/tool.py`
- Update `definitions()` to compute the intersection of supported capabilities across all active parsers loaded in `CodeStructureAtom._parsers`. If *no* parser supports an intent/parameter, it is pruned from the schema sent to the agent.

### [MODIFY] `src/specweaver/workspace/ast/parsers/factory.py`
- Register the `(".go",)` extension mapping it to the new `GoCodeStructure`.

### [MODIFY] `src/specweaver/workspace/ast/parsers/context.yaml`
- Update the `exposes` list to formally include `factory`, `go/codestructure`, `c/codestructure`, `cpp/codestructure`, and `markdown/codestructure` to resolve current architectural documentation violations.

### [MODIFY] Existing Language Parsers (`python`, `cpp`, `java`, `kotlin`, `typescript`, `rust`, `markdown`)
- **`list_symbols` Overrides**: Update the existing query extractions to prepend the class/struct/receiver name to methods (e.g., `Point.Move` instead of `Move`). For Markdown, potentially nest headers.
- **`_find_symbol_node` Overrides**: Add a uniform `if "." in symbol_name: scope, name = symbol_name.split(".", 1)` to all implementations. Use tree-sitter parent traversal or scope checks to match the exact class/method pair cleanly without using regex.
- **Capability Declarations**: Override `supported_intents()` and `supported_parameters()` in `CppCodeStructure`, `CCodeStructure`, `RustCodeStructure`, and `MarkdownCodeStructure` to explicitly exclude `decorator_filter` and `read_unrolled_symbol`/`extract_framework_markers` where they are semantically meaningless.

### [MODIFY] `docs/dev_guides/code_structure_and_ast_editing.md`
- Document the new Option B Dot-Notation API across the polyglot ecosystem so developers understand that method symbols are resolved securely using dot-notation.

### [NEW] `src/specweaver/workspace/ast/parsers/go/codestructure.py`
- Implements `GoCodeStructure(BaseTreeSitterParser)`.
- Defines `SCM_SKELETON_QUERY`, `SCM_SYMBOL_QUERY`, and `SCM_COMMENT_QUERY` targeting `function_declaration`, `method_declaration`, and `type_declaration`. 
  - *Note: `method_declaration` captures both `@receiver` and `@name`.*
- **Overrides `list_symbols`**: Automatically formats method names as `Receiver.MethodName` (e.g., `Point.Move`). This makes it language-agnostic for the LLM; the agent just asks for whatever string it sees in the list.
- **Overrides `_find_symbol_node`**: Uses a simple `symbol_name.split(".", 1)` to cleanly match both the receiver type and the method name in the AST without complex regex.
- **Capability Declarations**: Overrides `supported_intents()` and `supported_parameters()` to explicitly exclude `decorator_filter` and `extract_framework_markers` since Go does not use them.
- Implements `_is_symbol_valid` to support Go visibility rules (symbols starting with an uppercase letter are public, lowercase are private).
- Implements `extract_imports` targeting the `(import_declaration)` blocks.
- Explicitly raises an error for `decorator_filter`, as decorators do not exist in Go syntax.

### [NEW] `tests/unit/workspace/ast/parsers/go/test_codestructure.py`
- 100% parity with existing language parser tests.
- Covers symbol extraction, skeleton stripping, imports, `add_symbol`, and visibility filtering (capitalized vs lowercase).

### [MODIFY] Existing Language Unit Tests (`tests/unit/workspace/ast/parsers/*/test_codestructure.py`)
- Add specific unit tests for dot-notation resolution (`test_extract_symbol_dot_notation`) to Python, C++, Java, Kotlin, TypeScript, Rust, and Markdown to ensure `Class.Method` correctly isolates identical method names across different classes.

### [NEW] `tests/integration/core/loom/test_polyglot_ast_go.py`
- Integration tests ensuring `GoCodeStructure` behaves identically to the C/C++ parsers within the broader `BaseTreeSitterParser` abstraction.

## Research Notes
- **tree-sitter-go nodes**: Functions use `function_declaration`, methods use `method_declaration` with a `receiver` node. Interfaces and Structs are wrapped in `type_declaration` -> `type_spec` -> `struct_type` / `interface_type`.
- **Visibility**: Go lacks `public`/`private` keywords. Visibility filtering must check if `sym_name[0].isupper()` for "public".
- **Receiver Name Collisions & Polyglot Cleanup**: 
  > [!NOTE]
  > All languages will be treated exactly the same way. We avoid fragile regex entirely by using `symbol_name.split(".", 1)` universally in python, and checking the tree-sitter AST nodes structurally (e.g. checking if the method's parent class node matches the scope). The LLM Agent will dynamically copy the `Class.Method` strings from `list_symbols`, remaining 100% language agnostic.

## Verification Plan

### Automated Tests
1. `pytest tests/unit/workspace/ast/parsers/go/test_codestructure.py`
2. `pytest tests/integration/core/loom/test_polyglot_ast_go.py`
3. `tach check` to ensure boundaries remain clean.
4. `ruff check src/specweaver/workspace/ast/parsers/go`
