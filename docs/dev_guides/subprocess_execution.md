# Using SubprocessExecutor

Use when: your code needs to run an external process — a tool, a test runner, a script, a container.

## Rules

- **`subprocess` is banned**, `subprocess.run()` included, by ruff rule TID251 (`pyproject.toml`:
  *"Use SubprocessExecutor from specweaver.sandbox.execution.executor instead."*). All runner modules
  MUST use `SubprocessExecutor`.
- Exempt: `src/specweaver/sandbox/execution/` (the executor itself), test files, `scripts/**`
  (quality gates must not import the product they check), and `MCPExecutor`'s declared inline
  `noqa` (a long-lived JSON-RPC pipe; see `special_patterns_and_adaptations.md` §17).

## What it gives you

- **Timeout**: kills runaway processes with SIGTERM → SIGKILL escalation.
- **Resource limits**: memory and process caps (OS dependent), set at construction via
  `ResourceLimits`.
- **Environment stripping**: removes credentials (e.g. `GEMINI_API_KEY`) from the child.
- **Path validation**: a per-call `cwd_override` must resolve inside the constructor `cwd`.
- **Structured result**: `SubprocessResult` with `.exit_code`, `.stdout`, `.stderr`, `.timed_out`,
  `.duration_seconds`, `.events`.

## Basic usage

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

### Piping stdin

`input_text` sends data to the child's stdin (e.g. cargo test output into a formatter):

```python
# Run cargo test, capture its output
cargo_result = executor.execute(cmd=["cargo", "test", "--", "-Z", "unstable-options", "--format=json"])

# Pipe cargo's stdout into cargo2junit via input_text
junit_result = executor.execute(
    cmd=["cargo2junit"],
    input_text=cargo_result.stdout,
)
```

### Injecting an executor into language runners

Every language runner takes an optional `executor`:

```python
from specweaver.sandbox.language.core.python.runner import PythonQARunner

# Production: auto-creates a default executor
runner = PythonQARunner(cwd=workspace_path)

# Testing: inject a mock executor
mock_executor = MagicMock(spec=SubprocessExecutor)
runner = PythonQARunner(cwd=tmp_path, executor=mock_executor)
```

## Running a script from the engine (`BashActionAtom`)

`BashActionAtom` (`sandbox/execution/core/atom.py`) is the sanctioned way for the flow engine to run a
script from `.specweaver/scripts/` (C-EXEC-02's "Native CLI Action Node"). On top of
`SubprocessExecutor` it adds:

- canonical-path containment — the script must resolve inside `.specweaver/scripts/`, checked right
  before every execution (`WorkspaceBoundary`);
- default `ResourceLimits`;
- `env` only by explicit opt-in, never passed through;
- a resolved absolute `bash` path, never the bare string `"bash"`.

It never raises; every failure is a `FAILED` `AtomResult`.

> [!NOTE]
> **Resolve `bash` to an absolute path.** On Windows, `Popen(["bash", ...])` goes through
> `CreateProcess`'s search order, which checks `C:\Windows\System32` (the WSL launcher stub, if WSL
> is installed) *before* `%PATH%` — wherever Git Bash is in `PATH`. Call `shutil.which("bash")` and
> use the returned path as `argv[0]`. Details: `special_patterns_and_adaptations.md` §22.

Pipeline `action: bash` / `target: script` steps (C-EXEC-02 SF-02) reach it through
`BashActionHandler` — YAML shape and the `params:`-nesting trap: `docs/dev_guides/pipeline_engine_guide.md` §12.

`sw init` creates `.specweaver/scripts/` (C-EXEC-02 SF-03) with a placeholder `README.md` explaining
the containment rule.

> [!NOTE]
> **`cwd` under worktree isolation (INT-US-09).** The executor's boundary is its constructor `cwd`.
> Under worktree isolation the runner sets `RunContext.isolation.execution_root` to the worktree, and
> the untrusted-execution handlers (`BashActionHandler`, `ValidateTestsHandler`/`run_tests`) build
> their atom `cwd` as `context.isolation.execution_root or context.project_path`. So the executor —
> and `.specweaver/scripts/` containment — binds inside the worktree. With `execution_root` `None`
> (no isolation), `cwd` is `project_path`, byte-identical to pre-INT-US-09 behavior. Container-free
> host execution; see `pipeline_engine_guide.md` §7.

## Containerized QA Execution (`ContainerSubprocessExecutor`)

`ContainerSubprocessExecutor` (`sandbox/execution/container_executor.py`, `B-EXEC-01` Ephemeral Podman
Sub-Containers, part of US-9's Zero-Trust Sandbox) is a `SubprocessExecutor` **subclass** that runs
`execute()` in an ephemeral Podman/Docker container. It overrides only `execute()`: wraps `cmd` into
a `<podman|docker> run` with

- read-only source mount at `/workspace`, read-write scratch at `/scratch`;
- `--network none`, `--cap-drop ALL`, non-root `--user` on Linux/macOS;
- resource limits matching `BashActionAtom`'s;

then calls `super().execute()` for spawn, timeout, env stripping and `SubprocessResult`. The result
contract is unchanged; only where the process runs changes.

```python
from specweaver.sandbox.execution.container_executor import ContainerSubprocessExecutor
from specweaver.sandbox.execution.models import ContainerMounts

executor = ContainerSubprocessExecutor(
    cwd=project_root,
    mounts=ContainerMounts(
        source_root=project_root,
        scratch_root=project_root / ".specweaver" / ".sandbox" / "scratch",
        cache_root=project_root / ".specweaver" / ".sandbox" / "cache",
    ),
)
result = executor.execute(["python", "-m", "pytest", "tests/"])  # same SubprocessResult shape as host mode
```

- **Engine detection**: lazy, memoized per instance. The first `execute()` finds and liveness-probes
  (`<engine> info`) `podman`, else `docker`; neither → `ContainerEngineUnavailableError`.
- **Prepare phase**: a network-enabled `uv sync` into a persistent, lockfile-hash-gated cache runs
  first. The real execution is always `--network none`, so untrusted code never shares an invocation
  with network access.
- **Why a subclass**: `PythonQARunner.__init__(cwd, executor: SubprocessExecutor | None = None)` is
  typed to the concrete class. A wrapper would fail strict mypy unless that stable signature were
  widened. The subclass is Liskov-substitutable and delegates to, not duplicates, the parent. General
  pattern: `docs/dev_guides/special_patterns_and_adaptations.md` §23.

### Opt in via `QARunnerAtom`

Give `QARunnerAtom` a `SandboxSettings` with `execution_mode="container"` and it builds the executor:

```python
from specweaver.core.config.settings import SandboxSettings
from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom

atom = QARunnerAtom(cwd=project_root, sandbox_settings=SandboxSettings(execution_mode="container"))
result = atom.run({"intent": "run_tests", "target": "tests/"})  # runs inside a container
```

- Mounts derive from `cwd` (`.specweaver/.sandbox/{scratch,cache}`).
- No `sandbox_settings`, or `execution_mode="host"`, keeps host behavior byte-for-byte (NFR-7). Opt-in,
  not a default.
- `factory.resolve_runner()` accepts a container executor for all 5 language runners, but only
  `PythonQARunner` is validated end-to-end (mounts, artifact redirection, the bare-`"python"` rule
  below). A non-Python project given a container executor logs a warning, not a silent no-op.

### Enable from `specweaver.toml`

`load_settings()`/`load_settings_async()` (`core/config/settings_loader.py`) read an opt-in
`[sandbox]` table, the same way as `[standards]`:

```toml
# specweaver.toml
[sandbox]
execution_mode = "container"
```

An absent, empty or malformed `[sandbox]` falls back to `SandboxSettings()` (`execution_mode="host"`),
like `[standards]`. `ValidateTestsHandler`/`LintFixHandler` (the `validate+test` and lint-fix-reflection
steps) pass `context.config.sandbox` to `QARunnerAtom`, so this one line is enough — no pipeline code
changes.

### Container-mode rules in `PythonQARunner`

- **`PythonQARunner.run_debugger()` uses bare `"python"`, not `sys.executable`.** `sys.executable` is the *host*
  interpreter path (e.g. a Windows `.exe`); in a Linux container it fails with
  `exec: ...: executable file not found in $PATH`. `run_tests`/`run_linter`/`run_complexity` already
  used `"python"`. `isinstance(self._executor, ContainerSubprocessExecutor)` picks between the two.
  A real-engine integration test caught this; a mock would not.
- **`PythonQARunner._run_tach_check()` skips its `shutil.which("tach")` pre-check** in a container — it would check
  the host, not the image. The containerized `tach`'s exit code/stderr reports absence instead.
- **Every QA-runner method catches `ContainerEngineUnavailableError`** and returns the same synthetic
  failure it builds for a `<timeout>`.

Deliberate scope cut (SF-02/SF-04 Backlog): `validation_hydrator.py` (C03/C04 rule hydration) and the
agent-facing `facades.py` still build host-mode `QARunnerAtom`s. Per-SF plans:
`docs/roadmap/features/topic_06_sandbox/B-EXEC-01/` (`B-EXEC-01_sf01_implementation_plan.md` through
`_sf04_`).

## Security boundaries

### Environment stripping

The child gets a clean baseline (`PATH`, `HOME`, …) with **all known LLM credentials stripped**
(`OPENAI_API_KEY`, `GEMINI_API_KEY`, …). Add variables with `extra_env`:

```python
executor.execute(cmd=["echo", "hello"], extra_env={"MY_CUSTOM_VAR": "value"})
```

`extra_env` cannot re-inject a credential: stripping runs after injection.

### Working-directory escapes

The constructor `cwd` is resolved once and is the boundary. A per-call `cwd_override` is resolved
(following `../` and symlinks) and must stay inside it: outside → `ValueError` ("Path traversal
blocked"), missing → `FileNotFoundError`.

## Output events (DAP)

`SubprocessResult.events` always holds stdout and stderr as `OutputEvent`s (`commons/qa.py`), for
Debug Adapter Protocol (DAP) pipelines:

```python
for event in result.events:
    if event.category == "stdout":
        logger.debug(f"Process wrote: {event.output}")
```

(Real code logs with `%s`, not f-strings — `special_patterns_and_adaptations.md` §20.)
