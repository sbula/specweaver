# C-EXEC-02 SF-01 — BashActionAtom Core Execution

**Status**: APPROVED. Implemented 2026-07-13. · **FRs owned**: FR-2, FR-3, FR-4, FR-8, FR-9, FR-11,
FR-12, FR-13 · **Depends on**: none · Design: [C-EXEC-02_design.md](C-EXEC-02_design.md)
§Sub-features → SF-01

## Goal

`BashActionAtom` — an engine-internal Atom (never agent-facing) that resolves a script name to
`.specweaver/scripts/<name>`, validates canonical-path containment, invokes it via
`SubprocessExecutor` with default resource limits and explicit env opt-in, truncates output, and
turns every failure into a structured `AtomResult` — never raises. No pipeline wiring (SF-02).

- **Inputs**: `script` name, `args`, `working_dir`, `timeout_seconds`, `env`; `project_path` (constructor).
- **Outputs**: `AtomResult(status, message, exports={exit_code, stdout, stderr, duration_seconds})`.

## Where it plugs in

| Fact | Where |
|---|---|
| `run()` is synchronous and returns a **frozen dataclass** `AtomResult(status: AtomStatus, message: str, exports: dict = {})` — `message` is required, no default. `AtomStatus`: `SUCCESS`, `FAILED`, `RETRY`. | `sandbox/base.py` |
| Flat `run(context)`, like `RuleAtom` — this domain has exactly one operation. Flat vs. intent-dispatched is a per-domain choice, not implied by being an Atom. | `docs/architecture/01_foundational_principles/atoms_vs_tools.md` |
| `cwd`/`project_path` is always a constructor parameter (`QARunnerAtom`, `LanguageAtom`, `GitAtom`, `FileSystemAtom`), never a per-call `context` key → `BashActionAtom.__init__(self, cwd: Path)`. | existing Atoms |
| `execute(cmd: list[str], *, timeout_seconds: int \| None = None, extra_env: dict[str,str] \| None = None, cwd_override: Path \| None = None, input_text: str \| None = None) -> SubprocessResult`. Raises `ValueError`/`FileNotFoundError` only for `cwd_override` boundary/existence problems. **Never raises for a missing executable** — `Popen` failures are caught (`except OSError as exc: stderr = str(exc)`, executor.py:163-164) and returned as `SubprocessResult(exit_code=-1, stdout="", stderr=str(exc), ...)`. `PATH` is not in `_CREDENTIAL_VARS`/`_CREDENTIAL_PREFIXES`, and `_build_env()` applies `extra_env` **before** stripping — so FR-12's `PATH` rejection must live in the Atom. | `sandbox/execution/executor.py:90-190` |
| `bash`-not-found precedent: `if not shutil.which("tach"): ...`, "Pre-check tool existence before calling executor" (from Red/Blue finding `H-1 \ RED-1.2`). | `sandbox/language/core/python/runner.py:434` |
| `WorkspaceBoundary(roots: list[Path], api_paths: list[Path] \| None = None)`; `validate_path(requested: Path) -> Path` resolves symlinks (`Path.resolve()`, non-strict), raises `WorkspaceBoundaryError(msg)` (a plain `Exception` subclass) on escape. **Does not check existence** — neither `__init__` nor `validate_path` calls `.exists()`. So the Atom does its own `.is_file()` check, after containment (a `..`-traversal to a real outside file must fail as "containment violation", not "not found"). | `sandbox/security.py` |
| `ResourceLimits`: frozen dataclass, `max_memory_bytes: int \| None = None`, `max_processes: int \| None = None`, `max_file_size_bytes: int \| None = None` — all `None` (unbounded). `SubprocessExecutor` has no non-`None` defaults; FR-11's 2 GiB / 128-process defaults are Atom-local. | `sandbox/execution/models.py` |
| Exception style: `ProtocolAtom.run()` — specific excepts first (`ProtocolSchemaError`, `FileNotFoundError`), generic `except Exception as e` last, every branch returns `AtomResult`. `RuleAtom.run()`: `except Exception as exc: logger.exception(...); return AtomResult(FAILED, ...)`. | `ProtocolAtom`, `RuleAtom` |
| Sibling `core/` submodules (`qa_runner/core`, `git/core`, `code_structure/core`, `mcp/core`) use a **bare one-liner** `archetype: adapter` — no `module:`/`consumes:`/`forbids:` (that lives on domain-root files like `sandbox/execution/context.yaml`). This corrects the design's AD-1 wording. | sibling `context.yaml` |
| Test path convention: `tests/unit/sandbox/<domain>/core/<domain>/test_<domain>_atom.py` (doubled segment; see `language/core/language/test_language_atom.py`, `mcp/core/mcp/test_mcp_atom.py`). Real-subprocess precedent: `tests/unit/sandbox/execution/test_executor.py` (no `Popen` mocking — real timeout, real symlink-escape tests). | tests |
| TID251 exemption glob `"src/specweaver/sandbox/execution/*.py"` is **single-level** — it does not cover `sandbox/execution/core/*.py`. No problem: the Atom never imports `subprocess`. No `pyproject.toml` change. | `pyproject.toml` |

**One containment check per `run()`.** FR-2's load-time check belongs to SF-02 (pipeline YAML
validation). `run()` *is* the "immediately before execution" checkpoint: it re-resolves from disk
each call with nothing between the check and `execute()`. A second check in the same body adds
nothing (YAGNI).

## Changes

| File | Change | Purpose |
|------|--------|---------|
| `src/specweaver/sandbox/execution/core/__init__.py` | `[NEW]` | Empty, package marker (matches sibling `core/` submodules) |
| `src/specweaver/sandbox/execution/core/context.yaml` | `[NEW]` | `archetype: adapter` one-liner (matches `qa_runner/core`, `git/core`, `code_structure/core`, `mcp/core`) |
| `src/specweaver/sandbox/execution/core/atom.py` | `[NEW]` | `BashActionAtom` class |
| `tests/unit/sandbox/execution/core/execution/__init__.py` | `[NEW]` | Empty, package marker |
| `tests/unit/sandbox/execution/core/execution/test_execution_atom.py` | `[NEW]` | Unit tests for `BashActionAtom` |

No existing file changes. The `tach.toml` and `core/flow/context.yaml` edits SF-02 needs are
SF-03's; this SF's tests import `specweaver.sandbox.execution.core.atom` from sandbox-internal test
code and are unaffected.

**`atom.py`.** `BashActionAtom(Atom)`, constructor `cwd: Path` (= `project_path`), derives
`self._scripts_root = cwd / ".specweaver" / "scripts"`. `run(self, context: dict[str, Any]) -> AtomResult`,
built test-first in this order:

1. Read `script`; missing/empty → `FAILED` ("Missing 'script'").
2. `script` contains `/`, `\`, or `..` → `FAILED` ("must be a bare filename") — in-memory, before any I/O (FR-2 part 1).
3. Read `args` (default `[]`), `working_dir`, `timeout_seconds`, `env` (default `{}`).
4. `timeout_seconds` set and above `3600` (NFR-4 ceiling) → `FAILED`.
5. Any `env` key equal to `PATH` case-insensitively → `FAILED` ("may not set PATH") — FR-12 defense-in-depth.
6. Resolve `self._scripts_root / script` through
   `WorkspaceBoundary(roots=[self._scripts_root]).validate_path(...)`; catch
   `WorkspaceBoundaryError` → `FAILED` with its message. This is the pre-execution checkpoint.
7. Resolved path not `.is_file()` → `FAILED` ("Script not found").
8. `shutil.which("bash")` falsy → `FAILED` ("bash interpreter not found on PATH") — mirrors `python/runner.py:434`.
9. `cwd_override = self._cwd / working_dir` if set, else `None`. Containment/existence is left to
   `SubprocessExecutor._validate_cwd`.
10. `SubprocessExecutor(cwd=self._cwd, resource_limits=<2 GiB / 128 procs — FR-11>)`, then
    `.execute(["bash", str(resolved), *args], timeout_seconds=timeout_seconds, extra_env=env, cwd_override=cwd_override)`.
    In a `try`: `(ValueError, FileNotFoundError)` (working_dir boundary/existence) → `FAILED` with
    the message; final generic `Exception` → `FAILED`, `"crashed: {type}: {msg}"` (FR-13; specific
    first, catch-all last, never re-raise).
11. `result.exit_code == 0` → `AtomStatus.SUCCESS`, else `FAILED` (FR-5's convention, used by SF-02).
12. Return
    `AtomResult(status=..., message=f"bash script '{script}' exited {result.exit_code}", exports={"exit_code", "stdout": truncate(result.stdout), "stderr": truncate(result.stderr), "duration_seconds"})`.

`truncate(text)` (module-level, FR-8): if the UTF-8 encoding exceeds 1 MiB (`1_048_576` bytes),
slice to that byte length, decode with `errors="ignore"` (drops a split trailing multi-byte
character — harmless), append `...[TRUNCATED]`; else return unchanged.

## Tests

`tests/unit/sandbox/execution/core/execution/test_execution_atom.py` — real `bash` against
`tmp_path` fixture scripts, module-wide `@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not on PATH")`.
The planned tests; the 4 added at the pre-commit gate are under As built.

| Test | FR/NFR | Asserts |
|------|--------|---------|
| `test_missing_script_key_fails` | FR-2 | No `script` in context → `FAILED`, message mentions "script" |
| `test_script_name_with_separator_rejected` | FR-2 | `script="../../etc/passwd"` and `script="sub/dir.sh"` → `FAILED` before any filesystem access |
| `test_script_outside_scripts_dir_via_symlink_rejected` | FR-2, NFR-1 | Symlink inside `.specweaver/scripts/` pointing outside → `FAILED`, containment message |
| `test_missing_script_file_fails` | FR-2 | Valid bare name, containment passes, file absent → `FAILED`, "not found" |
| `test_successful_script_execution` | FR-3, FR-4, FR-5 | Fixture `.sh` (`exit 0`, `echo hello`) → `SUCCESS`, `exports["stdout"]` contains `"hello"`, `exit_code == 0` |
| `test_nonzero_exit_maps_to_failed` | FR-4, FR-5 | Fixture `exit 3` → `FAILED`, `exports["exit_code"] == 3` |
| `test_args_passed_through` | FR-3 | Fixture echoes `$1` → `exports["stdout"]` reflects the arg |
| `test_working_dir_resolved_relative_to_project` | FR-3 | With `working_dir` set, the script's `pwd` matches the resolved dir |
| `test_working_dir_escaping_project_rejected` | FR-3 | `working_dir="../../outside"` → `FAILED` (via `SubprocessExecutor._validate_cwd`'s `ValueError`) |
| `test_stdout_truncated_over_1mib` | FR-8 | Prints >1 MiB → `exports["stdout"]` ends with `...[TRUNCATED]`, length capped |
| `test_timeout_override_applied` | FR-9 | Sleeps 2s, `timeout_seconds=1` → `timed_out` behavior reflected (nonzero/failed exit) |
| `test_timeout_over_ceiling_rejected` | NFR-4 | `timeout_seconds=7200` → `FAILED` before execution, ceiling message |
| `test_resource_limits_applied_by_default` | FR-11 | Patch `specweaver.sandbox.execution.core.atom.SubprocessExecutor` with a `MagicMock`; assert `resource_limits=_DEFAULT_RESOURCE_LIMITS` in the call kwargs (not a live OOM test) |
| `test_env_map_passed_through` | FR-12 | `env={"MY_VAR": "x"}`, script echoes `$MY_VAR` → present in stdout |
| `test_env_path_override_rejected_case_insensitive` | FR-12 | `env={"PATH": "/evil"}`, `env={"Path": "/evil"}`, `env={"path": "/evil"}` → all `FAILED` before execution |
| `test_env_does_not_leak_run_context_vars` | FR-12, Security | No `env` → only `SubprocessExecutor`'s allowlist reaches the child |
| `test_bash_not_on_path_fails_cleanly` | NFR-9 | `shutil.which` → `None` → `FAILED`, "bash interpreter not found", no raw traceback |
| `test_crashing_executor_never_propagates` | FR-13 | `SubprocessExecutor.execute` raises unexpectedly → `FAILED`, `AtomResult` returned, nothing escapes `run()` |
| `test_atom_is_atom_subclass` | — | `isinstance(atom, Atom)` (as in `RuleAtom`'s tests) |

Fixture-script authoring (inline heredoc vs. `tmp_path`-written `.sh`) was left to the `dev` skill.

**Coverage.**

| ID | Covered by |
|----|-----------|
| FR-2 | Bare-name check + `WorkspaceBoundary` containment + `.is_file()`; tests: missing-script-key, separator, symlink-escape, missing-file |
| FR-3 | `["bash", resolved, *args]` argv; `cwd_override` delegated to `SubprocessExecutor._validate_cwd`; tests: successful-execution, args-passed, working-dir |
| FR-4 | `exports={exit_code, stdout, stderr, duration_seconds}`; test: successful-execution |
| FR-5 | exit code → `AtomStatus` (SF-02 maps `AtomStatus` → `StepStatus`); test: nonzero-exit |
| FR-8 | `_truncate()`, 1 MiB cap; test: stdout-truncated |
| FR-9 | `timeout_seconds` passthrough to `execute()`; test: timeout-override |
| FR-11 | `_DEFAULT_RESOURCE_LIMITS` (2 GiB / 128 procs) always passed; test: resource-limits-applied |
| FR-12 | env opt-in only (no implicit `RunContext.env_vars`), case-insensitive `PATH` rejection; tests: env-passed, path-rejected (3 variants), no-leak |
| FR-13 | Multi-except (`WorkspaceBoundaryError`, `ValueError`/`FileNotFoundError`, generic `Exception`), every branch returns `AtomResult`; test: crashing-executor-never-propagates |
| AD-1 | `context.yaml` = bare `archetype: adapter` |
| AD-2 | Explicit containment check despite Atom grant-bypass |
| AD-3 | Literal `WorkspaceBoundary` reuse |

NFR-1 (canonical, fail-closed), NFR-2 (fixed argv, `shell=False` from `SubprocessExecutor`), NFR-3
(inherited), NFR-4 (ceiling), NFR-5 (1 MiB), NFR-6 (literal bash; WSL path translation is an accepted
gap), NFR-8 (DEBUG logging inherited from `SubprocessExecutor`'s `logger.debug` in `execute()`),
NFR-9 (distinct message per branch), NFR-10 (only new files). NFR-6/7 are partly accepted
limitations by design.

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| 1 | Real `bash` in tests? | **Yes, guarded by `skipif`** (above) — matches today's WSL bridge, costs nothing after the Ubuntu migration (see project memory) |
| 2 | Where does FR-12's `PATH` rejection live? | **In `BashActionAtom` itself**, not only in SF-02's YAML validation — defense-in-depth, symmetric with FR-2; the Atom must not assume upstream validation ran |

Both approved by the user. Every other audit item was settled by codebase research.

Red/Blue review (2 cycles, converged, no code changes):

- `WorkspaceBoundaryError` vs. `(ValueError, FileNotFoundError)` cannot be mis-attributed: each
  `try` wraps a disjoint region (`boundary.validate_path()` vs. `executor.execute()`).
- `_truncate()` byte slicing (`encoded[:_MAX_OUTPUT_BYTES]`) may split a UTF-8 character;
  `errors="ignore"` drops it silently — accepted, better than `UnicodeDecodeError`.
- Cheap in-memory checks (bare name, timeout ceiling, `PATH`) run before filesystem I/O (containment
  resolve, `.is_file()`, `shutil.which`) for speed only. All run before `execute()`, so the order does
  not affect security.

Architecture check: no circular imports (`BashActionAtom` → `sandbox.execution` +
`sandbox.security`, both leaf-ward of `sandbox.execution.core`). Stays in the `sandbox` bounded
context. The `SubprocessExecutor.execute()` call remains the `B-EXEC-01` container-routing swap
point.

**Out of scope**: FR-7's JSON stdout parsing (YAGNI, cut by the design's Red/Blue review); WSL
Windows-path translation (NFR-6); `tach.toml`/`core/flow/context.yaml` wiring (SF-03);
`StepAction.BASH`/`BashActionHandler` (SF-02).

## As built (2026-07-13)

As planned, 8 files. All FR/NFR/AD coverage held; no FR dropped or reduced.

- **argv[0] is the resolved bash path**, not the string `"bash"`: `bash_path = shutil.which("bash")`,
  resolved once per `run()`. On Windows+WSL a bare `"bash"` hit WSL's `bash.exe` stub in
  `C:\Windows\System32` instead of Git Bash, because `CreateProcess` searches `System32` before
  `%PATH%` regardless of `PATH` order. NFR-6 reads as "invoke via the resolved bash path".
- 4 gap-closing tests added in the pre-commit gate (user-approved "Option A"):
  `test_workspace_boundary_error_handled_without_symlink`, `test_working_dir_escaping_project_rejected`
  re-scoped to hit `ValueError` (sibling `test_working_dir_nonexistent_rejected` takes
  `FileNotFoundError`), `test_shell_metacharacter_arg_treated_as_literal`,
  `test_non_string_arg_does_not_propagate_raw_exception`. 24 → 28 tests (1 platform-skip).
- **TECH-009 implemented here**: the gate's repo-wide `ruff check` found 6 pre-existing `TID251`
  violations. `git/core/executor.py` and `filesystem/core/search.py` moved to `SubprocessExecutor`
  via constructor/parameter DI ([TECH-009 design](../../topic_07_technical_debt/TECH-009/TECH-009_design.md)).
  `cli_drift.py` and `assurance/standards/discovery.py` keep raw `subprocess` with documented
  `noqa: TID251` (routing them through `sandbox` would cross a bounded-context line — deferred to
  TECH-009's backlog). `mcp/core/executor.py` keeps a documented exemption: its persistent,
  bidirectional subprocess does not fit one-shot `execute()` → **TECH-010**. A `C901` in
  `tests/unit/test_architecture.py` was also fixed. No C-EXEC-02 scope affected.
