# Implementation Plan: Internal Layer Enforcement (Tach) [SF-7: Target Rule C05 Subsumption (Tach)]
- **Feature ID**: 3.20a
- **Sub-Feature**: SF-7 — Target Rule C05 Subsumption (Tach)
- **Design Document**: docs/roadmap/phase_3/feature_3_20a/feature_3_20a_design.md
- **Design Section**: §Sub-Feature Decomposition → SF-7
- **Implementation Plan**: docs/roadmap/phase_3/feature_3_20a/feature_3_20a_sf7_implementation_plan.md
- **Status**: COMPLETED

## Goal
Gut the legacy hardcoded AST parser inside `c05_import_direction.py` and replace it with a generalized architecture boundary check on the target project. To ensure SpecWeaver remains strictly polyglot-capable, C05 will delegate to the `QARunnerInterface` rather than executing `tach` directly. This requires expanding the L4/L5 QA Runner capabilities and fixing existing L2 Architectural DMZ violations.

---

## 1. Loom Commons Interfaces (`src/specweaver/loom/commons/qa_runner/`)

### [MODIFY] `interface.py`
- Inherit polyglot architecture patterns by introducing two new data classes: `ArchitectureViolation` (file, code, message, rule_uri) and `ArchitectureRunResult` (violation_count, violations).
- Add new abstract method `run_architecture_check(self, target: str) -> ArchitectureRunResult` to the base `QARunnerInterface`.

### [MODIFY] `python/runner.py`
- Implement `run_architecture_check(...)` using Python's `subprocess.run` to orchestrate `uv run tach check --output json` (or `tach check`).
- The execution must point strictly at `self._cwd` (the target workspace).
- Gracefully handle `subprocess.CalledProcessError` to parse errors from Tach's JSON array output formats (`UndeclaredDependency`).
- Safely yield an empty result if parsing fails/hangs or if no bounding metadata was detected.

### [MODIFY] `typescript/runner.py`, `java/runner.py`, `kotlin/runner.py`, `rust/runner.py`
- Polyglot Engine Safety: To satisfy the ABC constraint imposed by adding `run_architecture_check` to the Interface, all other language adapters MUST implement a safe stub:
  ```python
  def run_architecture_check(self, target: str) -> ArchitectureRunResult:
      # Native checks (e.g. ArchUnit/ESLint) deferred to Feature 3.20b
      return ArchitectureRunResult(violation_count=0, violations=[])
  ```
- Failure to implement this exact stub will cause test orchestration crashes.

---

## 2. Loom Atom Engine (`src/specweaver/loom/atoms/qa_runner/`)

### [MODIFY] `atom.py`
- Introduce a new Intent handler: `_intent_run_architecture` returning `AtomResult`.
- Extract `target` from the orchestration context.
- Delegate checking safely via `self._runner.run_architecture_check(target)`.
- Export `violation_count` alongside standard list serialized violation exports mapping to `SUCCESS` or `FAILED` AtomStatuses.

---

## 3. Loom Tools Interface (`src/specweaver/loom/tools/qa_runner/`)

### [MODIFY] `tool.py`
- Update `ROLE_INTENTS` to whitelist `run_architecture` for `implementer`, `reviewer`, and `planner`.
- Add `run_architecture_check(self, target: str) -> ToolResult` dispatching the identical atom intent sequence.

### [MODIFY] `definitions.py`
- Map the exposed LLM intent. Add an `INTENT_DEFINITIONS["run_architecture"]` with the single standard string target parameter. 

---

## 4. Validation Engine Domain (`src/specweaver/validation/`)

### [MODIFY] `context.yaml`
- **Architectural Cleanup**: Formalize `specweaver/loom/commons/qa_runner` into the `consumes` array.
- Current rules C03 (Tests Pass) and C04 (Coverage) implicitly bypass global DMZ guards by importing L4 components. Allowing this formally stabilizes the Validation engine's usage of external interface wrappers without opening up broad I/O gaps.

### [MODIFY] `rules/code/c05_import_direction.py`
- **Tear Down**: Remove all dependency on `ast.parse` and statically scoped `_FORBIDDEN_RULES` mappings.
- **Pipeline Setup**: Resolve the project root dynamically (similarly to `c03`) and initialize `PythonQARunner(cwd=project_root)`. *(Future: upgrade to dynamic language adapter)*.
- **Execution**: Await/trigger `.run_architecture_check(target)`.
- **Parsing**: 
  - If output counts equal 0: return `self._pass("All structural architecture boundaries verified")`.
  - Iterate through `ArchitectureViolation` structures returned by the interface, mapping them exactly to `Finding(message=..., severity=Severity.ERROR)`.
  - *Mitigation strategy*: If the workspace lacks underlying configuration (missing `tach.toml`), detect empty results / specific fallback exceptions and return `self._skip(...)` to safely defer execution until SF-8 automaps boundaries in newer topologies.

---

## Technical Audit & Gotchas (Phase 2 & 3 Notes)
*   **JSON Schema**: Tach's output shape features nested `Located -> details -> Code -> UndeclaredDependency` dictionaries. The parsing step inside `PythonQARunner` must fail cleanly if Tach bumps APIs, using standard `.get()` defaulting to prevent `KeyError` crashes deep inside the workflow engine.
*   **Performance Cache**: Evaluating constraints using the AST historically takes ms. If passing boundaries to subprocesses generates > 400ms lag across unit tests, C05's testing footprint must be heavily mocked during unit runs outside E2E.
*   **`tach` System Requirement**: Assumes `tach` is resolvable inside the venv executing the codebase. Because SpecWeaver controls the execution environments and provides Tach as a dev-dependency, tests will pass locally.

## Verification
- Complete standard Pre-Commit Workflow phases.
- Unit Testing: Validate that `c05_import_direction` skips smoothly on invalid target environments and gracefully maps Tach errors into `RuleResult` failures holding multiple `Findings`.
- Cross architecture tests spanning PythonQARunner outputs to `Validation` interfaces must seamlessly decouple dependencies. 
