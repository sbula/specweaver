# Implementation Plan: Smart Scan Exclusions (Tiered) [SF-2: Orchestration Factory & Scaffolding]
- **Feature ID**: 3.32b
- **Sub-Feature**: SF-2 — Orchestration Factory & Scaffolding
- **Design Document**: docs/roadmap/features/topic_02_sensors/C-SENS-02_design.md
- **Design Section**: §Sub-Feature Decomposition & Technical Debt Refactoring → SF-2: Orchestration Factory & Scaffolding
- **Implementation Plan**: docs/roadmap/features/topic_02_sensors/C-SENS-02_sf2_impl_plan.md
- **Status**: FULLY IMPLEMENTED (Pre-commit complete)

## Proposed Changes

> [!WARNING]
> **Strict Architectural Deferment**: `src/specweaver/workspace/context/context.yaml` maps the entire `context/` module as an `archetype: contract`. However, `analyzers.py` currently executes physical `.glob()` and `.read_text()` OS operations natively! This is a massive boundary violation that triggers the Pre-Commit Quality gates. 
> **CRITICAL RULE FOR EXECUTING AGENT:** Do NOT attempt to refactor the file I/O operations out of `analyzers.py` during SF-2! This violation is **formally deferred to SF-4**, which physically moves the module out to `workspace/analyzers/` (Adapter Layer). Leave the violation as-is and strictly execute the SF-2 scope.

---
### 1. Abstract Interfaces & Union Scaffolding
#### [MODIFY] `src/specweaver/workspace/context/analyzers.py`
- **`LanguageAnalyzer` ABC:** Add `@abstractmethod def get_binary_ignore_patterns(self)` and `@abstractmethod def get_default_directory_ignores(self)` to enforce exclusion guarantees across all integrated languages.
- **`TreeSitterAnalyzerBase`:** Implement both methods linearly by delegating to `self.parser.get_binary_ignore_patterns()` and `self.parser.get_default_directory_ignores()`.
- **`AnalyzerFactory`:** Introduce a robust classmethod `@classmethod def get_all_analyzers(cls) -> list[LanguageAnalyzer]` to expose the total internal Polyglot union seamlessly (Python, TS, Java, Rust, Kotlin).

#### [MODIFY] `tests/unit/workspace/context/test_analyzers.py`
- Assert that `AnalyzerFactory.get_all_analyzers()` returns exactly 5 polyglot instances.
- Assert that `LanguageAnalyzer.get_default_directory_ignores()` bridges successfully across a mock Analyzer down to its code structure parser.

---
### 2. Scaffold `.specweaverignore` Globals
#### [MODIFY] `src/specweaver/workspace/project/scaffold.py`
- Within `scaffold_project(project_path: Path)`:
  - Dynamically iterate over `AnalyzerFactory.get_all_analyzers()`.
  - Compile the `default_directories` flat list.
  - Instantiate `SpecWeaverIgnoreParser(project_path)` from `specweaver.workspace.ast.parsers.exclusions`.
  - Fire `ensure_scaffolded(default_directories)`.
  - Inject `".specweaverignore"` natively into the tracking array if newly created.

#### [MODIFY] `tests/unit/workspace/project/test_scaffold.py`
- Assert that calling `scaffold_project` natively generates a `.specweaverignore` containing `__pycache__/`, `target/`, and `node_modules/` implicitly.
- Assert idempotency: subsequent scaffold runs do not erase existing custom user patterns within the ignore file.
