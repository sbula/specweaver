# Implementation Plan: Smart Scan Exclusions [SF-3: Technical Debt Refactoring]
- **Feature ID**: 3.32b
- **Sub-Feature**: SF-3 — Technical Debt Refactoring
- **Design Document**: docs/roadmap/phase_3/feature_3_32b_design.md
- **Design Section**: Sub-Feature Breakdown — SF-3
- **Implementation Plan**: docs/roadmap/phase_3/feature_3_32b_sf3_impl_plan.md
- **Status**: DRAFT

## Goal Description
Perform structural technical debt sweeps across the repository to seamlessly integrate the new polyglot orchestrator boundaries created in SF-2. This involves removing all temporary hardcoded Python glob exclusions and integrating pure polyglot hooks into `validation`, file system tooling (`loom`), boundary discovery (`assurance.standards`), and graph hashing (`assurance.graph.hasher`).

## Proposed Changes

---

### `specweaver.workspace.parsers`
Extends the tree-sitter abstraction layer to support polyglot AST traversal for traceability tags (`# @trace(FR-XX)` and `// @trace(FR-XX)`).

#### [MODIFY] `interfaces.py` (file:///C:/development/pitbula/specweaver/src/specweaver/workspace/parsers/interfaces.py)
- **Modifications**: 
  - `[x]` Add `extract_traceability_tags(self, code: str) -> set[str]` to `CodeStructureInterface`.

#### [MODIFY] `python/codestructure.py` (file:///C:/development/pitbula/specweaver/src/specweaver/workspace/parsers/python/codestructure.py)
- **Modifications**:
  - `[x]` Implement `extract_traceability_tags` for Python by inspecting tree-sitter `comment` nodes for `@trace()` patterns.

#### [MODIFY] `java/codestructure.py` / `kotlin/codestructure.py` / `rust/codestructure.py` / `typescript/codestructure.py` (file:///C:/development/pitbula/specweaver/src/specweaver/workspace/parsers/.../codestructure.py)
- **Modifications**:
  - `[x]` Implement `extract_traceability_tags` using respective tree-sitter semantics for each language's comment nodes.

---

### `specweaver.workspace.context`
Polyglot context analyzer wrappers for the parsers.

#### [MODIFY] `analyzers.py` (file:///C:/development/pitbula/specweaver/src/specweaver/workspace/context/analyzers.py)
- **Modifications**:
  - `[x]` Add `extract_test_mapped_requirements(self, directory: Path) -> set[str]` to the `LanguageAnalyzer` ABC.
  - `[x]` Implement it in `TreeSitterAnalyzerBase`. It will natively iterate over standard test file patterns for its language (e.g. `*Test.java` vs `test_*.py`) from the `directory`, invoke the parser's `extract_traceability_tags`, and return the unified mapping.

---

### `specweaver.core.loom`
Physical execution adapters (`search.py` ripgrep timeout prevention and dispatcher DI).

#### [MODIFY] `commons/filesystem/search.py` (file:///C:/development/pitbula/specweaver/src/specweaver/core/loom/commons/filesystem/search.py)
- **Modifications**:
  - Modify `grep_content` and `find_by_glob` and `iter_text_files` to accept `exclude_dirs: set[str] | None = None`.
  - In `_grep_ripgrep`, pass `--ignore-file .specweaverignore` if the file exists structurally.
  - In `find_by_glob` and `iter_text_files`, refactor `search_dir.rglob` logic into an `os.walk`-based recursion that actively drops directories matching `exclude_dirs`.

#### [MODIFY] `tools/filesystem/interfaces.py` and `tools/filesystem/tool.py` (file:///C:/development/pitbula/specweaver/src/specweaver/core/loom/tools/filesystem/interfaces.py)
- **Modifications**:
  - `FileSystemTool.__init__` and `create_filesystem_interface` to accept `exclude_dirs`. They thread it implicitly down into the `search.py` methods during tool calls.

#### [MODIFY] `dispatcher.py` (file:///C:/development/pitbula/specweaver/src/specweaver/core/loom/dispatcher.py)
- **Modifications**:
  - Inside `create_standard_set`, instantiate `AnalyzerFactory.get_all_analyzers()` and aggregate both `get_default_directory_ignores()` and `get_binary_ignore_patterns()` dynamically. Inject these arrays exclusively into the filesystem interface payload context as `exclude_dirs` and `exclude_patterns`.

---

### `specweaver.assurance.standards`
Discovery boundary implementation.

#### [MODIFY] `discovery.py` (file:///C:/development/pitbula/specweaver/src/specweaver/assurance/standards/discovery.py)
- **Modifications**:
  - Delete `_SKIP_DIRS`.
  - In `_walk_with_skips`, fetch the aggregated global Polyglot Exclusions (`get_default_directory_ignores` and `get_binary_ignore_patterns`) dynamically via `AnalyzerFactory.get_all_analyzers()`. Replace `_SKIP_DIRS` with this mathematically correct set + explicit dotfile checks. Filter files by extensions not in binary ignores.

---

### `specweaver.assurance.graph`
Semantic topological hashing operations.

#### [MODIFY] `hasher.py` (file:///C:/development/pitbula/specweaver/src/specweaver/assurance/graph/hasher.py)
- **Modifications**:
  - Replace the unbounded `directory.rglob("*")` inside `DependencyHasher._hash_directory` with `os.walk` or a bounded directory-pruning operation using `AnalyzerFactory` exceptions and `pathspec` for `.specweaverignore`.

---

### `specweaver.assurance.validation`
C09 validation Rule logic.

#### [MODIFY] `rules/code/c09_traceability.py` (file:///C:/development/pitbula/specweaver/src/specweaver/assurance/validation/rules/code/c09_traceability.py)
- **Modifications**:
  - `[x]` Remove direct `tree_sitter_python` logic and hardcoded Python `test_*.py` globs.
  - `[x]` Change `_find_and_parse_tests` to iterate across all instances from `AnalyzerFactory.get_all_analyzers()` and accumulate `mapped_ids.update(analyzer.extract_test_mapped_requirements(project_root))`.
  - `[x]` The validation algorithm, comparisons, and rule constraints remain permanently untouched in `validation`.

---

## Verification Plan

### Automated Coverage 
- Executing `pytest tests/unit/workspace/context/test_analyzers.py -v` to ensure the extended AST parsing catches `@trace()` properly across all languages.
- Executing `pytest tests/unit/assurance/validation/test_c09_traceability.py -v` to explicitly verify C09 remains blind to languages while keeping identical outputs.
- Executing `pytest tests/unit/core/loom/commons/filesystem/test_search.py -v` to ensure the timeout preventions fire successfully on `os.walk`.

### Manual Validation
- Run `/pre-commit` to ensure code checks execute fast sequentially.
- Perform an end-to-end sandbox run checking for architecture leaks via `tach check`.
