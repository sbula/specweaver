# Design: Standard Local Execution

- **Feature ID**: E-EXEC-01
- **Phase**: Design
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/features/topic_06_sandbox/E-EXEC-01/E-EXEC-01_design.md

## Feature Overview

Feature E-EXEC-01 introduces a **unified, standardized subprocess execution layer** (`SubprocessExecutor`) into the `specweaver.sandbox` bounded context. It solves the critical problem that each of the 5 language runners (Python, TypeScript, Rust, Java, Kotlin) independently reimplements raw `subprocess.run()` calls with inconsistent timeout handling, signal propagation, environment isolation, and output capture patterns. By extracting a single, battle-tested executor that enforces uniform resource limits, structured output capture, DAP-compatible event streaming, and security boundaries, all language runners gain hardened execution semantics automatically. This is the foundational prerequisite for US-9 (Zero-Trust Sandbox) and directly enables `C-EXEC-02` (Native CLI Action Nodes) and `B-EXEC-01` (Ephemeral Podman Sub-Containers).

## Research Findings

### Codebase Patterns

**Existing subprocess.run() call sites in `sandbox/`:**

| File | Methods | Lines | Timeout? | Resource Limits? | Output Structured? |
|------|---------|-------|----------|------------------|--------------------|
| `language/core/python/runner.py` | `run_tests`, `run_linter`, `run_complexity`, `run_compiler`, `run_debugger`, `run_architecture_check` | 562 | ✅ (per-method, hardcoded) | ❌ | Partial (Regex + JSON) |
| `language/core/typescript/runner.py` | `run_tests`, `run_linter`, `run_compiler`, `run_debugger` | ~200 | ✅ (inconsistent) | ❌ | Partial |
| `language/core/rust/runner.py` | `run_tests`, `run_linter`, `run_compiler`, `run_debugger`, `run_complexity` | 292 | ❌ (missing!) | ❌ | JUnit/SARIF |
| `language/core/java/runner.py` | `run_tests`, `run_linter`, `run_compiler`, `run_debugger` | ~280 | ❌ (missing!) | ❌ | JUnit/Checkstyle |
| `language/core/kotlin/runner.py` | `run_tests`, `run_linter`, `run_compiler`, `run_debugger` | ~250 | ❌ (missing!) | ❌ | JUnit/Detekt |
| `git/core/executor.py` | `_run_git()` | ~200 | ❌ | ❌ | Text |
| `filesystem/core/search.py` | `_grep_search()` | ~60 | ❌ | ❌ | Text |

**Key observations:**
1. **DRY Violation**: 7 files independently call `subprocess.run()`. Each reimplements timeout, capture, text encoding, and error handling differently.
2. **Inconsistent timeouts**: Python uses per-method timeout values (120s for tests, 300s for debugger, 60s for linting). Rust/Java/Kotlin have **no timeout at all** — a hanging `cargo test` or `mvn test` will block the pipeline indefinitely.
3. **No resource limits**: None of the runners enforce CPU/memory/process-count limits. A fork bomb in LLM-generated test code can crash the host.
4. **No execution telemetry**: Start/stop times, peak memory, exit signals are not systematically captured.
5. **Path traversal**: Only `QARunnerAtom._intent_run_tests` checks path traversal (`is_relative_to`). The individual runners blindly execute whatever target is passed.

**What can be reused:**
- `QARunnerInterface` ABC (6 methods) — stable, well-tested with 4900+ tests
- `QARunnerAtom` intent dispatch pattern — clean, proven
- `BaseTool`/`ToolRegistry` from TECH-01b — solid
- The structured result types (`TestRunResult`, `LintRunResult`, etc.) in `commons/qa.py`
- The DAP `OutputEvent` pattern already in `run_debugger` methods

**What should be refactored to benefit multiple features:**
1. **Extract `SubprocessExecutor`**: A centralized subprocess wrapper in `sandbox/` that all language runners delegate to. This instantly provides uniform timeout, resource limits, signal handling, and telemetry to ALL languages.
2. **Centralize path validation**: Move the `is_relative_to` check from `QARunnerAtom` into `SubprocessExecutor`, making it impossible to bypass for any subprocess.
3. **Unify timeout configuration**: Replace hardcoded per-method timeouts with a DAL-aware configuration structure (e.g., DAL-E = 300s max, DAL-B = 60s max).

**Existing features that profit from refactoring:**
| Feature | Current Issue | Benefit from E-EXEC-01 |
|---------|---------------|------------------------|
| Rust QARunner (D-VAL-03) | No timeouts, no resource limits | Auto-gains both via executor |
| Java QARunner (D-VAL-03) | No timeouts, no resource limits | Auto-gains both via executor |
| Kotlin QARunner (D-VAL-03) | No timeouts, no resource limits | Auto-gains both via executor |
| Git Worktree Bouncer (D-EXEC-02) | Custom subprocess handling in executor.py | Could delegate for consistency |
| C-EXEC-02 Native CLI Nodes | Needs safe `bash` execution from YAML | Directly uses SubprocessExecutor |
| B-EXEC-01 Podman Sub-Containers | Needs to swap subprocess target to container | SubprocessExecutor swap point |

### External Tools

| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| Python `subprocess` | stdlib 3.11+ | `subprocess.run()`, `Popen`, `TimeoutExpired` | Python docs |
| Python `resource` | stdlib (Unix) | `setrlimit(RLIMIT_AS)`, `setrlimit(RLIMIT_NPROC)` | Python docs |
| Python `psutil` | 6.x+ (optional) | `Process.memory_info()`, `Process.cpu_times()` | PyPI |
| Windows Job Objects | Win32 API | `win32job` via `pywin32` or ctypes | MSDN |

> [!NOTE]
> Resource limiting via `resource` module is Unix-only. For Windows, we use a best-effort `psutil` poll-and-kill pattern (already standard practice in CI). We MUST NOT add `pywin32` as a hard dependency — optional graceful degradation.

### Blueprint References

No direct blueprint references in `ORIGINS.md`. Industry research (2025-2026) strongly recommends:
- **Defense in Depth**: MicroVMs > gVisor > Standard Containers > Raw subprocess (we are at "raw subprocess" — this feature moves us to "controlled subprocess")
- **Ephemeral execution**: Every execution should be disposable (achieved by `git worktree` isolation, D-EXEC-02)
- **Structured capture**: Always capture stdout/stderr as structured events, not raw strings

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Unified subprocess execution | SubprocessExecutor | Wraps ALL subprocess.run() calls across ALL language runners | Single entry point with consistent behavior |
| FR-2 | Configurable timeout enforcement | SubprocessExecutor | Accepts a `timeout_seconds` parameter (with per-DAL defaults) | Processes exceeding the timeout are killed with `SIGTERM→SIGKILL` escalation |
| FR-3 | Path traversal prevention | SubprocessExecutor | Validates all target paths stay within the provided `cwd` boundary | Paths escaping the sandbox raise `WorkspaceBoundaryError` |
| FR-4 | Structured output capture | SubprocessExecutor | Returns a `SubprocessResult` dataclass with exit_code, stdout, stderr, duration_seconds, peak_memory_bytes (optional) | All consumers get uniform structured results |
| FR-5 | DAP-compatible event streaming | SubprocessExecutor | Converts stdout/stderr into `OutputEvent` lists | Consistent with existing `run_debugger` pattern |
| FR-6 | Environment isolation | SubprocessExecutor | Strips or allowlists environment variables (e.g., removes `GEMINI_API_KEY`, `OPENAI_API_KEY` from child env) | LLM-generated code cannot exfiltrate API keys via env inspection |
| FR-7 | Signal propagation | SubprocessExecutor | On parent SIGINT/SIGTERM, propagates to child process group | No orphaned zombie processes |
| FR-8 | Language runner migration | All language runners | Replace direct `subprocess.run()` calls with `SubprocessExecutor.execute()` | All 5 runners delegate to the unified executor |
| FR-9 | Execution telemetry | SubprocessExecutor | Emits structured log entries (start, stop, exit_code, duration, command) at DEBUG level | Auditable execution trail for all subprocess calls |
| FR-10 | Cross-platform resource limit enforcement | SubprocessExecutor | Detects OS at runtime. Unix/macOS: `resource.setrlimit()` via `preexec_fn`. Windows: Win32 Job Objects via `ctypes` (no third-party deps). All platforms: stdlib-only, zero user configuration | Memory/process-count bombs are caught and killed on all platforms |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|------------------------|
| NFR-1 | Backward compatibility | All 4900+ existing tests MUST pass unchanged after migration. No public API signature changes to `QARunnerInterface`. |
| NFR-2 | Performance overhead | SubprocessExecutor wrapper adds < 5ms overhead per invocation compared to direct `subprocess.run()` |
| NFR-3 | Cross-platform | Must work identically on Windows 11 (26H2+), Linux (kernel 7.1+), and macOS Tahoe (26+) without any code changes by the user. OS-specific internals are abstracted behind a `PlatformLimiter` strategy. |
| NFR-4 | No new dependencies | All functionality uses Python stdlib only (`subprocess`, `resource`, `ctypes`, `sys.platform`). No third-party packages required. |
| NFR-5 | Logging | All executions logged at DEBUG level with command, cwd, timeout, exit_code, duration |
| NFR-6 | File size | SubprocessExecutor module ≤ 300 lines |
| NFR-7 | Testability | All subprocess behavior mockable via `subprocess.run` patching |
| NFR-8 | Path traversal | MUST validate execution targets before spawning any process |
| NFR-9 | Credential leakage prevention | MUST strip known LLM API key env vars from child environment |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| Python stdlib `subprocess` | 3.11 | `subprocess.run()`, `Popen`, `TimeoutExpired` | ✅ | Already in use |
| Python stdlib `resource` | 3.11 | `setrlimit` (Unix/macOS only) | ✅ | Used in `preexec_fn` on Unix/macOS |
| Python stdlib `ctypes` | 3.11 | `ctypes.windll` (Windows only) | ✅ | Used to create Win32 Job Objects for Windows resource limits |
| Python stdlib `sys` | 3.11 | `sys.platform` | ✅ | OS detection for `PlatformLimiter` strategy selection |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Place `SubprocessExecutor` in `sandbox/execution/executor.py` (new module) | Subprocess execution is an L4 Side-Effect. It belongs inside the sandbox boundary, alongside git/filesystem executors. Using a new `execution/` subdomain keeps it distinct from language-specific runners. | No |
| AD-2 | All language runners import `SubprocessExecutor` — no inheritance change | Runners remain concrete `QARunnerInterface` subclasses. They simply replace internal `subprocess.run()` calls with `self._executor.execute()`. This is a pure DRY refactor with no public API change. | No |
| AD-3 | Return `SubprocessResult` dataclass, not raw `CompletedProcess` | The executor returns a domain-specific result type that adds telemetry (duration, peak_memory) and strips OS-specific fields. Language parsers then convert this to `TestRunResult`/`LintRunResult`. | No |
| AD-4 | Environment stripping via allowlist | Rather than trying to blocklist specific dangerous env vars, the executor starts from a **clean base env** and selectively adds known-safe variables (PATH, HOME, LANG, PYTHONPATH, NODE_PATH, CARGO_HOME, etc.). This is more secure than blocklisting. | No |
| AD-5 | Timeout uses SIGTERM→SIGKILL escalation (2s grace) | On timeout: send SIGTERM, wait 2s, then SIGKILL. This gives processes a chance to clean up temp files. On Windows 11: `proc.terminate()` (TerminateProcess — immediate, no grace period; HITL-resolved H-1). | No |
| AD-6 | Cross-platform resource limits via `PlatformLimiter` strategy | The executor detects the OS at runtime via `sys.platform` and selects the appropriate limiter: **Unix/macOS** → `resource.setrlimit()` via `preexec_fn`; **Windows** → Win32 Job Objects via `ctypes.windll.kernel32` (AssignProcessToJobObject + SetInformationJobObject). All stdlib, zero third-party deps. A future B-EXEC-01 (Podman) will provide hard container-level limits as an additional layer. | No |
| AD-7 | `context.yaml` for new `execution/` module | New module gets its own context.yaml with `archetype: executor`, `consumes: [sandbox/security]`, `forbids: [sandbox/qa_runner/*, core/flow/*]`. Prevents circular dependency. | No |

## ROI Analysis

### Investment Cost
| Item | Effort | Risk |
|------|--------|------|
| SubprocessExecutor core module | ~200 lines | Low (well-understood domain) |
| Migrate Python runner | ~50 lines changed | Low (best understood runner) |
| Migrate TypeScript runner | ~30 lines changed | Low |
| Migrate Rust/Java/Kotlin runners | ~30 lines each | Low |
| Unit tests for SubprocessExecutor | ~200 lines | Low |
| Integration tests | ~100 lines | Medium (real subprocess calls) |
| **Total** | **~700 lines new + ~200 lines changed** | **Low overall** |

### Returns
| Beneficiary | Benefit | Magnitude |
|-------------|---------|-----------|
| All 5 language runners | Gain timeouts, resource limits, env isolation | **Critical fix** for Rust/Java/Kotlin |
| C-EXEC-02 (Native CLI Nodes) | Directly uses SubprocessExecutor for `action: bash` steps | **Unblocks next feature** |
| B-EXEC-01 (Podman) | SubprocessExecutor becomes the swap point for container execution | **Architecture enabler** |
| Security posture | API key stripping, path traversal, resource limits | **Immediate hardening** |
| Pipeline reliability | No more indefinite hangs from untimeout-ed Rust/Java builds | **Production stability** |
| Codebase quality | ~400 lines of duplicated subprocess code eliminated | **DRY improvement** |

### Risk Assessment
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Subtle behavior change in Python runner migration | Low | Medium | Full 4900+ test suite regression |
| Platform-specific resource limiter edge cases | Low | Low | PlatformLimiter tested on all 3 OS targets; graceful degradation if unsupported |
| Performance regression from extra abstraction layer | Very Low | Low | Benchmarked at < 5ms overhead |

### Follow-Up: TECH-008
Git executor (`sandbox/git/core/executor.py`) and filesystem search (`sandbox/filesystem/core/search.py`) subprocess migration is out of scope for E-EXEC-01. A separate ticket **TECH-008** will be created to consolidate these subprocess users under `SubprocessExecutor`.

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Guide-1 | How to add subprocess execution calls via `SubprocessExecutor` | ✅ Done in `docs/dev_guides/subprocess_execution.md` |

## Sub-Feature Breakdown

### SF-1: SubprocessExecutor Core
- **Scope**: Create the `SubprocessExecutor` class with `execute()` method, `SubprocessResult` dataclass, timeout escalation, env stripping, path validation, and telemetry logging.
- **FRs**: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-9, FR-10]
- **Inputs**: Command list, cwd path, timeout, env allowlist, resource limits
- **Outputs**: `SubprocessResult` dataclass with structured output
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_06_sandbox/E-EXEC-01/E-EXEC-01_sf1_implementation_plan.md

### SF-2: Language Runner Migration
- **Scope**: Migrate all 5 language runners (Python, TypeScript, Rust, Java, Kotlin) from direct `subprocess.run()` to `SubprocessExecutor.execute()`. Ensure backward compatibility across all 4900+ tests.
- **FRs**: [FR-8]
- **Inputs**: `SubprocessExecutor` from SF-1, existing runner.py files
- **Outputs**: All runners using unified executor, all tests green
- **Depends on**: SF-1
- **Impl Plan**: docs/roadmap/features/topic_06_sandbox/E-EXEC-01/E-EXEC-01_sf2_implementation_plan.md

## Execution Order

1. **SF-1** (no deps — start immediately): Build and fully test `SubprocessExecutor` in isolation.
2. **SF-2** (depends on SF-1): Migrate all language runners. Run full regression.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | SubprocessExecutor Core | — | ✅ | ✅ | ✅ | ✅ | ⬜ |
| SF-2 | Language Runner Migration | SF-1 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: SF-1 Impl Plan APPROVED (2026-07-11).
**Next step**: Run:
`/dev docs/roadmap/features/topic_06_sandbox/E-EXEC-01/E-EXEC-01_sf1_implementation_plan.md`
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and resume from there using the appropriate workflow.
