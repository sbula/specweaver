# Feature 3.32e: Polyglot Expansion

## 1. Feature Overview

**Working Definition:**
Feature 3.32e adds Tree-sitter based AST parsers for C/C++, Go, and Standard SQL to the `workspace/ast/parsers` subsystem. It solves the lack of structural analysis for these high-value enterprise languages (Systems, Cloud-Native, and DB Context Harness) by implementing `CodeStructureInterface` for each using standard Tree-sitter grammars. It interacts with the `factory.py` registry and the `CodeStructureAtom` and explicitly avoids SQL dialect permutations by sticking to ANSI Standard SQL. Key constraints: Must use Tree-sitter, must adhere strictly to standard grammars, must avoid dialects.

---

## 2. Refactoring & ROI Analysis

**Background:**
Currently, SpecWeaver supports Python, Java, Kotlin, TypeScript, Rust, and Markdown. Each of these implements `CodeStructureInterface` independently.
Our codebase audit revealed that the text-manipulation logic (`extract_skeleton`, `extract_symbol`, `replace_symbol`, `delete_symbol`, `list_symbols`) inside these classes (e.g., `PythonCodeStructure` which is 432 lines long) is nearly identical. The only true differences between languages are the Tree-sitter Language bindings and the `.scm` (Scheme) query strings used to locate nodes.

**Proposed Refactoring:**
Before adding 4 new parsers (C, C++, Go, SQL), we should extract a `BaseTreeSitterParser(CodeStructureInterface)` class. This base class will handle all the byte-level encoding, `QueryCursor` matching, auto-indentation, and AST mutation logic. Concrete language classes will simply define `SCM_SKELETON_QUERY`, `SCM_SYMBOL_QUERY`, etc., and initialize their specific `Language` object.

**ROI Analysis (Pros/Cons):**
*   **Pros:**
    *   **Massive Redundancy Reduction:** Eliminates ~2000 lines of duplicated AST manipulation code across existing languages.
    *   **Future-Proofing:** Adding new languages (like C/C++, Go, SQL) becomes a trivial exercise of writing declarative `.scm` queries rather than imperative Python byte-manipulation.
    *   **Consistency:** Fixes to tree-sitter node bounds or whitespace handling will automatically propagate to all supported languages.
    *   **Existing Features Profit:** Phase 3.30 (Macro Evaluator) and Phase 3.32a (Context Condensation) will inherit a much more robust and unified text-mutation engine.
*   **Cons:**
    *   Requires touching all existing stable parsers, meaning we must run the full polyglot AST integration test suite to verify no regressions occur during the migration.
*   **Recommendation:** This refactoring should be **SF-1**. It perfectly aligns with the `pure-logic` archetype of the `workspace/ast/parsers` module and provides immense architectural leverage for this feature and all future language expansions.

---

## 3. Functional Requirements (FRs)

*   **FR-1:** The system SHALL provide a `BaseTreeSitterParser` that encapsulates all `CodeStructureInterface` generic AST mutation logic.
*   **FR-2:** The system SHALL parse C and C++ source files using `tree-sitter-c` and `tree-sitter-cpp` to extract skeletons, symbols, imports, and traceability tags via declarative `.scm` queries.
*   **FR-3:** The system SHALL parse Go source files (`.go`) using `tree-sitter-go` to extract skeletons, symbols, imports, and traceability tags.
*   **FR-4:** The system SHALL parse Standard SQL source files (`.sql`) using `tree-sitter-sql` to extract structural schemas (tables/views) and symbols (functions/procedures).
*   **FR-5:** The system SHALL complete the existing `MarkdownCodeStructure` stub, ensuring it implements the full `CodeStructureInterface` (including traceability tag extraction and symbol mutation) using the new `BaseTreeSitterParser`.
*   **FR-6:** The system SHALL register all new file extensions in `specweaver.workspace.ast.parsers.factory.get_default_parsers()`.
*   **FR-7:** The system SHALL dynamically prune `ToolDefinition` schemas (e.g. hiding `decorator_filter` or `extract_framework_markers`) if no active language parser supports them, ensuring agents never see useless capabilities.

---

## 4. Non-Functional Requirements (NFRs)

*   **NFR-1 (Compatibility):** The new grammars must be fully compatible with `tree-sitter >= 0.25.2` as mandated by the current `pyproject.toml`.
*   **NFR-2 (Architecture Boundaries):** The implementations MUST reside strictly within `specweaver.workspace.ast.parsers` and implement the `CodeStructureInterface`. No sandbox I/O is permitted (`pure-logic`).
*   **NFR-3 (Dialect Agnosticism):** The SQL parser MUST stick to ANSI Standard SQL. It SHALL NOT attempt to polyfill proprietary pgSQL or T-SQL syntax unless it is natively supported by the standard `tree-sitter-sql` grammar.

---

## 5. Sub-Feature Decomposition & Progress Tracker

| Sub-Feature | ID | Dependencies | Impl Plan | Dev | Pre-Commit | Committed |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **AST Base Class Refactoring** | SF-1 | None | ✅ | ✅ | ✅ | ✅ |
| **Markdown Parser Completion** | SF-2 | SF-1 | ✅ | ✅ | ✅ | ✅ |
| **C/C++ Parser Implementation** | SF-3 | SF-1 | ✅ | ✅ | ✅ | ✅ |
| **Go Parser Implementation** | SF-4 | SF-1 | ✅ | ✅ | ✅ | ✅ |
| **SQL Parser Implementation** | SF-5 | SF-1 | ✅ | ✅ | ✅ | ⬜ |

---

## 6. Session Handoff
Status: **COMPLETED**
The implementation plan for SF-5 (SQL Parser Implementation) is complete and approved.
Next Step: Run `/dev docs/roadmap/features/topic_02_sensors/D-SENS-03/D-SENS-03_sf5_implementation_plan.md` to begin implementation of SF-5.
