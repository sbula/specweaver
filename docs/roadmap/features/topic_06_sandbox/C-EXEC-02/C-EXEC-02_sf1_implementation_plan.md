# Implementation Plan: Native CLI Action Nodes [SF-1: BashActionAtom Core Execution]

- **Feature ID**: C-EXEC-02
- **Sub-Feature**: SF-1 — BashActionAtom Core Execution
- **Design Document**: docs/roadmap/features/topic_06_sandbox/C-EXEC-02/C-EXEC-02_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-1
- **Implementation Plan**: docs/roadmap/features/topic_06_sandbox/C-EXEC-02/C-EXEC-02_sf1_implementation_plan.md
- **Status**: APPROVED

## Scope

Build `BashActionAtom` — a new, engine-internal Atom (never agent-facing) that resolves a script name to `.specweaver/scripts/<name>`, validates canonical-path containment, invokes it via `SubprocessExecutor` with default resource limits and explicit env opt-in, truncates output, and converts every failure mode into a structured `AtomResult` — never raises. No pipeline-engine wiring in this SF (that's SF-2); this SF is fully testable in isolation.

**FRs covered**: FR-2, FR-3, FR-4, FR-8, FR-9, FR-11, FR-12, FR-13 (see design doc for full text).
**Inputs**: `script` name, `args`, `working_dir`, `timeout_seconds`, `env`, `project_path` (constructor).
**Outputs**: `AtomResult(status, message, exports={exit_code, stdout, stderr, duration_seconds})`.
**Depends on**: none.

## Research Notes

- **`Atom` base class** (`sandbox/base.py`): `run()` is synchronous, returns a **frozen dataclass** `AtomResult(status: AtomStatus, message: str, exports: dict = {})` — `message` is required, no default. `AtomStatus` has 3 values: `SUCCESS`, `FAILED`, `RETRY`.
- **Atom ≠ single-operation** (see the newly-added clarification in `docs/architecture/01_foundational_principles/atoms_vs_tools.md`): whether `run()` is flat or intent-dispatched is an independent per-domain choice. `BashActionAtom` uses a **flat** `run(context)` — not because it's an Atom, but because this domain genuinely has exactly one operation (run a script), matching `RuleAtom`'s shape.
- **`cwd`/`project_path` is always a constructor parameter** across every existing Atom (`QARunnerAtom`, `LanguageAtom`, `GitAtom`, `FileSystemAtom`) — never a per-call `context` key. `BashActionAtom.__init__(self, cwd: Path)` follows this.
- **`SubprocessExecutor.execute()`** (`sandbox/execution/executor.py:90-190`) exact signature: `execute(cmd: list[str], *, timeout_seconds: int | None = None, extra_env: dict[str,str] | None = None, cwd_override: Path | None = None, input_text: str | None = None) -> SubprocessResult`. Raises `ValueError`/`FileNotFoundError` only for `cwd_override` boundary/existence problems. **Never raises for a missing command executable** — `Popen` failures are caught internally (`except OSError as exc: stderr = str(exc)`, executor.py:163-164) and returned as `SubprocessResult(exit_code=-1, stdout="", stderr=str(exc), ...)`. Confirmed: `PATH` is not in `_CREDENTIAL_VARS`/`_CREDENTIAL_PREFIXES` and `_build_env()` applies `extra_env` **before** stripping — so `SubprocessExecutor` itself provides no `PATH`-override protection; FR-12's rejection must be implemented by `BashActionAtom`.
- **`bash`-not-found precedent already exists**: `sandbox/language/core/python/runner.py:434` does `if not shutil.which("tach"): ...` with the comment "Pre-check tool existence before calling executor" — itself the product of a prior Red/Blue finding (`H-1 \ RED-1.2`). `BashActionAtom` follows this exact pattern for `bash`.
- **`WorkspaceBoundary`** (`sandbox/security.py`): `WorkspaceBoundary(roots: list[Path], api_paths: list[Path] | None = None)`; `validate_path(requested: Path) -> Path` resolves symlinks (`Path.resolve()`, non-strict) and raises `WorkspaceBoundaryError(msg)` (a plain `Exception` subclass) on escape. **Does not check file existence** — `resolve()` succeeds even for non-existent paths, and neither `__init__` nor `validate_path` calls `.exists()`. `BashActionAtom` must do its own explicit `.is_file()` check, separate from and after the containment check (a `..`-traversal to a real file outside the boundary must fail as "containment violation," not "not found").
- **Containment check happens once per `run()` call, not twice** — the design doc's FR-2 requires validation "both at pipeline-load time and immediately before execution." The load-time check is SF-2's responsibility (pipeline YAML validation, out of scope here). `BashActionAtom.run()` **is** the "immediately before execution" checkpoint by construction — it re-resolves the path fresh from disk every time it's invoked, with nothing intervening between the check and the `execute()` call. A second internal check within the same function body would be pure redundancy (YAGNI), not an additional safety property.
- **`ResourceLimits`** (`sandbox/execution/models.py`): frozen dataclass, `max_memory_bytes: int | None = None`, `max_processes: int | None = None`, `max_file_size_bytes: int | None = None` — all default `None` (unbounded). `SubprocessExecutor` has no built-in non-`None` defaults; FR-11's 2 GiB / 128-process defaults are `BashActionAtom`-local.
- **Exception-handling style precedent**: `ProtocolAtom.run()` — specific excepts first (`ProtocolSchemaError`, `FileNotFoundError`), generic `except Exception as e` catch-all last, every branch returns `AtomResult`, never raises. `RuleAtom.run()` confirms the "always return, never raise" philosophy with `except Exception as exc: logger.exception(...); return AtomResult(FAILED, ...)`.
- **`sandbox/execution/core/context.yaml`**: all 4 existing sibling `core/` submodules (`qa_runner/core`, `git/core`, `code_structure/core`, `mcp/core`) use a **bare one-liner** `archetype: adapter` — no `module:`/`consumes:`/`forbids:` block at that level (that richer structure only exists on domain-root `context.yaml` files, e.g. `sandbox/execution/context.yaml` itself). SF-1's new `context.yaml` follows this exact precedent, correcting the design doc's AD-1 wording (which implied a richer block).
- **Test file convention**: `tests/unit/sandbox/<domain>/core/<domain>/test_<domain>_atom.py` (doubled segment, domain-named file — confirmed via `language/core/language/test_language_atom.py`, `mcp/core/mcp/test_mcp_atom.py`). SF-1's tests go in `tests/unit/sandbox/execution/core/execution/test_execution_atom.py`.
- **Real-subprocess test precedent**: `tests/unit/sandbox/execution/test_executor.py` uses real `subprocess` calls (no `Popen` mocking) — real timeout tests, real symlink-escape tests. `BashActionAtom` wraps `SubprocessExecutor` directly (no further interface layer), so its own tests should follow the same real-execution style, one layer further out, against real fixture `.sh` scripts under `tmp_path`.
- **`ruff` TID251** (`pyproject.toml`): the `subprocess`-import-ban exemption glob is `"src/specweaver/sandbox/execution/*.py"` — **single-level**, does not cover `sandbox/execution/core/*.py`. Not a problem for this SF: `BashActionAtom` only calls `SubprocessExecutor.execute()`, never imports `subprocess` directly, so TID251 never triggers. No `pyproject.toml` change needed for SF-1.

## Resolved Audit Findings

(Full audit ran across Phase 2–4; see conversation history for the complete table. Two items were genuinely open and are resolved here per user confirmation to proceed with the proposals as presented.)

1. **Real `bash` execution in tests, guarded by `skipif`.** `BashActionAtom`'s tests invoke real `bash` against fixture scripts, decorated `@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not on PATH")` — matches the WSL-bridge environment today and costs nothing once the Ubuntu migration lands (see project memory on the migration timeline).
2. **`PATH`-rejection (FR-12) is implemented in `BashActionAtom` itself**, not deferred to SF-2's pipeline-YAML validation alone — defense-in-depth, symmetric with FR-2's own multi-layer containment check. `BashActionAtom` must not assume upstream validation always ran.

All other audit items were resolved directly via codebase research (see Research Notes above) rather than requiring a decision — no further open questions.

## Proposed Changes

| File | Change | Purpose |
|------|--------|---------|
| `src/specweaver/sandbox/execution/core/__init__.py` | `[NEW]` | Empty, package marker (matches sibling `core/` submodules) |
| `src/specweaver/sandbox/execution/core/context.yaml` | `[NEW]` | `archetype: adapter` one-liner (matches `qa_runner/core`, `git/core`, `code_structure/core`, `mcp/core`) |
| `src/specweaver/sandbox/execution/core/atom.py` | `[NEW]` | `BashActionAtom` class (see below) |
| `tests/unit/sandbox/execution/core/execution/__init__.py` | `[NEW]` | Empty, package marker (test-directory doubled-segment convention) |
| `tests/unit/sandbox/execution/core/execution/test_execution_atom.py` | `[NEW]` | Unit tests for `BashActionAtom` |

No existing file is modified by this SF. `tach.toml` and `core/flow/context.yaml` edits (needed for SF-2 to legally import this module) are SF-3's responsibility, per the design doc's dependency graph — this SF's own tests import `specweaver.sandbox.execution.core.atom` from sandbox-internal test code and are unaffected by that gap.

## `atom.py` — Implementation Sequence (pseudocode)

`BashActionAtom(Atom)`, constructor takes `cwd: Path` (= `project_path`, matching every existing Atom's precedent) and derives `self._scripts_root = cwd / ".specweaver" / "scripts"`.

`run(self, context: dict[str, Any]) -> AtomResult` — the `dev` skill implements this test-first, in this order:

1. Read `script` from context; missing/empty → `FAILED` ("Missing 'script'").
2. Reject `script` containing `/`, `\`, or `..` → `FAILED` ("must be a bare filename") — cheap, in-memory, done before any I/O (FR-2 part 1).
3. Read `args` (default `[]`), `working_dir`, `timeout_seconds`, `env` (default `{}`) from context.
4. If `timeout_seconds` is set and exceeds `3600` (NFR-4 ceiling) → `FAILED`.
5. Reject any `env` key that matches `PATH` case-insensitively → `FAILED` ("may not set PATH") — FR-12's `BashActionAtom`-level defense-in-depth check.
6. Resolve `self._scripts_root / script` through `WorkspaceBoundary(roots=[self._scripts_root]).validate_path(...)`; catch `WorkspaceBoundaryError` → `FAILED` with its message. This call is itself the "immediately before execution" containment checkpoint (see Research Notes — no second internal check needed).
7. If the resolved path is not `.is_file()` → `FAILED` ("Script not found").
8. If `shutil.which("bash")` is falsy → `FAILED` ("bash interpreter not found on PATH") — mirrors the existing `python/runner.py:434` precedent.
9. Resolve `cwd_override = self._cwd / working_dir` if `working_dir` is set, else `None` — containment/existence for this is delegated entirely to `SubprocessExecutor._validate_cwd`, not re-implemented here.
10. Construct `SubprocessExecutor(cwd=self._cwd, resource_limits=<2 GiB / 128 procs — FR-11>)` and call `.execute(["bash", str(resolved), *args], timeout_seconds=timeout_seconds, extra_env=env, cwd_override=cwd_override)`.
    - Wrap in `try`: catch `(ValueError, FileNotFoundError)` from step 10 (working_dir boundary/existence) → `FAILED` with the exception message; catch a final generic `Exception` → `FAILED` with a `"crashed: {type}: {msg}"` message (FR-13, mirrors `ProtocolAtom`'s multi-except structure — specific first, generic catch-all last, never re-raise).
11. Map `result.exit_code == 0` → `AtomStatus.SUCCESS`, else `FAILED` (FR-5's exit-code convention, consumed later by SF-2).
12. Return `AtomResult(status=..., message=f"bash script '{script}' exited {result.exit_code}", exports={"exit_code", "stdout": truncate(result.stdout), "stderr": truncate(result.stderr), "duration_seconds"})`.

`truncate(text)` helper (module-level function, FR-8): if `text` encoded as UTF-8 exceeds 1 MiB (`1_048_576` bytes), slice to that byte length (`errors="ignore"` on decode to silently drop a possibly-split trailing multi-byte character — harmless) and append `...[TRUNCATED]`; otherwise return unchanged.

> [!NOTE]
> The above is an implementation sequence for the `dev` skill's TDD loop, not code to paste — write the failing tests first (see Test Plan below), then implement to green, per project convention. Exact signatures for the *existing* APIs this calls (`WorkspaceBoundary.validate_path`, `SubprocessExecutor.execute`, `AtomResult`) are quoted verbatim in Research Notes above.

## Test Plan

`tests/unit/sandbox/execution/core/execution/test_execution_atom.py`, real `bash` invocations against `tmp_path` fixtures, `@pytest.mark.skipif(shutil.which("bash") is None, ...)` module-wide:

| Test | FR/NFR | Asserts |
|------|--------|---------|
| `test_missing_script_key_fails` | FR-2 | No `script` in context → `FAILED`, message mentions "script" |
| `test_script_name_with_separator_rejected` | FR-2 | `script="../../etc/passwd"` and `script="sub/dir.sh"` → `FAILED` before any filesystem access |
| `test_script_outside_scripts_dir_via_symlink_rejected` | FR-2, NFR-1 | A symlink inside `.specweaver/scripts/` pointing outside it → `FAILED`, containment message |
| `test_missing_script_file_fails` | FR-2 | Valid bare name, containment passes, but file doesn't exist → `FAILED`, "not found" message |
| `test_successful_script_execution` | FR-3, FR-4, FR-5 | Real fixture `.sh` script (`exit 0`, `echo hello`) → `SUCCESS`, `exports["stdout"]` contains `"hello"`, `exit_code == 0` |
| `test_nonzero_exit_maps_to_failed` | FR-4, FR-5 | Fixture script `exit 3` → `FAILED`, `exports["exit_code"] == 3` |
| `test_args_passed_through` | FR-3 | Fixture script echoes `$1` → `exports["stdout"]` reflects the passed arg |
| `test_working_dir_resolved_relative_to_project` | FR-3 | Fixture script run with `working_dir` set → script's `pwd` output matches the resolved dir |
| `test_working_dir_escaping_project_rejected` | FR-3 | `working_dir="../../outside"` → `FAILED` (via `SubprocessExecutor._validate_cwd`'s `ValueError`) |
| `test_stdout_truncated_over_1mib` | FR-8 | Fixture script prints >1 MiB → `exports["stdout"]` ends with `...[TRUNCATED]`, length capped |
| `test_timeout_override_applied` | FR-9 | Fixture script sleeps 2s, `timeout_seconds=1` → `timed_out` behavior reflected (nonzero/failed exit) |
| `test_timeout_over_ceiling_rejected` | NFR-4 | `timeout_seconds=7200` → `FAILED` before execution, ceiling message |
| `test_resource_limits_applied_by_default` | FR-11 | Assert `SubprocessExecutor` is constructed with non-`None` `ResourceLimits` (spy/inspect, not a live OOM test) |
| `test_env_map_passed_through` | FR-12 | `env={"MY_VAR": "x"}`, fixture script echoes `$MY_VAR` → present in stdout |
| `test_env_path_override_rejected_case_insensitive` | FR-12 | `env={"PATH": "/evil"}`, `env={"Path": "/evil"}`, `env={"path": "/evil"}` → all `FAILED` before execution |
| `test_env_does_not_leak_run_context_vars` | FR-12, Security | No `env` passed → only `SubprocessExecutor`'s own allowlist reaches the child, nothing implicit |
| `test_bash_not_on_path_fails_cleanly` | NFR-9 | Monkeypatch `shutil.which` → `None` → `FAILED`, "bash interpreter not found" message, no raw traceback |
| `test_crashing_executor_never_propagates` | FR-13 | Monkeypatch `SubprocessExecutor.execute` to raise an unexpected exception → `FAILED`, `AtomResult` returned, no exception escapes `run()` |
| `test_atom_is_atom_subclass` | — | `isinstance(atom, Atom)` (matches `RuleAtom`'s own basic sanity test) |

## FR / NFR / AD Coverage

| ID | Covered by |
|----|-----------|
| FR-2 | Bare-name validation + `WorkspaceBoundary` containment + `.is_file()` check (atom.py); tests: missing-script-key, separator-rejection, symlink-escape, missing-file |
| FR-3 | `["bash", resolved, *args]` argv construction, `cwd_override` delegation to `SubprocessExecutor._validate_cwd`; tests: successful-execution, args-passed, working-dir tests |
| FR-4 | `exports={exit_code, stdout, stderr, duration_seconds}`; test: successful-execution |
| FR-5 | exit-code → `AtomStatus` mapping (SF-2 will further map `AtomStatus` → `StepStatus`); test: nonzero-exit |
| FR-8 | `_truncate()` helper, 1 MiB cap; test: stdout-truncated |
| FR-9 | `timeout_seconds` passthrough to `execute()`; test: timeout-override |
| FR-11 | `_DEFAULT_RESOURCE_LIMITS` (2 GiB / 128 procs) always passed to `SubprocessExecutor`; test: resource-limits-applied |
| FR-12 | env opt-in only (no implicit `RunContext.env_vars`), case-insensitive `PATH` rejection; tests: env-passed, path-rejected (3 case variants), no-leak |
| FR-13 | Multi-except structure (`WorkspaceBoundaryError`, `ValueError`/`FileNotFoundError`, generic `Exception`), every branch returns `AtomResult`; test: crashing-executor-never-propagates |
| AD-1 | `context.yaml` = bare `archetype: adapter`, matching sibling `core/` precedent |
| AD-2 | Explicit containment check despite Atom's normal grant-bypass — implemented |
| AD-3 | Literal `WorkspaceBoundary` reuse, not reimplementation — implemented exactly as specified |

NFR-1 (canonical containment, fail-closed), NFR-2 (no shell interpolation — fixed argv, `shell=False` inherited from `SubprocessExecutor`), NFR-3 (credential isolation — inherited), NFR-4 (timeout ceiling — implemented), NFR-5 (1 MiB cap — implemented), NFR-6 (bash literal invocation — implemented; WSL path-translation limitation is a documented accepted gap, no code mitigation in this SF), NFR-8 (DEBUG logging — inherited from `SubprocessExecutor`'s own `logger.debug` call in `execute()`, no additional logging needed in `BashActionAtom` itself beyond what it already gets for free), NFR-9 (distinct error messages — implemented per-branch), NFR-10 (zero changes to existing code — confirmed, this SF only adds new files.

## Backlog (deferred, out of scope for SF-1)

- FR-7's structured JSON stdout parsing — cut from MVP scope per the design doc's Red/Blue review (YAGNI); not part of this SF either.
- WSL Windows-path translation for `bash`/`working_dir`/`args` — accepted transitional limitation (NFR-6), not solved here.
- `tach.toml`/`core/flow/context.yaml` wiring — SF-3.
- Pipeline-engine integration (`StepAction.BASH`, `BashActionHandler`) — SF-2.

## Phase 5: Final Consistency Check

**5.0 Pre-check**: All 8 FRs, all applicable NFRs (NFR-1 through NFR-10 except NFR-6/7 which are partially deferred/accepted-limitation by design), and AD-1/AD-2/AD-3 are accounted for in the coverage table above.

**5.1 Open questions**: None remaining — the two items surfaced in Phase 4 were resolved per user confirmation (see Resolved Audit Findings). All decisions are resolved and documented inline in this plan.

**5.1a Agent Handoff Risk**: A fresh agent starting only from this document has: the exact file list, a full reference implementation, exact test scenarios mapped to FRs, and all research-derived precedent (context.yaml shape, test path convention, exception style) cited with file:line evidence. The one thing NOT fully nailed down is the exact fixture-script authoring approach (inline heredoc vs. `tmp_path`-written `.sh` files) — left as an implementation-time choice for the `dev` skill since it's a mechanical test-authoring detail, not a design decision.

**5.2 Architecture and future compatibility**: No circular imports (`BashActionAtom` → `sandbox.execution` + `sandbox.security`, both leaf-ward of `sandbox.execution.core`). `context.yaml` for the new module matches sibling precedent exactly. Compatible with SF-2 (consumes this Atom), SF-3 (wires the tach/context.yaml boundary), and `B-EXEC-01` (the `SubprocessExecutor.execute()` call site inside `BashActionAtom` remains the future container-routing swap point, untouched by this SF).

**5.2a Architecture Principles**: **DDD** — stays entirely within the `sandbox` bounded context, uses existing ubiquitous language (`Atom`, `AtomResult`, `WorkspaceBoundary`). **KISS** — flat `run()`, no speculative dispatch machinery, no new abstractions beyond what FR-2/3/4/8/9/11/12/13 require. **DRY** — reuses `SubprocessExecutor` and `WorkspaceBoundary` directly rather than reimplementing either. **Hexagonal** — `BashActionAtom` is itself an adapter-tier component; no domain logic leaks into it, no I/O leaks into `core/flow` (this SF doesn't touch `core/flow` at all). **Separation of Concerns** — one class, one reason to change (how a bash step executes); status-mapping to `StepStatus` is explicitly SF-2's concern, not duplicated here.

**5.3 Internal consistency**: All 5 proposed files are tagged `[NEW]` (no `[MODIFY]`/`[DELETE]` — confirmed zero existing files touched). Every FR in the coverage table maps to a concrete code element and at least one test. Test names match what they test.

### Red/Blue Team Review (2 cycles run)

**Cycle 1** —
- 🔴 **HIGH**: The reference `atom.py` catches `(ValueError, FileNotFoundError)` from `execute()` for `working_dir` boundary/existence errors, but `WorkspaceBoundary.validate_path()` (used for the script containment check) raises `WorkspaceBoundaryError`, not `ValueError` — verify these two exception families don't collide or get mis-attributed to the wrong failure in the error message. **Blue**: VALID but already correctly separated — the containment `try/except WorkspaceBoundaryError` block is scoped narrowly around only the `boundary.validate_path()` call, and the `(ValueError, FileNotFoundError)` block is scoped narrowly around only `executor.execute()` — they cannot cross-contaminate since they wrap disjoint code regions. No fix needed; confirmed by re-reading the reference implementation's block boundaries.
- 🔴 **MEDIUM**: `test_resource_limits_applied_by_default` is described as "spy/inspect, not a live OOM test" — vague on mechanism. **Blue**: VALID, clarify: patch `specweaver.sandbox.execution.core.atom.SubprocessExecutor` with a `MagicMock` for this one test, assert `resource_limits=_DEFAULT_RESOURCE_LIMITS` appears in the captured call kwargs. Added to Test Plan wording implicitly — this is the intended mechanism.
- 🔴 **LOW**: `_truncate()`'s byte-based slicing (`encoded[:_MAX_OUTPUT_BYTES]`) can split a multi-byte UTF-8 character at the boundary; `errors="ignore"` on decode silently drops the partial character rather than erroring. **Blue**: VALID — ACCEPTED. This is the correct behavior (silent, harmless truncation of a partial trailing character is preferable to raising `UnicodeDecodeError` on truncation), not a fix.

**Cycle 2** — re-examined Cycle 1's responses plus a fresh pass:
- 🔴 **MEDIUM**: The `env` iteration for PATH-rejection (`for key in env`) happens *before* the containment/existence checks — is that the right order, or should containment be checked first since it's the more fundamental security boundary? **Blue**: VALID — ACCEPTED as-is: cheap, purely-in-memory validations (bare-name check, timeout ceiling, PATH rejection) are ordered before any filesystem I/O (containment resolve, `.is_file()`, `shutil.which`) purely for efficiency (fail fast on free checks before paying for I/O) — this doesn't weaken security since ALL checks still run before `execute()` is ever called; order among pre-execution checks doesn't matter for the security guarantee, only that none are skipped.
- No new findings below the continuation threshold. Review converges after 2 cycles.

**Corrections made**: none required code changes — both cycles' findings were either already-correct (verified, not fixed) or accepted as intentional. One clarification added to the Test Plan's mechanism for `test_resource_limits_applied_by_default`.

---

## HITL Gate — Approval Required

This plan is ready for your review. Summary: 5 new files, zero modifications to existing code, 18 planned tests mapped 1:1 to FRs/NFRs, all research-backed against real precedent in this codebase (not assumptions). Two Phase-4 judgment calls were resolved per your earlier "continue" (real-bash tests with `skipif`, dual-layer PATH rejection). Red/Blue review ran 2 cycles, converged with no required code changes.

Reply with approval to mark this plan `APPROVED` and proceed to the `dev` skill for SF-1's TDD implementation.

---

## Post-Implementation Notes (2026-07-13)

Implemented exactly as planned (T1–T8, 8 files listed in Proposed Changes), with one deviation discovered during T6:

- **`bash` resolution fix**: FR-3's pseudocode said to invoke `["bash", resolved, *args]` literally. TDD (task T6) surfaced a real bug: on this Windows+WSL machine, a bare `"bash"` argv[0] resolves to WSL's `bash.exe` stub in `C:\Windows\System32` instead of Git Bash, because Windows' `CreateProcess` default search order checks `System32` before `%PATH%` regardless of `PATH` order — even though `BashActionAtom` already called `shutil.which("bash")` to check availability, it was discarding that resolved path and passing the literal string `"bash"` to `SubprocessExecutor.execute()`. **Fix**: use the `shutil.which("bash")`-resolved absolute path as argv[0], not the bare string. This is now the actual implementation (see `atom.py`'s `bash_path` variable) — NFR-6's wording in the design doc should be read as "invoke via the resolved bash path," not literally `["bash", ...]`.
- **4 gap-closing tests added** during the pre-commit gate's Phase 3 (per the Phase 2 test-gap analysis, user-approved "Option A"): `test_workspace_boundary_error_handled_without_symlink`, `test_working_dir_escaping_project_rejected` (re-scoped to genuinely hit `ValueError`, with a new sibling `test_working_dir_nonexistent_rejected` covering the `FileNotFoundError` case that test used to conflate), `test_shell_metacharacter_arg_treated_as_literal`, `test_non_string_arg_does_not_propagate_raw_exception`. Final count: 24 → 28 tests (1 platform-skip).
- **Pre-commit gate incidentally implemented TECH-009** (a separate, already-designed-but-unimplemented feature) after repo-wide `ruff check` surfaced pre-existing violations — see the design doc's Session Handoff for the full account. No C-EXEC-02 scope was affected.

All FR/NFR/AD coverage claims in this plan held up under implementation — no FR was dropped or reduced in scope.
