# C-SENS-02 SF-01 — Pure Logic Definitions & Ignorance Parser

**Status**: APPROVED · **Feature ID**: 3.32b · **Depends on**: — ·
Design: [C-SENS-02_design.md](C-SENS-02_design.md) §Sub-features → SF-01

## Goal

Pure-logic foundation only: per-language ignore patterns on `CodeStructureInterface` and a
`pathspec` aggregator in `exclusions.py`. Refactoring `discovery.py` and the `AnalyzerFactory` DI are
out of scope here (SF-03, SF-04).

## Changes

All `[x]` done.

1. **Dependency** · `pyproject.toml` — add `pathspec = "^0.12.0"` to core dependencies;
   `pytest-pathspec` to `dev` only if path mocking needs it.
2. **Interface** · `src/specweaver/workspace/ast/parsers/interfaces.py` — `CodeStructureInterface`
   gains abstract methods:
   - `def get_binary_ignore_patterns(self) -> list[str]: ...`
   - `def get_default_directory_ignores(self) -> list[str]: ...`
3. **Per-language patterns** — each `codestructure.py` returns:

| File · class | Binary patterns | Directory ignores |
|---|---|---|
| `src/specweaver/workspace/ast/parsers/python/codestructure.py` · `PythonCodeStructure` | `["*.pyc", "*.pyo", "*.pyd"]` | `["__pycache__/", ".pytest_cache/", ".tox/", ".venv/"]` |
| `src/specweaver/workspace/ast/parsers/java/codestructure.py` · `JavaCodeStructure` | `["*.class", "*.jar", "*.ear", "*.war"]` | `["target/", "build/"]` |
| `src/specweaver/workspace/ast/parsers/kotlin/codestructure.py` · `KotlinCodeStructure` | `["*.class", "*.jar"]` | `["target/", "build/", ".gradle/"]` |
| `src/specweaver/workspace/ast/parsers/rust/codestructure.py` · `RustCodeStructure` | `["*.rlib", "*.so", "*.dll", "*.pdb"]` | `["target/"]` |
| `src/specweaver/workspace/ast/parsers/typescript/codestructure.py` · `TypeScriptCodeStructure` | `[]` (Node runs source) | `["node_modules/", "dist/", "build/", "out/"]` |

4. **Pathspec aggregator** · `[NEW]` `src/specweaver/workspace/ast/parsers/exclusions.py` —
   `SpecWeaverIgnoreParser`:
   - takes `project_root: Path` only to read `.specweaverignore` (allowed lookup before cache
     locking);
   - `ensure_scaffolded(default_directories: list[str]) -> None` — safe append;
   - `get_compiled_spec(runtime_patterns: list[str]) -> pathspec.PathSpec` — ignore-file text plus
     runtime patterns.

   `workspace/ast/parsers` is `pure-logic`, so it may host the pathspec regex generation without
   breaking the `contract` constraints of `workspace/context`. The disk read of `.specweaverignore`
   is injected later, in SF-04.

## Tests

- `pytest tests/workspace/context/test_exclusions.py` (new).
- `get_compiled_spec` matches deterministically.
- `CodeStructureInterface` subclasses fail validation if an abstract method is missing.
- Run the pre-commit workflow (`@[/pre-commit]`) before committing.

## Decisions (audit)

- **Settled**: pathspec is required (not optional); SF-01 vs SF-03 overlap resolved; Workspace/Context
  I/O bounds resolved.
- **Architecture**: no circular dependencies. New methods in `interfaces.py` and the `codestructure`
  subclasses stay within `pure-logic`; `exclusions.py` does not cross into `loom/` (forbidden).
- **Roadmap**: with `AnalyzerFactory` decoupling deferred to **SF-04**, SF-01 is the pure foundation
  for topological exclusion — also a prerequisite for **Feature 3.33** (PostgreSQL Graph).
