# INT-US-03 SF-01 — Walkthrough

**Commit boundary:** CB-1 (single) · **Date:** 2026-07-18 · Plan:
[sf01](INT-US-03_sf01_implementation_plan.md)

## Delivered

`sw implement` pipes generation into QA: it runs the generated tests and validates the code
(C01–C08) in one loop and reports inline. Closes the first clause of the US-3 base contract
("generate the code, write the tests, run them"). Replaces the old "run `sw check` manually" ending.

| File | Change |
|---|---|
| `workflows/implementation/interfaces/cli.py` | `_build_implement_pipeline(stem)` — extracted builder; appends `run_tests` (`VALIDATE`/`TESTS`, `coverage=True`, loop-back gate → `generate_code`, `max_retries=2`) and `validate_code` (`VALIDATE`/`CODE`, `CONTINUE` gate = report-only) to the 2 generate steps; targets `tests/test_<stem>.py` / `src/<stem>.py`; `use_worktree` unset. `_report_implementation(run_state)` — tests pass/fail + coverage, code-validation rules + failed rule ids. QA-aware exit: `run_state.status != "completed"` → exit 1 (covers `run_tests` loop-back exhaustion); `validate_code` failure is report-only |
| `core/flow/handlers/validation.py` | `ValidateCodeHandler._find_code_path` honors `params["target"]` (resolved against `project_path`, path-traversal guard), else the legacy `output_dir` glob. No current caller sets `target` on a validate/code step |

Also fixed, regardless of origin (user direction):

- **`core/flow/engine/runner.py` file size (606 > 600, RED gate):** the pure
  `resolve_should_isolate` helper moved to `runner_utils.py`, re-exported (keeps the test import).
  runner.py is **592 lines → file-size gate: 0 errors**. 750 flow-engine/handler/integration tests
  pass; mypy + tach + ruff clean.
- **`test_log_artifact_event_concurrent_writes` SQLite flake:** per-connection `PRAGMA
  journal_mode=WAL` — switching *to* WAL needs an exclusive lock and SQLite doesn't reliably fire the
  busy handler for the mode switch, so 20 concurrent writers raced. WAL is now set **once** at
  construction (`_ensure_wal`, single-threaded; WAL is persistent) and `busy_timeout` is 30s; only
  INSERT contention remains. **0 failures in 20 stress runs** (was ~2/15). `test_busy_timeout_set`
  updated (5000→30000).

Repo convention: `CLAUDE.md` now says commit **directly to `main`** — no feature branches.

Scope: **host mode**; no US-9 worktree isolation (SF-03), no `lint_fix` (SF-02), no Podman. Real
worktree-bounded execution is SF-03's proof; the US-3 base-contract box stayed `[ ]` until then.

## Proof

| Test | Cases |
|---|---|
| `tests/unit/core/flow/handlers/test_validate_code_find_path.py` (new) | 8 |
| `tests/unit/workflows/implementation/test_implement_pipeline.py` (new) | 7 |
| `tests/unit/workflows/implementation/test_implement_reporting.py` (new) | 7 |
| `tests/integration/interfaces/cli/test_cli_implement.py` | +3 new QA-loop cases; 3 existing stubbed |
| `tests/e2e/conftest.py` | new opt-in `stub_implement_qa` fixture, applied to 5 pre-existing `sw implement` e2e tests |

Pre-commit added 3 edge cases on the user's challenge: coverage-0 boundary, the `elif not passed`
fallback branch, empty-string target — 15 unit tests total.

| Check | Result |
|-------|--------|
| Unit | **4677 passed**, 15 skipped (+ 1 pre-existing SQLite-lock flake, passes in isolation — fixed above) |
| Integration | **449 passed**, 5 skipped |
| E2E | **144 passed**, 1 skipped |
| **Grand total** | **5270 passed** |
| ruff (`src/ tests/`) | ✅ clean |
| mypy (`src/`) | ✅ no issues (303 files) |
| complexity (C901) | ✅ clean |
| tach | ✅ all modules validated |
| file size | changed files OK (cli 245, validation 477) |

Approvals: design APPROVED by Steve Bula (2026-07-17), AD-5/6/7 "yes" (AD-5 and AD-7 later
superseded — see design); plan audit Q1–Q6 → (a); Red/Blue correction merged (`test_full_pipeline`);
4 unit gaps approved.

