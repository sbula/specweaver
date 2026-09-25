# E-EXEC-01 SF-01 — SubprocessExecutor Core

**Status**: APPROVED. Implemented `40934fa3` (2026-07-11). · **FRs owned**: FR-1, FR-2, FR-3, FR-4,
FR-5, FR-6, FR-7, FR-9, FR-10 · **Depends on**: none · Design: [E-EXEC-01_design.md](E-EXEC-01_design.md) §Sub-features → SF-01

## Goal

Build `SubprocessExecutor` (`execute()`), the `SubprocessResult` dataclass, the cross-platform
`PlatformLimiter`, timeout escalation, environment allowlisting, path validation and structured
telemetry logging — tested in isolation, ready for SF-02's 5 runners:

- `PythonQARunner` (`sandbox/language/core/python/runner.py`)
- `TypeScriptRunner` (`sandbox/language/core/typescript/runner.py`)
- `RustRunner` (`sandbox/language/core/rust/runner.py`)
- `JavaRunner` (`sandbox/language/core/java/runner.py`)
- `KotlinRunner` (`sandbox/language/core/kotlin/runner.py`)

Platforms: Windows 11 (26H2+), Linux (kernel 7.1+, all distros with Python 3.11+), macOS Tahoe (26+).

## Where it plugs in

| Fact | Where |
|---|---|
| All 5 runners call `subprocess.run()` with `capture_output=True, text=True, check=False`. Only Python tracks duration (`time.monotonic()`) and catches `subprocess.TimeoutExpired` | runners |
| `OutputEvent`: `category: str`, `output: str`, `file: str = ""`, `line: int = 0` | `commons/qa.py` (L117-126) |
| `WorkspaceBoundary.validate_path()` — the path validation pattern | `sandbox/security.py` (L76-99) |
| Sandbox modules use `archetype: adapter` in `context.yaml` | `sandbox/*` |
| `SUPPORTED_LANGUAGES = frozenset({"python", "java", "kotlin", "typescript", "rust"})` | `_detect.py` |

Win32 Job Objects (ctypes): `CreateJobObjectW`, `SetInformationJobObject`, `AssignProcessToJobObject`;
`JOBOBJECT_EXTENDED_LIMIT_INFORMATION` as a `ctypes.Structure`; `LimitFlags = JOB_OBJECT_LIMIT_PROCESS_MEMORY`
(0x00000100). Nested jobs work on Windows 8+, so CI is safe.

Unix/macOS `resource`: `resource.setrlimit(resource.RLIMIT_AS, (soft, hard))` limits virtual memory and
`resource.setrlimit(resource.RLIMIT_NPROC, (soft, hard))` process count, on Linux AND macOS, applied via
the `preexec_fn` parameter of `subprocess.Popen`.

## Decisions (HITL)

| # | Decision | User Choice |
|---|----------|-------------|
| H-1 | Windows timeout escalation | Use `proc.terminate()` — TerminateProcess is the Windows equivalent of SIGKILL. 2s grace applies only on Unix. |
| H-2 | Win32 Job Object handle access | Use `OpenProcess(PROCESS_ALL_ACCESS, False, proc.pid)` via ctypes (public `.pid`, not `proc._handle`). Close handle via `CloseHandle` after assignment. |
| H-3 | Environment allowlist scope | Include `GIT_EXEC_PATH, GIT_DIR` in default allowlist now (forward-compatible with TECH-009). |
| H-4 | `context.yaml` forbids | Add explicit `forbids: [sandbox/qa_runner, core/flow]` entries to `sandbox/execution/context.yaml`. |
| H-5 | Signal propagation | Use `os.setpgrp()` on Unix/macOS. Executor manages child lifecycle explicitly. |

## Changes

1. [NEW] `src/specweaver/sandbox/execution/__init__.py` — empty; implicit namespace package.
2. [NEW] `src/specweaver/sandbox/execution/context.yaml` — explicit forbids against circular
   dependencies (H-4):

```yaml
archetype: adapter
forbids:
  - sandbox/qa_runner
  - core/flow
```

3. [NEW] `src/specweaver/sandbox/execution/executor.py` — ≤ 300 lines.

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

   1. **`_build_env()`** — child env = allowlist + `extra_env`. Default allowlist:
      `PATH, HOME, USERPROFILE, LANG, LC_ALL, TERM, PYTHONPATH, PYTHONHASHSEED, NODE_PATH, CARGO_HOME,
      JAVA_HOME, GRADLE_HOME, GOPATH, GOROOT, VIRTUAL_ENV, CONDA_PREFIX, TMPDIR, TEMP, TMP, SystemRoot,
      COMSPEC, GIT_EXEC_PATH, GIT_DIR` (the git pair per H-3). With `strip_credentials=True` it removes
      `GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, MISTRAL_API_KEY, QWEN_API_KEY,
      AWS_SECRET_ACCESS_KEY, AZURE_*` — **also from `extra_env`**, so a caller cannot inject a key back.
   2. **`_validate_cwd()`** — `cwd` resolves (`Path.resolve()`, following symlinks) to an existing
      directory that does not escape a parent boundary (if provided). `Popen` gets the resolved path,
      not the symlink.
   3. **Timeout escalation** (H-1) — `subprocess.Popen` (not `subprocess.run`), then
      `proc.communicate(timeout=timeout_seconds)`. On `TimeoutExpired`: **Unix/macOS** send `SIGTERM`
      to the process group, wait 2s grace, then `SIGKILL` if still alive; **Windows** `proc.terminate()`
      (TerminateProcess — immediate). Windows is asymmetric: `proc.terminate()` IS the kill; Win32
      console processes have no graceful shutdown.
   4. **Signal propagation** (H-5) — `os.setpgrp()` via `preexec_fn` on Unix/macOS creates a process
      group; the executor manages the child lifecycle, so Ctrl+C won't independently kill a test
      subprocess.
   5. **Output events** — stdout/stderr lines become `commons/qa.OutputEvent` objects.
   6. **Telemetry** — DEBUG: `{"action": "subprocess_execute", "cmd": cmd, "cwd": str, "timeout": int, "exit_code": int, "duration_seconds": float, "timed_out": bool}`

4. [NEW] `src/specweaver/sandbox/execution/platform_limiter.py` — ≤ 150 lines.

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

   `UnixLimiter` behaves the same on Linux and macOS (both have `resource.setrlimit()`);
   `WindowsLimiter` uses only `ctypes` (stdlib); `NoOpLimiter` logs a warning and does not block.

| File | Change |
|---|---|
| `src/specweaver/sandbox/execution/__init__.py` | NEW |
| `src/specweaver/sandbox/execution/context.yaml` | NEW |
| `src/specweaver/sandbox/execution/executor.py` | NEW |
| `src/specweaver/sandbox/execution/platform_limiter.py` | NEW |
| `tests/unit/sandbox/execution/__init__.py` | NEW, empty |
| `tests/unit/sandbox/execution/test_executor.py` | NEW, ~250 lines |
| `tests/unit/sandbox/execution/test_platform_limiter.py` | NEW, ~150 lines |

Commit 1: `feat(sandbox): add SubprocessExecutor with cross-platform resource limits [E-EXEC-01 SF-01]`
— all new tests pass, full 4900+ suite regression, lint clean, complexity clean.

## Tests

`tests/unit/sandbox/execution/test_executor.py`:

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

`tests/unit/sandbox/execution/test_platform_limiter.py`:

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

Platform skips: `TestUnixLimiter` via `@pytest.mark.skipif(sys.platform == "win32")`; `TestWindowsLimiter`
via `@pytest.mark.skipif(sys.platform != "win32")`. `TestGetPlatformLimiter` mocks `sys.platform` and
runs everywhere.

```bash
pytest tests/unit/sandbox/execution/ -v
pytest tests/ -x -q
ruff check src/specweaver/sandbox/execution/
```

Manual: `WindowsLimiter` creates a job object on Windows; `UnixLimiter` applies limits on Linux and
identically on macOS (manual scripts in `.tmp/`).

## Red/Blue review

| Attack | Defense | Covered by |
|---|---|---|
| LLM test code reads `os.environ["GEMINI_API_KEY"]` and sends it out | Clean env from the allowlist — the key does not exist in the child | FR-6 |
| Counter: re-inject via `extra_env={"GEMINI_API_KEY": "..."}` | `_build_env()` enforces `strip_credentials=True` on `extra_env` too | `test_extra_env_does_not_override_stripped` |
| Symlink in the workspace to `/etc/passwd` or `C:\Windows\System32`, passed as `cwd_override` | `_validate_cwd()` resolves symlinks, checks the absolute path is inside the boundary | FR-3, `test_path_traversal_symlink_blocked` |
| Counter: create the symlink after validation, before spawn (TOCTOU) | Resolve at `Popen` creation in the same synchronous call; `Popen` gets the resolved path | Known limit — see below |
| Fork bomb: `while True: os.fork()` (Unix) or endless subprocesses (Windows) | `UnixLimiter` sets `RLIMIT_NPROC` via `preexec_fn`; `WindowsLimiter` sets `JOB_OBJECT_LIMIT_PROCESS_MEMORY` and `JOB_OBJECT_LIMIT_ACTIVE_PROCESS` | FR-10 |
| Counter: many processes, each under the per-process memory cap | `max_memory_bytes` (per-process) plus the timeout kill the whole tree at the deadline; `os.setpgrp()` (H-5) kills the group, not just the parent | FR-10 + FR-2 + FR-7; limiter + timeout tests |

**Known limitation (TOCTOU)**: a race between `_validate_cwd()` and `Popen()` is theoretically
possible. B-EXEC-01 (Podman container isolation) closes it; the current defense suffices for DAL-E
prototyping assurance.

Backlog: TECH-009 — migrate `git/core/executor.py` and `filesystem/core/search.py` to `SubprocessExecutor`.

## As built

**Since moved** (noted 2026-09-25): `SubprocessResult` and `ResourceLimits` now live in
`sandbox/execution/models.py`; `executor.py` is 338 lines (over the ≤ 300 target); `context.yaml`
forbids `sandbox.qa_runner.*` and `core.flow.*` and consumes `commons.qa`. The `RLIMIT_NPROC` ceiling
was re-derived on 2026-08-17 — see the design, FR-10.
