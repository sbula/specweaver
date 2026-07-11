# Implementation Plan: Standard Local Execution [SF-1: SubprocessExecutor Core]

- **Feature ID**: E-EXEC-01
- **Sub-Feature**: SF-1 — SubprocessExecutor Core
- **Design Document**: docs/roadmap/features/topic_06_sandbox/E-EXEC-01/E-EXEC-01_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-1
- **Implementation Plan**: docs/roadmap/features/topic_06_sandbox/E-EXEC-01/E-EXEC-01_sf1_implementation_plan.md
- **Status**: APPROVED

## Scope

Create the `SubprocessExecutor` class with `execute()` method, `SubprocessResult` dataclass, cross-platform `PlatformLimiter`, timeout escalation, environment allowlisting, path validation, and structured telemetry logging.

**FRs**: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-9, FR-10

**Runners in scope** (all 5 existing language runners that will consume this in SF-2):
- `PythonQARunner` (`sandbox/language/core/python/runner.py`)
- `TypeScriptRunner` (`sandbox/language/core/typescript/runner.py`)
- `RustRunner` (`sandbox/language/core/rust/runner.py`)
- `JavaRunner` (`sandbox/language/core/java/runner.py`)
- `KotlinRunner` (`sandbox/language/core/kotlin/runner.py`)

**Platforms**: Windows 11 (26H2+), Linux (kernel 7.1+, all distros with Python 3.11+), macOS Tahoe (26+)

## Research Notes

### Codebase Patterns Found
- All 5 language runners call `subprocess.run()` with `capture_output=True, text=True, check=False`
- Python runner is the only one using `time.monotonic()` for duration tracking
- Python runner uses `subprocess.TimeoutExpired` exception for timeout handling
- `OutputEvent` dataclass in `commons/qa.py` (L117-126) has: `category: str`, `output: str`, `file: str = ""`, `line: int = 0`
- `WorkspaceBoundary.validate_path()` in `sandbox/security.py` (L76-99) provides the path validation pattern
- Sandbox modules use `archetype: adapter` in their `context.yaml`
- `SUPPORTED_LANGUAGES = frozenset({"python", "java", "kotlin", "typescript", "rust"})` in `_detect.py`

### Win32 Job Objects (ctypes)
- Use `CreateJobObjectW`, `SetInformationJobObject`, `AssignProcessToJobObject`
- Define `JOBOBJECT_EXTENDED_LIMIT_INFORMATION` via `ctypes.Structure`
- Set `LimitFlags = JOB_OBJECT_LIMIT_PROCESS_MEMORY` (0x00000100)
- On modern Windows (8+), nested jobs are supported, safe in CI environments
- Use `OpenProcess(PROCESS_ALL_ACCESS, False, proc.pid)` to get handle (NOT private `proc._handle`)

### Unix/macOS resource module
- `resource.setrlimit(resource.RLIMIT_AS, (soft, hard))` — limits virtual memory (works on Linux AND macOS)
- `resource.setrlimit(resource.RLIMIT_NPROC, (soft, hard))` — limits process count (Linux AND macOS)
- Applied via `preexec_fn` parameter of `subprocess.Popen`

## HITL-Resolved Decisions

| # | Decision | User Choice |
|---|----------|-------------|
| H-1 | Windows timeout escalation | Use `proc.terminate()` — TerminateProcess is the Windows equivalent of SIGKILL. 2s grace applies only on Unix. |
| H-2 | Win32 Job Object handle access | Use `OpenProcess(PROCESS_ALL_ACCESS, False, proc.pid)` via ctypes (public `.pid`, not `proc._handle`). Close handle via `CloseHandle` after assignment. |
| H-3 | Environment allowlist scope | Include `GIT_EXEC_PATH, GIT_DIR` in default allowlist now (forward-compatible with TECH-008). |
| H-4 | `context.yaml` forbids | Add explicit `forbids: [sandbox/qa_runner, core/flow]` entries to `sandbox/execution/context.yaml`. |
| H-5 | Signal propagation | Use `os.setpgrp()` on Unix/macOS. Executor manages child lifecycle explicitly. |

## Proposed Changes

### Component: Execution Module (NEW)

---

#### [NEW] `src/specweaver/sandbox/execution/__init__.py`

Empty `__init__.py` — implicit namespace package.

---

#### [NEW] `src/specweaver/sandbox/execution/context.yaml`

> [!IMPORTANT]
> Per H-4, includes explicit forbids to prevent circular dependencies.

```yaml
archetype: adapter
forbids:
  - sandbox/qa_runner
  - core/flow
```

---

#### [NEW] `src/specweaver/sandbox/execution/executor.py`

Core module. ≤ 300 lines.

```python
@dataclass(frozen=True)
class SubprocessResult:
    """Structured result from a subprocess execution."""
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False
    events: list[OutputEvent] = field(default_factory=list)

@dataclass(frozen=True)
class ResourceLimits:
    """Cross-platform resource constraints for subprocess execution."""
    max_memory_bytes: int | None = None    # Virtual memory limit
    max_processes: int | None = None       # Fork bomb protection
    max_file_size_bytes: int | None = None # Output file size cap

class SubprocessExecutor:
    """Unified, cross-platform subprocess execution with security boundaries.

    Handles all OS-specific differences internally so callers see one
    consistent API across Windows, Linux, and macOS.

    Args:
        cwd: Working directory for all subprocesses.
        timeout_seconds: Default timeout (overridable per-call).
        resource_limits: Optional resource constraints.
        env_allowlist: Env vars to forward to child (default: safe set).
        strip_credentials: If True, remove known API key env vars.
    """
    def __init__(
        self,
        cwd: Path,
        timeout_seconds: int = 120,
        resource_limits: ResourceLimits | None = None,
        env_allowlist: frozenset[str] | None = None,
        strip_credentials: bool = True,
    ) -> None: ...

    def execute(
        self,
        cmd: list[str],
        *,
        timeout_seconds: int | None = None,
        extra_env: dict[str, str] | None = None,
        cwd_override: Path | None = None,
    ) -> SubprocessResult:
        """Execute a subprocess with full security and telemetry."""
        ...
```

**Key implementation details:**

1. **`_build_env()`**: Builds child environment from allowlist + extra_env. Default allowlist:
   `PATH, HOME, USERPROFILE, LANG, LC_ALL, TERM, PYTHONPATH, PYTHONHASHSEED,
    NODE_PATH, CARGO_HOME, JAVA_HOME, GRADLE_HOME, GOPATH, GOROOT,
    VIRTUAL_ENV, CONDA_PREFIX, TMPDIR, TEMP, TMP, SystemRoot, COMSPEC,
    GIT_EXEC_PATH, GIT_DIR`
   If `strip_credentials=True`, explicitly removes:
   `GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, MISTRAL_API_KEY,
    QWEN_API_KEY, AWS_SECRET_ACCESS_KEY, AZURE_*`

> [!NOTE]
> Per H-3: `GIT_EXEC_PATH` and `GIT_DIR` are included in the default allowlist now for forward-compatibility with TECH-008 git executor migration.

2. **`_validate_cwd()`**: Ensures `cwd` resolves to an existing directory and does not escape a parent boundary (if provided).

3. **Timeout escalation** (H-1): Uses `subprocess.Popen` (not `subprocess.run`) for fine-grained control:
   - Start process
   - `proc.communicate(timeout=timeout_seconds)`
   - On `TimeoutExpired`:
     - **Unix/macOS**: send `SIGTERM` to process group, wait 2s grace, then `SIGKILL` if still alive
     - **Windows**: `proc.terminate()` (TerminateProcess — immediate, no grace period)

> [!WARNING]
> Windows timeout is asymmetric: `proc.terminate()` IS the kill. There is no graceful shutdown for Win32 console processes. The 2s SIGTERM→SIGKILL grace period applies only on Unix/macOS.

4. **Signal propagation** (H-5): Uses `os.setpgrp()` via `preexec_fn` on Unix/macOS to create a process group. The executor explicitly manages the child lifecycle — Ctrl+C won't independently kill a test subprocess.

5. **Output events**: Converts stdout/stderr lines to `OutputEvent` objects (reusing `commons/qa.OutputEvent`).

6. **Telemetry logging**: Logs at DEBUG level: `{"action": "subprocess_execute", "cmd": cmd, "cwd": str, "timeout": int, "exit_code": int, "duration_seconds": float, "timed_out": bool}`

---

#### [NEW] `src/specweaver/sandbox/execution/platform_limiter.py`

Cross-platform resource limiting strategy. ≤ 150 lines.

```python
class PlatformLimiter(ABC):
    """Abstract strategy for OS-specific resource limiting."""

    @abstractmethod
    def make_preexec_fn(self, limits: ResourceLimits) -> Callable[[], None] | None:
        """Return a preexec_fn for subprocess.Popen, or None."""

    @abstractmethod
    def apply_post_start(self, proc: subprocess.Popen, limits: ResourceLimits) -> None:
        """Apply limits after process start (e.g., Win32 Job Objects)."""

class UnixLimiter(PlatformLimiter):
    """Uses resource.setrlimit() via preexec_fn. Works on Linux AND macOS."""

    def make_preexec_fn(self, limits: ResourceLimits) -> Callable[[], None] | None:
        """Return a callable that sets RLIMIT_AS and RLIMIT_NPROC."""
        ...

    def apply_post_start(self, proc: subprocess.Popen, limits: ResourceLimits) -> None:
        """No-op on Unix — limits are applied pre-exec."""
        pass

class WindowsLimiter(PlatformLimiter):
    """Uses Win32 Job Objects via ctypes.windll.kernel32.

    Per H-2: uses OpenProcess(PROCESS_ALL_ACCESS, False, proc.pid) to get
    the process handle (not the private proc._handle attribute).
    """

    def make_preexec_fn(self, limits: ResourceLimits) -> None:
        """No preexec_fn on Windows — limits applied post-start."""
        return None

    def apply_post_start(self, proc: subprocess.Popen, limits: ResourceLimits) -> None:
        """Create Job Object, set memory limits, assign process."""
        # 1. CreateJobObjectW(None, None)
        # 2. SetInformationJobObject with JOBOBJECT_EXTENDED_LIMIT_INFORMATION
        # 3. handle = OpenProcess(PROCESS_ALL_ACCESS, False, proc.pid)
        # 4. AssignProcessToJobObject(job_handle, handle)
        # 5. CloseHandle(handle)
        ...

class NoOpLimiter(PlatformLimiter):
    """Fallback for unsupported platforms. Logs a warning."""
    ...

def get_platform_limiter() -> PlatformLimiter:
    """Auto-detect OS and return the appropriate limiter."""
    if sys.platform.startswith("linux") or sys.platform == "darwin":
        return UnixLimiter()
    elif sys.platform == "win32":
        return WindowsLimiter()
    else:
        return NoOpLimiter()
```

> [!NOTE]
> **Cross-platform guarantee**: `UnixLimiter` works identically on Linux and macOS since both support `resource.setrlimit()`. `WindowsLimiter` uses only `ctypes` (stdlib). `NoOpLimiter` is the safe fallback for exotic platforms — logs a warning but does not block execution.

---

### Component: Tests (NEW)

---

#### [NEW] `tests/unit/sandbox/execution/__init__.py`

Empty init.

---

#### [NEW] `tests/unit/sandbox/execution/test_executor.py`

~250 lines. Tests:

| Test Class | Test Method | FR | Description |
|-----------|-------------|-----|-------------|
| `TestSubprocessResult` | `test_frozen_dataclass` | FR-4 | SubprocessResult is immutable |
| `TestSubprocessResult` | `test_default_values` | FR-4 | Default events=[], timed_out=False |
| `TestSubprocessExecutor` | `test_execute_simple_command` | FR-1 | `echo hello` returns exit_code=0, stdout="hello" |
| `TestSubprocessExecutor` | `test_execute_failing_command` | FR-1 | Non-zero exit code captured correctly |
| `TestSubprocessExecutor` | `test_timeout_kills_process` | FR-2 | Process running > timeout is killed, timed_out=True |
| `TestSubprocessExecutor` | `test_timeout_default_from_init` | FR-2 | Default timeout from constructor used when not overridden |
| `TestSubprocessExecutor` | `test_path_traversal_blocked` | FR-3 | cwd_override with `../` raises error |
| `TestSubprocessExecutor` | `test_path_traversal_symlink_blocked` | FR-3 | Symlink escaping boundary raises error |
| `TestSubprocessExecutor` | `test_output_events_generated` | FR-5 | stdout/stderr lines become OutputEvent objects |
| `TestSubprocessExecutor` | `test_output_events_category_stdout` | FR-5 | stdout events have category="stdout" |
| `TestSubprocessExecutor` | `test_output_events_category_stderr` | FR-5 | stderr events have category="stderr" |
| `TestSubprocessExecutor` | `test_env_stripping_gemini` | FR-6 | GEMINI_API_KEY not in child environment |
| `TestSubprocessExecutor` | `test_env_stripping_openai` | FR-6 | OPENAI_API_KEY not in child environment |
| `TestSubprocessExecutor` | `test_env_stripping_anthropic` | FR-6 | ANTHROPIC_API_KEY not in child environment |
| `TestSubprocessExecutor` | `test_env_stripping_all_providers` | FR-6 | All 5 LLM API key env vars stripped |
| `TestSubprocessExecutor` | `test_env_allowlist_forwarded` | FR-6 | PATH, HOME forwarded to child |
| `TestSubprocessExecutor` | `test_env_git_vars_forwarded` | FR-6 | GIT_EXEC_PATH, GIT_DIR forwarded |
| `TestSubprocessExecutor` | `test_extra_env_injected` | FR-6 | Custom env vars added via extra_env |
| `TestSubprocessExecutor` | `test_extra_env_does_not_override_stripped` | FR-6 | Cannot inject GEMINI_API_KEY via extra_env |
| `TestSubprocessExecutor` | `test_signal_propagation_unix` | FR-7 | Process group created on Unix/macOS (skipif Windows) |
| `TestSubprocessExecutor` | `test_duration_tracked` | FR-9 | duration_seconds > 0 |
| `TestSubprocessExecutor` | `test_debug_logging` | FR-9 | Logger called with expected structured fields |
| `TestSubprocessExecutor` | `test_debug_logging_contains_cmd` | FR-9 | Log entry contains the command that was run |

---

#### [NEW] `tests/unit/sandbox/execution/test_platform_limiter.py`

~150 lines. Tests:

| Test Class | Test Method | FR | Description |
|-----------|-------------|-----|-------------|
| `TestGetPlatformLimiter` | `test_returns_unix_on_linux` | FR-10 | `sys.platform="linux"` → UnixLimiter |
| `TestGetPlatformLimiter` | `test_returns_unix_on_darwin` | FR-10 | `sys.platform="darwin"` → UnixLimiter |
| `TestGetPlatformLimiter` | `test_returns_windows_on_win32` | FR-10 | `sys.platform="win32"` → WindowsLimiter |
| `TestGetPlatformLimiter` | `test_returns_noop_on_unknown` | FR-10 | `sys.platform="freebsd"` → NoOpLimiter |
| `TestNoOpLimiter` | `test_noop_preexec_returns_none` | FR-10 | NoOpLimiter.make_preexec_fn returns None |
| `TestNoOpLimiter` | `test_noop_apply_post_start_noop` | FR-10 | NoOpLimiter.apply_post_start does nothing |
| `TestNoOpLimiter` | `test_noop_logs_warning` | FR-10 | NoOpLimiter logs a warning about unsupported platform |
| `TestResourceLimits` | `test_frozen_dataclass` | FR-10 | ResourceLimits is immutable |
| `TestResourceLimits` | `test_default_none_values` | FR-10 | All limits default to None |
| `TestUnixLimiter` | `test_preexec_fn_calls_setrlimit_memory` | FR-10 | Mocks resource.setrlimit, verifies RLIMIT_AS |
| `TestUnixLimiter` | `test_preexec_fn_calls_setrlimit_nproc` | FR-10 | Mocks resource.setrlimit, verifies RLIMIT_NPROC |
| `TestUnixLimiter` | `test_preexec_fn_skips_none_limits` | FR-10 | Does not call setrlimit when limit is None |
| `TestUnixLimiter` | `test_apply_post_start_is_noop` | FR-10 | apply_post_start does nothing on Unix |
| `TestWindowsLimiter` | `test_job_object_creation` | FR-10 | Mocks ctypes.windll, verifies CreateJobObjectW called |
| `TestWindowsLimiter` | `test_open_process_uses_pid` | FR-10 | Verifies OpenProcess called with proc.pid |
| `TestWindowsLimiter` | `test_close_handle_called` | FR-10 | Verifies CloseHandle called after assignment |
| `TestWindowsLimiter` | `test_make_preexec_fn_returns_none` | FR-10 | Windows preexec_fn is always None |

> [!WARNING]
> Unix-specific tests (`TestUnixLimiter`) will be skipped on Windows via `@pytest.mark.skipif(sys.platform == "win32")`. Windows-specific tests (`TestWindowsLimiter`) will be skipped on Unix/macOS via `@pytest.mark.skipif(sys.platform != "win32")`. Platform detection tests (`TestGetPlatformLimiter`) mock `sys.platform` to run on all platforms.

## Red Team / Blue Team Cycles

### Cycle 1: Credential Exfiltration

**Red Team Attack**: LLM-generated test code calls `os.environ["GEMINI_API_KEY"]` and sends it to an external URL.

**Blue Team Defense**: SubprocessExecutor builds a clean env from allowlist. Even if the child code calls `os.environ`, `GEMINI_API_KEY` does not exist in the child's environment. The credential is invisible.

**Counter-attack**: Attacker uses `extra_env={"GEMINI_API_KEY": "..."}` to inject the key back.

**Defense Enhancement**: `_build_env()` MUST enforce that `strip_credentials=True` blocks keys from `extra_env` too. Test `test_extra_env_does_not_override_stripped` verifies this. Even if a caller explicitly passes `GEMINI_API_KEY` in `extra_env`, the executor strips it.

**Result**: ✅ Covered by FR-6 + test `test_extra_env_does_not_override_stripped`.

---

### Cycle 2: Path Traversal via Symlink

**Red Team Attack**: LLM-generated code creates a symlink inside the workspace that points to `/etc/passwd` or `C:\Windows\System32`, then passes that symlink as `cwd_override`.

**Blue Team Defense**: `_validate_cwd()` calls `Path.resolve()` to follow symlinks, then checks if the resolved absolute path is still within the allowed boundary.

**Counter-attack**: Attacker creates the symlink AFTER validation but BEFORE the subprocess starts (TOCTOU race).

**Defense Enhancement**: The executor resolves the path at the moment of `Popen` creation (inside the same synchronous call). Additionally, the working directory for `Popen` is set to the resolved path, not the symlink. For full TOCTOU protection, B-EXEC-01 (container isolation) is the definitive solution. Document this as a known limitation.

**Result**: ✅ Covered by FR-3 + test `test_path_traversal_symlink_blocked`. TOCTOU risk documented as out-of-scope (mitigated by B-EXEC-01).

> [!NOTE]
> **Known limitation (TOCTOU)**: Between `_validate_cwd()` and `Popen()`, a race condition is theoretically possible. This is fully mitigated by B-EXEC-01 (Podman container isolation). For DAL-E prototyping assurance level, the current defense is sufficient.

---

### Cycle 3: Fork Bomb / Resource Exhaustion

**Red Team Attack**: LLM-generated test code runs `while True: os.fork()` (Unix) or spawns infinite subprocesses (Windows), consuming all system resources.

**Blue Team Defense**:
- **Unix/macOS**: `UnixLimiter` sets `RLIMIT_NPROC` via `preexec_fn`, limiting the number of child processes.
- **Windows**: `WindowsLimiter` sets `JOB_OBJECT_LIMIT_PROCESS_MEMORY` and `JOB_OBJECT_LIMIT_ACTIVE_PROCESS` via Job Objects, preventing memory exhaustion and process proliferation.

**Counter-attack**: Attacker spawns processes that each consume max memory within the per-process limit.

**Defense Enhancement**: Both `max_memory_bytes` (per-process) AND timeout work together. Even if each child stays under memory limits, the timeout kills the entire tree after the deadline. The `os.setpgrp()` (H-5) ensures the entire process group is killed, not just the parent.

**Result**: ✅ Covered by FR-10 + FR-2 + FR-7. UnixLimiter tests verify RLIMIT_NPROC. WindowsLimiter tests verify Job Object creation. Timeout tests verify kill-on-deadline.

## Commit Boundaries

### Commit 1: SubprocessExecutor Core + Tests
- **Files**:
  - [NEW] `src/specweaver/sandbox/execution/__init__.py`
  - [NEW] `src/specweaver/sandbox/execution/context.yaml`
  - [NEW] `src/specweaver/sandbox/execution/executor.py`
  - [NEW] `src/specweaver/sandbox/execution/platform_limiter.py`
  - [NEW] `tests/unit/sandbox/execution/__init__.py`
  - [NEW] `tests/unit/sandbox/execution/test_executor.py`
  - [NEW] `tests/unit/sandbox/execution/test_platform_limiter.py`
- **Message**: `feat(sandbox): add SubprocessExecutor with cross-platform resource limits [E-EXEC-01 SF-1]`
- **Verification**: All new tests pass. Full 4900+ suite regression. Lint clean. Complexity clean.

## Verification Plan

### Automated Tests
```bash
pytest tests/unit/sandbox/execution/ -v
pytest tests/ -x -q
ruff check src/specweaver/sandbox/execution/
```

### Manual Verification
- Verify on Windows that `WindowsLimiter` creates a job object (manual test script in `.tmp/`)
- Verify on Linux that `UnixLimiter` applies resource limits (manual test script in `.tmp/`)
- Verify on macOS that `UnixLimiter` applies resource limits identically to Linux

## Backlog
- TECH-008: Migrate `git/core/executor.py` and `filesystem/core/search.py` to `SubprocessExecutor`
