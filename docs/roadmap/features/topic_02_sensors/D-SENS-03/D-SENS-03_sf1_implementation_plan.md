# Implementation Plan: Polyglot Expansion [SF-1: AST Base Class Refactoring]
- **Feature ID**: 3.32e
- **Sub-Feature**: SF-1 — AST Base Class Refactoring
- **Design Document**: docs/roadmap/features/topic_02_sensors/D-SENS-03/D-SENS-03_design.md
- **Design Section**: §Sub-Feature Decomposition -> SF-1
- **Implementation Plan**: docs/roadmap/features/topic_02_sensors/D-SENS-03/D-SENS-03_sf1_implementation_plan.md
- **Status**: APPROVED

## 1. Scope
Extract a `BaseTreeSitterParser` from the existing polyglot AST implementations (`PythonCodeStructure`, `JavaCodeStructure`, `TypeScriptCodeStructure`, `RustCodeStructure`, `KotlinCodeStructure`, `MarkdownCodeStructure`) to eliminate ~2000 lines of redundant byte-level Tree-sitter manipulation.
*Note: Per HITL decision, Markdown is explicitly included in this SF and will be forcibly migrated to standard string return types.*

## 2. Proposed Changes

### 2.1 New File: `src/specweaver/workspace/parsers/base.py`
Create `BaseTreeSitterParser` which implements `CodeStructureInterface`.
- **Properties**: `language` and `parser` must be initialized by subclasses.
- **Class Attributes**: Subclasses must provide `SCM_SKELETON_QUERY`, `SCM_SYMBOL_QUERY`, `SCM_IMPORT_QUERY`, `SCM_COMMENT_QUERY`.
- **Core Methods**: Move the generic implementations of `extract_skeleton`, `extract_symbol`, `extract_symbol_body`, `extract_imports`, `list_symbols`, and `extract_traceability_tags` here.
- **Mutation Hooks**: 
  - `replace_symbol`, `replace_symbol_body`, `add_symbol`, `delete_symbol` will handle the generic Tree-sitter bounds resolution.
  - They will delegate the actual string formatting to subclass hooks: `_format_replacement(self, new_code: str, margin: int) -> bytes` and `_format_body_injection(self, new_code: str, margin: int) -> bytes`.

### 2.2 Modify Parsers
Modify the following to inherit from `BaseTreeSitterParser` instead of `CodeStructureInterface`:
- `src/specweaver/workspace/parsers/python/codestructure.py`
- `src/specweaver/workspace/parsers/java/codestructure.py`
- `src/specweaver/workspace/parsers/typescript/codestructure.py`
- `src/specweaver/workspace/parsers/rust/codestructure.py`
- `src/specweaver/workspace/parsers/kotlin/codestructure.py`
- `src/specweaver/workspace/parsers/markdown/codestructure.py`

For each, delete the duplicated `extract_*` methods and define the required SCM query string constants and formatting hooks. Markdown's `extract_skeleton` must be rewritten to output strings, not JSON.

## 3. Testing Strategy
No new tests are required. The definition of success for SF-1 is that the existing polyglot test suite passes with 100% parity.
- Run: `pytest tests/unit/workspace/parsers/`
- Run: `pytest tests/e2e/` (To ensure context condensation and macro evaluator integrations remain stable).

## Research Notes
- Python uses whitespace indentation, whereas Java/Rust/TS use curly braces `{}`. The generic mutation methods (`replace_symbol_body`) cannot blindly inject strings without knowing the language's block wrapper rules. The base class MUST expose formatting hooks for subclasses to handle indentation vs braces.
- Markdown currently violates the `extract_skeleton` return type by returning JSON instead of a raw text skeleton. It must be excluded from this strict refactoring and handled separately in SF-2.
