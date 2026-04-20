# Feature 3.32b: Smart Scan Exclusions (Tiered)
**Status:** Design Phase Approved

## 1. Feature Description & Context
The SpecWeaver engine heavily relies on cross-repo I/O for LLM file searching (Agents) and Semantic Hashing (`DependencyHasher`). We require a 3-tier file exclusion strategy to strictly protect agent token windows from binary hallucination and accelerate `< 50ms` NFR pipeline caching bounds.

## 2. Functional Requirements (FRs)
- **FR-1:** The Engine must enforce structural exclusions for Polyglot build paths (`target/`, `node_modules/`, `build/`).
- **FR-2:** The Engine must statically enforce binary file exclusions to protect token context (`*.pyc`, `*.class`, `*.rlib`, `*.jar`).
- **FR-3:** System must parse `.specweaverignore` identically to `.gitignore` semantics using `pathspec`.
- **FR-4:** Scaffolding operations must automatically populate `.specweaverignore` with language-specific directory defaults if missing.
- **FR-5:** Exclusions must seamlessly integrate with `TopologyGraph.stale_nodes` to intercept file iterations mathematically before deep I/O execution.

## 3. Non-Functional Requirements (NFRs)
- **NFR-1:** Extensibility - Language rules must automatically extend without modifying the `loom` execution engine (Dependency Injection).
- **NFR-2:** Performance - Unrolling `rglob` trees must map via compiled `pathspec` or unified `stale_nodes` prefixing to meet extreme `< 50ms` NFRs.
- **NFR-3:** Mono-Repo Resilience - The global exclusion engine must handle hybrid projects (e.g. Python backend + Typescript frontend) safely without `AnalyzerFactory` detection collisions.

## 4. Sub-Feature Decomposition & Technical Debt Refactoring

The feature will be rolled out by updating native modules while simultaneously refactoring legacy loops.

### SF-1: Pure Logic Definitions & Ignorance Parser
- Update `CodeStructureInterface` to support polyglot ignore patterns.
- Implement across `Python`, `Rust`, `Java`, `Kotlin`, `TS` subclasses (binary bounds vs directory limits).
- Extract legacy `pathspec` parsing logic out of `discovery.py` and centralize it into `workspace/context/exclusions.py`.

### SF-2: Orchestration Factory & Scaffolding
- Update `AnalyzerFactory` with `get_all_analyzers()` to support Polyglot Global Union aggregations.
- Enhance scaffolding pipelines natively to prefill `.specweaverignore` globally.

### SF-3: Technical Debt Refactoring (The Execution Sweeps)
- **Refactor `discovery.py`**: Delete the hardcoded Python-centric `_SKIP_DIRS` block entirely. Bind the `discover_files` loop to the new Polyglot Engine via `AnalyzerFactory`.
- **Refactor `search.py`**: Intercept `iter_text_files` and `find_by_glob` in `loom` to utilize injected exclusion matrices, preventing token timeouts.
- **Refactor `hasher.py`**: Remove redundant manual string `rglob` filtering natively in favor of the unified orchestrator payload.
- **Refactor `c09_traceability.py`**: Rip out the hardcoded `test_*.py` iteration block. Bind it to the `AnalyzerFactory` to correctly query `*Test.java` and `*_scenarios.rs` tests natively, resolving polyglot isolation violations.

### SF-4: Analyzer Dependency Injection (Strict Decoupling)
- Abstract `workspace/context/analyzers.py` entirely out of the Contract layer.
- Move Polyglot Tree-sitter implementations seamlessly into `workspace/analyzers/` (Adapter Layer).
- Construct `AnalyzerFactoryProtocol` in the pure-logic layer.
- Thread the instance completely through the `/flow` orchestrator via Dependency Injection to cure the legacy `hasher.py` I/O boundary violation structurally.
- **CRITICAL NOTE (From SF-1 Phase 1 Gate):** Ensure that the `SpecWeaverIgnoreParser` physical OS I/O traversal (e.g., calling `Path.read_text()` or `open()`) introduced inside the `pure-logic` `exclusions.py` engine is fully abstracted away via DI to definitively resolve its architectural violation!
- **CRITICAL NOTE (From SF-1 Phase 2 Test Gaps):** The two skipped placeholder tests inside `test_exclusions.py` MUST be solidly implemented during SF-4 integration:
  1. `test_deferred_integration_orchestrator_initializes_ignores_sf4`
  2. `test_deferred_e2e_topological_spec_bypass_hidden_binary_sf4`

### SF-5: Integration Debt Remediation (DI Consistency)
- Refactor the orchestrating nodes `ToolDispatcher`, `PipelineRunner`, and `C09TraceabilityRule` which statically imported `AnalyzerFactory`, skipping the rigorous DI checks originally scoped in SF-4.
- Route `AnalyzerFactoryProtocol` sequentially down the Flow Handlers using `RunContext`.
- Ensure all tests correctly mock or pass dependencies downward without violating the orchestrator barrier.

## 5. Progress Tracker

| Sub-Feature | Design/Arch | Impl Plan | Code (`/dev`) | E2E Tests |
| :--- | :---: | :---: | :---: | :---: |
| SF-1: Pure Logic Definitions & Ignorance Parser | ✅ | ✅ | ✅ | ✅ |
| SF-2: Orchestration Factory & Scaffolding | ✅ | ✅ | ✅ | ✅ |
| SF-3: Technical Debt Refactoring | ✅ | ✅ | ✅ | ✅ |
| SF-4: Analyzer Dependency Injection | ✅ | ✅ | ✅ | ✅ |
| SF-5: Integration Debt Remediation (DI) | ✅ | ✅ | ✅ | ✅ |

## 6. Session Handoff

**Next Action:** Sub-Feature 5 Implementation Plan is Approved! The immediately actionable step for the subsequent session is to execute the `/dev docs/roadmap/phase_3/feature_3_32b_sf5_impl_plan.md` workflow.
