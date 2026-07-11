# Using SubprocessExecutor

This guide explains how to safely execute external processes using SpecWeaver's unified `SubprocessExecutor`.

**WARNING:** Direct usage of `subprocess.run()` is forbidden in the codebase to prevent resource exhaustion, credential leakage, and unbounded execution times. You MUST use `SubprocessExecutor`.

## Core Features

- **Timeout Enforcement:** Kills runaway processes using a SIGTERM \u2192 SIGKILL escalation.
- **Resource Limits:** Automatically caps memory usage and process count (OS dependent).
- **Environment Stripping:** Automatically removes sensitive credentials (e.g. `GEMINI_API_KEY`) from the child process.
- **Path Validation:** Prevents directory traversal attacks by ensuring the target directory is inside the workspace boundary.

## Basic Usage

```python
from pathlib import Path
from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.execution.models import ResourceLimits

# 1. Initialize with the absolute path to the permitted working directory
executor = SubprocessExecutor(cwd=Path("/path/to/workspace"))

# 2. Execute a command safely
result = executor.execute(
    command=["pytest", "tests/"],
    timeout_seconds=120,
    limits=ResourceLimits(
        max_memory_bytes=512 * 1024 * 1024, # 512 MB
        max_processes=50
    )
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

## Security Boundaries

### Environment Stripping
The executor forwards a clean baseline of environment variables (like `PATH` and `HOME`) and **strips all known LLM credentials** (e.g., `OPENAI_API_KEY`, `GEMINI_API_KEY`).
If you need to inject custom environment variables safely, use `extra_env`:
```python
executor.execute(["echo", "hello"], extra_env={"MY_CUSTOM_VAR": "value"})
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
