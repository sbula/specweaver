# A-SENS-01 SF-01 — Polyglot Parser Decoupling

**Status**: APPROVED · **Feature ID**: 3.32 · **FRs owned**: NFR-2 · **Depends on**: — ·
Design: [A-SENS-01_design.md](A-SENS-01_design.md) §Sub-features → SF-01

## Goal

Three parallel AST implementations existed, so Workspace topology was not polyglot. Move the
Tree-Sitter extractors out of the restricted `loom` sandbox into a `pure-logic` boundary at
`workspace/ast/parsers/`. SF-02 needs this for dependency hashing across Java, Kotlin, Python, Rust
and TypeScript, without breaking `dmz` consumption rules.

## Changes

**Workspace parsers (new home for pure-logic parsers)**

1. `[NEW]` `src/specweaver/workspace/ast/parsers/context.yaml` — `name: parsers`, `level: module`,
   `archetype: pure-logic`, `consumes: []`, `forbids: [specweaver/loom/*]`, `exposes: [interfaces]`.
2. `[MODIFY]` `src/specweaver/workspace/ast/parsers/interfaces.py` — moved from
   `core/loom/commons/language/interfaces.py`. Add `extract_imports(self, code: str) -> list[str]` to
   `CodeStructureInterface`; the query targets standard imports only.
3. `[NEW/MOVE]` `src/specweaver/workspace/ast/parsers/<language>/codestructure.py`:
   - Do **not** move whole language folders. Move ONLY `codestructure.py` (and related `parsers.py`
     utilities) from `core/loom/commons/language/<lang>/` to `workspace/ast/parsers/<lang>/`.
   - `runner.py`, `scenario_converter.py`, `stack_trace_filter.py` stay in
     `core/loom/commons/language/<lang>/` — they are execution adapters.
   - Add `extract_imports` to each `codestructure.py` using language-specific Tree-Sitter `.scm`
     nodes (`import_statement` in python/ts, `import_declaration` in java).

**Workspace context**

4. `src/specweaver/workspace/context/context.yaml` — add `specweaver/workspace/ast/parsers` to
   `consumes`.
5. `src/specweaver/workspace/context/analyzers.py`:
   - delete the `ast`-based `PythonAnalyzer`;
   - `LanguageAnalyzer` and `AnalyzerFactory` become proxies to the parsers in
     `workspace/ast/parsers/`;
   - `extract_imports` delegates to the active tree-sitter interface; all 5 languages enabled;
   - `infer_archetype` applies standard-library heuristics per language (Java: `java.*`/`javax.*`,
     Rust: `std::*`, etc.) to the raw imports, so framework imports (Spring/FastAPI) classify as
     `adapter`. The parsers stay unaware of SpecWeaver's business rules.

**Loom language commons** (now execution only: runners and scenario converters)

6. `src/specweaver/core/loom/commons/language/context.yaml` — add `specweaver/workspace/ast/parsers`
   to `consumes`; drop "AST Parsing" / "Pure Logic" from the descriptions.
7. `src/specweaver/core/loom/commons/language/evaluator.py` and
   `src/specweaver/core/loom/atoms/code_structure/atom.py` — import from
   `specweaver.workspace.ast.parsers.interfaces`.

**Assurance standards**

8. `src/specweaver/assurance/standards/tree_sitter_base.py` — delete custom grammar loaders; inherit
   grammar logic from `workspace/ast/parsers`, so the C-bindings are instantiated once per language
   per process.

## Tests

| Check | Proves |
|---|---|
| `pytest tests/workspace/context/test_analyzers.py` | the auto-inferrer reads TypeScript imports |
| `pytest tests/core/loom/atoms/test_code_structure.py` | the Agent atoms still extract AST boundaries |
| `tach check` | the move removed cyclic dependencies and obeys `forbids` in `context.yaml` |
| final git diff | no duplicate `tree_sitter` or `LanguageAnalyzer` loops left in `analyzers.py` |
