# Implementation Plan: Smart Scan Exclusions (Tiered) [SF-4: Analyzer Dependency Injection]
- **Feature ID**: 3.32b
- **Sub-Feature**: SF-4 — Analyzer Dependency Injection
- **Design Document**: docs/roadmap/phase_3/feature_3_32b_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-4
- **Implementation Plan**: docs/roadmap/phase_3/feature_3_32b_sf4_impl_plan.md
- **Status**: APPROVED

## Goal Description
Implement strict architectural decoupling for the pure-logic engine. Move all concrete Tree-Sitter powered language analyzers out of the pure-logic `context` domain and into a new `workspace/analyzers` adapter module. Construct Pure-logic Protocols and leverage global Dependency Injection natively through the `/flow` orchestrator to pass the active Factory into `DependencyHasher` and others, permanently eliminating the `Path.read_text`, `open()`, and Tree-Sitter C-binding architecture violations.

## Proposed Changes

---

### `specweaver.workspace.context`
Pure-logic protocols preventing circular imports and C-binding contamination.

#### [MODIFY] `context.yaml` (file:///C:/development/pitbula/specweaver/src/specweaver/workspace/context/context.yaml)
- **Modifications**: 
  - Change `exposes:` to list `analyzer_protocols` instead of `analyzers` to maintain visibility bounds.

#### [NEW] `analyzer_protocols.py` (file:///C:/development/pitbula/specweaver/src/specweaver/workspace/context/analyzer_protocols.py)
- **Content**: 
  - Migrate the abstract base class `LanguageAnalyzer(ABC)` logic here from `analyzers.py` to decouple it from tree-sitter. 
  - Define `AnalyzerFactoryProtocol(Protocol)` with `for_directory` and `get_all_analyzers` methods.

#### [MODIFY] `analyzers.py` (file:///C:/development/pitbula/specweaver/src/specweaver/workspace/context/analyzers.py)
- **Modifications**:
  - Delete file! All Concrete implementations (`PythonAnalyzer`, `JavaAnalyzer`, `AnalyzerFactory`) will be physically moved to `workspace/analyzers`. 

#### [MODIFY] `inferrer.py` (file:///C:/development/pitbula/specweaver/src/specweaver/workspace/context/inferrer.py)
- **Modifications**:
  - Update `infer_and_write` to require an injected `analyzer_factory: AnalyzerFactoryProtocol` instead of importing it globally. 

---

### `specweaver.workspace.analyzers` (New Adapter Layer)

#### [NEW] `context.yaml` (file:///C:/development/pitbula/specweaver/src/specweaver/workspace/analyzers/context.yaml)
- **Content**: `archetype: adapter`. Explains that this layer binds pure-logic protocols to physical Tree-Sitter parser implementations.

#### [NEW] `factory.py` / `implementations.py` (file:///C:/development/pitbula/specweaver/src/specweaver/workspace/analyzers/)
- **Content**:
  - Move `TreeSitterAnalyzerBase` and all language subclasses (`PythonAnalyzer`, etc) here.
  - Move the concrete `AnalyzerFactory` implementation here. It will implement `AnalyzerFactoryProtocol`.

---

### `specweaver.workspace.parsers`
Pure logic code structure and ignore parsing protocols.

#### [MODIFY] `context.yaml` (file:///C:/development/pitbula/specweaver/src/specweaver/workspace/parsers/context.yaml)
- **Modifications**:
  - Add `- exclusions` to the `exposes:` list since it is utilized externally by `scaffold.py`.

#### [MODIFY] `exclusions.py` (file:///C:/development/pitbula/specweaver/src/specweaver/workspace/parsers/exclusions.py)
- **Modifications**:
  - **HITL Gate Resolution (Option A)**: To clear the I/O violation inside `pure-logic` without pulling in `loom`, define a minimalist `IgnoreIOHandler` Protocol exclusively inside `exclusions.py` with `read_text(path) -> str`, `append_lines(path, lines)`, and `exists(path) -> bool`.
  - Update `SpecWeaverIgnoreParser.__init__` to strictly require `io_handler: IgnoreIOHandler`.
  - Replace physical `open()`, `.read_text()`, and `.exists()` calls within `SpecWeaverIgnoreParser` with calls to the injected `io_handler`.

---

### `specweaver.core.flow`
The Orchestrator.

#### [MODIFY] `engine/runner.py` (file:///C:/development/pitbula/specweaver/src/specweaver/core/flow/engine/runner.py)
- **Modifications**:
  - Instantiate `AnalyzerFactory` physically from the `adapters`.
  - Pass the factory deeply via dependency injection into context inferrers, the `DependencyHasher`, and standard file discovery routines.
  - Instantiate a concrete `IgnoreIOHandler` wrapping standard OS operations and inject it into `SpecWeaverIgnoreParser`.

---

### `specweaver.assurance.graph` & `specweaver.assurance.standards`

#### [MODIFY] `hasher.py` (file:///C:/development/pitbula/specweaver/src/specweaver/assurance/graph/hasher.py)
- **Modifications**:
  - **HITL Gate Resolution (Option B)**: Modify `DependencyHasher.__init__` to explicitly demand `analyzer_factory: AnalyzerFactoryProtocol` via Point-to-Point injection. This ensures pure-logic architectural decoupling is physically visible.
  - Update `compute_hashes` and `_hash_directory` to use `self.analyzer_factory` instead of importing globally.

#### [MODIFY] `discovery.py` (file:///C:/development/pitbula/specweaver/src/specweaver/assurance/standards/discovery.py)
- **Modifications**:
  - Update `discover_files` downstream functions to accept an injected `analyzer_factory: AnalyzerFactoryProtocol` instead of physical global imports.

---

### Test Enhancements
- Implement the skipped tests in `test_exclusions.py`:
  1. `test_deferred_integration_orchestrator_initializes_ignores_sf4` - Verify that `/flow` instantiates the parser globally.
  2. `test_deferred_e2e_topological_spec_bypass_hidden_binary_sf4` - E2E verification of topological bounds bypassing binaries via the DI factory.
- Ensure all other `test_` files update their `DependencyHasher`, `AnalyzerFactory`, and `SpecWeaverIgnoreParser` instantiation signatures with mocks or actual injections.

---

## Design Validation & Verification Plan

### FR/NFR Alignment Check
- **FRs Supported:** The `pathspec` ignores, token suppression bounds, and automatic scaffolding logic remaining 100% untouched algorithmically confirms zero functional regression for FR-1 through FR-5.
- **NFR-1 (Extensibility):** Dependency Injecting the `AnalyzerFactoryProtocol` through the `flow` engine means new language bounds can be plugged in instantly without modifying `hasher.py`.
- **NFR-2 (Performance):** Point-to-point DI has `< 1ms` static overhead, honoring `< 50ms` NFRs.

### Architecture Isolation Check
- `workspace/context/context.yaml`: Exposed correctly (`analyzer_protocols`).
- `workspace/analyzers/context.yaml`: Declared as `archetype: adapter`.
- `workspace/parsers/exclusions.py`: Removed physical `open()` and successfully mapped via DI `IgnoreIOHandler`.
- Result: **Zero isolation warnings.**

### Automated Tests
- Run `pytest tests/unit/workspace/context/test_exclusions.py` to verify the SF-4 skipped tests pass successfully leveraging mocked `IgnoreIOHandler`.
- Mock out `AnalyzerFactoryProtocol` globally across `test_hasher.py`, `test_inferrer.py`, and `test_discovery.py` to satisfy new point-to-point requirements.
- Run `tach check` to conclusively verify that `workspace/context` no longer has I/O violations or tree-sitter side-effects.
- Run `mypy` natively.

### Manual Verification
- Execute `/pre-commit` pipeline.
