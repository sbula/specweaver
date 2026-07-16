# Implementation Plan: Ephemeral Podman Sub-Containers [SF-02: QA-Runner DI Wiring]

- **Feature ID**: B-EXEC-01
- **Sub-Feature**: SF-02 — QA-Runner DI Wiring
- **Design Document**: docs/roadmap/features/topic_06_sandbox/B-EXEC-01/B-EXEC-01_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_06_sandbox/B-EXEC-01/B-EXEC-01_sf02_implementation_plan.md
- **Status**: APPROVED

## Scope

Wire SF-01's `ContainerSubprocessExecutor` into `QARunnerAtom`/`PythonQARunner` via a widened DI
seam: `factory.resolve_runner` gains an `executor` parameter, `QARunnerAtom.__init__` gains a
`sandbox_settings` parameter that builds a `ContainerSubprocessExecutor` when container mode is
requested, and `PythonQARunner` gains the container-mode-specific behavior it structurally cannot
avoid owning itself (tach pre-check skip, `ContainerEngineUnavailableError` handling, artifact-path
redirection to the scratch mount).

**FRs covered**: FR-1, FR-4.
**Inputs**: SF-01's `ContainerSubprocessExecutor`/`ContainerMounts`; `PythonQARunner`'s existing
argv-building logic (unchanged in shape, extended for redirection).
**Outputs**: `QARunnerAtom` produces containerized QA results when a `ContainerSubprocessExecutor`
is injected; unchanged host-mode behavior otherwise.
**Depends on**: SF-01 (committed).

## Research Notes

- **The swap point**: every `PythonQARunner` method (`run_tests`, `run_linter`, `run_complexity`,
  `run_compiler`, `run_debugger`, `run_architecture_check` — `sandbox/language/core/python/runner.py`)
  calls `self._executor.execute(cmd, ...)` **exactly once**. `PythonQARunner.__init__(cwd,
  executor: SubprocessExecutor | None = None)` already has the DI seam (`runner.py:131`). All 5
  language runners (Python/TS/Rust/Kotlin/Java) share this exact constructor shape.
- **No `input_text` usage exists today**: none of `PythonQARunner`'s 6 methods pass `input_text`
  to `execute()`. Confirmed not applicable — no `-i`/`--interactive` flag handling needed for this
  SF's actual call sites.
- **`RunContext.config`** (`core/flow/handlers/base.py:53`): `Any = None  #
  SpecWeaverSettings | None` — already present on every handler's context; not this SF's concern
  directly (that's SF-04), but establishes that `QARunnerAtom.__init__` gaining a
  `sandbox_settings` parameter is all that's needed for callers to eventually pass it through.
- **Factory/atom call sites for `QARunnerAtom`** (4 total, `grep -rn "QARunnerAtom("` across
  `src/`): `core/flow/handlers/validation.py:407`, `core/flow/handlers/lint_fix.py:215`,
  `core/flow/handlers/validation_hydrator.py:80`, `sandbox/qa_runner/interfaces/facades.py:180`.
  Only the first two are wired for container mode (SF-04); the other two are left unwired for
  scope discipline (Backlog).
- **No existing `test_factory.py`** for `qa_runner/core/factory.py` — a new one is added (direct
  unit coverage for the widened DI signature, since none existed before).

## Resolved Audit Findings

1. **(#1, HIGH)** `run_architecture_check`'s host-side `shutil.which("tach")` pre-check is made
   conditional on `not isinstance(self._executor, ContainerSubprocessExecutor)` — skipped in
   container mode, letting the containerized `tach check` invocation's own exit/stderr signal
   absence (existing `OSError`→stderr path already handles it).
7. **(#7, MEDIUM)** Engine-unavailable failures raise SF-01's `ContainerEngineUnavailableError`,
   caught once per `PythonQARunner` method (all 6), converted into the same kind of
   synthetic-failure result each method already builds for its `<timeout>` case (e.g.
   `TestFailure(nodeid="<sandbox>", message=...)`, matching the existing pattern at
   `runner.py:188`).
9. **(#9, MEDIUM)** `factory.resolve_runner`'s DI seam is widened generically for all 5
   languages, but the "is this runner class Python?" check and its accompanying WARNING log for
   non-Python + container-mode combinations live **once, centrally, in `factory.py`** — not
   duplicated across 4 language-runner files.

## Proposed Changes

| File | Change | Purpose |
|------|--------|---------|
| `src/specweaver/sandbox/qa_runner/core/factory.py` | `[MODIFY]` | Widen `resolve_runner(cwd, executor=None)`; central non-Python + container-mode WARNING log |
| `src/specweaver/sandbox/qa_runner/core/atom.py` | `[MODIFY]` | `QARunnerAtom.__init__` gains `sandbox_settings: SandboxSettings \| None = None`; builds `ContainerSubprocessExecutor` when `execution_mode == "container"` |
| `src/specweaver/sandbox/language/core/python/runner.py` | `[MODIFY]` | Conditional `tach` pre-check skip; catch `ContainerEngineUnavailableError` in all 6 methods; artifact-path redirection to `/scratch` when containerized |
| `src/specweaver/core/config/settings.py` | `[MODIFY]` | Add bare `SandboxSettings(BaseModel)` model (`execution_mode: Literal["host","container"] = "host"`) — pulled forward from SF-03 due to a type-hint dependency (see Post-Implementation Notes) |
| `tests/unit/sandbox/qa_runner/core/qa_runner/test_factory.py` | `[NEW]` | DI-passthrough tests for the widened `resolve_runner` signature |
| `tests/unit/sandbox/qa_runner/core/qa_runner/test_atom.py` | `[MODIFY]` | `sandbox_settings` → executor selection tests |
| `tests/unit/sandbox/language/core/language/python/test_runner.py` | `[MODIFY]` | Conditional tach-precheck-skip test; `ContainerEngineUnavailableError` → synthetic-failure test |
| `tests/integration/sandbox/atoms/qa_runner/python/test_container_atom_integration.py` | `[NEW]` | Real `podman`/`docker` run, full assembled chain: `factory.resolve_runner()` → `PythonQARunner` → `ContainerSubprocessExecutor` |

## Implementation Sequence (pseudocode)

1. `factory.resolve_runner(cwd: Path, executor: SubprocessExecutor | None = None) -> QARunnerInterface`: thread `executor` through to whichever language-runner constructor is selected (all 5 already accept it). After selection, if `executor` is a `ContainerSubprocessExecutor` and the selected class is not `PythonQARunner`, `logger.warning("container sandboxing is validated for Python projects only; %s may not have its toolchain available in the sandbox image", runner.language_name)` — centralizes Finding #9's warning in one place.
2. `QARunnerAtom.__init__(self, cwd: Path, language: str = "python", sandbox_settings: SandboxSettings | None = None) -> None`: if `sandbox_settings is None or sandbox_settings.execution_mode == "host"`, behavior is byte-for-byte identical to today (`executor=None` passed to `resolve_runner`, preserving NFR-7). Else, build `mounts = ContainerMounts(source_root=cwd, scratch_root=cwd/".specweaver"/".sandbox"/"scratch", cache_root=cwd/".specweaver"/".sandbox"/"cache")`, construct `ContainerSubprocessExecutor(cwd=cwd, mounts=mounts)`, pass it as `executor=` to `resolve_runner`.
3. `PythonQARunner`: `_run_tach_check()` skips the host-side `shutil.which("tach")` pre-check when `isinstance(self._executor, ContainerSubprocessExecutor)`. All 6 methods catch `ContainerEngineUnavailableError` and convert it to the same synthetic-failure shape each already builds for its `<timeout>` case. Artifact-writing paths (`COVERAGE_FILE`, `--junitxml`, `--cache-dir`/`PYTHONDONTWRITEBYTECODE`) redirect into `/scratch` when the executor is a `ContainerSubprocessExecutor` (FR-4/AD-5).

## Test Plan

| Test | FR/NFR | Asserts |
|------|--------|---------|
| `test_tach_precheck_skipped_in_container_mode` | Finding #1 | `PythonQARunner` with a `ContainerSubprocessExecutor` → `shutil.which("tach")` NOT called on the host |
| `test_tach_precheck_still_runs_in_host_mode` | Finding #1 | `PythonQARunner` with a plain `SubprocessExecutor` → host-side `shutil.which("tach")` check unchanged |
| `test_container_engine_unavailable_becomes_synthetic_failure` | Finding #7 | `ContainerEngineUnavailableError` raised during `run_tests` → returns a `TestRunResult` with a `<sandbox>`-nodeid `TestFailure`, not an unhandled exception |
| `test_resolve_runner_threads_executor_to_python` | FR-1, AD-2 | `factory.resolve_runner(cwd, executor=mock)` → `PythonQARunner._executor is mock` |
| `test_resolve_runner_warns_on_non_python_container_executor` | Finding #9 | `resolve_runner` with a TS-project cwd + a `ContainerSubprocessExecutor` → warning logged, `TypeScriptRunner` still constructed (no crash, no silent no-op) |
| `test_qa_runner_atom_host_mode_default_unchanged` | FR-9, NFR-7 | `QARunnerAtom(cwd=...)` (no `sandbox_settings`) → behavior/executor identical to pre-feature |
| `test_qa_runner_atom_container_mode_builds_container_executor` | FR-1, AD-2 | `QARunnerAtom(cwd=..., sandbox_settings=SandboxSettings(execution_mode="container"))` → `ContainerSubprocessExecutor` constructed with mounts derived from `cwd` |
| **Integration** `test_container_atom_integration` (real Podman, full chain) | FR-1..FR-4 | `factory.resolve_runner()` → `PythonQARunner` → `ContainerSubprocessExecutor` → real engine |

## FR / NFR / AD Coverage

| ID | Covered by |
|----|-----------|
| FR-1 | `ContainerSubprocessExecutor` construction gated on `execution_mode`; tests: `test_qa_runner_atom_container_mode_builds_container_executor`, `test_resolve_runner_threads_executor_to_python` |
| FR-4 | Artifact-path redirection in `runner.py` — covered by the integration round-trip test (host-level unit mocking can't meaningfully assert real file writes land under `/scratch`) |
| AD-2 | `factory.resolve_runner`/`QARunnerAtom.__init__` DI widening; tests throughout |
| AD-5 | Artifact-path redirection (FR-4) |

## Backlog (deferred, out of scope for SF-02)

- **`validation_hydrator.py` / `facades.py` container wiring**: the other 2 of 4 `QARunnerAtom`
  call sites; deferred for scope discipline — SF-04 only wires `validation.py`/`lint_fix.py`.
- **`run_debugger` containerization fast-follow**: already flagged in the design doc's Refactoring
  Opportunities.

## Phase 5: Final Consistency Check

**5.1 Open questions**: None remaining.

**5.2 Architecture**: `qa_runner/core/{atom,factory}.py` import `sandbox.execution.container_executor`
— an existing, already-legal sandbox-internal direction. No `tach.toml` change required.

### Red/Blue Team Review (1 cycle — no findings beyond what implementation caught, see below)

No pre-approval Red/Blue findings beyond the design-level ones already resolved. The real bug this
sub-feature exposed (`sys.executable` vs. bare `"python"`) was caught by the real-engine
integration test during implementation, not by this plan's own review — see Post-Implementation
Notes.

---

## HITL Gate — Approval Required

This plan is ready for review. Summary: 4 modified source files, 4 new/modified test files,
widens an existing DI seam rather than inventing a new one, zero `tach.toml` changes.

Reply with approval to mark this plan `APPROVED` and proceed to the `dev` skill for SF-02's TDD
implementation.

---

## Post-Implementation Notes

**Landed as planned**: `factory.resolve_runner(cwd, executor=None)` widened, centralized
non-Python + container-mode warning; `QARunnerAtom.__init__` gains `sandbox_settings`;
`PythonQARunner`'s tach pre-check skip + `ContainerEngineUnavailableError` handling across all 6
methods.

**Sequencing correction found mid-implementation**: this sub-feature's `sandbox_settings:
SandboxSettings | None` type hint needs `SandboxSettings` to exist, but the model was originally
slotted entirely in SF-03. Rather than loosely type it `Any`, pulled just the `SandboxSettings`
**model definition** (in `core/config/settings.py`) forward into this sub-feature — the
TOML-loading wiring (`_load_toml_sandbox`, threading into `load_settings_async()`) stays in SF-03
as planned. 4 new tests for the bare model, counted in SF-03's own test count.

**Test coverage exceeded the plan**: per the user's standing "don't forget e2e/integration tests"
preference, added a real-engine integration test
(`tests/integration/sandbox/atoms/qa_runner/python/test_container_atom_integration.py`)
exercising the full assembled chain — `factory.resolve_runner()` → `PythonQARunner` →
`ContainerSubprocessExecutor` → a real, live Podman engine. This test's first run failed for
real, catching a genuine bug no mocked unit test could: `PythonQARunner.run_debugger()` built its
command with `sys.executable` (the *host's* interpreter path — a Windows `.exe` path on the
implementing machine), which is meaningless inside a Linux container (`exec: ...: executable file
not found in $PATH`). Fixed: `run_debugger` now uses the bare string `"python"` in container mode
(matching how `run_tests`/`run_linter`/`run_complexity` already worked), selected via the same
`isinstance(self._executor, ContainerSubprocessExecutor)` check already used for the tach
pre-check skip. 2 new unit tests lock in both branches; the integration test now passes for real.
Documented as a general lesson in `special_patterns_and_adaptations.md` §23's addendum:
physical-execution-target swaps need auditing for host-specific path assumptions, and unit-test
mocks alone can't catch this class of bug.

**Quality note**: 3 files crossed the file-size YELLOW soft-threshold (450 lines for source) as a
direct result of this sub-feature's additions — `qa_runner/core/atom.py` (452),
`language/core/python/runner.py` (592), `test_atom.py` (689, tests threshold is 675). All still
`0 errors` on the size gate; not refactored, since splitting a cohesive class to dodge a soft
line-count metric isn't warranted (several pre-existing sandbox files already sit further into
this band, e.g. `sandbox/filesystem/interfaces/tool.py` at 521).

**Test counts**: 27 new tests, all green (173 language-runner tests + 439 qa_runner/language/config
tests overall, zero regressions). Full suite: unit 4605 passed/15 skipped, integration 434
passed/5 skipped/15 deselected, e2e 139 passed/1 skipped.

**Documentation updated**: `subprocess_execution.md` (new "Opt-In via QARunnerAtom" section + the
`sys.executable` gotcha note), `special_patterns_and_adaptations.md` (§23 addendum).

**Committed as**: `7e31ea9b`.
