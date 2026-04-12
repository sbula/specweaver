# Implementation Plan: Polyglot AST Skeleton Extractor [SF-2: AST Symbol Writer]
- **Feature ID**: 3.22
- **Sub-Feature**: SF-2 — AST Symbol Writer (Write Side)
- **Design Document**: docs/roadmap/phase_3/feature_3_22/feature_3_22_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-2
- **Implementation Plan**: docs/roadmap/phase_3/feature_3_22/feature_3_22_sf2_implementation_plan.md
- **Status**: APPROVED

## 1. Goal Description

Implement the **CodeStructureTool: Write Side** capability requested in Sub-Feature 2. This introduces granular mutational routing (`replace_symbol`, `replace_symbol_body`, `add_symbol`, and `delete_symbol`) across the 5 language AST schemas (Python, TS, Java, Kotlin, Rust) allowing an LLM Agent to safely and surgically inject, delete, or replace AST symbols directly on disk without generating complex regex expressions or loading full file blobs into context windows.

## 2. Proposed Changes

### 2.1. Interfaces & Definitions

#### [MODIFY] src/specweaver/loom/commons/language/interfaces.py
- Add `@abstractmethod def replace_symbol(self, code: str, symbol_name: str, new_code: str) -> str:` to `CodeStructureInterface`.
- Add `@abstractmethod def replace_symbol_body(self, code: str, symbol_name: str, new_code: str) -> str:`.
- Add `@abstractmethod def add_symbol(self, code: str, target_parent: str | None, new_code: str) -> str:`.
- Add `@abstractmethod def delete_symbol(self, code: str, symbol_name: str) -> str:`.

#### [MODIFY] src/specweaver/loom/tools/code_structure/definitions.py
- Add `REPLACE_SYMBOL_SCHEMA`, `REPLACE_SYMBOL_BODY_SCHEMA`, `ADD_SYMBOL_SCHEMA`, and `DELETE_SYMBOL_SCHEMA` as definitions.
- Expose the definitions into `get_code_structure_schema()`.

### 2.2. Polyglot Parsers

#### [MODIFY] src/specweaver/loom/commons/language/python/codestructure.py
- Implement the 4 mutation methods.
- **Logic**: Use the robust parent-walking logic present in `extract_symbol` to identify the `start_byte` and `end_byte` bounds.
> [!NOTE]
> **Auto-Indentation (Format Fixing):** For Python `replace` and `add` operations, the parser will extract the relative `start_point[1]` integer margin of the target node and automatically prepend those boundary spaces iteratively to every newline inside the LLM's raw `new_code` string before performing the `utf-8` splice, fully shielding the system from `IndentationError` crashes.

#### [MODIFY] src/specweaver/loom/commons/language/{java,kotlin,rust,typescript}/codestructure.py
- Replicate the exact bounded slice logic applied in the Python parser since all 5 parsers resolve `name_node.parent` identically to find boundaries.

### 2.3. Atoms & Tools

#### [MODIFY] src/specweaver/loom/atoms/code_structure/atom.py
- Map intents for `replace_symbol`, `replace_symbol_body`, `add_symbol`, and `delete_symbol` in `run()`.
- Generate mutated AST byte-string payload by calling the internal `parser.<intent>()` method.
> [!NOTE]
> **Dual-Consumer Architecture Override:** `CodeStructureAtom` is explicitly authorized to execute `self._executor.write(path, mutated_code)` atomically, safely breaking the parallel-mechanism isolation rule to avoid catastrophic complexity in the orchestrator.
- Return `AtomResult(SUCCESS)` reflecting the physical mutation.

#### [MODIFY] src/specweaver/loom/tools/code_structure/tool.py
- Register the 4 mutational intents inside `ROLE_INTENTS` mapping for the `implementer` role.
- Map the agent facade explicitly to `self._atom.run()`.
- Implement rigorous pre-flight `.check_grant()` mapped against `AccessMode.WRITE` or `AccessMode.FULL` permissions.

## 3. Research Notes

- **Tree-Sitter Bytes**: `tree-sitter` inherently isolates node boundaries natively through `.start_byte` and `.end_byte` coordinates. This eliminates the need for regex matching lines or indentations entirely. We can literally slice the `utf-8` bytecode blob up to `start_byte`, insert the `new_code` payload, and stitch the remaining file payload from `end_byte` to the EOF smoothly.
- **Persistence Access**: `CodeStructureAtom` is already instantiated with `FileExecutor`. Thus, persisting the mutated string straight to the filesystem is natively supported and bypasses circular dependency tool injection.

## 4. Audit & Architectural Findings

- **Resolved (Formatting)**: Auto-Indentation adopted in AST Parsers to prevent LLM hallucination crashes.
- **Resolved (Architectural Rule)**: Approved Dual-Consumer bypass allowing Atom isolation persistence. 
- **Resolved (Symbol Replace Scope)**: Adopted 4 independent precise actions replacing the primitive `write_symbol`: `replace_symbol`, `replace_symbol_body`, `add_symbol`, `delete_symbol`.

## 5. Verification Plan

### Automated Tests
- Implement `test_write_symbol_python`, `test_write_symbol_typescript`, `test_write_symbol_java`, `test_write_symbol_rust`, and `test_write_symbol_kotlin` natively inside `test_polyglot_ast_edge_cases.py` ensuring exact byte replacement.
- Execute unit and integration loops universally.
> ✅ **SF-2 Phase 1 (Python) Complete:** Unit and Integration tests implemented for python edge cases. JVM/Rust to follow in Boundary 2.
> ✅ **SF-2 Phase 2 (Polyglot) Complete:** Unit and Integration edge case tests implemented for JVM/Rust/TS reaching 75% coverage.
> ✅ **SF-2 Phase 3 (Engine Bindings) Complete:** Boundary 3 completed. All polyglot edge cases and integration boundaries are hardened and pass E2E matrix.
