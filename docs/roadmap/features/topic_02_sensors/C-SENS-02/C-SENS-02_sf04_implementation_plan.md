# C-SENS-02 SF-04 — Analyzer Dependency Injection

**Status**: APPROVED · **Feature ID**: 3.32b · **Depends on**: SF-03 ·
Design: [C-SENS-02_design.md](C-SENS-02_design.md) §Sub-features → SF-04

**FRs owned: FR-4.** Scaffolding seeds language defaults when the ignore file is missing.
Recorded 2026-08-17 under `specweaver-dev` §3.2c, from `INT-US-05-SF03-MIG`. Proof and mutant:
`tests/unit/workspace/ast/parsers/test_exclusions.py` — neutralising the seeding branch fails 6.

## Goal

Move the concrete Tree-Sitter analyzers out of the pure-logic `context` domain into a new
`workspace/analyzers` adapter module. Pure-logic protocols plus dependency injection through the
`/flow` orchestrator pass the factory into `DependencyHasher` and the others. This removes the
`Path.read_text`, `open()` and Tree-Sitter C-binding architecture violations.

## Changes

Paths under `src/specweaver/`.

**`specweaver.workspace.context`** — pure-logic protocols; no circular imports, no C-bindings:

1. `workspace/context/context.yaml` — `exposes:` lists `analyzer_protocols` instead of `analyzers`.
2. `[NEW]` `workspace/context/analyzer_protocols.py`:
   - the `LanguageAnalyzer(ABC)` base moves here from `analyzers.py`, free of tree-sitter;
   - `AnalyzerFactoryProtocol(Protocol)` with `for_directory` and `get_all_analyzers`.
3. `workspace/context/analyzers.py` — deleted. Concrete classes (`PythonAnalyzer`, `JavaAnalyzer`,
   `AnalyzerFactory`) move to `workspace/analyzers`.
4. `workspace/context/inferrer.py` — `infer_and_write` requires an injected
   `analyzer_factory: AnalyzerFactoryProtocol` instead of a global import.

**`specweaver.workspace.analyzers`** (new adapter layer):

5. `[NEW]` `workspace/analyzers/context.yaml` — `archetype: adapter`; binds pure-logic protocols to
   the Tree-Sitter parser implementations.
6. `[NEW]` `factory.py` / `implementations.py` — `TreeSitterAnalyzerBase`, all language subclasses
   (`PythonAnalyzer`, etc) and the concrete `AnalyzerFactory`, which implements
   `AnalyzerFactoryProtocol`.

**`specweaver.workspace.ast.parsers`**:

7. `workspace/ast/parsers/context.yaml` — add `- exclusions` to `exposes:` (used by `scaffold.py`).
8. `workspace/ast/parsers/exclusions.py` (Option A, see Decisions) — define a minimal
   `IgnoreIOHandler` Protocol in `exclusions.py`: `read_text(path) -> str`, `append_lines(path, lines)`,
   `exists(path) -> bool`. `SpecWeaverIgnoreParser.__init__` requires `io_handler: IgnoreIOHandler`;
   its `open()`, `.read_text()` and `.exists()` calls go through it.

**`specweaver.core.flow`** — `core/flow/engine/runner.py`:

9. Build `AnalyzerFactory` from the `adapters` and inject it into context inferrers,
   `DependencyHasher` and file discovery. Build a concrete `IgnoreIOHandler` over OS operations and
   inject it into `SpecWeaverIgnoreParser`.

**`specweaver.assurance.graph` & `specweaver.assurance.standards`**:

10. `assurance/graph/hasher.py` (Option B) — `DependencyHasher.__init__` requires
    `analyzer_factory: AnalyzerFactoryProtocol` (point-to-point injection, so the decoupling is
    visible). `compute_hashes` and `_hash_directory` use `self.analyzer_factory`.
11. `assurance/standards/discovery.py` — `discover_files` and its callees accept an injected
    `analyzer_factory: AnalyzerFactoryProtocol`.

## Tests

- Implement the skipped tests in `test_exclusions.py`:
  1. `test_deferred_integration_orchestrator_initializes_ignores_sf4` — `/flow` instantiates the parser.
  2. `test_deferred_e2e_topological_spec_bypass_hidden_binary_sf4` — E2E: topological bounds skip
     binaries via the DI factory.
- Update every `test_` file's `DependencyHasher`, `AnalyzerFactory` and `SpecWeaverIgnoreParser`
  construction (mocks or real injection).
- `pytest tests/unit/workspace/context/test_exclusions.py` — the SF-04 tests pass with a mocked
  `IgnoreIOHandler`.
- Mock `AnalyzerFactoryProtocol` in `test_hasher.py`, `test_inferrer.py`, `test_discovery.py`.
- `tach check` — `workspace/context` has no I/O violations or tree-sitter side-effects. `mypy`.
- `/pre-commit`.

## Decisions (audit)

| # | Question | Chosen |
|---|---|---|
| Option A | How to remove the I/O from `pure-logic` `exclusions.py` without pulling in `loom`? | a local `IgnoreIOHandler` Protocol, injected |
| Option B | How does `DependencyHasher` get the factory? | explicit constructor parameter (point-to-point) |

Requirements check:
- FR-1 through FR-5: `pathspec` ignores, token suppression and scaffolding are 100% unchanged
  algorithmically — no functional regression.
- NFR-1: new language bounds plug in through the injected `AnalyzerFactoryProtocol` without changing
  `hasher.py`.
- NFR-2: point-to-point DI costs `< 1ms`, within `< 50ms`.

Isolation check: `workspace/context/context.yaml` exposes `analyzer_protocols`;
`workspace/analyzers/context.yaml` is `archetype: adapter`; `workspace/ast/parsers/exclusions.py`
has no `open()` (DI `IgnoreIOHandler`). **Zero isolation warnings.**
