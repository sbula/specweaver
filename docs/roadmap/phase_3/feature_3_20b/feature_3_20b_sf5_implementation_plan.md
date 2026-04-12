# Implementation Plan: Feature 3.20b [SF-5: Polyglot Architecture Configs]

- **Feature ID**: 3.20b
- **Sub-Feature**: SF-5 — Polyglot Architecture Configs
- **Design Document**: docs/roadmap/phase_3/feature_3_20b/feature_3_20b_design.md
- **Status**: APPROVED

## 1. Goal Description

Establish Polyglot Architectural Config bounds for non-Python languages directly hooked into SpecWeaver's internal `DALLevel`. Because SpecWeaver must natively assert architectural boundaries (analogous to Python's `tach check`), the TS adapter will instantiate `.eslintrc.json` payload rules mirroring the `context.yaml` restrictions, and the Java adapter will generate temporary `@Test` payloads evaluating identical limits under `ArchUnit`.

## 2. HITL Verified Decisions

1. **Auto-Discovery Proxy:** Instead of passing the rigid SpecWeaver Data Model (`context.db`) downwards breaking layer definitions, the `qa_runner` natively performs stateless `Factory` checks (`package.json`, `pom.xml`, etc) avoiding cyclic boundaries.
2. **Commons Enum Namespace:** `DALLevel` is migrated downward exclusively into an `L0` Foundation Layer (`specweaver.commons.enums.dal`) such that deep-layer adapters like `qa_runner` can cleanly import strictly-typed Enums uniformly across the whole application DAG.
3. **Execution Artifact Patterns:**
   - Java: Implements a dynamically generated generic `SpecweaverArchUnitTest.java` in the target `.tmp/` area, executing directly via `mvn` before cleanup.
   - TS: Generates and proxies AST restrictions completely via native `npx eslint -c .eslint-specweaver-arch.json`.

---

## 3. Proposed Changes

### 3.1. Foundation Module (`specweaver.commons`)
Establishes the structural namespace completely isolated from business or execution logic.
#### [NEW] `src/specweaver/commons/context.yaml`
- Sets module archetype `raw-data` forcing `consumes: []`.
#### [NEW] `src/specweaver/commons/enums/dal.py`
- Moves `DALLevel` Enum and its schema metadata completely out of `config`.
#### [NEW] `src/specweaver/commons/enums/__init__.py`

### 3.2. Config Subsystems (`specweaver.core.config`)
#### [DELETE] `src/specweaver/config/dal.py`
#### [MODIFY] `src/specweaver/config/dal_resolver.py`
- Transitions import: `from specweaver.commons.enums.dal import DALLevel`

### 3.3. QARunner Commons Interfaces (`specweaver.core.loom.commons.qa_runner`)
#### [MODIFY] `src/specweaver/loom/commons/qa_runner/context.yaml`
- Adds `specweaver/commons` natively to the `consumes: ` list avoiding Layer violation constraints.
#### [MODIFY] `src/specweaver/loom/commons/qa_runner/interface.py`
- Expands `run_architecture_check` parameter: `dal_level: DALLevel | None = None`
#### [NEW] `src/specweaver/loom/commons/qa_runner/factory.py`
- Encodes physical `resolve_runner(cwd: Path) -> QARunnerInterface` returning JVM vs TS vs Python instances checking file artifacts explicitly.

### 3.4. Language Runner Adapters
#### [MODIFY] `src/specweaver/loom/commons/qa_runner/typescript/runner.py`
- Overrides `run_architecture_check` injecting dynamically constructed JSON `no-restricted-imports` and wrapping CLI output parsing.
#### [MODIFY] `src/specweaver/loom/commons/qa_runner/java/runner.py`
- Implements dynamic injection logic utilizing Java strings formatted explicitly as JUnit/ArchUnit combinations dropping inside `.tmp/`.

### 3.5. Internal Integrations
#### [MODIFY] `src/specweaver/validation/rules/code/c05_import_direction.py`
#### [MODIFY] `src/specweaver/loom/atoms/qa_runner/atom.py`
#### Refactor
- Search across the workspace and mutate all prior `from specweaver.core.config.dal import DALLevel` imports resolving them successfully to `commons`.

---

## 4. Verification Plan

1. **Python Unit Tests:** Implement comprehensive standard unit tests for parsing, rule generation models (`TSRunner` `.eslintrc` output and `JavaRunner` test generation strings).
5. **Integration Gate:** Synthesize a fake node `package.json` testing project with `context.yaml` defining a `forbids: [...]` rule. Route CLI `c05_import_direction` against it natively, forcing an architectural exit code generation dynamically inside Python. Ensure ESLint output mappings parse flawlessly!

---

## 5. Dev Task Breakdown

1. `Task 1`: **Commons Foundation Enum** - Create `specweaver/commons/enums/dal.py` and strictly configure its `context.yaml` as an `L0` layer without consumers. Migrate `DALLevel`, and update `config/dal_resolver.py`.
2. `Task 2`: **QARunner Boundaries & Interface** - Loosen `qa_runner/context.yaml` to consume `specweaver/commons`. Overload `QARunnerInterface.run_architecture_check(target, dal_level=None)` tracking string across boundaries into Python/Kotlin/Rust stubs.
3. `Task 3`: **QARunner Auto-Discovery Factory** - Code `src/specweaver/loom/commons/qa_runner/factory.py` deploying `resolve_runner(cwd) -> Interface` scanning target paths actively for marker files mapping polyglot.
4. `Task 4`: **Wiring Validation Callers** - Reconnect the internal execution points at `c05_import_direction.py` and `QARunnerAtom` routing via the dynamic factory.
5. `Task 5`: **TypeScript ESLint Pipeline** - Realize AST constraints in `TypeScriptRunner.run_architecture_check`. Deploy JSON structural payload dropping to `.tmp` invoking `npx eslint`.
6. `Task 6`: **Java ArchUnit Pipeline** - Hardcode `JavaRunner` JUnit generator writing `ArchitectureTest.java` invoking `mvn` runtime output extraction.
