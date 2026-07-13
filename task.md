# Task List: C-EXEC-02 SF-1 — BashActionAtom Core Execution

- **Implementation Plan**: docs/roadmap/features/topic_06_sandbox/C-EXEC-02/C-EXEC-02_sf1_implementation_plan.md
- **Commit boundaries**: 1 (small, cohesive single-class feature — 5 new files, no existing files touched)

## Adversarial Test Matrix

| Bucket | Covered by |
|--------|-----------|
| **Happy Path** | `test_successful_script_execution`, `test_args_passed_through`, `test_working_dir_resolved_relative_to_project`, `test_env_map_passed_through` |
| **Boundary/Edge Cases** | `test_stdout_truncated_over_1mib`, `test_timeout_over_ceiling_rejected`, `test_timeout_override_applied`, `test_nonzero_exit_maps_to_failed` |
| **Graceful Degradation** | `test_bash_not_on_path_fails_cleanly`, `test_crashing_executor_never_propagates`, `test_missing_script_file_fails` |
| **Hostile/Wrong Input** | `test_script_name_with_separator_rejected`, `test_script_outside_scripts_dir_via_symlink_rejected`, `test_working_dir_escaping_project_rejected`, `test_env_path_override_rejected_case_insensitive`, `test_missing_script_key_fails` |

All 4 buckets covered — no bucket is empty, no justification needed.

## Tasks (single commit boundary)

- [x] **T1 — Scaffolding**: Create `src/specweaver/sandbox/execution/core/__init__.py` (empty), `src/specweaver/sandbox/execution/core/context.yaml` (`archetype: adapter`), `tests/unit/sandbox/execution/core/execution/__init__.py` (empty). No TDD cycle — no behavior to test.
- [x] **T2 — `_truncate()` helper** (FR-8): Red → Green → Refactor. Tests: under-limit passthrough, exactly-at-limit, over-limit truncation + marker, multi-byte UTF-8 char at the boundary doesn't raise.
- [x] **T3 — Construction + cheap input validation** (FR-2 part 1, FR-12, NFR-4): `BashActionAtom.__init__`, then `run()`'s in-memory checks only (missing `script`, separator/`..` rejection, timeout ceiling, case-insensitive `PATH` rejection in `env`). Tests: `test_atom_is_atom_subclass`, `test_missing_script_key_fails`, `test_script_name_with_separator_rejected`, `test_timeout_over_ceiling_rejected`, `test_env_path_override_rejected_case_insensitive`.
- [x] **T4 — Containment + existence** (FR-2 part 2, AD-2, AD-3): `WorkspaceBoundary` integration, `.is_file()` check. Tests: `test_script_outside_scripts_dir_via_symlink_rejected`, `test_missing_script_file_fails`.
- [x] **T5 — `bash` availability check** (NFR-9): `shutil.which("bash")` pre-check. Test: `test_bash_not_on_path_fails_cleanly`.
- [x] **T6 — Happy-path execution** (FR-3, FR-4, FR-5, FR-11): argv construction, `working_dir` → `cwd_override`, `SubprocessExecutor` construction with default `ResourceLimits`, exit-code → `AtomStatus` mapping. Tests: `test_successful_script_execution`, `test_nonzero_exit_maps_to_failed`, `test_args_passed_through`, `test_working_dir_resolved_relative_to_project`, `test_working_dir_escaping_project_rejected`, `test_resource_limits_applied_by_default`.
  - **Real bug found + fixed during TDD**: `SubprocessExecutor.execute(["bash", ...])` with the bare string `"bash"` resolved to WSL's `bash.exe` stub in `C:\Windows\System32` instead of Git Bash, because Windows' `CreateProcess` default search order checks `System32` before `%PATH%` regardless of PATH order. Fixed by resolving `shutil.which("bash")` once and using the returned absolute path as argv[0] instead of the literal string `"bash"`. See design/impl-plan correction note below.
- [x] **T7 — Output truncation + env passthrough integration** (FR-8, FR-12): wire `_truncate()` into `exports`, confirm `env` reaches the child, confirm no implicit `RunContext`-style leakage. Tests: `test_stdout_truncated_over_1mib`, `test_env_map_passed_through`, `test_env_does_not_leak_run_context_vars`.
- [x] **T8 — Timeout override + exception containment** (FR-9, FR-13): `timeout_seconds` passthrough; multi-except structure (`WorkspaceBoundaryError`, `(ValueError, FileNotFoundError)`, generic `Exception`) — never propagate. Tests: `test_timeout_override_applied`, `test_crashing_executor_never_propagates`.

**Refactor**: extracted `_validate_cheap()` helper to bring `run()` under the C901 complexity limit (was 11, limit 10). Ruff + mypy clean.

## Commit Boundary 1 (after T1–T8)

- [x] Run full project test suite (unit + integration + e2e) — zero regressions (4511 unit + 424 integration + 139 e2e, all passed).
- [/] Pre-commit quality gate (`.agents/skills/specweaver-pre-commit/SKILL.md`):
  - [x] Phase 1 — Architecture verification: no violations, `tach check` clean.
  - [x] Phase 2 — Test gap analysis: 2 genuine gaps + 2 hardening stories found, presented via artifact, user approved "Option A" (implement all 4).
  - [x] Phase 3 — Implemented all 4 gap-closing tests (`test_workspace_boundary_error_handled_without_symlink`, `test_working_dir_escaping_project_rejected` re-scoped + new `test_working_dir_nonexistent_rejected`, `test_shell_metacharacter_arg_treated_as_literal`, `test_non_string_arg_does_not_propagate_raw_exception`). 28 passed, 1 skipped (symlink/admin), ruff clean.
  - [ ] Phase 4 — Re-run full test suite.
  - [ ] Phase 5 — Code quality checks (ruff, mypy, complexity, file size).
  - [ ] Phase 6 — Documentation updates.
  - [ ] Phase 7 — Walkthrough artifact.
  - [ ] Phase 7.5 — Red/Blue adversarial review of code changes.
- [ ] **STOP — HITL commit gate.** Wait for explicit user commit/proceed.
- [ ] After commit: update Design Doc Progress Tracker (`Dev ✅`, `Pre-Commit ✅`, `Committed ✅` for SF-1) and Session Handoff.
