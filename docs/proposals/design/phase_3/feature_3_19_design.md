# Design: Polyglot QARunner Interface

- **Feature ID**: 3.19
- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/proposals/design/phase_3/feature_3_19_design.md

## Feature Overview

Feature 3.19 transforms the `QARunnerInterface` from a Python-only construct into a fully-implemented polyglot execution engine spanning both **Atoms** (engine-internal rules) and **Tools** (agent-facing actions). It wraps the target-language CLI commands for Python, Kotlin, Java, Rust, and TypeScript (React) into dedicated language runner implementations. Each implementation will deeply integrate with its language's standard tooling (`cargo`, `gradlew`, `mvn`, `npm`/`jest`, `pytest`). Beyond testing, linting, and complexity, the interface is expanded to govern **compiling** and **debugging**, parsing test results into `TestRunResult`, `LintRunResult`, and `ComplexityRunResult` via open-source protocols (JUnit XML and SARIF), while routing detailed compiler/debugger standard errors back to the LLM agent identically.

## Research Findings

### Codebase Patterns
Presently, the `PythonQARunner` (`src/specweaver/loom/commons/qa_runner/python.py`) interacts directly with `pytest` and `ruff`. We will extend `src/specweaver/loom/commons/qa_runner/` by creating dedicated modules (`rust.py`, `java.py`, `kotlin.py`, `typescript.py`) that implement the expanded `QARunnerInterface`. Crucially, we must also update the Agent-facing Tool (`src/specweaver/loom/tools/qa_runner/tool.py`) to expose these new capabilities (`compile`, `debug`) so the AI Agents themselves can trigger native builds and debug execution loops just like the Pipeline Engine does with Atoms. 

**Runner Resolution Strategy**: The factory function `_resolve_runner` will aggressively determine which runner (and build tool variant) to instantiate by first checking for explicit overrides in the local `context.yaml` of the target directory or Database Config. If absent, it will fall back to **target-aware structural tracing**—scanning upwards from the specific file/directory being executed looking for anchor files (e.g., if testing `src/native/rust_lib.rs`, it traces up to find a nested `Cargo.toml` → Rust Cargo runner; if testing `tests/test_py.py`, it traces up to root `pyproject.toml` → Python runner). This guarantees that heterogeneous workspaces (like Python projects with Rust extensions) are natively supported.

### External Tools & CLI Invocations
The implementations MUST execute exact CLI patterns:
- **JUnitParser / SARIF-tools**: Generalized outputs natively parsed.
- **Rust (Cargo)**: Compile: `cargo build`. Test: `cargo test -- --format=json | cargo2junit > junit.xml`. Lint: `cargo clippy --message-format=json`.
- **Java/Kotlin (Gradle)**: Compile: `gradlew classes` / `gradlew assemble`. Test: `gradlew test` (JUnit in `build/test-results/test/`). Lint: `gradlew detekt --report sarif...` / `gradlew pmdMain` (SARIF plugin).
- **Java/Kotlin (Maven)**: Compile: `mvn compile`. Test: `mvn test` (JUnit in `target/surefire-reports/`). Lint: `mvn detekt:check` (SARIF) / `mvn pmd:pmd` (SARIF).
- **TypeScript (NPM)**: Compile: `tsc --noEmit` or `npm run build`. Test: `jest --reporters=default --reporters=jest-junit`. Lint: `eslint -f sarif -o eslint.sarif`.

### Blueprint References
none stated

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Unified Interface Refactor | System | Update `interface.py` | The bounds encompass Test, Lint, Complexity, **Compile**, and **Debug**. The Data Models are expanded to support `stacktrace: str`, `rule_uri: str`, etc. |
| FR-2 | Agent-facing Tools | Agent | Update `qa_runner/tool.py` | The LLM agents natively gain permissioned access to trigger `compile()` and `debug()` through the Loom Sandbox, utilizing identical Black Box resolution patterns. |
| FR-3 | Python Support | System | Align `PythonQARunner` | Python executes tests, linting, complexity, compiling, and debugging by conforming to the new unified data models. |
| FR-4 | Rust Support | System | Build `RustRunner` | Rust executes tests, linting, compiling, complexity natively via `cargo` wrappers mapping to generic bounds. |
| FR-5 | Java Support | System | Build `JavaRunner` | Java executes tests, compilation, linting via Maven (`mvn compile/test/pmd`) and Gradle natively mapping outputs. |
| FR-6 | Kotlin Support | System | Build `KotlinRunner` | Kotlin executes tests, compilation, complexity via Gradle/Maven and `detekt` pushing SARIF maps. |
| FR-7 | TypeScript Support| System | Build `TypeScriptRunner`| TS executes tests, compiling, linting/complexity natively via `tsc`, `jest-junit` and `eslint` SARIF formatters. |
| FR-8 | E2E Testing | System | Implement Tests | Every runner class must be rigorously tested using mock CLI executions to verify parsing rules for each respective language across all 5 operational intents. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Performance | Parsers MUST resolve external CLI results securely and within the defined timeout bounds. |
| NFR-2 | Testability | Tests for all 5 runners MUST mock subprocess shell executions seamlessly to prevent needing Java/Rust/Node installed on the CI testing environment. |
| NFR-3 | Graceful Degradation | If a specific language runner cannot parse a SARIF/JUnit file (e.g., compile error prevented generation), it MUST dump the raw stderr into a generic `TestFailure` block instead of crashing the flow engine, actively feeding compile failures straight to the LLM agent. |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| `junitparser` | 3.1.2| `JUnitXml.fromfile()` | Yes | Required for test parsing |
| `sarif-tools` | 1.0.0| `SARIF` schema models | Yes | Required for linting logs |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Dedicated Package Sub-Modules | Separating run logic, parsers, and interfaces into dedicated folders (e.g. `java/runner.py`, `java/parsers.py`) per language prevents God-class bloat as lint/test logic diversifies. | Yes |
| AD-2 | E2E Subprocess Mocking | Mocking subprocess outputs allows the full battery of runners to be tested comprehensively on a Python-only local machine or CI. | No |

## Sub-Feature Breakdown

### SF-1: Core Interface, Compilers & Python/TS Handlers
- **Scope**: Updates `interface.py` and `qa_runner/tool.py` to accept stacktraces/SARIF bounds and add `compile`/`debug` commands. Aligns the `PythonQARunner` and implements the `TypeScriptRunner`.
- **FRs**: [FR-1, FR-2, FR-3, FR-7, FR-8]
- **Inputs**: Polyglot execution parameters simulating Agents requesting builds/tests.
- **Outputs**: Validated compile/debug/test/lint/complexity runners using mock JUnit/SARIF files.
- **Depends on**: none
- **Impl Plan**: docs/proposals/roadmap/phase_3/feature_3_19_sf1_implementation_plan.md

### SF-2: JVM Handlers (Java & Kotlin)
- **Scope**: Implements `JavaRunner` and `KotlinRunner` compiling and parsing outputs from Gradle (`gradlew`), Maven (`mvn`), detekt, and PMD.
- **FRs**: [FR-5, FR-6, FR-8]
- **Inputs**: JVM polyglot requests and mock JVM fail/pass payloads.
- **Outputs**: Validated Java and Kotlin compilation & test runners.
- **Depends on**: SF-1
- **Impl Plan**: docs/proposals/roadmap/phase_3/feature_3_19_sf2_implementation_plan.md

### SF-3: Rust Handler
- **Scope**: Implements `RustRunner` using Cargo and Clippy natively, mapping `cargo build` exits to the generic bounds.
- **FRs**: [FR-4, FR-8]
- **Inputs**: Rust polyglot requests.
- **Outputs**: Validated Rust runner integrating `cargo`.
- **Depends on**: SF-1
- **Impl Plan**: docs/proposals/roadmap/phase_3/feature_3_19_sf3_implementation_plan.md

### SF-4: Polyglot Submodule Architecture Refactor
- **Scope**: Refactors god-classes (`java.py`, `kotlin.py`, `rust.py`) into dedicated package submodules (`java/runner.py`, `java/parsers.py`) alongside migrating their respective unit and integration test folders natively inside `tests/unit/.../java/` to prevent directory and module bloat. **Must natively refactor `_parse_detekt_complexity` and `_parse_pmd_complexity` to extract values purely via structural SARIF properties instead of brittle string regex scraping (fixing compiler upgrade vulnerability)**. **Must perform an exhaustive evaluation and backfill of E2E and Unit test gaps across all Polyglot handlers (Java/Kotlin/Rust) to ensure complete ecosystem parity and structural coverage.**
- **FRs**: [FR-1]
- **Inputs**: Existing unified runner files.
- **Outputs**: Clean domain-driven package modules mapping per-language correctly.
- **Depends on**: SF-2, SF-3
- **Impl Plan**: docs/proposals/roadmap/phase_3/feature_3_19_sf4_implementation_plan.md

## Execution Order

1. SF-1 (Core Interface, Compilers & Python/TS)
2. SF-2 (JVM Handlers) and SF-3 (Rust Handler) in parallel (both depend only on SF-1)
3. SF-4 (Polyglot Submodule Architecture Refactor)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | Core Interface & Python/TS | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-2 | JVM Handlers (Java & Kotlin)| SF-1 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-3 | Rust Handler | SF-1 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-4 | Submodule Refactoring | SF-2, SF-3 | ✅ | ✅ | ⬜ | ⬜ | ⬜ |

## Session Handoff
Execute `@[/dev]` targeting `docs/proposals/roadmap/phase_3/feature_3_19_sf4_implementation_plan.md` to begin safely refactoring the Polyglot boundaries.
**Current status**: Implementation Plan for SF-3 is APPROVED.
**Next step**: Run the following command to begin building the code for SF-3 via TDD:
`@[/dev] docs/proposals/roadmap/phase_3/feature_3_19_sf3_implementation_plan.md`
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜
in any row and resume from there using the appropriate workflow.
