# C-SENS-02 SF-02 — Orchestration Factory & Scaffolding

**Status**: FULLY IMPLEMENTED (Pre-commit complete) · **Feature ID**: 3.32b · **Depends on**: SF-01 ·
Design: [C-SENS-02_design.md](C-SENS-02_design.md) §Sub-features → SF-02

**FRs owned: FR-2.** Polyglot binary-file exclusions. Recorded 2026-08-17 under `specweaver-dev`
§3.2c, from `INT-US-05-SF03-MIG`. Proof and mutant:
`tests/unit/workspace/ast/parsers/test_polyglot_exclusions.py` — emptying Java's `*.class`/`*.jar`
list fails it, and nothing else under `tests/unit/workspace` notices.

## Goal

Expose the polyglot union of analyzers and use it to scaffold `.specweaverignore`.

> [!WARNING]
> **Out of scope: the I/O violation in `analyzers.py`.** `src/specweaver/workspace/context/context.yaml`
> declares `context/` as `archetype: contract`, yet `analyzers.py` runs `.glob()` and `.read_text()`.
> Do NOT refactor that here — it is deferred to SF-04, which moves the module to
> `workspace/analyzers/` (Adapter Layer).

## Changes

1. **Union** · `src/specweaver/workspace/context/analyzers.py`:
   - `LanguageAnalyzer` ABC: `@abstractmethod def get_binary_ignore_patterns(self)` and
     `@abstractmethod def get_default_directory_ignores(self)`, so every language provides both.
   - `TreeSitterAnalyzerBase`: delegates to `self.parser.get_binary_ignore_patterns()` and
     `self.parser.get_default_directory_ignores()`.
   - `AnalyzerFactory`: `@classmethod def get_all_analyzers(cls) -> list[LanguageAnalyzer]` returns
     the whole polyglot union (Python, TS, Java, Rust, Kotlin).
2. **Scaffold** · `src/specweaver/workspace/project/scaffold.py` — in
   `scaffold_project(project_path: Path)`:
   - iterate `AnalyzerFactory.get_all_analyzers()` and build the flat `default_directories` list;
   - `SpecWeaverIgnoreParser(project_path)` from `specweaver.workspace.ast.parsers.exclusions`, then
     `ensure_scaffolded(default_directories)`;
   - add `".specweaverignore"` to the tracking array if newly created.

## Tests

| File | Case |
|---|---|
| `tests/unit/workspace/context/test_analyzers.py` | `AnalyzerFactory.get_all_analyzers()` returns exactly 5 instances |
| | `LanguageAnalyzer.get_default_directory_ignores()` delegates through a mock analyzer to its parser |
| `tests/unit/workspace/project/test_scaffold.py` | `scaffold_project` writes a `.specweaverignore` containing `__pycache__/`, `target/`, `node_modules/` |
| | idempotent: a second run keeps the user's custom patterns |
