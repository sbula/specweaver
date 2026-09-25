# B-EXEC-01 SF-02 — QA-Runner DI Wiring

**Status**: APPROVED. Committed as `7e31ea9b`. · **FRs owned**: FR-1, FR-4 · **Depends on**: SF-01
(committed) · Design: [B-EXEC-01_design.md](B-EXEC-01_design.md) §Sub-features → SF-02

## Goal

Wire SF-01's `ContainerSubprocessExecutor` into `QARunnerAtom`/`PythonQARunner` through a widened
DI seam:
- `factory.resolve_runner` gains an `executor` parameter;
- `QARunnerAtom.__init__` gains `sandbox_settings` and builds a `ContainerSubprocessExecutor` when
  container mode is requested;
- `PythonQARunner` gets the container-mode behavior only it can own: tach pre-check skip,
  `ContainerEngineUnavailableError` handling, artifact redirection to the scratch mount.

Output: containerized QA results when a `ContainerSubprocessExecutor` is injected; unchanged
host-mode behavior otherwise.

## Where it plugs in

- **The swap point**: every `PythonQARunner` method (`run_tests`, `run_linter`, `run_complexity`,
  `run_compiler`, `run_debugger`, `run_architecture_check` —
  `sandbox/language/core/python/runner.py`) calls `self._executor.execute(cmd, ...)` **exactly
  once**. `PythonQARunner.__init__(cwd, executor: SubprocessExecutor | None = None)` is the DI seam
  (`runner.py:131`). All 5 language runners (Python/TS/Rust/Kotlin/Java) share this constructor.
- **No `input_text` usage**: none of the 6 methods passes `input_text` to `execute()`, so no
  `-i`/`--interactive` handling is needed.
- **`RunContext.config`** (`core/flow/handlers/base.py:53`): `Any = None  #
  SpecWeaverSettings | None` — on every handler's context. So `QARunnerAtom.__init__` gaining
  `sandbox_settings` is all callers need (they pass it in SF-04).
- **`QARunnerAtom(` call sites** (4, `grep -rn "QARunnerAtom("` across `src/`):
  `core/flow/handlers/validation.py:407`, `core/flow/handlers/lint_fix.py:215`,
  `core/flow/handlers/validation_hydrator.py:80`, `sandbox/qa_runner/interfaces/facades.py:180`.
  Only the first two get container mode (SF-04).
- No `test_factory.py` existed for `qa_runner/core/factory.py`; one is added.
- `qa_runner/core/{atom,factory}.py` importing `sandbox.execution.container_executor` is an existing,
  legal sandbox-internal direction. No `tach.toml` change.

## Changes

1. `factory.resolve_runner(cwd: Path, executor: SubprocessExecutor | None = None) -> QARunnerInterface`:
   thread `executor` into the selected language-runner constructor (all 5 accept it). If `executor`
   is a `ContainerSubprocessExecutor` and the class is not `PythonQARunner`:
   `logger.warning("container sandboxing is validated for Python projects only; %s may not have its toolchain available in the sandbox image", runner.language_name)`.
2. `QARunnerAtom.__init__(self, cwd: Path, language: str = "python", sandbox_settings: SandboxSettings | None = None) -> None`:
   - `sandbox_settings is None or sandbox_settings.execution_mode == "host"` → byte-for-byte
     today's behavior (`executor=None` to `resolve_runner`, NFR-7);
   - else build
     `mounts = ContainerMounts(source_root=cwd, scratch_root=cwd/".specweaver"/".sandbox"/"scratch", cache_root=cwd/".specweaver"/".sandbox"/"cache")`,
     construct `ContainerSubprocessExecutor(cwd=cwd, mounts=mounts)`, pass it as `executor=`.
3. `PythonQARunner`:
   - `_run_tach_check()` skips the host `shutil.which("tach")` pre-check when
     `isinstance(self._executor, ContainerSubprocessExecutor)`;
   - all 6 methods catch `ContainerEngineUnavailableError` → the synthetic-failure shape each
     already builds for `<timeout>`;
   - `COVERAGE_FILE`, `--junitxml`, `--cache-dir`/`PYTHONDONTWRITEBYTECODE` redirect into `/scratch`
     when containerized (FR-4/AD-5);
   - `PythonQARunner.run_debugger()` uses the bare string `"python"` in container mode (same `isinstance` check),
     like `run_tests`/`run_linter`/`run_complexity`. `sys.executable` is the *host's* interpreter
     path (a Windows `.exe` on the implementing machine), meaningless in a Linux container
     (`exec: ...: executable file not found in $PATH`).
4. `SandboxSettings(BaseModel)` (`execution_mode: Literal["host","container"] = "host"`) lands here,
   pulled forward from SF-03: the `sandbox_settings: SandboxSettings | None` type hint needs it,
   and `Any` is too loose. The TOML loading (`_load_toml_sandbox`, `load_settings_async()`) stays in
   SF-03.

| File | Change | Purpose |
|------|--------|---------|
| `src/specweaver/sandbox/qa_runner/core/factory.py` | `[MODIFY]` | Widen `resolve_runner(cwd, executor=None)`; central non-Python + container-mode WARNING log |
| `src/specweaver/sandbox/qa_runner/core/atom.py` | `[MODIFY]` | `QARunnerAtom.__init__` gains `sandbox_settings: SandboxSettings \| None = None`; builds `ContainerSubprocessExecutor` when `execution_mode == "container"` |
| `src/specweaver/sandbox/language/core/python/runner.py` | `[MODIFY]` | Conditional `tach` pre-check skip; catch `ContainerEngineUnavailableError` in all 6 methods; artifact-path redirection to `/scratch` when containerized |
| `src/specweaver/core/config/settings.py` | `[MODIFY]` | Add bare `SandboxSettings(BaseModel)` model (`execution_mode: Literal["host","container"] = "host"`) — pulled forward from SF-03 |
| `tests/unit/sandbox/qa_runner/core/qa_runner/test_factory.py` | `[NEW]` | DI-passthrough tests for the widened `resolve_runner` signature |
| `tests/unit/sandbox/qa_runner/core/qa_runner/test_atom.py` | `[MODIFY]` | `sandbox_settings` → executor selection tests |
| `tests/unit/sandbox/language/core/language/python/test_runner.py` | `[MODIFY]` | Conditional tach-precheck-skip test; `ContainerEngineUnavailableError` → synthetic-failure test |
| `tests/integration/sandbox/atoms/qa_runner/python/test_container_atom_integration.py` | `[NEW]` | Real `podman`/`docker` run, full assembled chain: `factory.resolve_runner()` → `PythonQARunner` → `ContainerSubprocessExecutor` |

## Tests

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

FR-4 is proven by the integration round trip — a host-level mock cannot show real writes landing
under `/scratch`. AD-2: DI widening, tested throughout; AD-5: redirection (FR-4).

## Decisions (audit)

| # | Question | Chosen | Severity |
|---|----------|--------|----------|
| #1 | How does `run_architecture_check` detect a missing `tach` in container mode? | The host `shutil.which("tach")` pre-check runs only when `not isinstance(self._executor, ContainerSubprocessExecutor)`; in container mode the containerized `tach check`'s exit/stderr signals absence (existing `OSError`→stderr path) | HIGH |
| #7 | How does an unavailable engine surface? | SF-01's `ContainerEngineUnavailableError`, caught once per method (all 6), converted to the synthetic failure each builds for `<timeout>` (e.g. `TestFailure(nodeid="<sandbox>", message=...)`, as at `runner.py:188`) | MEDIUM |
| #9 | Where does the "non-Python + container mode" warning live? | Once, centrally, in `factory.py` — the seam is widened for all 5 languages, but the check is not duplicated across 4 runner files | MEDIUM |

Out of scope: container wiring for `validation_hydrator.py`/`facades.py` (the other 2 of 4 call
sites); `run_debugger` containerization fast-follow (design §Risks, follow-ups).

## As built

- Landed as planned (`factory.resolve_runner(cwd, executor=None)`, central warning,
  `sandbox_settings`, tach skip, engine-error handling), plus the `SandboxSettings` model (Changes §4; its 4 tests count in SF-03) and
  the `run_debugger` `"python"` fix (Changes §3), which the real-engine integration test caught on
  its first run. 2 unit tests lock both branches. Lesson recorded in
  `special_patterns_and_adaptations.md` §23's addendum: swapping the physical execution target needs
  an audit for host-specific path assumptions; unit-test mocks cannot catch this class of bug.
- Size gate: 3 files crossed the YELLOW soft threshold (450 lines for source; 675 for tests) —
  `qa_runner/core/atom.py` (452), `language/core/python/runner.py` (592), `test_atom.py` (689). Still
  `0 errors`; not split — splitting a cohesive class for a soft metric is not warranted (e.g.
  `sandbox/filesystem/interfaces/tool.py` already sits at 521).
- Tests: 27 new (173 language-runner + 439 qa_runner/language/config tests overall). Suite at
  commit: unit 4605 passed/15 skipped, integration 434 passed/5 skipped/15 deselected, e2e 139
  passed/1 skipped.
- Docs: `subprocess_execution.md` ("Opt-In via QARunnerAtom" + the `sys.executable` note),
  `special_patterns_and_adaptations.md` (§23 addendum).
