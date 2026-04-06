# Implementation Plan: Polyglot AST Skeleton Extractor [SF-1]
- **Feature ID**: 3.22
- **Sub-Feature**: SF-1 — Polyglot AST Extractor
- **Design Document**: docs/proposals/roadmap/phase_3/feature_3_22/feature_3_22_design.md
- **Implementation Plan**: docs/proposals/roadmap/phase_3/feature_3_22/feature_3_22_sf1_implementation_plan.md
- **Status**: DRAFT

## 1. Goal Description

Implement SF-1: Polyglot AST Extractor to solve "Context Window Bloat" without triggering LLM memory hallucinations. We are introducing a new **CodeStructureTool** and its backing **AstAtom** to provide `read_file_structure` and `read_symbol` capabilities. All language-specific definitions (such as `.scm` Tree-Sitter queries and AST parsers) will be housed within the newly consolidated `loom/commons/language/` registry to ensure strict separation between Pure Logic consumption and C-Binary I/O execution.

## 2. Proposed Changes

### Component 1: Language Commons Refactoring (The Migration)
*Consolidates QA Runners and unlocks AST parsing by moving language brains up one directory level.*

#### [MODIFY] `src/specweaver/loom/commons/language/<lang>/` (Migration)
This is a required structural refactor. The current `qa_runner` acts as a vertical silo. We must promote languages to a horizontal commons:
1. **Move:** Migrate `src/specweaver/loom/commons/qa_runner/python/` entirely to `src/specweaver/loom/commons/language/python/runner.py`.
2. **Move:** Migrate all other existing `qa_runner` plugins (TypeScript, Java, Kotlin, Rust) into their respective `language/<lang>/runner.py` destinations.
3. **Refactor Imports:** Update `QARunnerFactory`, `QARunnerAtom`, and `QARunnerTool` to import from the newly consolidated `commons/language/` hierarchy.
4. **Verify:** Run all tests to ensure the `qa_runner` works identically before proceeding.

### Component 1b: The AST Parsers (New)
#### [NEW] `src/specweaver/loom/commons/language/<lang>/ast_parser.py`
- Create AST definitions alongside the newly migrated runners.
- Store the `.scm` Tree-Sitter queries (`@definition.function`, `@definition.class`) inside the file or as adjacent `.scm` files.
- Provide a standard interface: `extract_skeleton(code: str) -> str` and `extract_symbol(code: str, symbol: str) -> str`.

### Component 2: The Atom (Trusted Engine I/O)
*Provides unrestricted execution of the AST engine for SpecWeaver internal use.*

#### [NEW] `src/specweaver/loom/atoms/code_structure/atom.py`
- Implements `AstAtom` inheriting from `Atom`.
- Provides `run_extract_skeleton(path: str)` and `run_extract_symbol(path: str, symbol: str)`.
- **Flow:** Uses `FileExecutor` to read the file string, dynamically dispatches to the correct language parser in `commons/language/`, executes the `.scm` query, and formats the output.
- **Dependency:** Strictly imports from `commons/language`.

### Component 3: The Tool (Agent Interface)
*Provides sandboxed, role-gated access for the LLM.*

#### [NEW] `src/specweaver/loom/tools/code_structure/tool.py`
- Implements `CodeStructureTool`.
- Contains intents: `read_file_structure` and `read_symbol`.
- **Validation:** Verifies `FolderGrant` and checks `ROLE_INTENTS` before delegating to the `AstAtom`.

#### [NEW] `src/specweaver/loom/tools/code_structure/interfaces.py`
- Defines `ReviewerCodeStructureInterface` and `ImplementerCodeStructureInterface` ensuring physical absence of unauthorized tools.

#### [NEW] `src/specweaver/loom/tools/code_structure/definitions.py`
- Provides the exact JSON Schema for the LLM. 
- Example: `"name": "read_file_structure", "description": "Returns only the signatures and docstrings of a file, stripping implementation bodies to save tokens."`

### Component 4: Integration
*Plumbing the tool into the agent workflows.*

#### [MODIFY] `src/specweaver/loom/dispatcher.py`
- Register `CodeStructureTool` and its intents to make them active across the LLM prompt handlers.

#### [MODIFY] `src/specweaver/flow/_review.py` & `flow/_generation.py`
- Ensure the `CodeStructureTool` is appended to the available toolbox for the Reviewer and Implementer LLMs. 

---

## 3. Implementation Caveats (`[!WARNING]`)

> [!WARNING]
> **Missing SCM Queries Fallback:**
> If `AstAtom` encounters a file type (e.g., `.yaml`) with no registered parser, it must NOT fail silently or default to full-file reading. It must raise an explicit `CodeStructureError`: `"AST Structure Extraction not supported for .yaml files. Please use read_file."`

> [!WARNING]
> **No Write Capabilities (Deferred to SF-2):**
> Do not attempt to implement `write_symbol` in this plan. Safely patching AST nodes requires significantly higher complexity and is explicitly scoped out of SF-1 to prevent scope creep.

## 4. Verification Plan

### Automated Tests
1. **Unit Tests (`tests/unit/loom/commons/language/python/test_ast.py`)**: 
   - Feed raw Python string fixtures into the parser. Verify that standard methods return their signatures and stripped bodies exactly.
2. **Integration Tests (`tests/integration/loom/tools/code_structure/test_tool.py`)**:
   - Provide a dummy project workspace. Fire `read_file_structure` intent from the tool. Assert JSON output limits and folder-grant boundary enforcement.

### Manual Verification
- Execute `sw review` against a dirty spec. Ensure the Agent chooses to use `read_file_structure` instead of `read_file`, and successfully reads the returned skeleton without hallucinating the file's remaining body.
