# Design: Git & Filesystem Subprocess Migration to SubprocessExecutor

- **Feature ID**: TECH-009
- **Epic**: Topic 07 (Technical Debt)
- **Status**: DESIGN_COMPLETE
- **Origin**: E-EXEC-01 backlog (SF-1 §Backlog, SF-2 §Backlog, Design §Follow-Up)

## Business Context & Goal

E-EXEC-01 introduced `SubprocessExecutor` — a unified, cross-platform subprocess execution layer with timeout escalation, environment isolation, credential stripping, path validation, and telemetry logging. All five language runners were migrated to use it.

However, two additional subprocess consumers were explicitly scoped out:

1. **`sandbox/git/core/executor.py`** — `GitExecutor.run()` calls `subprocess.run()` directly with manual timeout handling and no env isolation.
2. **`sandbox/filesystem/core/search.py`** — `_grep_ripgrep()` calls `subprocess.run()` directly with no env isolation, no credential stripping, and no telemetry.

These two files represent the **last remaining raw `subprocess.run()` calls** in the sandbox. Migrating them completes the subprocess unification started by E-EXEC-01.

## Problem Statement

| Issue | GitExecutor | search.py (_grep_ripgrep) |
|-------|-------------|---------------------------|
| Direct `subprocess.run()` | ✅ Line 118 | ✅ Line 123 |
| No env isolation | ✅ Full parent env inherited | ✅ Full parent env inherited |
| No credential stripping | ✅ API keys leak to git child | ✅ API keys leak to rg child |
| No telemetry logging | ✅ Only debug log, no timing | ✅ No telemetry at all |
| No resource limits | ✅ | ✅ |
| Timeout handling | Manual via `subprocess.TimeoutExpired` | Manual via `subprocess.TimeoutExpired` |
| Platform-specific kill escalation | ❌ Missing | ❌ Missing |

## Goals

1. **Eliminate all raw `subprocess.run()` / `subprocess.Popen()` calls** from the sandbox — `SubprocessExecutor` becomes the single entry point.
2. **Gain env isolation + credential stripping** for git and ripgrep subprocesses for free.
3. **Gain structured telemetry** (duration, exit code, timed_out) for git and ripgrep calls.
4. **Gain timeout escalation** (SIGTERM → SIGKILL on Unix) for git and ripgrep processes.
5. **Preserve all existing behavior** — `GitExecutor` public API (`run()` → `ExecutorResult`), `EngineGitExecutor` subclass, `grep_content()` / `find_by_glob()` public APIs are unchanged.

## Non-Goals

- **Changing `GitExecutor`'s public API**. Callers still call `executor.run("status", "--short")` and get back an `ExecutorResult`.
- **Changing `grep_content()` / `find_by_glob()` APIs**. Callers still get the same list-of-dicts return format.
- **Removing Python fallback paths** in `search.py`. The Python fallback (`_grep_python`, `find_by_glob`) does not use subprocess at all — only `_grep_ripgrep` does.
- **Migrating `filesystem/core/executor.py`** (FileExecutor). This is a pure-Python file I/O executor — it does not use subprocess.

## Technical Details

### SF-1: GitExecutor Migration

**Current**: `GitExecutor.run()` builds `cmd = ["git", "-C", str(self._cwd), command, *args]` and calls `subprocess.run(cmd, ...)` directly.

**After**: `GitExecutor` receives a `SubprocessExecutor` via constructor injection. `run()` delegates to `self._subprocess_executor.execute(cmd)` and maps the `SubprocessResult` back to `ExecutorResult`.

Key considerations:
- `EngineGitExecutor` subclasses `GitExecutor` — it inherits the migrated `run()` method automatically.
- The `SubprocessExecutor` must be configured with `GIT_EXEC_PATH` and `GIT_DIR` in its env allowlist (already included per E-EXEC-01 H-3).
- `GitExecutor.__init__` gains an optional `subprocess_executor` parameter. If not provided, it creates a default one internally (preserving backward compatibility for tests and existing call sites that don't inject one).
- `ExecutorResult` remains unchanged — the mapping is `SubprocessResult.exit_code → ExecutorResult.exit_code`, etc.

### SF-2: Filesystem Search (ripgrep) Migration

**Current**: `_grep_ripgrep()` calls `subprocess.run(cmd, capture_output=True, text=True, timeout=TOOL_TIMEOUT_SECONDS)` directly.

**After**: `_grep_ripgrep()` receives a `SubprocessExecutor` and calls `executor.execute(cmd, timeout_seconds=TOOL_TIMEOUT_SECONDS)`.

Key considerations:
- `grep_content()` is the public API — it must accept an optional `SubprocessExecutor` parameter and forward it to `_grep_ripgrep()`.
- The calling chain is: `FileSystemTool.grep() → grep_content() → _grep_ripgrep()`. The `FileSystemTool` will construct a `SubprocessExecutor` and pass it down.
- `_grep_ripgrep()` signature changes from taking `rg_path` to taking `rg_path + executor`. The `SubprocessResult.timed_out` flag replaces the manual `except TimeoutExpired` handling.

## Sub-Feature Breakdown

### SF-1: GitExecutor Subprocess Migration
- **Scope**: Inject `SubprocessExecutor` into `GitExecutor`, replace `subprocess.run()` in `run()` method, maintain `ExecutorResult` API, ensure `EngineGitExecutor` inherits cleanly.
- **FRs**: Env isolation, credential stripping, telemetry, timeout escalation for git commands.
- **Files**: `sandbox/git/core/executor.py`, `sandbox/git/core/engine_executor.py` (verify inheritance), `sandbox/git/core/atom.py` (inject executor), `sandbox/git/interfaces/facades.py` (inject executor).
- **Depends on**: E-EXEC-01 (complete)

### SF-2: Filesystem Search Subprocess Migration
- **Scope**: Inject `SubprocessExecutor` into ripgrep call path, replace `subprocess.run()` in `_grep_ripgrep()`, maintain `grep_content()` / `find_by_glob()` APIs.
- **FRs**: Env isolation, credential stripping, telemetry, timeout escalation for ripgrep.
- **Files**: `sandbox/filesystem/core/search.py`, `sandbox/filesystem/interfaces/tool.py` (inject executor).
- **Depends on**: E-EXEC-01 (complete)

## Execution Order

Both SFs are independent — they can be implemented in either order. SF-1 is recommended first since `GitExecutor` has a cleaner injection surface (constructor DI).

1. **SF-1** (GitExecutor migration) — constructor injection, straightforward mapping.
2. **SF-2** (ripgrep migration) — function parameter threading, slightly more plumbing.

## Verification Plan

### Automated Tests
- Full test suite regression: `pytest tests/ -x -q`
- Targeted git tests: `pytest tests/unit/sandbox/git/ tests/integration/sandbox/git/ -x -q`
- Targeted filesystem tests: `pytest tests/unit/sandbox/filesystem/ tests/integration/sandbox/filesystem/ -x -q`
- Code quality: `ruff check src/specweaver/sandbox/git/ src/specweaver/sandbox/filesystem/`

### Verification Criteria
- Zero raw `subprocess.run()` or `subprocess.Popen()` calls remain in `sandbox/git/` or `sandbox/filesystem/`.
- `import subprocess` removed from both `executor.py` and `search.py`.
- All existing tests pass without modification (backward compatibility).
- New tests verify env isolation and credential stripping for git and ripgrep subprocesses.

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Subtle behavior change in git timeout handling | Low | Medium | `SubprocessResult.timed_out` maps directly to existing `ExecutorResult(status="error")` path |
| `EngineGitExecutor` inheritance breaks | Very Low | High | Only overrides `_BLOCKED_ALWAYS` — `run()` is inherited unchanged |
| ripgrep JSON parsing affected by SubprocessResult | Very Low | Low | `SubprocessResult.stdout` is identical to `subprocess.CompletedProcess.stdout` |
| Test fixtures that mock `subprocess.run` directly | Medium | Low | Find-and-replace mock targets to `SubprocessExecutor.execute` |

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | GitExecutor Migration | E-EXEC-01 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-2 | Filesystem Search Migration | E-EXEC-01 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
