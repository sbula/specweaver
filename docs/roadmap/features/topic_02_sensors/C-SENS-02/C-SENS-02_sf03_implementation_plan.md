# C-SENS-02 SF-03 — Technical Debt Refactoring

**Status**: COMPLETED · **Feature ID**: 3.32b · **Depends on**: SF-02 ·
Design: [C-SENS-02_design.md](C-SENS-02_design.md) §Sub-features → SF-03

**FRs owned: FR-3.** `.specweaverignore` parsed with `.gitignore` semantics via `pathspec`.
Recorded 2026-08-17 under `specweaver-dev` §3.2c, from `INT-US-05-SF03-MIG`. Proof and mutant:
`tests/unit/workspace/ast/parsers/test_exclusions.py` — compiling the spec from an empty pattern
list fails 6 tests.

## Goal

Remove the hard-coded Python glob exclusions and wire the polyglot boundaries from SF-02 into
`validation`, the filesystem tooling (`loom`), boundary discovery (`assurance.standards`) and graph
hashing (`assurance.graph.hasher`).

## Changes

Paths under `src/specweaver/`. `[x]` = done.

**`specweaver.workspace.ast.parsers`** — polyglot traceability tags (`# @trace(FR-XX)` and
`// @trace(FR-XX)`):

1. `[x]` `interfaces.py` — `extract_traceability_tags(self, code: str) -> set[str]` on
   `CodeStructureInterface`.
2. `[x]` `python/codestructure.py` — reads tree-sitter `comment` nodes for `@trace()`.
3. `[x]` `java/codestructure.py` / `kotlin/codestructure.py` / `rust/codestructure.py` /
   `typescript/codestructure.py` — same, using each language's comment nodes.

**`specweaver.workspace.context`** — `analyzers.py`:

4. `[x]` `extract_test_mapped_requirements(self, directory: Path) -> set[str]` on the
   `LanguageAnalyzer` ABC; `TreeSitterAnalyzerBase` iterates the language's test file patterns
   (`*Test.java` vs `test_*.py`) under `directory`, calls the parser's `extract_traceability_tags`,
   returns the union.

**`specweaver.core.loom`** — ripgrep timeout prevention and dispatcher DI:

5. `commons/filesystem/search.py`:
   - `grep_content`, `find_by_glob`, `iter_text_files` accept `exclude_dirs: set[str] | None = None`;
   - `_grep_ripgrep` passes `--ignore-file .specweaverignore` when the file exists;
   - `find_by_glob` and `iter_text_files` replace `search_dir.rglob` with `os.walk` recursion that
     drops directories matching `exclude_dirs`.
6. `tools/filesystem/interfaces.py` and `tools/filesystem/tool.py` — `FileSystemTool.__init__` and
   `create_filesystem_interface` accept `exclude_dirs` and pass it to the `search.py` methods.
7. `dispatcher.py` — `create_standard_set` calls `AnalyzerFactory.get_all_analyzers()`, aggregates
   `get_default_directory_ignores()` and `get_binary_ignore_patterns()`, and injects them into the
   filesystem interface as `exclude_dirs` and `exclude_patterns`.

**`specweaver.assurance.standards`** — `discovery.py`:

8. Delete `_SKIP_DIRS`. `_walk_with_skips` gets the global exclusions (`get_default_directory_ignores`
   and `get_binary_ignore_patterns`) from `AnalyzerFactory.get_all_analyzers()`, plus explicit
   dotfile checks; files with binary-ignored extensions are filtered out.

**`specweaver.assurance.graph`** — `hasher.py`:

9. `DependencyHasher._hash_directory`: replace unbounded `directory.rglob("*")` with `os.walk` (or
   bounded pruning) using `AnalyzerFactory` exclusions and `pathspec` for `.specweaverignore`.

**`specweaver.assurance.validation`** — `rules/code/c09_traceability.py`:

10. `[x]` Remove direct `tree_sitter_python` logic and the hard-coded `test_*.py` globs.
11. `[x]` `_find_and_parse_tests` iterates `AnalyzerFactory.get_all_analyzers()` and accumulates
    `mapped_ids.update(analyzer.extract_test_mapped_requirements(project_root))`.
12. `[x]` The validation algorithm, comparisons and rule constraints stay unchanged in `validation`.

## Tests

| Command | Proves |
|---|---|
| `pytest tests/unit/workspace/context/test_analyzers.py -v` | `@trace()` found in every language |
| `pytest tests/unit/assurance/validation/test_c09_traceability.py -v` | C09 is language-blind with identical outputs |
| `pytest tests/unit/core/loom/commons/filesystem/test_search.py -v` | the `os.walk` exclusions prevent timeouts |
| `/pre-commit`; `tach check` on a sandbox run | no architecture leaks |
