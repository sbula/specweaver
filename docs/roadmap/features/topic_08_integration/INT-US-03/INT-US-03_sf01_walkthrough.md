# Walkthrough — INT-US-03 SF-01: Generation → QA Test Loop

**Commit boundary:** CB-1 (single) · **Date:** 2026-07-18

## What changed and why

`sw implement` previously stopped after writing `src/<stem>.py` + `tests/test_<stem>.py` and told the
user to run `sw check` manually. SF-01 makes it autonomous: the `implement_spec` pipeline now pipes
generation into QA — it runs the generated tests and validates the code (C01–C08) in one loop, and
reports the outcome inline. This closes the first clause of the US-3 base contract ("generate the code,
write the tests, run them").

### Source changes (2 files)
- **`workflows/implementation/interfaces/cli.py`**
  - `_build_implement_pipeline(stem)` — extracted builder; appends `run_tests` (`VALIDATE`/`TESTS`,
    `coverage=True`, loop-back gate → `generate_code`, `max_retries=2`) and `validate_code`
    (`VALIDATE`/`CODE`, `CONTINUE` gate = report-only) to the existing 2 generate steps. QA steps target
    `tests/test_<stem>.py` / `src/<stem>.py` and leave `use_worktree` unset (SF-03 threads isolation).
  - `_report_implementation(run_state)` — inline QA report (tests pass/fail + coverage, code-validation
    rules + failed rule ids). Stale "run sw check manually" message removed.
  - QA-aware exit: `run_state.status != "completed"` → exit 1 (covers `run_tests` loop-back exhaustion);
    `validate_code` failure is report-only (does not fail the command).
- **`core/flow/handlers/validation.py`**
  - `ValidateCodeHandler._find_code_path` now honors an explicit `params["target"]` (resolved against
    `project_path`, with a path-traversal guard), falling back to the legacy `output_dir` glob when no
    target is set. Backward-compatible (no current caller sets `target` on a validate/code step).

### Test changes
- `tests/unit/core/flow/handlers/test_validate_code_find_path.py` (new, 8)
- `tests/unit/workflows/implementation/test_implement_pipeline.py` (new, 7)
- `tests/unit/workflows/implementation/test_implement_reporting.py` (new, 7)
- `tests/integration/interfaces/cli/test_cli_implement.py` (+3 new QA-loop cases; 3 existing stubbed)
- `tests/e2e/conftest.py` — new opt-in `stub_implement_qa` fixture; applied to 5 pre-existing
  `sw implement` e2e tests (they exercise other behavior; real QA proof is SF-03).

## Verification results

| Check | Result |
|-------|--------|
| Unit | **4677 passed**, 15 skipped (+ 1 pre-existing SQLite-lock flake, passes in isolation) |
| Integration | **449 passed**, 5 skipped |
| E2E | **144 passed**, 1 skipped |
| **Grand total** | **5270 passed** |
| ruff (`src/ tests/`) | ✅ clean |
| mypy (`src/`) | ✅ no issues (303 files) |
| complexity (C901) | ✅ clean |
| tach | ✅ all modules validated |
| file size | changed files OK (cli 245, validation 477); 1 pre-existing RED `runner.py` 606>600 (untouched) |

## HITL gate decisions

- **Design Phase 6 (approval):** APPROVED by Steve Bula (2026-07-17). AD-5/6/7 resolved "yes"
  (force isolation on for implement; fix the `D-EXEC-01` prose defect; adopt the generate-step-isolation
  + `allowed_paths` approach for SF-03).
- **Impl-plan Phase 4 (audit findings):** Q1–Q6 all resolved to option (a) — incl. the cross-module
  `ValidateCodeHandler` enhancement (Q1), report-only `validate_code` gate (Q2), QA-aware exit (Q3).
- **Impl-plan Phase 5 (consistency):** APPROVED; Red/Blue correction merged (`test_full_pipeline` update).
- **Dev Phase 2 (task list):** APPROVED — single commit boundary CB-1, foundation-first.
- **Pre-commit Phase 1–2 (architecture + test gap):** presented combined; no architecture violations;
  4 unit gaps approved.
- **Pre-commit Phase 3 (implement tests):** user challenged edge-case completeness → 3 additional edge
  cases added (coverage-0 boundary, the `elif not passed` fallback branch, empty-string target). 15 unit
  tests total; approved.
- **Pre-commit Phase 4:** noted 1 pre-existing SQLite-lock flake (unrelated module, passes in isolation)
  transparently rather than papering over it.

## Inherited issues — FIXED (per user direction: fix regardless of origin)
1. **`core/flow/engine/runner.py` file size (606 > 600, RED gate):** moved the pure `resolve_should_isolate`
   helper to its natural home `runner_utils.py` and re-exported it (keeps the test import working).
   runner.py is now **592 lines → file-size gate: 0 errors**. Verified: 750 flow-engine/handler/integration
   tests pass; mypy + tach + ruff clean.
2. **`test_log_artifact_event_concurrent_writes` SQLite flake:** root cause was per-connection
   `PRAGMA journal_mode=WAL` — switching *to* WAL needs an exclusive lock and SQLite doesn't reliably fire
   the busy handler for the mode switch, so 20 concurrent writers raced. Fix: set WAL **once** at
   construction (`_ensure_wal`, single-threaded; WAL is persistent) and raise `busy_timeout` to 30s; per
   connection no longer switches mode → only INSERT contention remains (handled by the timeout). Verified
   **0 failures in 20 stress runs** (was ~2/15). Updated `test_busy_timeout_set` (5000→30000).

## Repo convention change
`CLAUDE.md` updated: commit **directly to `main`** — no feature branches (per user directive).

## Scope boundaries
SF-01 runs QA in **host mode** and does not thread the US-9 worktree isolation (SF-03) or add the
`lint_fix` step (SF-02). Podman/containers are out of scope for the entire feature. Real worktree-bounded
execution is proven by SF-03's verifiable-proof e2e — so the US-3 base-contract box stays `[ ]`.
