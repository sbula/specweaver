# Implementation Plan: Standard Local Execution [SF-2: Language Runner Migration]

- **Feature ID**: E-EXEC-01
- **Sub-Feature**: SF-2 — Language Runner Migration
- **Design Document**: docs/roadmap/features/topic_06_sandbox/E-EXEC-01/E-EXEC-01_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-2
- **Implementation Plan**: docs/roadmap/features/topic_06_sandbox/E-EXEC-01/E-EXEC-01_sf2_implementation_plan.md
- **Status**: APPROVED

## Scope

Migrate all 5 language runners (Python, TypeScript, Rust, Java, Kotlin) from direct `subprocess.run()` calls to `SubprocessExecutor.execute()`. Ensure backward compatibility across all 4900+ tests with zero public API changes.

**FRs**: FR-8
**NFR-1**: All 4900+ existing tests MUST pass unchanged after migration.

## HITL-Resolved Decisions

| # | Decision | User Choice |
|---|----------|-------------|
| H-1 | Python `_run_tach_check` FileNotFoundError handling | Option C — `shutil.which("tach")` pre-check. **Extended to ALL runners** (RED-1.2): every runner method must pre-check its external tool via `shutil.which()` before calling executor. |
| H-2 | TypeScript `self.cwd` vs `self._cwd` | Rename to `self._cwd` for consistency with all 4 other runners. Adapt all TS tests that reference `runner.cwd`. |
| M-1 | Constructor executor parameter | Option A — optional with default `SubprocessExecutor(cwd=cwd)`. Zero breaking changes, DI available for testing. |
| M-2 | Forbid `import subprocess` in runners | Option B — add ruff `flake8-tidy-imports` ban rule in `pyproject.toml`. |
| M-3 | Timeout strategy | Option C — configurable per-method. Class-level `_DEFAULT_TIMEOUT = 120`. Methods like `run_tests` pass `timeout` param through. Build-heavy methods (`run_compiler`, `run_debugger` for Rust/Java/Kotlin) use `_BUILD_TIMEOUT = 300`. |
| M-4 | Dev guide `command=` kwarg | Option A — fix the guide. Combined with `input_text` docs in Commit 3. |
| L-1 | Duration tracking | Option A — use executor's `result.duration_seconds`. |
| L-2 | Remove unused imports | Option A — remove `import time`, `import subprocess`. |
| L-3 | Commit granularity | Option A — 4 commits (3 original + Commit 0 for executor extension). |

## Research Notes

### Call Site Inventory

| Runner | File | `subprocess.run()` Calls | Has Timeout? | Piping? | Notes |
|--------|------|--------------------------|-------------|---------|-------|
| **Python** | `language/core/python/runner.py` | 7 (L168, L229, L238, L253, L313, L398, L468) | ✅ (per-method) | ❌ | Most complex — 7 call sites |
| **TypeScript** | `language/core/typescript/runner.py` | 3 (L91, L158, L258) | ✅ (inconsistent) | ❌ | Uses `shutil.which()` for tool resolution |
| **Rust** | `language/core/rust/runner.py` | 8 (L63, L71, L142, L150, L200, L208, L242, L268) | ❌ missing! | ✅ `input=` | **Inline imports** inside method bodies. Pipes stdout between `cargo test`→`cargo2junit` and `cargo clippy`→`clippy-sarif`. |
| **Java** | `language/core/java/runner.py` | 6 (L90, L130, L179, L206, L225, L323) | ❌ missing! | ❌ | Uses file-based SARIF output (not stdout) for linting/complexity. |
| **Kotlin** | `language/core/kotlin/runner.py` | 5 (L83, L129, L178, L205, L231) | ❌ missing! | ❌ | Nearly identical to Java. |

**Total**: ~29 `subprocess.run()` call sites across 5 runners.

### Test File Inventory

| Runner | Test File | Mock Sites | Mock Pattern |
|--------|-----------|------------|-------------|
| **Python** | `tests/unit/sandbox/language/core/language/python/test_runner.py` | 9 | `patch("subprocess.run")` |
| **Python** | `tests/unit/sandbox/language/core/language/python/test_runner_architecture.py` | — | `patch("subprocess.run")` |
| **TypeScript** | `tests/unit/sandbox/language/core/language/typescript/test_runner.py` | 8 | `patch("subprocess.run")` |
| **Rust** | `tests/unit/sandbox/language/core/language/rust/test_runner.py` | 5 | `patch("subprocess.run")` |
| **Java** | `tests/unit/sandbox/language/core/language/java/test_runner.py` | 9 | `patch("subprocess.run")` |
| **Kotlin** | `tests/unit/sandbox/language/core/language/kotlin/test_runner.py` | 5 | `patch("subprocess.run")` |

**Mock target changes**: All `patch("subprocess.run")` → mock the `SubprocessExecutor.execute` method instead. The mock return value changes from `MagicMock(returncode=..., stdout=..., stderr=...)` to `SubprocessResult(exit_code=..., stdout=..., stderr=..., duration_seconds=..., timed_out=...)`.

### SubprocessExecutor API (from SF-1, extended in Commit 0)

```python
executor = SubprocessExecutor(
    cwd=Path("/workspace"),
    timeout_seconds=120,
    resource_limits=ResourceLimits(),
    strip_credentials=True,
)

result: SubprocessResult = executor.execute(
    cmd=["pytest", "tests/"],
    timeout_seconds=120,       # override default
    extra_env={"MY_VAR": "v"}, # additional env vars
    cwd_override=Path("sub"),  # override cwd (validated)
    input_text="stdin data",   # NEW in Commit 0 — pipe stdin
)
# result.exit_code, result.stdout, result.stderr, result.duration_seconds, result.timed_out, result.events
```

### Key Migration Pattern

Before:
```python
proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=str(self._cwd))
# proc.returncode, proc.stdout, proc.stderr
```

After:
```python
result = self._executor.execute(cmd, timeout_seconds=60)
# result.exit_code, result.stdout, result.stderr, result.duration_seconds
```

**Critical differences:**
- `.returncode` → `.exit_code`
- `TimeoutExpired` exception → `result.timed_out` flag
- `cwd=str(self._cwd)` → set at executor constructor
- `input=data` → `input_text=data` (Commit 0 extension)

### Tool Pre-Check Pattern (H-1 + RED-1.2)

Every runner method that calls an external tool MUST pre-check:

```python
if not shutil.which("tach"):
    return ArchitectureRunResult(violation_count=1, violations=[
        ArchitectureViolation(file="<validation_engine>", code="FileNotFoundError",
            message="Tach is not installed or not found in PATH.")
    ])
result = self._executor.execute(["tach", "check", "--output", "json"])
```

Applied to:
- Python: `tach` (in `_run_tach_check`)
- TypeScript: `npx`, `tsc`, `node`, `tsx` (in `run_compiler`, `run_debugger`)
- Rust: `cargo`, `cargo2junit`, `clippy-sarif` (in `run_tests`, `run_linter`, `run_complexity`, `run_compiler`, `run_debugger`)
- Java: `mvn`/`gradle` or wrapper scripts (in all methods)
- Kotlin: `mvn`/`gradle` or wrapper scripts (in all methods)

### Timeout Constants

```python
class PythonQARunner(QARunnerInterface):
    _DEFAULT_TIMEOUT: int = 120
    _BUILD_TIMEOUT: int = 300  # run_debugger
```

For Rust/Java/Kotlin, `_BUILD_TIMEOUT = 300` is used for `run_tests`, `run_compiler`, `run_debugger` because cargo/maven/gradle builds can take minutes.

> [!NOTE]
> The `run_tests` method already accepts a `timeout` parameter in the interface. The runner passes this through to the executor. Other methods use class constants.

## Proposed Changes

### Component: SubprocessExecutor Extension (MODIFY — 3 files)

---

#### [MODIFY] [executor.py](file:///c:/development/pitbula/specweaver/src/specweaver/sandbox/execution/executor.py)

Add `input_text: str | None = None` parameter to `execute()` method. When provided, pass to `proc.communicate(input=input_text, timeout=...)`.

```python
def execute(
    self,
    cmd: list[str],
    *,
    timeout_seconds: int | None = None,
    extra_env: dict[str, str] | None = None,
    cwd_override: Path | None = None,
    input_text: str | None = None,  # NEW
) -> SubprocessResult:
```

---

#### [MODIFY] [test_executor.py](file:///c:/development/pitbula/specweaver/tests/unit/sandbox/execution/test_executor.py)

Add 3 tests:

| Test Method | Description |
|------------|-------------|
| `test_input_text_piped_to_stdin` | Pass input_text, verify child receives it on stdin |
| `test_input_text_none_default` | Default None → no stdin piped |
| `test_input_text_with_timeout` | input_text + timeout → correct behavior |

---

#### [MODIFY] [subprocess_execution.md](file:///c:/development/pitbula/specweaver/docs/dev_guides/subprocess_execution.md)

Fix M-4: `command=` → `cmd=`. Add `input_text` usage example. Fix `limits=` parameter placement (constructor-level, not per-call).

---

### Component: Language Runners (MODIFY — 5 files)

Each runner follows the same migration pattern:

1. **Constructor**: Add `executor: SubprocessExecutor | None = None` parameter (default creates one from `cwd`)
2. **Each method**: Replace `subprocess.run()` → `self._executor.execute()`
3. **Pre-checks**: Add `shutil.which()` before calling external tools
4. **Imports**: Remove `import subprocess`, `import time` (where only used for duration tracking)
5. **Timeout**: Use class constants `_DEFAULT_TIMEOUT` / `_BUILD_TIMEOUT`

---

#### [MODIFY] [runner.py](file:///c:/development/pitbula/specweaver/src/specweaver/sandbox/language/core/python/runner.py)

**PythonQARunner** — 7 call sites migrated.

Import changes:
- Remove: `import subprocess`, `import time`
- Add: `import shutil`, `from specweaver.sandbox.execution import SubprocessExecutor`

Constructor:
```python
def __init__(self, cwd: Path, executor: SubprocessExecutor | None = None) -> None:
    self._cwd = cwd
    self._executor = executor or SubprocessExecutor(cwd=cwd)
```

Method-specific notes:
- `run_tests`: Remove `time.monotonic()` duration tracking. Use `result.duration_seconds`. Remove `try/except TimeoutExpired` → check `result.timed_out`.
- `run_linter`: 3 subprocess calls → 3 executor calls. Remove `contextlib.suppress(subprocess.TimeoutExpired)` → check `result.timed_out`.
- `run_complexity`: 1 call.
- `run_debugger`: 1 call. `result.events` replaces manual OutputEvent construction.
- `_run_tach_check`: Add `shutil.which("tach")` pre-check. 1 call. `FileNotFoundError` branch replaced by pre-check.

---

#### [MODIFY] [runner.py](file:///c:/development/pitbula/specweaver/src/specweaver/sandbox/language/core/typescript/runner.py)

**TypeScriptRunner** — 3 call sites.

Rename: `self.cwd` → `self._cwd` (H-2 consistency).

Import changes:
- Remove: `import subprocess`, `import time`
- Add: `from specweaver.sandbox.execution import SubprocessExecutor`

Constructor:
```python
def __init__(self, cwd: Path, executor: SubprocessExecutor | None = None) -> None:
    self._cwd = cwd  # RENAMED from self.cwd
    self._executor = executor or SubprocessExecutor(cwd=cwd)
```

Method-specific notes:
- `run_compiler`: Already has `shutil.which("npx")`. Replace `FileNotFoundError` catch with pre-check returning the same error result.
- `run_debugger`: Same pre-check pattern for `npx`/`node`/`tsx`.
- `run_architecture_check`: 1 call. Already has timeout.

---

#### [MODIFY] [runner.py](file:///c:/development/pitbula/specweaver/src/specweaver/sandbox/language/core/rust/runner.py)

**RustRunner** — 8 call sites. **Special: uses `input=` piping (2 sites).**

Import changes:
- Remove ALL inline `import subprocess` from method bodies (L52, L131, L185, L233, L262)
- Remove inline `import time` from `run_tests` (L53)
- Add: `import shutil`, `from specweaver.sandbox.execution import SubprocessExecutor`

Constructor:
```python
def __init__(self, cwd: Path, executor: SubprocessExecutor | None = None) -> None:
    self._cwd = cwd
    self._executor = executor or SubprocessExecutor(cwd=cwd)
```

Method-specific notes:
- `run_tests`: Two-stage pipe: `cargo test` → `cargo2junit`. Use `result = self._executor.execute(["cargo", "test", ...])`, then `junit_result = self._executor.execute(["cargo2junit"], input_text=result.stdout)`.
- `run_linter`: Two-stage pipe: `cargo clippy` → `clippy-sarif`. Same `input_text` pattern.
- `run_complexity`: Two-stage pipe: `cargo clippy` → `clippy-sarif`. Same pattern.
- `run_compiler`: Single call. Add `shutil.which("cargo")` pre-check.
- `run_debugger`: Single call. Add pre-check.
- **Narrow `except Exception`** (RED-2.3): Replace with `except (OSError, json.JSONDecodeError, AttributeError, junitparser.JUnitXmlError)` where applicable.

---

#### [MODIFY] [runner.py](file:///c:/development/pitbula/specweaver/src/specweaver/sandbox/language/core/java/runner.py)

**JavaRunner** — 6 call sites.

Import changes:
- Remove: `import subprocess`
- Add: `import shutil`, `from specweaver.sandbox.execution import SubprocessExecutor`

Constructor:
```python
def __init__(self, cwd: Path, executor: SubprocessExecutor | None = None) -> None:
    self._cwd = cwd
    self._build_tool: str | None = None
    self._executor = executor or SubprocessExecutor(cwd=cwd)
```

Method-specific notes:
- `run_tests`: Build tool pre-check (`mvn`/`gradle`/wrapper). Uses `_BUILD_TIMEOUT`.
- `run_linter`/`run_complexity`: SARIF file-based output — executor call doesn't use stdout, but gains timeout + env isolation.
- `run_architecture_check`: Has existing `TimeoutExpired` handling → replace with `result.timed_out`.

---

#### [MODIFY] [runner.py](file:///c:/development/pitbula/specweaver/src/specweaver/sandbox/language/core/kotlin/runner.py)

**KotlinRunner** — 5 call sites. Nearly identical to Java.

Same import, constructor, and migration pattern as Java.

---

### Component: Test Migration (MODIFY — 7 files)

---

#### [MODIFY] `tests/unit/sandbox/language/core/language/python/test_runner.py` (9 mock sites)
#### [MODIFY] `tests/unit/sandbox/language/core/language/python/test_runner_architecture.py`
#### [MODIFY] `tests/unit/sandbox/language/core/language/typescript/test_runner.py` (8 mock sites)
#### [MODIFY] `tests/unit/sandbox/language/core/language/rust/test_runner.py` (5 mock sites)
#### [MODIFY] `tests/unit/sandbox/language/core/language/java/test_runner.py` (9 mock sites)
#### [MODIFY] `tests/unit/sandbox/language/core/language/kotlin/test_runner.py` (5 mock sites)

For ALL test files:
- Change mock target: `patch("subprocess.run")` → `patch.object(SubprocessExecutor, "execute")`
- Change mock return value: `MagicMock(returncode=0, stdout="...", stderr="")` → `SubprocessResult(exit_code=0, stdout="...", stderr="", duration_seconds=0.1)`
- For TS tests: update any `runner.cwd` references → `runner._cwd`

---

#### [NEW] `tests/unit/sandbox/language/core/test_runner_migration.py`

Central migration verification tests:

| Test Method | Description |
|------------|-------------|
| `test_python_runner_accepts_executor` | `PythonQARunner(cwd, executor=mock)` stores it |
| `test_python_runner_creates_default_executor` | `PythonQARunner(cwd)` auto-creates executor |
| `test_typescript_runner_uses_private_cwd` | `TypeScriptRunner(cwd)._cwd` is set |
| `test_rust_runner_accepts_executor` | Same as Python |
| `test_java_runner_accepts_executor` | Same as Python |
| `test_kotlin_runner_accepts_executor` | Same as Python |

---

### Component: Configuration (MODIFY — 1 file)

---

#### [MODIFY] `pyproject.toml`

Add ruff `flake8-tidy-imports` ban rule for `subprocess` module in language runners (M-2):

```toml
[tool.ruff.lint.flake8-tidy-imports.banned-api]
"subprocess".msg = "Use SubprocessExecutor from specweaver.sandbox.execution instead. See docs/dev_guides/subprocess_execution.md."
```

> [!WARNING]
> This ban is GLOBAL. The `SubprocessExecutor` itself and test files that need raw subprocess must be exempted via per-file-ignores:
> ```toml
> [tool.ruff.lint.per-file-ignores]
> "src/specweaver/sandbox/execution/*.py" = ["TID251"]
> "tests/**" = ["TID251"]
> ```

---

## Red Team / Blue Team Cycles

See: [sf2_red_blue_analysis.md](file:///C:/Users/steve/.gemini/antigravity-ide/brain/abc3f44d-e757-4263-b061-0ee36932bb3a/sf2_red_blue_analysis.md)

Summary: 2 cycles, 14 findings, converged. 1 CRITICAL (fixed: input_text API gap), 3 HIGH (all fixed), 5 MEDIUM (4 fixed, 1 accepted risk), 2 LOW (fixed). 3 accepted risks documented.

---

## Commit Boundaries

### Commit 0: SubprocessExecutor input_text Extension
- **Files**:
  - [MODIFY] `src/specweaver/sandbox/execution/executor.py`
  - [MODIFY] `tests/unit/sandbox/execution/test_executor.py`
- **Message**: `feat(sandbox): add input_text support to SubprocessExecutor [E-EXEC-01 SF-2]`
- **Verification**: All SF-1 existing tests pass. 3 new tests pass.

### Commit 1: Python Runner Migration
- **Files**:
  - [MODIFY] `src/specweaver/sandbox/language/core/python/runner.py`
  - [MODIFY] `tests/unit/sandbox/language/core/language/python/test_runner.py`
  - [MODIFY] `tests/unit/sandbox/language/core/language/python/test_runner_architecture.py`
  - [NEW] `tests/unit/sandbox/language/core/test_runner_migration.py` (Python entries only)
- **Message**: `refactor(sandbox): migrate PythonQARunner to SubprocessExecutor [E-EXEC-01 SF-2]`
- **Verification**: All Python runner tests pass. Full suite regression.

### Commit 2: TypeScript + Rust Runner Migration
- **Files**:
  - [MODIFY] `src/specweaver/sandbox/language/core/typescript/runner.py`
  - [MODIFY] `src/specweaver/sandbox/language/core/rust/runner.py`
  - [MODIFY] `tests/unit/sandbox/language/core/language/typescript/test_runner.py`
  - [MODIFY] `tests/unit/sandbox/language/core/language/rust/test_runner.py`
  - [MODIFY] `tests/unit/sandbox/language/core/test_runner_migration.py` (add TS + Rust entries)
- **Message**: `refactor(sandbox): migrate TS and Rust runners to SubprocessExecutor [E-EXEC-01 SF-2]`
- **Verification**: TS rename `self.cwd` → `self._cwd` verified. Rust inline imports removed. All tests green.

### Commit 3: Java + Kotlin + Config + Docs + Final Regression
- **Files**:
  - [MODIFY] `src/specweaver/sandbox/language/core/java/runner.py`
  - [MODIFY] `src/specweaver/sandbox/language/core/kotlin/runner.py`
  - [MODIFY] `tests/unit/sandbox/language/core/language/java/test_runner.py`
  - [MODIFY] `tests/unit/sandbox/language/core/language/kotlin/test_runner.py`
  - [MODIFY] `tests/unit/sandbox/language/core/test_runner_migration.py` (add Java + Kotlin entries)
  - [MODIFY] `pyproject.toml` (subprocess ban rule)
  - [MODIFY] `docs/dev_guides/subprocess_execution.md` (fix cmd=, add input_text)
- **Message**: `refactor(sandbox): migrate Java and Kotlin runners, ban subprocess import [E-EXEC-01 SF-2]`
- **Verification**: Full 4900+ test suite regression. ruff + mypy + C90 + tach clean.

---

## Verification Plan

### Automated Tests (per commit)
```bash
pytest tests/unit/sandbox/execution/ -v
pytest tests/unit/sandbox/language/ -v
pytest tests/ -x -q
```

### Full Quality Gate (Commit 3 — final)
```bash
ruff check src/specweaver/sandbox/language/
ruff check --select C90 src/specweaver/sandbox/language/
mypy src/specweaver/sandbox/language/
tach check
```

### Manual Verification
- Verify no `import subprocess` remains in any runner.py (grep check)
- Run `sw test` on a real Python project to verify end-to-end
- Verify timeout behavior on a deliberately slow test

---

## Accepted Risks

| # | Risk | Justification |
|---|------|---------------|
| 1 | Broad `except Exception` in Java/Kotlin runners | Pre-existing issue. Out of scope for FR-8. Narrowed for Rust only (higher risk due to multi-stage pipes). Java/Kotlin deferred to TECH debt. |
| 2 | Java/Kotlin stdout capture overhead for SARIF-based methods | Negligible overhead (< 1ms). Consistency outweighs micro-optimization. |
| 3 | TOCTOU gap between `shutil.which()` and executor call | Same accepted risk as SF-1. Probability essentially zero. Executor catches OSError as fallback. |

---

## Backlog (generated by this plan)

- **TECH-010**: Narrow `except Exception` in Java/Kotlin runners to specific exception types.
- **TECH-009**: (existing) Migrate `git/core/executor.py` and `filesystem/core/search.py` to `SubprocessExecutor`.
