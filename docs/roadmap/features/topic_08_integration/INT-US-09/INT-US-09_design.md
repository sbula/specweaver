# Design: Zero-Trust Sandbox Integration — QA Runner → Podman/Docker Injection (INT-US-09)

- **Feature ID**: INT-US-09
- **Phase**: Design
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/features/topic_08_integration/INT-US-09/INT-US-09_design.md

## Feature Overview

Feature INT-US-09 adds the Base Integration Contract that forces all QA Runner execution
(`QARunnerAtom`, US-3 Core / `D-VAL-01`, `D-VAL-03`) to run inside the existing Podman/Docker
sandbox infrastructure (`D-EXEC-01`) instead of directly against the host filesystem, with the
host source tree mounted read-only and a separate scratch volume mounted for temporary test
artifacts only.

It solves the Remote Code Execution exposure created by LLM-generated test/lint code: today
`QARunnerAtom` resolves a language runner (currently `PythonQARunner`) that shells out via
`SubprocessExecutor` directly against the host `cwd` with full read/write access to the project
tree, so untrusted, LLM-authored test code can read or corrupt anything the SpecWeaver process
can reach. Containerizing execution and asymmetrically mounting source (RO) vs. a scratch
directory (RW, artifacts-only) bounds that blast radius — this is the exact gap flagged by
`B-EXEC-01` ("Ephemeral Podman Sub-Containers... Resolves Agent RCE vulnerabilities").

It interacts with `sandbox.qa_runner` (atom/factory/interface + concrete language runners),
`sandbox.execution` (a new container-aware executor sitting alongside `SubprocessExecutor`),
`core.config` (a new opt-in `[sandbox]` config surface), and the `D-EXEC-01` Podman/Docker CLI
conventions already used for `sw serve` deployment. It does NOT touch `C-EXEC-02`'s
`BashActionAtom` (host-side `.specweaver/scripts/` execution — a separate, already-complete
trust boundary), the `sw serve` deployment container's own runtime, or the other sandbox tool
families (filesystem, git, code_structure, mcp).

Key constraints: strict RO source mount / separate RW scratch mount for test artifacts (per the
story contract text); container execution is **opt-in** (default `execution_mode: host`,
confirmed with the user — see Session Handoff) so existing bare-host installs and CI keep working
unmodified until they explicitly enable it; once enabled, the run fails closed (actionable error)
rather than silently falling back to host execution if no container engine is available; must
respect `sandbox` layering (tools→atoms→commons, `commons` forbids `tools`/`atoms`) and the
project's "no raw subprocess" rule — all process spawning still goes through the existing
`SubprocessExecutor`, just with a `podman`/`docker run ...` argv instead of a bare tool invocation.

## Research Findings

### Codebase Patterns

**QA Runner execution chain (the swap point).** `QARunnerAtom` (`src/specweaver/sandbox/qa_runner/core/atom.py:64`)
resolves a `QARunnerInterface` via `factory.resolve_runner(cwd)` and dispatches by `intent`
(`run_tests`, `run_linter`, `run_complexity`, `run_compiler`, `run_debugger`,
`run_architecture_check`) to methods on that runner — never touches subprocess directly.
`PythonQARunner` (`src/specweaver/sandbox/language/core/python/runner.py:131`) is the concrete
implementation: **every one of its methods builds an argv list and calls
`self._executor.execute(cmd, timeout_seconds=...)` exactly once**, and its constructor already
accepts `executor: SubprocessExecutor | None = None` as a dependency-injection seam. This is the
single, pre-existing point where container routing can be introduced without touching parsing
logic (`TestRunResult`, `LintRunResult`, etc.) at all.

**`SubprocessExecutor`** (`src/specweaver/sandbox/execution/executor.py:75`) is the mandated
subprocess boundary (`.execute(cmd, *, timeout_seconds=None, extra_env=None, cwd_override=None,
input_text=None) -> SubprocessResult`). It already owns timeout handling (SIGTERM→grace→SIGKILL),
env-var allowlisting, hard credential stripping, and path-containment validation
(`_validate_cwd`). It has **no container concept today** — resource limits are OS-level only
(`rlimit`/Win32 Job Objects via `PlatformLimiter`).

**`D-EXEC-01` (Podman/Docker Integration) is unrelated to per-run sandboxing.** The repo-root
`Containerfile`/`compose.yaml` containerize the *whole `sw serve` process* (one container = one
long-lived deployment), bind-mounting the user's entire project tree read-write at `/projects`.
There is no podman/docker Python SDK dependency anywhere in `pyproject.toml` or `src/`, and
`workspace/project/scaffold.py` has zero container scaffolding logic. **INT-US-09 needs a new,
separate ephemeral-container mechanism** — reusing D-EXEC-01's CLI/image conventions where
sensible, but not its Containerfile or compose flow.

**House style precedent — `C-EXEC-02`'s `BashActionAtom`** (`src/specweaver/sandbox/execution/core/atom.py`)
is the closest prior "restricted execution" feature and is now complete. It (a) constructs its
own `SubprocessExecutor` instance per call with hardcoded `ResourceLimits(max_memory_bytes=
2_147_483_648, max_processes=128)`, (b) reuses `WorkspaceBoundary.validate_path()` for path
containment rather than hand-rolling a check, and (c) lives in its own submodule
(`execution/core/`) with its own `context.yaml`, rather than modifying the leaf `execution/executor.py`
module in place. Its own design doc explicitly names `B-EXEC-01` as the intended future consumer
of this same swap point. INT-US-09 follows the identical pattern: a new component that *wraps*
`SubprocessExecutor`, not a rewrite of it.

**Anti-patterns to avoid** (`docs/architecture/06_lessons_and_future/anti_patterns.md`): "Putting
tool-consuming code in `commons/`" and "Creating parallel security classes (e.g.
`WorkspaceBoundary`)" — both directly apply here: the new container component must live in an
already-`sandbox`-internal, already-tach-exposed module (`execution.core`), and must reuse
`WorkspaceBoundary`/`ResourceLimits` rather than inventing new containment or limit primitives.

**Boundary rules** (`tach.toml`, `docs/architecture/03_system_topology/hard_dependency_rules.md`):
only `core.flow` may reach into `sandbox`, and only via atoms — never `tools`/`commons` directly.
Within `sandbox`, `commons`-tier leaf modules forbid `tools`/`atoms`. `sandbox` already
`depends_on` `specweaver.core.config`, so a new `[sandbox]` config section is tach-legal. The
`execution.core` interface is already exposed for external consumption; a new class placed there
requires no new `[[interfaces]]` entry.

### External Tools

| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| Podman CLI | ≥ 4.0 | `run --rm --read-only --tmpfs --pids-limit --network none -v SRC:/workspace:ro -v SCRATCH:/scratch:rw --cap-drop ALL --security-opt no-new-privileges --user UID:GID IMAGE ...` | [Podman docs](https://docs.podman.io/en/latest/markdown/podman-run.1.html) |
| Docker CLI | ≥ 20.10 | Same flag surface as above (`docker run` is flag-compatible with `podman run` for this use case) | [Docker run reference](https://docs.docker.com/reference/cli/docker/container/run/) |

No new Python SDK dependency (`docker`/`podman-py`) is added — see AD-1. Both `podman-py` and
`docker-py` are actively maintained, but external research found no functional gain from a second
client library when the existing `SubprocessExecutor` can invoke either engine's CLI with an
identical flag set; adding one would mean maintaining two divergent socket/auth paths for no
benefit over the CLI, and `podman-py`'s own maintainers flag incomplete docker-py drop-in
compatibility.

### Blueprint References

No external blueprint reference exists for D-EXEC-01/B-EXEC-01 in `docs/ORIGINS.md` — these are
original SpecWeaver designs, not adapted from a named external tool. `ORIGINS.md`'s "Archon"
entries concern git-worktree isolation (`D-EXEC-02`), a different capability.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Container Routing | QARunnerAtom | The system SHALL route test/lint/complexity/compile/architecture-check execution through a new container-aware executor when `execution_mode: "container"` is configured | Commands run inside an ephemeral Podman/Docker container instead of directly on the host |
| FR-2 | Read-Only Source Mount | Container Executor | The system SHALL bind-mount the project source tree read-only into the container | The container process cannot write to any path under the mounted source root |
| FR-3 | Writable Scratch Mount | Container Executor | The system SHALL bind-mount a dedicated scratch directory read-write into the container, isolated from the source mount | Test artifacts (coverage data, JUnit XML, `.pytest_cache`) are writable only under the scratch path |
| FR-4 | Artifact Path Redirection | PythonQARunner | The system SHALL redirect all known artifact-writing paths (`COVERAGE_FILE`, `--junitxml`, `--cache-dir`/`PYTHONDONTWRITEBYTECODE`) into the scratch mount via explicit CLI/env overrides | No write attempt targets the read-only source mount during a normal run |
| FR-5 | Result Contract Parity | Container Executor | The system SHALL return the container's exit code, stdout, and stderr through the existing `SubprocessResult` contract unchanged | `QARunnerAtom`'s existing parsing logic (`TestRunResult`, `LintRunResult`, etc.) requires no modification. If any current QA runner call site passes `input_text` to `execute()`, the container invocation SHALL add `-i`/`--interactive` so stdin still reaches the containerized process — the implementation plan SHALL confirm whether any call site actually uses `input_text` today |
| FR-6 | Dual-Engine Support | Container Executor | The system SHALL support both Podman and Docker as interchangeable engines, auto-detecting whichever is present on `PATH` (preferring rootless Podman when both are available — see AD-6) | Container mode works on hosts with either engine installed |
| FR-7 | Fail-Closed on Missing Engine | Container Executor | When `execution_mode: "container"` is set but neither a functional `podman` nor `docker` binary is detected, the system SHALL fail the QA run with an actionable error naming the missing engine | The run never silently downgrades to unsandboxed host execution once container mode is explicitly enabled |
| FR-8 | Guaranteed Cleanup | Container Executor | The system SHALL remove the ephemeral container after every execution, including on timeout or crash | No orphaned containers remain after a QA run, verified via `podman/docker ps -a` |
| FR-9 | Opt-In Default | Configuration | The system SHALL default `execution_mode` to `"host"` and only route through the container executor when explicitly configured to `"container"` | Existing installs, CI pipelines, and test suites are unaffected until an operator opts in |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Performance | Added container start/stop overhead SHALL NOT exceed 2000 ms per QA invocation on a host with the sandbox image already pulled/cached (warm-image path only; first-pull cost is excluded and documented separately). |
| NFR-2 | Security — mount isolation | The container's root filesystem SHALL be mounted read-only (`--read-only`) except for the explicit scratch bind mount and a `/tmp` tmpfs; no other writable path SHALL exist inside the container. |
| NFR-3 | Security — network egress | Container network SHALL default to `--network none` (no egress) for all QA runs under this contract; any exception is out of scope here and deferred to `SF-02` (`E-EXEC-02` Air-Gapped Network Egress Control). |
| NFR-4 | Security — privilege | The container SHALL run as a non-root user, with `--cap-drop ALL` and `--security-opt no-new-privileges:true` set unconditionally. |
| NFR-5 | Resource limits | The container SHALL enforce a memory ceiling and a process/pid ceiling. Defaults SHALL match the existing `BashActionAtom` precedent (2 GiB memory, 128 processes) for consistency rather than introducing a new limits schema (see AD-4). A CPU ceiling is intentionally NOT set by SF-01 — `BashActionAtom` sets none either — and is flagged as a candidate hardening item for `SF-02`/`SF-03`, not silently omitted. |
| NFR-6 | Cleanup guarantee | 100% of ephemeral containers SHALL be removed after execution (success, failure, or timeout) — verified in integration tests by asserting empty `podman/docker ps -a` output after each run. Removal SHALL NOT rely on the `--rm` flag alone (see AD-8). |
| NFR-7 | Backward compatibility | With `execution_mode` left at its default (`"host"`), zero behavior change SHALL occur — all existing QA runner unit/integration/e2e tests SHALL pass unmodified. |
| NFR-8 | Observability | Every containerized QA run SHALL log the resolved engine (`podman`/`docker`), image reference, and mount paths at INFO level. |
| NFR-9 | Error handling | Per FR-7, engine-detection failure in container mode SHALL raise a typed, actionable error (not a bare `SubprocessResult` with a nonzero exit code indistinguishable from a real test failure). |
| NFR-10 | Test tiering | Unit tests for the container executor SHALL mock/stub at the `execute()` boundary (no real container spawn). Integration/e2e tests SHALL be marked `integration`/`e2e` per project convention and SHALL skip (not fail) when no functional container engine is detected on the test-running host; CI SHALL provision a real container engine in at least one job lane so this path is not permanently skipped in practice. |
| NFR-11 | Platform scope | Native Linux (the CI runner, and the project's upcoming primary dev environment per its Ubuntu migration) is the supported target for FR-2/FR-3's mount/ownership semantics. VM-backed engines (Podman Desktop/Docker Desktop on Windows/macOS) are explicitly best-effort, not a completion blocker for SF-01, to avoid building throwaway platform-specific shims. |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| Podman CLI | 4.0 | `run --read-only --tmpfs --pids-limit --network none -v ...:ro -v ...:rw --cap-drop --security-opt --user --rm` | Y | Preferred engine (AD-6); rootless mode has no shared root daemon, smaller default capability set than Docker. |
| Docker CLI | 20.10 | Same flag surface | Y | Supported fallback; `dockerd` runs as root, so this is a materially weaker isolation boundary than rootless Podman — documented, not hidden. |

No new Python package dependency is introduced (see AD-1) — `pyproject.toml` is unchanged by this
contract.

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | New `ContainerSubprocessExecutor` **subclasses** `SubprocessExecutor` (added under `sandbox/execution/core/`), overriding `execute()` to wrap the incoming `cmd` into a `podman`/`docker run` argv and then delegate to `super().execute(wrapped_cmd, ...)` for the actual spawn, timeout handling, env stripping, and result contract | `PythonQARunner.__init__(cwd, executor: SubprocessExecutor | None = None)` is typed to the concrete class, not a protocol — a composition-only wrapper could not satisfy that type hint under strict mypy without widening a stable, existing signature. Subclassing is a legitimate Liskov-substitutable specialization here (same result contract, different physical spawn target) — it delegates to, rather than duplicates, the parent's logic, so it does not trip the "parallel security class" anti-pattern. Avoids adding `podman-py`/`docker-py` per external research — CLI-via-`SubprocessExecutor` covers the full required flag surface with one code path for both engines | No |
| AD-2 | Extend `factory.resolve_runner(cwd)` and `QARunnerAtom.__init__` with an optional sandbox-mode parameter (sourced from the new `[sandbox]` config) that injects `ContainerSubprocessExecutor` in place of the default host `SubprocessExecutor` | `PythonQARunner.__init__(cwd, executor=None)` already has the DI seam; extending existing call sites is strictly additive and preserves NFR-7 | No |
| AD-3 | Reuse `WorkspaceBoundary` for source-root and scratch-root path containment | Documented anti-pattern forbids parallel security classes | No |
| AD-4 | Reuse `BashActionAtom`'s `ResourceLimits` values (2 GiB memory / 128 processes) as the container's default resource ceiling | Avoids inventing a second, divergent limits schema for the same underlying concern | No |
| AD-5 | Redirect all pytest/coverage/lint artifact paths (`.pytest_cache`, `.coverage`, `--junitxml`, `PYTHONDONTWRITEBYTECODE=1`) to the scratch mount via explicit env/CLI flags at the `PythonQARunner` call site | Required because the source mount is read-only; identified as the top practical gotcha in external research | No |
| AD-6 | Prefer rootless Podman when both engines are available on a host; Docker remains a supported fallback but is documented as a weaker isolation boundary (root daemon) for this specific untrusted-code path | Matches D-EXEC-01's existing "supports both" posture while being explicit, not silent, about the security delta between engines | No |
| AD-7 | The exact mechanism for getting the target project's installed toolchain (pytest/ruff/tach/mypy, etc.) into the ephemeral container without a full reinstall on every invocation is **deferred to the SF-01 implementation plan**, but the design is split into two distinct phases to reconcile with NFR-3 (see AD-9): a **prepare phase** (network-enabled, runs `uv sync` from the project's own lockfile into a persistent, project-keyed cache volume — this phase executes only trusted, project-declared dependency resolution, never LLM-generated test code) and an **execute phase** (the actual QA run, mounts the pre-warmed cache read-only alongside the RO source, `--network none` per NFR-3 with zero exceptions). The prepare phase SHALL be gated by comparing a hash of `uv.lock`/`pyproject.toml` against a stamp file in the cache volume, re-running `uv sync` only when it changes — otherwise every run pays a full reinstall cost, defeating NFR-1. The cache-vs-host-venv choice (rather than mounting the host's own `.venv`) avoids the cross-OS/arch binary-incompatibility failure mode of mounting a Windows/macOS-built virtualenv into a Linux container base image, but the final bake/cache strategy still needs an implementation-time spike | No |
| AD-8 | `ContainerSubprocessExecutor` SHALL launch containers with a deterministic `--name` (derived from the run-id), and SHALL run an idempotent `podman/docker rm -f <name>` both immediately before start (in case a prior crashed run left a same-named container behind) and unconditionally in a `finally` block after execution — not relying on `--rm` alone, which only guarantees removal on graceful container exit, not when the outer `SubprocessExecutor` delivers `SIGKILL` to a hung client process on timeout | Closes the gap between FR-8/NFR-6's "guaranteed cleanup" claim and the actual mechanics of `SubprocessExecutor`'s existing SIGTERM→SIGKILL timeout path, which only guarantees the local CLI client process dies, not that the container it spawned is removed | No |
| AD-9 | The QA-execution container itself is always `--network none`, without exception, for every intent covered by SF-01. Any network access required for dependency resolution happens only in AD-7's separate prepare phase, never in the same container instance that runs LLM-generated test/lint code | Prevents a direct contradiction between NFR-3 (default-deny network for untrusted code) and AD-7's need for `uv sync` to reach a package index | No |

## ROI Analysis

### Investment Cost

| Item | Effort | Risk |
|------|--------|------|
| `ContainerSubprocessExecutor` + `MountSpec`/`ContainerProfile` value objects | Medium | Low–Medium (flag surface is well-trodden per external research) |
| `factory.py` / `QARunnerAtom` DI wiring for sandbox mode | Low | Low |
| New `[sandbox]` config schema in `core.config` | Low | Low |
| Per-project dependency bootstrap (image/cache strategy, AD-7) | Medium–High | Medium (cross-platform correctness, first-run latency) |
| New test coverage (unit/integration/e2e — greenfield, no existing container tests) | Medium | Low |

### Returns

| Beneficiary | Benefit | Magnitude |
|-------------|---------|-----------|
| All SpecWeaver operators | Closes the RCE exposure `E-EXEC-01`'s own design doc named as "the foundational prerequisite for US-9" | High |
| US-9 Zero-Trust Sandbox | Clears the last pending Core Required item (`E-EXEC-01`/`C-EXEC-02` are already ✅) | High |
| `SF-02` (Security Defenses) / `SF-03` (Extreme Paranoia) | `ContainerProfile` becomes their attachment point for network policy and ledger hooks | Medium (enablement, not immediate) |

### Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Operator enables `execution_mode: container` on a host without podman/docker installed | Medium | Medium | FR-7/NFR-9 fail closed with an actionable, engine-naming error; documented in the dev guide |
| Cross-platform dependency bootstrap adds first-run latency or hits binary-incompatible packages | Medium | Medium | AD-7 defers exact mechanism to an implementation-time spike; persistent cache volume amortizes cost after the first run |
| Host-owned scratch dir vs. container's non-root user UID/GID mismatch causes permission-denied writes | Medium | Low (fails loud, not silent data loss) | Implementation plan must `chown` the scratch dir pre-run or use `--user $(id -u):$(id -g)` / Podman's `:U` mount option |
| Orphaned containers from a crash mid-run | Low | Low | Deterministic `--name` plus idempotent pre-run and `finally`-block `rm -f` (AD-8) — not `--rm` alone |
| CI never actually provisions a container engine, so the containerized path is permanently skipped and never exercised (false confidence) | Medium | High | NFR-10 requires at least one CI job lane with a real engine available; integration/e2e tests skip (not silently pass) when absent |
| `uv sync` prepare-phase cache goes stale (dependencies changed but cache not invalidated), silently testing against outdated dependencies | Low | Medium | AD-7's lockfile-hash stamp-file check forces a re-sync whenever `uv.lock`/`pyproject.toml` changes |

### Refactoring Opportunities

| Existing Feature | Current Issue | Benefit from This Feature | Effort |
|-----------------|---------------|---------------------------|--------|
| `BashActionAtom` (`C-EXEC-02`) | Runs arbitrary `.specweaver/scripts/` bash directly on the host | Could route through the same `ContainerSubprocessExecutor` for defense-in-depth | Medium (deferred — out of this contract's scope, flagged as a future capability, not committed here) |
| `QARunnerAtom._intent_run_debugger` | Executes an arbitrary entrypoint — arguably higher RCE risk than tests/lint | Same swap point as FR-1; should adopt the container profile as a fast-follow within `SF-01`'s implementation plan rather than a separate roadmap item. Note: `run_debugger`'s current streaming behavior for `DebugRunResult`/`OutputEvent` must be re-verified before extending container routing to it, since `SubprocessExecutor.execute()` returns a single, fully-captured `SubprocessResult` rather than a live stream | Low |
| `BashActionAtom`'s hardcoded `ResourceLimits` | Limits values duplicated ad hoc rather than shared | Extract a shared `ResourceLimits`/`MountSpec` value object used by both atoms, avoiding future drift | Low |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Containerized QA Execution | Extend `docs/dev_guides/subprocess_execution.md` with a new section covering the DI pattern, `[sandbox]` config flag, engine detection/preference order, and mount layout | ⬜ To be written during Pre-commit |

## Sub-Feature Breakdown

### SF-01: Core QA Runner Containerized Injection (Containerized Isolation)
- **Scope**: Implements the container-routing swap point — `ContainerSubprocessExecutor`, the RO source / RW scratch mount contract, artifact-path redirection, dual-engine detection, fail-closed behavior, and the opt-in `[sandbox]` config. Delivers `B-EXEC-01` (Ephemeral Podman Sub-Containers).
- **FRs**: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9]
- **Inputs**: `PythonQARunner`'s existing argv-building logic (unchanged); host source root and a designated scratch directory path; the new `[sandbox]` config block; installed `podman`/`docker` CLI on the host.
- **Outputs**: A `SubprocessResult`-compatible response for every QA intent, produced inside an ephemeral, auto-removed container when `execution_mode: "container"` is set; unchanged host-mode behavior otherwise.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_08_integration/INT-US-09/INT-US-09_sf01_implementation_plan.md

### SF-02: Security Defenses Integration (Pending Design)
- **Scope**: Air-Gapped Network Egress Control (`E-EXEC-02`) integration contract — attaches a configurable network policy on top of SF-01's `ContainerProfile` (default-deny per NFR-3, with an explicit, audited allowlist mechanism for tests that genuinely need network access).
- **FRs**: [FR-1: Allow declaring a scoped network allowlist per QA target, FR-2: Log and audit every non-default network grant]
- **Inputs**: `ContainerProfile` from SF-01; a target-level network policy declaration.
- **Outputs**: Network-restricted or explicitly-allowlisted container runs, with an audit trail.
- **Depends on**: SF-01
- **Impl Plan**: ⬜

### SF-03: Extreme Execution Paranoia Integration (Pending Design)
- **Scope**: Functional Agent Sandboxing / Black Box Ledgers (`A-EXEC-01`) integration contract — disables continuous chat context around QA execution, managing hand-offs via an explicit disk ledger (`Request in` → `Context boots` → `Result out`) built on top of SF-01's container invocation boundary.
- **FRs**: [FR-1: Persist a mechanically-verifiable ledger entry for every containerized QA invocation, FR-2: Reject a new hydration if the prior ledger entry is not in a terminal state]
- **Inputs**: `ContainerSubprocessExecutor` invocation events from SF-01.
- **Outputs**: Disk-backed ledger records providing deterministic state recovery independent of chat context.
- **Depends on**: SF-01
- **Impl Plan**: ⬜

### SF-04: Mathematical Speed & Security (Rust) Integration (Pending Design)
- **Scope**: Git Worktree Bouncer C-Bindings (`A-EXEC-03`) integration contract — replaces the OS-level `subprocess.run(["git"])` diff-striping mechanics with native Rust `libgit2` C-bindings. Declared as a Sub-Story Add-On of US-9 in the master roadmap; grouped under this base contract for tracking consistency even though its substance (git diff-striping performance) is independent of SF-01's container-routing mechanism.
- **FRs**: [FR-1: Replace subprocess-based git diff-striping with PyO3 `libgit2` bindings behind the existing `GitExecutor` interface, FR-2: Preserve identical diff-striping semantics and test coverage]
- **Inputs**: Existing `GitExecutor`/Git Worktree Bouncer (`D-EXEC-02`) behavior as the compatibility baseline.
- **Outputs**: A drop-in, faster `GitExecutor` implementation with no behavioral change.
- **Depends on**: SF-01 *(tracking-only — kept for roadmap consistency with the other SFs under this base contract; SF-04's substance, native Rust `libgit2` bindings for `GitExecutor`, has no real technical coupling to SF-01's container-routing work and MAY be implemented in parallel if a team chooses to reorder)*
- **Impl Plan**: ⬜

## Execution Order

1. SF-01 (no deps — start immediately)
2. SF-02, SF-03, SF-04 can run in parallel (all depend only on SF-01)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Core QA Runner Containerized Injection | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | Security Defenses Integration | SF-01 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-03 | Extreme Execution Paranoia Integration | SF-01 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-04 | Mathematical Speed & Security (Rust) Integration | SF-01 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: SF-01 (Core QA Runner Containerized Injection) is COMPLETE — Design, Impl Plan, Dev, Pre-Commit, and Committed all ✅ across 4 commit boundaries (`68c34359`, `7e31ea9b`, `8046f12c`, `a2143124`). `B-EXEC-01` (Ephemeral Podman Sub-Containers) is delivered.
**Decisions confirmed with user**: Container execution is opt-in (`execution_mode` defaults to `"host"`); once explicitly enabled, missing engines fail closed rather than silently falling back to host execution. Non-root `--user` mapping (NFR-4) is in SF-01's scope, not deferred.
**Known gaps carried forward (see `INT-US-09_sf01_implementation_plan.md`'s Backlog and CB-4 progress notes)**: no literal e2e-tier (CLI-invocation) test exists yet, so `master_story_roadmap.md`/`capability_matrix.md` status flips are still pending — an open decision for the user, not resolved. A capstone integration test (real pipeline handler → real container → real `pytest`, exercising the `uv sync` prepare phase for the first time) was proposed and declined for SF-01; worth revisiting. `validation_hydrator.py`/`facades.py` remain on host-mode `QARunnerAtom` construction (deliberate scope cut). CI provisioning of a real engine and the `Containerfile.sandbox` GHCR publish pipeline are both unimplemented Backlog items — `execution_mode: "container"` requires an operator to build the image locally today.
**Next step**: SF-02 (Security Defenses Integration / `E-EXEC-02` Air-Gapped Network Egress Control) has no design yet — trigger the `specweaver-design` skill for it when ready, not `dev`.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜
in any row and resume from there using the appropriate skill.
