# Implementation Plan: Deep Semantic Hashing [SF-1: Polyglot Parser Decoupling]
- **Feature ID**: 3.32
- **Sub-Feature**: SF-1 — Polyglot Parser Decoupling
- **Design Document**: docs/roadmap/phase_3/feature_3_32/feature_3_32_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-1
- **Implementation Plan**: docs/roadmap/phase_3/feature_3_32/feature_3_32_sf1_implementation_plan.md
- **Status**: APPROVED

## Goal Description
Technical debt has resulted in 3 parallel AST implementations across SpecWeaver, breaking polyglot capabilities for Workspace topology. This plan completely resolves this technical debt by decoupling the state-of-the-art Tree-Sitter polyglot extractors out of the restricted `loom` sandbox and moving them into a native `pure-logic` boundary at `workspace/parsers/`. 

This enables native, high-speed AST dependency hashing for Java, Kotlin, Python, Rust, and TypeScript (required for the subsequent SF-2 Semantic Hasher) without violating `dmz` consumption rules.

## Proposed Changes

---

### Component: Workspace Parsers (New)

The new home for all pure-logic Tree-Sitter parsers, moved out of the `loom` execution boundary.

#### [NEW] `src/specweaver/workspace/parsers/context.yaml`
- Set `name: parsers`, `level: module`, `archetype: pure-logic`.
- `consumes: []`
- `forbids: [specweaver/loom/*]`
- `exposes: [interfaces]`

#### [MODIFY] `src/specweaver/workspace/parsers/interfaces.py`
- **Move** from `core/loom/commons/language/interfaces.py`.
- **Action**: Add a new protocol method: `extract_imports(self, code: str) -> list[str]` to the `CodeStructureInterface`. Ensure the query targets only standard imports.

#### [NEW/MOVE] `src/specweaver/workspace/parsers/<language>/codestructure.py`
- **Action**: DO NOT move the entire language folders! You must manually move ONLY the `codestructure.py` (and any related `parsers.py` utility files) from `core/loom/commons/language/<lang>/` to `workspace/parsers/<lang>/`.
- **Action**: Leave `runner.py`, `scenario_converter.py`, and `stack_trace_filter.py` securely inside `core/loom/commons/language/<lang>/` (they are physical execution adapters).
- **Action**: Add an `extract_imports` method to each `codestructure.py` using language-specific Tree-Sitter `.scm` nodes (e.g. `import_statement` in python/ts, `import_declaration` in java).

---

### Component: Workspace Context

Refactoring the inferrer pipelines to use the new polyglot parsers.

#### [MODIFY] `src/specweaver/workspace/context/context.yaml`
- **Action**: Add `specweaver/workspace/parsers` to `consumes`.

#### [MODIFY] `src/specweaver/workspace/context/analyzers.py`
- **Action**: Completely delete the legacy `ast`-based `PythonAnalyzer`. 
- **Action**: Refactor `LanguageAnalyzer` and `AnalyzerFactory` to act as direct proxies mapping to the Tree-Sitter parsers in `workspace/parsers/`.
- **Action**: Ensure `extract_imports` seamlessly delegates the query to the active tree-sitter interface. All 5 languages must be uncommented and activated.
- **Action**: Update `infer_archetype` for all 5 languages to securely apply standard library heuristics (Java: `java.*`/`javax.*`, Rust: `std::*`, etc.) to the raw Tree-Sitter imports. This correctly classifies imports of frameworks (like Spring/FastAPI) as `adapter` archetypes, while keeping the underlying parsers oblivious to SpecWeaver's business rules.

---

### Component: Loom Language Commons

Cleaning up the Agent execution boundaries after the move.

#### [MODIFY] `src/specweaver/core/loom/commons/language/context.yaml`
- **Action**: Add `specweaver/workspace/parsers` to `consumes`.
- **Action**: Remove any mentions of "AST Parsing" or "Pure Logic" from the descriptions. This module is now strictly for physical execution (runners and scenario converters).

#### [MODIFY] `src/specweaver/core/loom/commons/language/evaluator.py`
- **Action**: Update imports to point to `specweaver.workspace.parsers.interfaces`.

#### [MODIFY] `src/specweaver/core/loom/atoms/code_structure/atom.py`
- **Action**: Update imports to point to `specweaver.workspace.parsers.interfaces`.

---

### Component: Assurance Standards

Deduplicating parallel Tree-Sitter engine initializations.

#### [MODIFY] `src/specweaver/assurance/standards/tree_sitter_base.py`
- **Action**: Delete any custom grammar language loaders. 
- **Action**: Import and inherit the grammar logic securely from `workspace/parsers` to ensure only one instance of the heavy C-bindings is instantiated per language across the entire SpecWeaver process.

---

## Verification Plan

### Automated Tests
- Run `pytest tests/workspace/context/test_analyzers.py` to assert the auto-inferrer gracefully reads TypeScript imports.
- Run `pytest tests/core/loom/atoms/test_code_structure.py` to prove the Agent atoms still accurately synthesize AST boundaries.
- Run `tach check` globally to assert that moving the parsers resolved all cyclic dependencies and obeyed `forbids` boundaries in `context.yaml`.

### Clean-Up Verification
- Perform a final git diff to verify no `tree_sitter` or `LanguageAnalyzer` duplicate loops remain in `analyzers.py`.
