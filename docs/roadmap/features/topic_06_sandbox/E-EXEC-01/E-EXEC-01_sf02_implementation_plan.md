# E-EXEC-01 SF-02 — Language Runner Migration

**Status**: APPROVED. Final commit `de9ffcd6` (2026-07-12). · **FRs owned**: FR-8 (and NFR-1: all
4900+ existing tests pass unchanged) · **Depends on**: SF-01 · Design: [E-EXEC-01_design.md](E-EXEC-01_design.md) §Sub-features → SF-02

## Goal

Move all 5 language runners (Python, TypeScript, Rust, Java, Kotlin) from direct `subprocess.run()`
to `SubprocessExecutor.execute()`, with zero public API changes.

## Where it plugs in

| Runner | File | `subprocess.run()` Calls | Has Timeout? | Piping? | Notes |
|--------|------|--------------------------|-------------|---------|-------|
| **Python** | `language/core/python/runner.py` | 7 (L168, L229, L238, L253, L313, L398, L468) | ✅ (per-method) | ❌ | Most complex — 7 call sites |
| **TypeScript** | `language/core/typescript/runner.py` | 3 (L91, L158, L258) | ✅ (inconsistent) | ❌ | Uses `shutil.which()` for tool resolution |
| **Rust** | `language/core/rust/runner.py` | 8 (L63, L71, L142, L150, L200, L208, L242, L268) | ❌ missing! | ✅ `input=` | **Inline imports** inside method bodies. Pipes stdout between `cargo test`→`cargo2junit` and `cargo clippy`→`clippy-sarif`. |
| **Java** | `language/core/java/runner.py` | 6 (L90, L130, L179, L206, L225, L323) | ❌ missing! | ❌ | Uses file-based SARIF output (not stdout) for linting/complexity. |
| **Kotlin** | `language/core/kotlin/runner.py` | 5 (L83, L129, L178, L205, L231) | ❌ missing! | ❌ | Nearly identical to Java. |

~29 `subprocess.run()` call sites in total.

| Runner | Test File | Mock Sites |
|--------|-----------|------------|
| **Python** | `tests/unit/sandbox/language/core/language/python/test_runner.py` | 9 |
| **Python** | `tests/unit/sandbox/language/core/language/python/test_runner_architecture.py` | — |
| **TypeScript** | `tests/unit/sandbox/language/core/language/typescript/test_runner.py` | 8 |
| **Rust** | `tests/unit/sandbox/language/core/language/rust/test_runner.py` | 5 |
| **Java** | `tests/unit/sandbox/language/core/language/java/test_runner.py` | 9 |
| **Kotlin** | `tests/unit/sandbox/language/core/language/kotlin/test_runner.py` | 5 |

All mock `patch("subprocess.run")` returning `MagicMock(returncode=..., stdout=..., stderr=...)`.

Executor API (SF-01, plus `input_text` from Commit 0):

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

## Decisions (HITL)

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

Red/Blue: 2 cycles, 14 findings, converged. 1 CRITICAL (the `input_text` API gap — fixed), 3 HIGH (all
fixed), 5 MEDIUM (4 fixed, 1 accepted), 2 LOW (fixed). 3 accepted risks:

| # | Risk | Justification |
|---|------|---------------|
| 1 | Broad `except Exception` in Java/Kotlin runners | Pre-existing, out of scope for FR-8. Narrowed for Rust only (higher risk: multi-stage pipes). Java/Kotlin deferred to TECH debt (TECH-010 in this plan). |
| 2 | Java/Kotlin stdout capture overhead for SARIF-based methods | Negligible (< 1ms). Consistency outweighs micro-optimization. |
| 3 | TOCTOU gap between `shutil.which()` and executor call | Same accepted risk as SF-01. Probability essentially zero; the executor catches OSError as fallback. |

## Changes

### Migration pattern

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

- `.returncode` → `.exit_code`
- `TimeoutExpired` exception → `result.timed_out` flag
- `cwd=str(self._cwd)` → set at executor constructor
- `input=data` → `input_text=data` (Commit 0)

Per runner: (1) constructor takes `executor: SubprocessExecutor | None = None` (default built from
`cwd`); (2) `subprocess.run()` → `self._executor.execute()`; (3) `shutil.which()` pre-check before
each external tool; (4) drop `import subprocess`, and `import time` where it only tracked duration;
(5) timeouts from `_DEFAULT_TIMEOUT` / `_BUILD_TIMEOUT`.

Tool pre-check (H-1 + RED-1.2):

```python
if not shutil.which("tach"):
    return ArchitectureRunResult(violation_count=1, violations=[
        ArchitectureViolation(file="<validation_engine>", code="FileNotFoundError",
            message="Tach is not installed or not found in PATH.")
    ])
result = self._executor.execute(["tach", "check", "--output", "json"])
```

Applied to: Python `tach` (`_run_tach_check`); TypeScript `npx`, `tsc`, `node`, `tsx` (`run_compiler`,
`run_debugger`); Rust `cargo`, `cargo2junit`, `clippy-sarif` (`run_tests`, `run_linter`,
`run_complexity`, `run_compiler`, `run_debugger`); Java and Kotlin `mvn`/`gradle` or wrapper scripts
(all methods).

Timeouts:

```python
class PythonQARunner(QARunnerInterface):
    _DEFAULT_TIMEOUT: int = 120
    _BUILD_TIMEOUT: int = 300  # run_debugger
```

Rust/Java/Kotlin use `_BUILD_TIMEOUT = 300` for `run_tests`, `run_compiler`, `run_debugger` — cargo,
maven and gradle builds take minutes. `run_tests` passes the interface's `timeout` parameter through;
other methods use the class constants.

### Commit 0 — executor `input_text`

`src/specweaver/sandbox/execution/executor.py`: add `input_text: str | None = None`; when set, pass it
to `proc.communicate(input=input_text, timeout=...)`.

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

`docs/dev_guides/subprocess_execution.md` (M-4): `command=` → `cmd=`; add an `input_text` example;
`limits=` belongs on the constructor, not per call.

### Runners

**PythonQARunner** (`src/specweaver/sandbox/language/core/python/runner.py`) — 7 call sites. Remove
`import subprocess`, `import time`; add `import shutil`, `from specweaver.sandbox.execution import SubprocessExecutor`.

```python
def __init__(self, cwd: Path, executor: SubprocessExecutor | None = None) -> None:
    self._cwd = cwd
    self._executor = executor or SubprocessExecutor(cwd=cwd)
```

- `run_tests`: `result.duration_seconds` replaces `time.monotonic()`; `result.timed_out` replaces
  `try/except TimeoutExpired`.
- `run_linter`: 3 calls; `result.timed_out` replaces `contextlib.suppress(subprocess.TimeoutExpired)`.
- `run_complexity`: 1 call. `run_debugger`: 1 call; `result.events` replaces manual OutputEvent
  construction.
- `_run_tach_check`: `shutil.which("tach")` pre-check replaces the `FileNotFoundError` branch; 1 call.

**TypeScriptRunner** (`src/specweaver/sandbox/language/core/typescript/runner.py`) — 3 call sites.
`self.cwd` → `self._cwd` (H-2). Remove `import subprocess`, `import time`; add
`from specweaver.sandbox.execution import SubprocessExecutor`.

```python
def __init__(self, cwd: Path, executor: SubprocessExecutor | None = None) -> None:
    self._cwd = cwd  # RENAMED from self.cwd
    self._executor = executor or SubprocessExecutor(cwd=cwd)
```

- `run_compiler`: already has `shutil.which("npx")`; the pre-check returns the same error result the
  `FileNotFoundError` catch did.
- `run_debugger`: same pre-check for `npx`/`node`/`tsx`.
- `run_architecture_check`: 1 call; already has a timeout.

**RustRunner** (`src/specweaver/sandbox/language/core/rust/runner.py`) — 8 call sites, 2 with `input=`
piping. Remove ALL inline `import subprocess` (L52, L131, L185, L233, L262) and the inline `import time`
in `run_tests` (L53); add `import shutil`, `from specweaver.sandbox.execution import SubprocessExecutor`.

```python
def __init__(self, cwd: Path, executor: SubprocessExecutor | None = None) -> None:
    self._cwd = cwd
    self._executor = executor or SubprocessExecutor(cwd=cwd)
```

- `run_tests`: `cargo test` → `cargo2junit`:
  `result = self._executor.execute(["cargo", "test", ...])`, then
  `junit_result = self._executor.execute(["cargo2junit"], input_text=result.stdout)`.
- `run_linter` and `run_complexity`: `cargo clippy` → `clippy-sarif`, same `input_text` pattern.
- `run_compiler`: single call, `shutil.which("cargo")` pre-check. `run_debugger`: single call, pre-check.
- RED-2.3: narrow `except Exception` to
  `except (OSError, json.JSONDecodeError, AttributeError, junitparser.JUnitXmlError)` where applicable.

**JavaRunner** (`src/specweaver/sandbox/language/core/java/runner.py`) — 6 call sites. Remove
`import subprocess`; add `import shutil`, `from specweaver.sandbox.execution import SubprocessExecutor`.

```python
def __init__(self, cwd: Path, executor: SubprocessExecutor | None = None) -> None:
    self._cwd = cwd
    self._build_tool: str | None = None
    self._executor = executor or SubprocessExecutor(cwd=cwd)
```

- `run_tests`: build tool pre-check (`mvn`/`gradle`/wrapper); `_BUILD_TIMEOUT`.
- `run_linter`/`run_complexity`: SARIF goes to a file, so stdout is unused, but the call gains timeout
  and env isolation.
- `run_architecture_check`: `result.timed_out` replaces the `TimeoutExpired` handling.

**KotlinRunner** (`src/specweaver/sandbox/language/core/kotlin/runner.py`) — 5 call sites; same
imports, constructor and pattern as Java.

### Config — `pyproject.toml` (M-2)

```toml
[tool.ruff.lint.flake8-tidy-imports.banned-api]
"subprocess".msg = "Use SubprocessExecutor from specweaver.sandbox.execution instead. See docs/dev_guides/subprocess_execution.md."
```

The ban is GLOBAL, so the executor itself and tests that need raw subprocess are exempted:
> ```toml
> [tool.ruff.lint.per-file-ignores]
> "src/specweaver/sandbox/execution/*.py" = ["TID251"]
> "tests/**" = ["TID251"]
> ```

### Commits

| Commit | Files | Message |
|---|---|---|
| 0 | [MODIFY] `src/specweaver/sandbox/execution/executor.py`, `tests/unit/sandbox/execution/test_executor.py` | `feat(sandbox): add input_text support to SubprocessExecutor [E-EXEC-01 SF-02]` |
| 1 | [MODIFY] `src/specweaver/sandbox/language/core/python/runner.py`, Python `test_runner.py` + `test_runner_architecture.py`; [NEW] `tests/unit/sandbox/language/core/test_runner_migration.py` (Python entries only) | `refactor(sandbox): migrate PythonQARunner to SubprocessExecutor [E-EXEC-01 SF-02]` |
| 2 | [MODIFY] `src/specweaver/sandbox/language/core/typescript/runner.py`, `src/specweaver/sandbox/language/core/rust/runner.py`, their `test_runner.py`, `test_runner_migration.py` (add TS + Rust entries) | `refactor(sandbox): migrate TS and Rust runners to SubprocessExecutor [E-EXEC-01 SF-02]` |
| 3 | [MODIFY] `src/specweaver/sandbox/language/core/java/runner.py`, `src/specweaver/sandbox/language/core/kotlin/runner.py`, their `test_runner.py`, `test_runner_migration.py` (add Java + Kotlin entries), `pyproject.toml` (subprocess ban rule), `docs/dev_guides/subprocess_execution.md` (fix cmd=, add input_text) | `refactor(sandbox): migrate Java and Kotlin runners, ban subprocess import [E-EXEC-01 SF-02]` |

Per-commit checks: Commit 0 — SF-01 tests plus 3 new pass. Commit 1 — Python runner tests, full suite.
Commit 2 — TS rename `self.cwd` → `self._cwd` verified, Rust inline imports removed, all green.
Commit 3 — full 4900+ regression; ruff + mypy + C90 + tach clean.

## Tests

`tests/unit/sandbox/execution/test_executor.py` — 3 added:

| Test Method | Description |
|------------|-------------|
| `test_input_text_piped_to_stdin` | Pass input_text, verify child receives it on stdin |
| `test_input_text_none_default` | Default None → no stdin piped |
| `test_input_text_with_timeout` | input_text + timeout → correct behavior |

All six runner test files above: `patch("subprocess.run")` → `patch.object(SubprocessExecutor, "execute")`;
return value `MagicMock(returncode=0, stdout="...", stderr="")` →
`SubprocessResult(exit_code=0, stdout="...", stderr="", duration_seconds=0.1)` (fields
`SubprocessResult(exit_code=..., stdout=..., stderr=..., duration_seconds=..., timed_out=...)`); TS tests
`runner.cwd` → `runner._cwd`.

[NEW] `tests/unit/sandbox/language/core/test_runner_migration.py`:

| Test Method | Description |
|------------|-------------|
| `test_python_runner_accepts_executor` | `PythonQARunner(cwd, executor=mock)` stores it |
| `test_python_runner_creates_default_executor` | `PythonQARunner(cwd)` auto-creates executor |
| `test_typescript_runner_uses_private_cwd` | `TypeScriptRunner(cwd)._cwd` is set |
| `test_rust_runner_accepts_executor` | Same as Python |
| `test_java_runner_accepts_executor` | Same as Python |
| `test_kotlin_runner_accepts_executor` | Same as Python |

```bash
pytest tests/unit/sandbox/execution/ -v
pytest tests/unit/sandbox/language/ -v
pytest tests/ -x -q
```

Final gate (Commit 3):

```bash
ruff check src/specweaver/sandbox/language/
ruff check --select C90 src/specweaver/sandbox/language/
mypy src/specweaver/sandbox/language/
tach check
```

Manual: no `import subprocess` left in any runner.py (grep); `sw test` on a real Python project;
timeout behavior on a deliberately slow test.

## As built

Backlog raised: **TECH-010** — narrow `except Exception` in Java/Kotlin runners. **TECH-009**
(existing) — migrate `git/core/executor.py` and `filesystem/core/search.py` to `SubprocessExecutor`;
since done.

**Since changed** (noted 2026-09-25): the ruff ban message now reads "Use SubprocessExecutor from
specweaver.sandbox.execution.executor instead." (`pyproject.toml`). In the roadmap, TECH-010 is "MCP
Persistent-Process Executor Migration", not the narrowing above.
