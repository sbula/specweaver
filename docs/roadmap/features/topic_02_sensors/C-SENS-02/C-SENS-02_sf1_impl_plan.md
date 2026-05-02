# Implementation Plan: Smart Scan Exclusions (Tiered) [SF-1: Pure Logic Definitions & Ignorance Parser]
- **Feature ID**: 3.32b
- **Sub-Feature**: SF-1 — Pure Logic Definitions & Ignorance Parser
- **Design Document**: docs/roadmap/features/topic_02_sensors/C-SENS-02_design.md
- **Status**: APPROVED

---

## Proposed Changes

### 1. External Dependencies
#### [x] [MODIFY] `pyproject.toml`
- Add `pathspec = "^0.12.0"` to the core dependencies.
- Add `pytest-pathspec` to `dev` constraints if mocking paths are required.

### 2. Interface Definitions (Pure Logic)
#### [x] [MODIFY] `src/specweaver/workspace/ast/parsers/interfaces.py`
- Update `CodeStructureInterface`:
  - Add abstract method: `def get_binary_ignore_patterns(self) -> list[str]: ...`
  - Add abstract method: `def get_default_directory_ignores(self) -> list[str]: ...`

### 3. Polyglot Target Implementations
#### [x] [MODIFY] `src/specweaver/workspace/ast/parsers/python/codestructure.py`
- In `PythonCodeStructure`: Return `["*.pyc", "*.pyo", "*.pyd"]` and `["__pycache__/", ".pytest_cache/", ".tox/", ".venv/"]`.
#### [x] [MODIFY] `src/specweaver/workspace/ast/parsers/java/codestructure.py`
- In `JavaCodeStructure`: Return `["*.class", "*.jar", "*.ear", "*.war"]` and `["target/", "build/"]`.
#### [x] [MODIFY] `src/specweaver/workspace/ast/parsers/kotlin/codestructure.py`
- In `KotlinCodeStructure`: Return `["*.class", "*.jar"]` and `["target/", "build/", ".gradle/"]`.
#### [x] [MODIFY] `src/specweaver/workspace/ast/parsers/rust/codestructure.py`
- In `RustCodeStructure`: Return `["*.rlib", "*.so", "*.dll", "*.pdb"]` and `["target/"]`.
#### [x] [MODIFY] `src/specweaver/workspace/ast/parsers/typescript/codestructure.py`
- In `TypeScriptCodeStructure`: Return `[]` (Node runs source) and `["node_modules/", "dist/", "build/", "out/"]`.

### 4. Mathematical Pathspec Aggregator
#### [x] [NEW] `src/specweaver/workspace/ast/parsers/exclusions.py`
*(Note: Because `workspace/ast/parsers` is natively `pure-logic`, it legally hosts the mathematical Regex Tree generation for pathspec without violating the `contract` constraints of `workspace/context`. The actual OS traversal reading `.specweaverignore` from disk will be safely injected later during SF-4).*
- Create `SpecWeaverIgnoreParser` class:
  - Takes `project_root: Path` solely for referencing the `.specweaverignore` physical read (Permitted lookup logic prior to cache locking).
  - Method `ensure_scaffolded(default_directories: list[str]) -> None`: Safe append logic.
  - Method `get_compiled_spec(runtime_patterns: list[str]) -> pathspec.PathSpec`: Combines the text in ignore files with runtime bounds.

---

## Verification Plan

### Automated Tests
- Run `pytest tests/workspace/context/test_exclusions.py` (to be created natively during `/dev`). 
- Assert `get_compiled_spec` deterministic matching. 
- Assert `CodeStructureInterface` subclass validation using abstract bounds.

> **CRITICAL DEVELOPER RULE**: 
> @[/pre-commit]
> You must physically invoke the pre-commit workflow explicitly before committing to branch. 

---

# [Workflow: /implementation-plan] Phase 5: Final Consistency Check

### 5.1. Open Questions & Agent Handoff Risk
- **Unresolved Decisions:** None. All design drift (Pathspec optionally vs strictly, SF-1 vs SF-3 overlap, and Workspace/Context I/O bounds) have been definitively boxed out. 
- **Agent Handoff Risk:** None. The next Agent dropping into `/dev` will clearly see that it ONLY implements the `CodeStructureInterface` extensions and builds `exclusions.py`. The creation of SF-4 explicitly signals the subsequent agent *not* to refactor `discovery.py` or the `AnalyzerFactory` DI injection during SF-1.

### 5.2. Architecture and Future Compatibility
- **Tach Bounds:** No circular dependencies introduced. Adding methods to `interfaces.py` and `codestructure` subclasses perfectly respects the `pure-logic` constraints. Creating `exclusions.py` does not cross into `loom/` (forbidden).
- **Roadmap Soundness:** Because we deferred the strict decoupling of `AnalyzerFactory` into the discrete **SF-4**, SF-1 acts as a pure mathematical foundation for topological exclusion logic. This lays down identical prerequisites required by **Feature 3.33** (PostgreSQL Graph) bounding.

### 5.3. Internal Consistency
- Every physical file proposed has concrete inputs and outputs tagged linearly in Section 3. 
- We are exclusively introducing pure-logic abstractions and parsing engines. 
