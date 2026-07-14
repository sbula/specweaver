# Using SubprocessExecutor

This guide explains how to safely execute external processes using SpecWeaver's unified `SubprocessExecutor`.

**WARNING:** Direct usage of `subprocess.run()` is **banned** via ruff rule TID251. All runner modules MUST use `SubprocessExecutor`. The only exemption is `src/specweaver/sandbox/execution/` (the executor itself) and test files.

## Core Features

- **Timeout Enforcement:** Kills runaway processes using a SIGTERM → SIGKILL escalation.
- **Resource Limits:** Automatically caps memory usage and process count (OS dependent). Configured at constructor time via `ResourceLimits`.
- **Environment Stripping:** Automatically removes sensitive credentials (e.g. `GEMINI_API_KEY`) from the child process.
- **Path Validation:** Prevents directory traversal attacks by ensuring the target directory is inside the workspace boundary.
- **Structured Results:** Returns `SubprocessResult` with `.exit_code`, `.stdout`, `.stderr`, `.timed_out`, `.duration_seconds`.

## Basic Usage

```python
from pathlib import Path
from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.execution.models import ResourceLimits

# 1. Initialize with the absolute path to the permitted working directory
#    Resource limits are set at construction time, not per-call.
executor = SubprocessExecutor(
    cwd=Path("/path/to/workspace"),
    resource_limits=ResourceLimits(
        max_memory_bytes=512 * 1024 * 1024,  # 512 MB
        max_processes=50,
    ),
)

# 2. Execute a command safely
result = executor.execute(
    cmd=["pytest", "tests/"],
    timeout_seconds=120,
)

# 3. Handle the structured result
if result.exit_code == 0:
    print(f"Success! Passed in {result.duration_seconds:.2f}s")
    print(result.stdout)
else:
    print(f"Failed. Error: {result.stderr}")

# Did it time out?
if result.timed_out:
    print("Process exceeded the 120s timeout and was killed.")
```

## Piping Input to a Process

Use `input_text` to send data to a process via stdin (e.g., piping cargo test output through a formatter):

```python
# Run cargo test, capture its output
cargo_result = executor.execute(cmd=["cargo", "test", "--", "-Z", "unstable-options", "--format=json"])

# Pipe cargo's stdout into cargo2junit via input_text
junit_result = executor.execute(
    cmd=["cargo2junit"],
    input_text=cargo_result.stdout,
)
```

## Dependency Injection in Language Runners

All language runners accept an optional `executor` parameter for testability:

```python
from specweaver.sandbox.language.core.python.runner import PythonQARunner

# Production: auto-creates a default executor
runner = PythonQARunner(cwd=workspace_path)

# Testing: inject a mock executor
mock_executor = MagicMock(spec=SubprocessExecutor)
runner = PythonQARunner(cwd=tmp_path, executor=mock_executor)
```

## Engine-Internal Script Execution (BashActionAtom)

`sandbox/execution/core/atom.py`'s `BashActionAtom` is the sanctioned way for the flow engine to run a script from `.specweaver/scripts/` (C-EXEC-02's "Native CLI Action Node" primitive). It wraps `SubprocessExecutor` with the additional constraints a script-running Atom needs: canonical-path containment (the script must resolve inside `.specweaver/scripts/`, checked immediately before every execution — see `WorkspaceBoundary`), default `ResourceLimits`, explicit-opt-in `env` (never an implicit passthrough), and a resolved absolute `bash` path (never the bare string `"bash"` — see the note below). It never raises; every failure mode returns a `FAILED` `AtomResult`.

> [!NOTE]
> **`bash` must be resolved to an absolute path, never invoked as the bare string `"bash"`.** On Windows, `Popen(["bash", ...])` goes through `CreateProcess`'s default search order, which checks `C:\Windows\System32` (containing the WSL launcher stub, if WSL is installed) *before* consulting `%PATH%` — regardless of where Git Bash appears in `PATH`. This silently invokes the wrong interpreter. Always resolve via `shutil.which("bash")` first and use the returned path as `argv[0]`.

Pipeline-level `action: bash` / `target: script` steps (C-EXEC-02 SF-2) invoke `BashActionAtom` via `BashActionHandler` — see `docs/dev_guides/pipeline_engine_guide.md` §12 for the YAML shape and the `params:`-nesting requirement.

`.specweaver/scripts/` is created automatically by project scaffolding (`sw init`, C-EXEC-02 SF-3) with a placeholder `README.md` explaining the containment rule above — you don't need to create it by hand.

## Security Boundaries

### Environment Stripping
The executor forwards a clean baseline of environment variables (like `PATH` and `HOME`) and **strips all known LLM credentials** (e.g., `OPENAI_API_KEY`, `GEMINI_API_KEY`).
If you need to inject custom environment variables safely, use `extra_env`:
```python
executor.execute(cmd=["echo", "hello"], extra_env={"MY_CUSTOM_VAR": "value"})
```
*Note: You cannot use `extra_env` to re-inject stripped credentials. The stripping happens after injection.*

### Sandbox Escapes
The executor verifies that the `cwd` provided during initialization actually exists and does not resolve outside the workspace (e.g. `../` or symlinks). A `WorkspaceBoundaryError` is raised if it detects an escape attempt.

## Emitting Output Events (DAP)

`SubprocessResult` automatically captures stdout and stderr as `OutputEvent` streams if `capture_events=True` (which is the default).
This makes it easy to integrate with Debug Adapter Protocol (DAP) pipelines:

```python
for event in result.events:
    if event.category == "stdout":
        logger.debug(f"Process wrote: {event.output}")
```
