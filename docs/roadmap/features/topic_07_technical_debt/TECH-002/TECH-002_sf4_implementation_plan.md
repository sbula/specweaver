# Implementation Plan: Validation Layer Isolation [SF-4]
- **Feature ID**: TECH-002
- **Sub-Feature**: SF-4 — Validation Layer Isolation
- **Design Document**: [TECH-002_design.md](file:///c:/development/pitbula/specweaver/docs/roadmap/features/topic_07_technical_debt/TECH-002/TECH-002_design.md)
- **Design Section**: §Sub-Feature Breakdown → SF-4
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-002/TECH-002_sf4_implementation_plan.md
- **Status**: APPROVED

---

## 1. Research Notes

### 1.1 Current Violations

Three validation rules in `assurance/validation/rules/code/` directly import from `specweaver.sandbox`, violating the `forbids: specweaver/sandbox/*` constraint in both:
- [context.yaml](file:///c:/development/pitbula/specweaver/src/specweaver/assurance/validation/context.yaml) (line 22): `forbids: specweaver/sandbox/*`
- [code/context.yaml](file:///c:/development/pitbula/specweaver/src/specweaver/assurance/validation/rules/code/context.yaml) (line 20): `forbids: specweaver/sandbox/*`

| Rule | File | Sandbox Import(s) | Lines |
|------|------|-------------------|-------|
| C03 `TestsPassRule` | [c03_tests_pass.py](file:///c:/development/pitbula/specweaver/src/specweaver/assurance/validation/rules/code/c03_tests_pass.py) | `from specweaver.sandbox.base import AtomStatus` (L57), `from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom` (L58) | 57-58 |
| C04 `CoverageRule` | [c04_coverage.py](file:///c:/development/pitbula/specweaver/src/specweaver/assurance/validation/rules/code/c04_coverage.py) | `from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom` (L52) | 52 |
| C05 `ImportDirectionRule` | [c05_import_direction.py](file:///c:/development/pitbula/specweaver/src/specweaver/assurance/validation/rules/code/c05_import_direction.py) | `from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom` (L40) | 40 |

C05 also imports `from specweaver.core.config.dal_resolver import DALResolver` (L39). This import is legitimate for `assurance.validation` (`consumes: specweaver/config`) but moves to the hydrator because it is only needed for atom invocation context.

### 1.2 Three Call Sites

The design doc (SF-4 scope) identifies three call sites that must route through a hydrated flow path:

| # | Call Site | File | Current Call |
|---|-----------|------|-------------|
| 1 | `ValidateCodeHandler._run_validation` | [validation.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/handlers/validation.py#L263-L331) | `execute_validation_pipeline(pipeline, content, spec_path, context={"analyzer_factory": ...})` |
| 2 | CLI `check` command | [cli.py](file:///c:/development/pitbula/specweaver/src/specweaver/assurance/validation/interfaces/cli.py#L260) | `execute_validation_pipeline(resolved, content, target_path)` — no context |
| 3 | API `POST /check` | [validation.py](file:///c:/development/pitbula/specweaver/src/specweaver/interfaces/api/v1/validation.py#L67) | `execute_validation_pipeline(resolved, content, abs_path)` — no context |

### 1.3 `Rule.context` Contract

The `Rule` ABC ([models.py](file:///c:/development/pitbula/specweaver/src/specweaver/assurance/validation/models.py)) already supports context injection:
- `rule.context` is a `dict[str, Any]` property (getter returns `self._context`, setter assigns).
- The [executor.py](file:///c:/development/pitbula/specweaver/src/specweaver/assurance/validation/executor.py#L184-L187) already merges `ast_payload` and any `context` dict into `rule.context = base_context` after instantiation (lines 184-187).
- SF-4 rules will read QA results from `self.context` via the agreed keys.

### 1.4 Context Data Shape (HITL-Resolved: H-1)

The hydrated context values use the **Full AtomResult dict** shape:
```python
{"status": str, "message": str, "exports": dict[str, Any]}
```
Where `status` is the **uppercase** `AtomStatus` enum value string (e.g., `"FAILED"`, `"SUCCESS"`, `"RETRY"`), serialized via `result.status.value`. This is plain data — no sandbox types imported.

C03 needs `status` and `message` for timeout detection. C04 and C05 only need `exports`.

> [!CAUTION]
> **Bug fix in C04:** The current C04 (line 67) compares `result.status == "failed"` (lowercase string) against the `AtomStatus` enum. After SF-4, the status string is `"FAILED"` (uppercase, from `AtomStatus.FAILED.value`). Both C03 and C04 must compare against `"FAILED"` consistently.

### 1.5 Context Key Contract (from Design Doc)

- `"qa_tests_result"` → Full dict from `QARunnerAtom.run({"intent": "run_tests", ...})`
- `"qa_coverage_result"` → Full dict from `QARunnerAtom.run({"intent": "run_tests", "coverage": True, ...})`
- `"qa_architecture_result"` → Full dict from `QARunnerAtom.run({"intent": "run_architecture", ...})`
- If a key is absent → rule calls `self._skip(...)` or `self._fail(...)` (for C03 if test files are present).

### 1.6 Tach Configuration

- `specweaver.assurance.validation` currently `depends_on: ["specweaver.sandbox", ...]` ([tach.toml](file:///c:/development/pitbula/specweaver/tach.toml#L34-L36) line 35).
- After SF-4, `specweaver.sandbox` MUST be removed from this `depends_on` list.
- `specweaver.core.flow` already `depends_on: ["specweaver.sandbox", "specweaver.assurance.validation"]` — so the flow layer is allowed to bridge both.
- `specweaver.assurance.validation.interfaces` `depends_on: ["specweaver.core.flow", ...]` (tach.toml line 40) — importing from `core.flow.handlers` is legal.
- `specweaver.interfaces.api` `depends_on: ["specweaver.core.flow", ...]` (tach.toml line 81) — importing from `core.flow.handlers` is legal.

### 1.7 AD-5: `execute_validation_flow` Entry Point

The design doc (AD-5) mandates: "CLI and API will delegate validation checks to a new `execute_validation_flow` entry point in `core.flow`."

This is implemented as a public function in a new module `core/flow/handlers/validation_hydrator.py`. The function `execute_validation_flow` performs hydration AND calls `execute_validation_pipeline` — it is a complete replacement for the direct `execute_validation_pipeline` call in CLI and API. This prevents CLI/API from needing to know about hydration at all.

### 1.8 AD-8: Optimize QA Executions

The hydration logic inspects `pipeline.steps` for active rule IDs (`C03`, `C04`, `C05`) BEFORE instantiating any `QARunnerAtom`. If all three are disabled, no atoms are created and no subprocesses are run.

### 1.9 Existing Test Coverage for Rules

| Test File | Rules Covered | Lines | Impact |
|-----------|--------------|-------|--------|
| [test_c01_c02_c03.py](file:///c:/development/pitbula/specweaver/tests/unit/assurance/validation/rules/test_c01_c02_c03.py) | C01, C02, C03 | 245 | C03 tests (lines 154-244) mock `QARunnerAtom`. **Replace with new file.** |
| [test_code_rules.py](file:///c:/development/pitbula/specweaver/tests/unit/assurance/validation/rules/code/test_code_rules.py) | C01, C02, C05, C06, C07, C08 | 522 | C05 tests (lines 117-193) mock `PythonQARunner`. **Replace with new file.** |
| [test_code_rules_execution.py](file:///c:/development/pitbula/specweaver/tests/unit/assurance/validation/rules/code/test_code_rules_execution.py) | C03 (8 tests), C04 (8 tests) | 671 | ALL C03/C04 tests (lines 43-458) mock `QARunnerAtom`. **Replace with new file.** Also contains Generator tests (lines 461-598) and runner filtering tests (lines 600-671) that are unaffected. |

> [!IMPORTANT]
> **HITL-Resolved (M-5): Test migration strategy is Option 2 — Replace with new files.**
> The old test files will be replaced entirely with new test files that use context injection. Generator tests and runner filtering tests from `test_code_rules_execution.py` that are unaffected by SF-4 will be preserved in their original file.

### 1.10 C04 Target Path Bug

C04 line 59 passes `str(spec_path)` as the `target` to `QARunnerAtom`. But `spec_path` in the flow handler context is the *spec* file, not the code file. The hydrator fixes this by always using the correct `code_path`.

### 1.11 Test File Path Derivation (HITL-Resolved: H-2)

The hydrator duplicates ~10 lines of test-file-finding logic (project root search, `tests/` rglob) from `TestsPassRule.check()`. This is acceptable because:
- C03 still needs the logic to produce meaningful skip messages.
- The duplication is minimal and stable.
- It keeps the hydrator self-contained.

### 1.12 DAL-Level Three-Layer Gap (HITL-Resolved: H-9)

A systematic audit revealed that `dal_level` is broken at **every layer** between C05 and the actual architecture checker:

| Layer | File | Status |
|-------|------|--------|
| **Caller (C05 / hydrator)** | [c05_import_direction.py](file:///c:/development/pitbula/specweaver/src/specweaver/assurance/validation/rules/code/c05_import_direction.py#L52-L57) | ✅ Correctly passes `"dal_level": dal_enum` in context dict |
| **Atom** | [atom.py `_intent_run_architecture`](file:///c:/development/pitbula/specweaver/src/specweaver/sandbox/qa_runner/core/atom.py#L387-L400) | ❌ Reads `target` from context but **ignores** `dal_level`. Calls `self._runner.run_architecture_check(target=target)` without forwarding `dal_level` |
| **Interface** | [interface.py `run_architecture_check`](file:///c:/development/pitbula/specweaver/src/specweaver/sandbox/qa_runner/core/interface.py#L166-L179) | ✅ Abstract method accepts `dal_level: DALLevel \| None = None` |
| **PythonQARunner** | [runner.py](file:///c:/development/pitbula/specweaver/src/specweaver/sandbox/language/core/python/runner.py#L427-L473) | ❌ Accepts `dal_level` in signature but **never uses it**. Runs blind `tach check` globally — no context.yaml forbids, no target scoping, no DAL-awareness |
| **TypeScriptRunner** | [runner.py](file:///c:/development/pitbula/specweaver/src/specweaver/sandbox/language/core/typescript/runner.py#L192-L287) | ✅ Reads context.yaml forbids, generates ESLint config, runs per-file check |
| **JavaRunner** | [runner.py](file:///c:/development/pitbula/specweaver/src/specweaver/sandbox/language/core/java/runner.py#L235-L354) | ✅ Reads context.yaml forbids, generates ArchUnit test, runs per-file check |
| **RustRunner / KotlinRunner** | stubs | ⚠️ Accept param, return empty result (deferred) |

**Decision (H-9):** Fix all three layers in SF-4 (Option C — full fix):
1. **Atom**: Extract `dal_level` from context, forward to runner (2 lines)
2. **PythonQARunner**: Implement context.yaml forbids parsing + target-scoped AST import checking (matching TS/Java parity), with `dal_level` used for logging and potential strictness control
3. **Tests**: Add atom dal_level forwarding tests and PythonQARunner DAL-awareness tests

> [!CAUTION]
> Without the atom fix, the hydrator would pass `dal_level` into a void — the same silent failure as today. Without the PythonQARunner fix, even a correctly forwarded `dal_level` would be ignored by the runner.

---

## 2. Proposed Changes

### Component: Validation Rules (Pure Logic Layer)

#### [MODIFY] [c03_tests_pass.py](file:///c:/development/pitbula/specweaver/src/specweaver/assurance/validation/rules/code/c03_tests_pass.py)

**Goal:** Remove all sandbox imports. Read test execution results from `self.context["qa_tests_result"]`.

**Changes:**
1. Remove `from specweaver.sandbox.base import AtomStatus` (line 57).
2. Remove `from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom` (line 58).
3. Remove all `QARunnerAtom` instantiation and `.run()` calls (lines 60-69).
4. Replace with `self.context.get("qa_tests_result")` lookup.
5. If key is missing AND test files exist → `self._fail("Test execution results not available (QA context not hydrated)")`.
6. If key is missing AND no test files → `self._skip(...)` (unchanged from current behavior).
7. Parse `result_data` dict directly for `status`, `message`, `exports` keys.
8. For timeout detection: check `result_data.get("status") == "FAILED"` and `"timed out"` in message.

**New `check()` method structure:**
```python
def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
    if spec_path is None:
        return self._skip("No file path provided")

    # Derive test file (unchanged logic)
    test_name = f"test_{spec_path.stem}.py"
    project_root = spec_path.parent
    while project_root != project_root.parent:
        if (project_root / "pyproject.toml").exists():
            break
        project_root = project_root.parent

    tests_dir = project_root / "tests"
    if not tests_dir.is_dir():
        return self._skip("No tests/ directory found")

    matches = list(tests_dir.rglob(test_name))
    if not matches:
        return self._skip(f"No test file '{test_name}' found")

    test_file = matches[0]

    # Read pre-hydrated QA results from context
    result_data = self.context.get("qa_tests_result")
    if result_data is None:
        return self._fail(
            "Test execution results not available (QA context not hydrated)",
            [Finding(message="Rule requires pre-hydrated QA context", severity=Severity.ERROR)],
        )

    # Check for timeout
    if result_data.get("status") == "FAILED" and "timed out" in (
        result_data.get("message") or ""
    ).lower():
        return self._fail(
            "Tests timed out after 60 seconds",
            [Finding(message="Test execution timed out", severity=Severity.ERROR)],
        )

    exports = result_data.get("exports") or {}
    failed = exports.get("failed", 0)
    errors = exports.get("errors", 0)

    if failed == 0 and errors == 0:
        return self._pass(f"All tests in {test_file.name} passed")

    # Build failure message (same logic as current lines 87-104)
    failures = exports.get("failures", [])
    failure_msgs = [f.get("message", "") for f in failures]
    if failure_msgs:
        message = "; ".join(failure_msgs)
        message = message[-500:]  # Truncate to 500 chars
    else:
        message = "No output"

    return self._fail(
        "Tests failed",
        [Finding(message=message, severity=Severity.ERROR,
                 suggestion="Fix failing tests before proceeding.")],
    )
```

---

#### [MODIFY] [c04_coverage.py](file:///c:/development/pitbula/specweaver/src/specweaver/assurance/validation/rules/code/c04_coverage.py)

**Goal:** Remove all sandbox imports. Read coverage results from `self.context["qa_coverage_result"]`.

**Changes:**
1. Remove `from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom` (line 52).
2. Remove all `QARunnerAtom` instantiation and `.run()` calls (lines 54-65).
3. Replace with `self.context.get("qa_coverage_result")` lookup.
4. If key is missing → `self._fail("Coverage results not available (QA context not hydrated)")`.
5. Parse `result_data["exports"]` dict directly for `coverage_pct`.
6. Fix the timeout status check: compare `result_data.get("status") == "FAILED"` (uppercase) instead of the buggy `result.status == "failed"` (lowercase) at line 67.

**New `check()` method structure:**
```python
def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
    if spec_path is None:
        return self._skip("No file path provided")

    # Read pre-hydrated QA results from context
    result_data = self.context.get("qa_coverage_result")
    if result_data is None:
        return self._fail(
            "Coverage results not available (QA context not hydrated)",
            [Finding(message="Rule requires pre-hydrated QA context", severity=Severity.ERROR)],
        )

    # Check for timeout (fixed: uppercase "FAILED")
    if result_data.get("status") == "FAILED" and "timed out" in (
        result_data.get("message") or ""
    ).lower():
        return self._fail(
            "Coverage check timed out",
            [Finding(message="Coverage check timed out", severity=Severity.ERROR)],
        )

    exports = result_data.get("exports") or {}
    coverage = exports.get("coverage_pct")

    if coverage is None:
        return self._warn(
            "Could not parse coverage from output",
            [Finding(message="Coverage output unparseable", severity=Severity.WARNING)],
        )

    coverage_int = int(coverage)

    if coverage_int < self._threshold:
        return self._fail(
            f"Coverage {coverage_int}% below threshold {self._threshold}%",
            [Finding(
                message=f"Coverage: {coverage_int}% (threshold: {self._threshold}%)",
                severity=Severity.ERROR,
                suggestion=f"Add tests to reach at least {self._threshold}% coverage.",
            )],
        )

    return self._pass(f"Coverage: {coverage_int}% (threshold: {self._threshold}%)")
```

> [!NOTE]
> C04 no longer derives `project_root` or runs any I/O. The hydrator provides coverage results pre-computed. The `_threshold` constructor parameter continues to work unchanged.

---

#### [MODIFY] [c05_import_direction.py](file:///c:/development/pitbula/specweaver/src/specweaver/assurance/validation/rules/code/c05_import_direction.py)

**Goal:** Remove all sandbox AND dal_resolver imports. Read architecture check results from `self.context["qa_architecture_result"]`.

**Changes:**
1. Remove `from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom` (line 40).
2. Remove `from specweaver.core.config.dal_resolver import DALResolver` (line 39) — moves to hydrator.
3. Remove all `QARunnerAtom` instantiation, `DALResolver` resolution, and `.run()` calls (lines 44-58).
4. Replace with `self.context.get("qa_architecture_result")` lookup.
5. If key is missing → `self._skip("Architecture check results not available")`.
6. Parse `result_data["exports"]` dict directly for `violation_count` and `violations`.
7. **Remove the `_FORBIDDEN_IMPORTS` list** (lines 17-19). It becomes dead code after refactoring — the `context.yaml` forbids patterns enforced by the hydrator/runner are the authoritative source now.

**New `check()` method structure:**
```python
def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
    if not spec_path:
        return self._skip("Cannot run architecture checks without a file path")

    # Read pre-hydrated QA results from context
    result_data = self.context.get("qa_architecture_result")
    if result_data is None:
        return self._skip("Architecture check results not available")

    exports = result_data.get("exports") or {}
    violation_count = exports.get("violation_count", 0)

    if violation_count == 0:
        return self._pass("All imports follow layering rules")

    findings: list[Finding] = []
    violations = exports.get("violations", [])
    for viol in violations:
        msg = viol.get("message", "Unknown violation")
        code = viol.get("code", "UNKNOWN")
        findings.append(
            Finding(
                message=f"Architecture boundary violated: {msg}",
                line=0,
                severity=Severity.ERROR,
                suggestion=f"See architectural boundary configuration (Code: {code}).",
            )
        )

    if findings:
        return self._fail(f"Found {violation_count} architectural violation(s)", findings)

    return self._fail("Architectural violations detected.", [])
```

> [!NOTE]
> The `_FORBIDDEN_IMPORTS` list is removed (dead code after refactoring — H-3). The `import logging` and `logging.getLogger(__name__)` call that was inline inside `check()` can optionally be moved to module scope.

---

### Component: Flow Orchestrator (Context Hydration)

#### [NEW] [validation_hydrator.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/handlers/validation_hydrator.py)

**Goal:** Create a module with two public functions:
1. `hydrate_code_validation_context` — pre-runs QA atoms and returns a context dict.
2. `execute_validation_flow` — the full entry point for CLI/API (AD-5). Performs hydration, then calls `execute_validation_pipeline`.

This module lives in `core.flow.handlers/` — the flow layer is the only layer allowed to orchestrate both sandbox and validation (AD-4).

**Public API:**
```python
def hydrate_code_validation_context(
    pipeline: ValidationPipeline,
    code_path: Path,
    project_path: Path,
) -> dict[str, Any]:
    """Pre-run QA atoms for active code validation rules (AD-8).

    Inspects pipeline.steps to determine which atoms to run.
    Each atom call is wrapped in try/except — on failure, the
    context key is set to an error dict (status="FAILED",
    message="Hydration error: ...", exports={}).

    Returns a dict suitable for passing as `context` to
    execute_validation_pipeline.
    """


def execute_validation_flow(
    pipeline: ValidationPipeline,
    content: str,
    code_path: Path,
    project_path: Path,
    *,
    context: dict[str, Any] | None = None,
) -> list[RuleResult]:
    """AD-5 entry point: hydrate QA context, then run pipeline.

    This is the single entry point for CLI and API to run code
    validation with pre-hydrated QA context. Internal flow
    handlers (ValidateCodeHandler) call hydrate_code_validation_context
    directly and merge with their existing context.

    Args:
        pipeline: Resolved ValidationPipeline.
        content: File content to validate.
        code_path: Path to the code file being validated.
        project_path: Project root for QARunnerAtom.
        context: Optional additional context to merge (e.g. analyzer_factory).

    Returns:
        List of RuleResult from execute_validation_pipeline.
    """
    qa_context = hydrate_code_validation_context(pipeline, code_path, project_path)
    merged = {**(context or {}), **qa_context}
    return execute_validation_pipeline(pipeline, content, code_path, context=merged)
```

**`hydrate_code_validation_context` Implementation:**
1. Extract active rule IDs: `active_rules = {step.rule for step in pipeline.steps}`.
2. Instantiate `QARunnerAtom` only if any of `C03`, `C04`, `C05` are active. Reuse one atom instance.
3. For each active rule, run the appropriate atom intent inside a try/except:
   - `"C03"`: Derive test file path (project root → `tests/` rglob). If found, run `atom.run({"intent": "run_tests", "target": relative_test_path, "timeout": 60})`. Serialize: `{"status": result.status.value, "message": result.message, "exports": result.exports}`. If no test file found, set key to `None`.
   - `"C04"`: Run `atom.run({"intent": "run_tests", "target": str(code_path), "coverage": True, "coverage_threshold": threshold, "timeout": 120})`. Same serialization. The `threshold` comes from pipeline step params (if available) or defaults to 70.
   - `"C05"`: Resolve DAL via `DALResolver(project_root).resolve(code_path)`. Run `atom.run({"intent": "run_architecture", "target": str(code_path.absolute()), "dal_level": dal_enum})`. Same serialization.
4. On exception per atom: Set context key to `{"status": "FAILED", "message": f"Hydration error: {e}", "exports": {}}`. This allows the rule to fail/skip with a descriptive message while other rules (C01, C02, C06, C07, C08) continue.
5. Return the context dict.

> [!IMPORTANT]
> **AD-8 compliance:** If C03/C04/C05 are ALL disabled in the pipeline (via settings), no `QARunnerAtom` is instantiated and no subprocesses run.

> [!WARNING]
> **C04 threshold extraction:** The hydrator must extract the `threshold` param from the C04 pipeline step (`step.params.get("threshold", 70)`) to pass to the atom. This matches the current behavior where C04 constructs `QARunnerAtom` with `coverage_threshold=self._threshold` from its constructor.

---

#### [MODIFY] [validation.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/handlers/validation.py)

**Goal:** Wire `ValidateCodeHandler._run_validation` to call `hydrate_code_validation_context` before `execute_validation_pipeline`.

**Changes to `_run_validation` (line 263-331):**

After the pipeline is loaded and settings applied (line 300), but before `execute_validation_pipeline` is called (line 326), add hydration:

```python
from specweaver.core.flow.handlers.validation_hydrator import hydrate_code_validation_context

qa_context = hydrate_code_validation_context(pipeline, code_path, cwd_path)

# Merge QA context with existing context
base_context = {"analyzer_factory": analyzer_factory} if analyzer_factory else {}
base_context.update(qa_context)

content = code_path.read_text(encoding="utf-8")
return execute_validation_pipeline(
    pipeline,
    content,
    spec_path,
    context=base_context,
)
```

> [!NOTE]
> The existing `context={"analyzer_factory": analyzer_factory}` at line 330 is preserved and merged with the QA context. The `analyzer_factory` is used by other rules (e.g., C12) and must not be lost.

---

### Component: CLI Call Site (AD-5)

#### [MODIFY] [cli.py](file:///c:/development/pitbula/specweaver/src/specweaver/assurance/validation/interfaces/cli.py)

**Goal:** Route code-level validation through `execute_validation_flow` (AD-5 entry point) instead of calling `execute_validation_pipeline` directly.

**Changes to `check` command (around line 260):**

Replace:
```python
results = execute_validation_pipeline(resolved, content, target_path)
```

With:
```python
if level == "code":
    from specweaver.core.flow.handlers.validation_hydrator import execute_validation_flow
    results = execute_validation_flow(resolved, content, target_path, project_root)
else:
    results = execute_validation_pipeline(resolved, content, target_path)
```

> [!NOTE]
> The CLI is in `assurance/validation/interfaces/` which `depends_on: ["specweaver.core.flow"]` (tach.toml line 40). Importing from `core.flow.handlers` is legal. The import is lazy (inside the `if` branch) to avoid loading sandbox modules for non-code validation.

---

### Component: API Call Site (AD-5)

#### [MODIFY] [validation.py](file:///c:/development/pitbula/specweaver/src/specweaver/interfaces/api/v1/validation.py)

**Goal:** Route code-level validation through `execute_validation_flow` (AD-5) instead of calling `execute_validation_pipeline` directly.

**Changes to `run_check` (line 67):**

Replace:
```python
results = execute_validation_pipeline(resolved, content, abs_path)
```

With:
```python
if body.level == "code":
    from specweaver.core.flow.handlers.validation_hydrator import execute_validation_flow
    results = execute_validation_flow(resolved, content, abs_path, project_root)
else:
    results = execute_validation_pipeline(resolved, content, abs_path)
```

> [!NOTE]
> `specweaver.interfaces.api` `depends_on: ["specweaver.core.flow"]` (tach.toml line 81). The import is lazy for the same reason as the CLI.
>
> The API context.yaml has `forbids: specweaver/sandbox/*` (line 25). `execute_validation_flow` lives in `core.flow.handlers`, NOT in `sandbox`, so this import is legal. The sandbox imports happen inside the hydrator, which is in the flow layer.

---

### Component: DAL-Level Propagation Fix (Atom Layer)

#### [MODIFY] [atom.py](file:///c:/development/pitbula/specweaver/src/specweaver/sandbox/qa_runner/core/atom.py)

**Goal:** Fix `_intent_run_architecture` to extract `dal_level` from context and forward it to the runner.

**Changes to `_intent_run_architecture` (line 387-400):**

```diff
 def _intent_run_architecture(self, context: dict[str, Any]) -> AtomResult:
-    """Run architectural checks.
-
-    Context keys:
-        target: str — file or directory to check (required).
-    """
+    """Run architectural checks.
+
+    Context keys:
+        target: str — file or directory to check (required).
+        dal_level: DALLevel | None — active DAL for strictness decisions (optional).
+    """
     target = context.get("target")
     if not target:
         return AtomResult(
             status=AtomStatus.FAILED,
             message="Missing 'target' in context for run_architecture intent.",
         )
 
-    result = self._runner.run_architecture_check(target=target)
+    dal_level = context.get("dal_level")
+    result = self._runner.run_architecture_check(target=target, dal_level=dal_level)
```

> [!NOTE]
> This is a 2-line fix + docstring update (L-1). The `dal_level` value flows from the hydrator's context dict through the atom to the language-specific runner. Without this fix, the hydrator would pass `dal_level` into a void.

---

### Component: PythonQARunner DAL-Awareness

#### [MODIFY] [runner.py](file:///c:/development/pitbula/specweaver/src/specweaver/sandbox/language/core/python/runner.py)

**Goal:** Make `PythonQARunner.run_architecture_check` DAL-aware, matching the pattern established by TypeScriptRunner and JavaRunner. The method must:
1. Read the nearest `context.yaml` forbids list for the target file
2. Perform AST-level import checking against those forbids (supplementing tach)
3. Log `dal_level` for diagnostic purposes
4. Continue running tach as before for global boundary violations

**Design rationale:** TypeScript uses ESLint with `no-restricted-imports` and Java uses ArchUnit — both dynamically generated from `context.yaml` forbids. For Python, the equivalent is AST-based import scanning: parse the target file's `import` and `from ... import` statements and check them against the `context.yaml` forbids glob patterns. This supplements tach (which checks `tach.toml` module boundaries) with per-file `context.yaml` forbids checking.

**Changes to `run_architecture_check` (line 427-473):**

```python
def run_architecture_check(
    self,
    target: str,
    dal_level: DALLevel | None = None,
) -> ArchitectureRunResult:
    """Run architectural boundary checks via tach + context.yaml forbids.

    Combines two checks:
    1. Global tach boundary check (existing behavior)
    2. Per-file context.yaml forbids check (new — parity with TS/Java)

    Args:
        target: File or directory to check (relative to cwd).
        dal_level: Active DAL for the target boundary.
    """
    import ast

    import yaml

    logger.debug(
        "PythonQARunner.run_architecture_check: target=%s, dal=%s", target, dal_level
    )

    # --- Phase 1: context.yaml forbids check ---
    forbids_violations: list[ArchitectureViolation] = []
    target_path = self._cwd / target
    if target_path.is_file() and target_path.suffix == ".py":
        ctx_dir = target_path.parent
        while (
            ctx_dir != self._cwd
            and ctx_dir.parent != ctx_dir
            and not (ctx_dir / "context.yaml").exists()
        ):
            ctx_dir = ctx_dir.parent

        ctx_file = ctx_dir / "context.yaml"
        forbids: list[str] = []
        if ctx_file.exists():
            try:
                data = yaml.safe_load(ctx_file.read_text(encoding="utf-8")) or {}
                forbids = data.get("forbids", [])
            except Exception as e:
                logger.warning("Failed to parse context.yaml at %s: %s", ctx_file, e)

        if forbids:
            try:
                source = target_path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(target_path))
            except Exception as e:
                logger.warning("Failed to parse %s for import checking: %s", target_path, e)
                tree = None

            if tree is not None:
                # RED-5: Collect nodes inside TYPE_CHECKING blocks to avoid false positives
                type_checking_ids: set[int] = set()
                for node in ast.walk(tree):
                    if (
                        isinstance(node, ast.If)
                        and isinstance(node.test, ast.Name)
                        and node.test.id == "TYPE_CHECKING"
                    ):
                        for child in ast.walk(node):
                            type_checking_ids.add(id(child))

                for node in ast.walk(tree):
                    if id(node) in type_checking_ids:
                        continue
                    import_module: str | None = None
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            import_module = alias.name
                            forbids_violations.extend(
                                self._check_forbids(import_module, forbids, target_path, node)
                            )
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        import_module = node.module
                        forbids_violations.extend(
                            self._check_forbids(import_module, forbids, target_path, node)
                        )

> [!CAUTION]
> **RED-5 fix:** The AST walker MUST skip imports inside `if TYPE_CHECKING:` blocks. These are type-only imports that are never executed at runtime and should NOT be treated as boundary violations. Without this fix, any file with `if TYPE_CHECKING: from specweaver.sandbox... import ...` would produce false positives.

    # --- Phase 2: tach boundary check (existing behavior) ---
    tach_result = self._run_tach_check()

    # --- Merge results ---
    all_violations = forbids_violations + tach_result.violations
    return ArchitectureRunResult(
        violation_count=len(all_violations),
        violations=all_violations,
    )


    # --- Helper methods (H-1: these are methods of PythonQARunner) ---

    def _check_forbids(
        self,
        import_module: str,
        forbids: list[str],
        target_path: Path,
        node: ast.AST,
    ) -> list[ArchitectureViolation]:
        """Check if an import matches any forbids pattern.

        Supports glob-style patterns:
        - "specweaver/sandbox/*" matches "specweaver.sandbox.anything"
        - "specweaver/llm" matches "specweaver.llm" exactly
        """
        import fnmatch

        violations: list[ArchitectureViolation] = []
        # Normalize forbids from path-style to module-style
        for pattern in forbids:
            module_pattern = pattern.replace("/", ".")
            if fnmatch.fnmatch(import_module, module_pattern):
                violations.append(
                    ArchitectureViolation(
                        file=str(target_path),
                        code="ForbiddenImport",
                        message=(
                            f"Import '{import_module}' violates context.yaml "
                            f"forbids pattern '{pattern}'"
                        ),
                    )
                )
        return violations

    def _run_tach_check(self) -> ArchitectureRunResult:
        """Run global tach boundary check (extracted from original method)."""
        try:
            proc = subprocess.run(
                ["python", "-m", "tach", "check", "--output", "json"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(self._cwd),
            )
            if proc.stderr:
                logger.debug(f"PythonQARunner: tach check stderr: {proc.stderr}")
        except subprocess.TimeoutExpired:
            logger.warning("PythonQARunner: tach check timed out")
            return ArchitectureRunResult(
                violation_count=1,
                violations=[
                    ArchitectureViolation(
                        file="<validation_engine>",
                        code="TimeoutExpired",
                        message="Architecture check timed out while executing tach.",
                    )
                ],
            )
        except FileNotFoundError:
            logger.warning("PythonQARunner: tach not found")
            return ArchitectureRunResult(
                violation_count=1,
                violations=[
                    ArchitectureViolation(
                        file="<validation_engine>",
                        code="FileNotFoundError",
                        message="Tach architectural linter is not installed or not found in paths.",
                    )
                ],
            )

        return self._build_architecture_result(proc.stdout)
```

> [!IMPORTANT]
> **Two-phase architecture:** Phase 1 checks `context.yaml` forbids via AST import scanning (per-file, like TS/Java). Phase 2 runs tach globally (existing behavior). Results are merged. This means both tach boundary violations AND context.yaml forbids violations are reported.

> [!IMPORTANT]
> **H-1 clarification:** `_check_forbids` and `_run_tach_check` are **methods of `PythonQARunner`**, not standalone functions. The code above uses proper method indentation (4-space indent inside the class body). The `self` parameter confirms they access instance state (`self._cwd`, `self._build_architecture_result`).

> [!NOTE]
> The `_check_forbids` helper normalizes forbids patterns from path-style (`specweaver/sandbox/*`) to module-style (`specweaver.sandbox.*`) before matching with `fnmatch`. This matches the format used in `context.yaml` across the codebase.

> [!NOTE]
> `dal_level` is logged for diagnostics. Future enhancements (e.g., DAL_A/B treating warnings as errors) can key off this value without further plumbing changes.

---

### Component: Boundary Configuration Cleanup

#### [MODIFY] [tach.toml](file:///c:/development/pitbula/specweaver/tach.toml)

**Goal:** Remove `specweaver.sandbox` from `specweaver.assurance.validation` depends_on.

**Change (line 35):**
```toml
# Before:
depends_on = ["specweaver.sandbox", "specweaver.workspace.analyzers", "specweaver.core.config"]

# After:
depends_on = ["specweaver.workspace.analyzers", "specweaver.core.config"]
```

> [!CAUTION]
> This removal is ONLY safe after ALL three rules (C03, C04, C05) have been refactored. Execute this change LAST in the commit. Verify with `uv run tach check`.

---

## 3. Verification Plan

### Automated Tests

#### [NEW] `tests/unit/assurance/validation/rules/code/test_c03_context.py`

**Replaces C03 tests** from `test_c01_c02_c03.py` (lines 154-244) and `test_code_rules_execution.py` (lines 43-255).

New tests use context injection (no `QARunnerAtom` mocking):

1. `test_rule_id` — `rule_id == "C03"`, `name == "Tests Pass"`.
2. `test_skip_when_no_path` — `spec_path=None` → SKIP.
3. `test_skip_when_no_tests_dir` — No `tests/` dir → SKIP.
4. `test_skip_when_no_test_file` — `tests/` exists but no matching file → SKIP.
5. `test_pass_when_context_reports_success` — Set `rule.context = {"qa_tests_result": {"status": "SUCCESS", "message": "Passed", "exports": {"failed": 0, "errors": 0}}}` → PASS.
6. `test_fail_when_context_reports_failure` — Set context with `exports: {"failed": 1, "failures": [{"message": "assert False"}]}` → FAIL.
7. `test_fail_when_timeout` — Set context with `{"status": "FAILED", "message": "timed out after 120s"}` → FAIL with "timed out" message.
8. `test_fail_when_context_missing_but_tests_exist` — Test file exists, no context key → FAIL ("not hydrated").
9. `test_fail_output_truncated` — Long failure message truncated to 500 chars.
10. `test_fail_no_output` — `failures: []` → FAIL with "No output".

#### [NEW] `tests/unit/assurance/validation/rules/code/test_c04_context.py`

**Replaces C04 tests** from `test_code_rules_execution.py` (lines 263-458).

1. `test_rule_id` — `rule_id == "C04"`, `name == "Coverage"`.
2. `test_skip_when_no_path` — `spec_path=None` → SKIP.
3. `test_pass_when_above_threshold` — Context with `exports: {"coverage_pct": 95.0}` → PASS.
4. `test_fail_when_below_threshold` — Context with `exports: {"coverage_pct": 40.0}` → FAIL.
5. `test_pass_at_exact_threshold` — `coverage_pct == threshold` → PASS.
6. `test_fail_one_below_threshold` — `coverage_pct == threshold - 1` → FAIL.
7. `test_warn_when_coverage_none` — `exports: {"coverage_pct": None}` → WARN.
8. `test_fail_when_timeout` — `{"status": "FAILED", "message": "timed out"}` → FAIL.
9. `test_fail_when_context_missing` — No context key → FAIL ("not hydrated").
10. `test_custom_threshold` — `CoverageRule(threshold=90)._threshold == 90`.
11. `test_default_threshold` — `CoverageRule()._threshold == 70`.

#### [MODIFY] `tests/unit/assurance/validation/rules/test_c01_c02_c03.py`

**Remove C03 tests** (class `TestTestsPassRule`, lines 154-244). Keep C01 (`TestSyntaxValidRule`) and C02 (`TestTestsExistRule`) unchanged.

#### [MODIFY] `tests/unit/assurance/validation/rules/code/test_code_rules.py`

**Replace C05 tests** (class `TestC05ImportDirection`, lines 117-193) with context-injected versions:

1. `test_clean_imports` — Context with `exports: {"violation_count": 0}` → PASS.
2. `test_forbidden_cli_import` — Context with `exports: {"violation_count": 1, "violations": [...]}` → FAIL.
3. `test_no_file_path_skips` — `spec_path=None` → SKIP.
4. `test_missing_context_skips` — No context key → SKIP ("Architecture check results not available").
5. `test_missing_payload_fails` — `exports: {"violation_count": 2, "violations": []}` → FAIL.
6. `test_rule_id` — `rule_id == "C05"`.

**Remove sandbox imports** from the test file (`from specweaver.sandbox.qa_runner.core.interface import ...`).

#### [MODIFY] `tests/unit/assurance/validation/rules/code/test_code_rules_execution.py`

**Remove C03 class** (`TestC03TestsPass`, lines 43-255) and **C04 class** (`TestC04Coverage`, lines 263-458). Keep Generator tests (lines 461-598) and runner filtering tests (lines 600-671) unchanged.

**Remove sandbox imports** at top of file: `from specweaver.sandbox.base import AtomResult, AtomStatus` references inside test methods.

#### [NEW] `tests/unit/core/flow/test_validation_hydrator.py`

Test the new `hydrate_code_validation_context` and `execute_validation_flow` functions:

1. `test_hydrates_tests_result_when_c03_active` — Pipeline with C03 step, mock `QARunnerAtom`, verify `qa_tests_result` key populated with correct dict shape.
2. `test_hydrates_coverage_result_when_c04_active` — Pipeline with C04 step, verify `qa_coverage_result` key.
3. `test_hydrates_architecture_result_when_c05_active` — Pipeline with C05 step, verify `qa_architecture_result` key.
4. `test_skips_all_atoms_when_no_qa_rules_active` — Pipeline with only C01/C02 steps → empty context dict, `QARunnerAtom` never instantiated.
5. `test_no_test_file_sets_none_for_c03` — C03 active but no test file found → `qa_tests_result is None`.
6. `test_atom_exception_produces_error_dict` — `QARunnerAtom.run()` raises → context key is `{"status": "FAILED", "message": "Hydration error: ...", "exports": {}}`.
7. `test_execute_validation_flow_calls_pipeline` — Verify `execute_validation_flow` calls `execute_validation_pipeline` with merged context.
8. `test_execute_validation_flow_merges_extra_context` — Verify extra `context` arg is merged with hydrated QA context.

#### [MODIFY] `tests/unit/sandbox/qa_runner/core/qa_runner/test_atom.py`

**Add `dal_level` forwarding tests** to `TestAtomRunArchitecture` (around line 536):

1. `test_architecture_forwards_dal_level` — Pass `{"intent": "run_architecture", "target": "src/", "dal_level": DALLevel.DAL_B}`. Verify `run_architecture_check` is called with `dal_level=DALLevel.DAL_B`.
2. `test_architecture_forwards_none_dal_level` — Pass `{"intent": "run_architecture", "target": "src/"}` (no dal_level key). Verify `run_architecture_check` is called with `dal_level=None`.

#### [NEW] `tests/unit/sandbox/language/core/language/python/test_runner_architecture.py`

**Test PythonQARunner DAL-aware architecture checking:**

1. `test_forbids_violation_detected` — Create a temp Python file with `from specweaver.sandbox.base import Atom` and a `context.yaml` with `forbids: ["specweaver/sandbox/*"]`. Verify violation is returned with code `"ForbiddenImport"`.
2. `test_no_forbids_violation_when_clean` — Python file with only `import os`. Same `context.yaml`. Verify zero violations from forbids phase.
3. `test_no_context_yaml_skips_forbids_check` — No `context.yaml` present. Only tach results returned.
4. `test_forbids_pattern_glob_matching` — Verify `specweaver/sandbox/*` matches `specweaver.sandbox.anything.deep` but not `specweaver.core.config`.
5. `test_forbids_exact_match` — Verify `specweaver/llm` matches `specweaver.llm` but not `specweaver.llm_tools`.
6. `test_tach_and_forbids_merged` — Mock tach to return 1 violation. Add a forbids violation. Verify `violation_count == 2` and both are present.
7. `test_dal_level_logged` — Pass `dal_level=DALLevel.DAL_A`. Verify it appears in debug log output (caplog).
8. `test_non_python_file_skips_forbids` — Pass a `.txt` target. Verify only tach results returned.
9. `test_directory_target_skips_forbids` — Pass a directory target. Verify only tach results returned.
10. `test_syntax_error_in_target_skips_forbids` — Target file has invalid Python syntax. Verify forbids phase is skipped gracefully (no crash), tach results still returned.
11. `test_type_checking_import_not_flagged` — Python file with `if TYPE_CHECKING: from specweaver.sandbox.base import Atom`. Same `context.yaml` with `forbids: ["specweaver/sandbox/*"]`. Verify **zero** forbids violations (RED-5 fix).

### Manual Verification

1. Run the full unit test suite for validation rules:
   ```
   uv run pytest tests/unit/assurance/validation/ -v
   ```

2. Run the new hydrator tests:
   ```
   uv run pytest tests/unit/core/flow/test_validation_hydrator.py -v
   ```

3. Run atom architecture tests (including new dal_level forwarding tests):
   ```
   uv run pytest tests/unit/sandbox/qa_runner/core/qa_runner/test_atom.py::TestAtomRunArchitecture -v
   ```

4. Run Python runner architecture tests:
   ```
   uv run pytest tests/unit/sandbox/language/core/language/python/test_runner_architecture.py -v
   ```

5. Run tach check and verify `specweaver.sandbox` is no longer in `specweaver.assurance.validation` deps:
   ```
   uv run tach check
   ```

6. Verify no sandbox imports remain in validation rules (grep check):
   ```
   grep -r "from specweaver.sandbox" src/specweaver/assurance/validation/rules/code/c03_tests_pass.py src/specweaver/assurance/validation/rules/code/c04_coverage.py src/specweaver/assurance/validation/rules/code/c05_import_direction.py
   ```

7. Run the full test suite to verify zero regression:
   ```
   uv run pytest tests/ -x --timeout=120
   ```

---

## 4. Commit Boundaries

### Single Commit: SF-4 Validation Layer Isolation

**Production code (ordered):**
1. `atom.py` — fix `_intent_run_architecture` to extract and forward `dal_level` (DAL gap fix, layer 2)
2. `runner.py` (PythonQARunner) — implement context.yaml forbids checking + dal_level logging (DAL gap fix, layer 3)
3. `c03_tests_pass.py` — refactored to read from context
4. `c04_coverage.py` — refactored to read from context (fixes status comparison bug)
5. `c05_import_direction.py` — refactored to read from context
6. `validation_hydrator.py` [NEW] — `hydrate_code_validation_context` + `execute_validation_flow`
7. `core/flow/handlers/validation.py` — wire hydrator into `ValidateCodeHandler._run_validation`
8. `assurance/validation/interfaces/cli.py` — route code validation through `execute_validation_flow`
9. `interfaces/api/v1/validation.py` — route code validation through `execute_validation_flow`
10. `tach.toml` — remove `specweaver.sandbox` from validation deps

**Tests:**
1. `test_atom.py` — add `dal_level` forwarding tests to `TestAtomRunArchitecture`
2. `test_runner_architecture.py` [NEW] — PythonQARunner DAL-aware architecture tests
3. `test_c03_context.py` [NEW] — C03 context-injected tests (replaces old C03 tests)
4. `test_c04_context.py` [NEW] — C04 context-injected tests (replaces old C04 tests)
5. `test_c01_c02_c03.py` — remove C03 test class only
6. `test_code_rules.py` — replace C05 test class with context-injected tests
7. `test_code_rules_execution.py` — remove C03/C04 test classes, keep Generator + filtering tests
8. `test_validation_hydrator.py` [NEW] — hydrator unit tests

---

## 5. ROI Analysis

### Pros
1. **Architectural purity**: `validation` becomes truly `pure-logic` — no sandbox imports, no subprocess execution, no I/O. The `forbids: specweaver/sandbox/*` constraint is finally enforced.
2. **Testability**: Rules can be tested with simple dict injection — no mocking of `QARunnerAtom` or `PythonQARunner` needed. Test files are cleaner and faster.
3. **Performance** (AD-8): Disabled rules no longer trigger unnecessary subprocess calls.
4. **Boundary enforcement**: Removes the last `specweaver.sandbox` dependency from `specweaver.assurance.validation` in tach.toml.
5. **Single entry point** (AD-5): CLI and API both call `execute_validation_flow` — no risk of forgetting hydration.
6. **Bug fix**: C04 status comparison (`"failed"` → `"FAILED"`) is corrected.
7. **DAL-level end-to-end fix**: `dal_level` now flows from hydrator → atom → runner. The PythonQARunner checks `context.yaml` forbids (parity with TS/Java), closing a three-layer gap where the value was silently dropped.
8. **Cross-language parity**: All runners (Python, TypeScript, Java) now enforce `context.yaml` forbids boundaries per-file. Python adds AST-based import scanning alongside tach's global checks.

### Cons
1. **Indirection**: Rules can no longer self-execute QA checks — they depend on upstream hydration.
2. **Test file churn**: 4 new test files, 4 modified test files. Total ~350 new test lines, ~400 removed mock-based lines.
3. **~10 lines of duplicated logic**: Test-file-finding logic exists in both the hydrator and C03.
4. **Scope increase**: DAL-level fix adds ~80 lines to PythonQARunner and ~100 lines of tests, increasing SF-4 blast radius slightly.

---

## 6. Resolved HITL Decisions

| # | Severity | Topic | Decision |
|---|----------|-------|----------|
| H-1 | HIGH | Context data shape | Full AtomResult dict (`{"status": str, "message": str, "exports": dict}`) |
| H-2 | HIGH | Test file path derivation | Hydrator derives path (~10 lines duplication) |
| M-3 | MEDIUM | API/CLI hydration trigger | `level == "code"` check, combined with AD-8 internal optimization |
| M-4 | MEDIUM | C04 coverage target | Hydrator uses correct `code_path` (fixes existing bug) |
| M-5 | MEDIUM | Test migration strategy | **Option 2: Replace with new test files** |
| M-6 | MEDIUM | Hydrator exception handling | Catch → error dict per atom call |
| L-7 | LOW | Status string casing | Uppercase (`"FAILED"`, `"SUCCESS"`) from `AtomStatus.value` |
| L-8 | LOW | Documentation | Defer Guide-2 to pre-commit |
| H-9 | HIGH | DAL-level three-layer gap | **Option C: Full fix in SF-4** — atom forwarding + PythonQARunner context.yaml forbids + target-scoped AST import checking. All in one commit. |
| H-10 | HIGH | TYPE_CHECKING false positives (RED-5) | **Option A:** Skip imports inside `if TYPE_CHECKING:` blocks during AST walk. Adds ~10 lines. Prevents false positive `ForbiddenImport` violations for type-only imports. |

> [!IMPORTANT]
> **Pre-commit Reminder (L-8):** Guide-2 ("How to write a validation rule that receives injected context") MUST be written during the `/pre-commit` workflow. Add this to the pre-commit checklist. It is NOT part of the SF-4 development commit.

---

## 7. Backlog

- **Guide-2 documentation**: To be written during pre-commit (L-8). Must document the context key contract, the `execute_validation_flow` entry point, and how new rules should read from `self.context`.
