# Walkthrough — INT-US-03 SF-02: Lint-Fix Reflection Loop Integration

**Commit boundary:** CB-1 (single) · **Date:** 2026-07-18

## What changed and why
SF-02 adds the `lint_fix` step (ruff auto-fix + LLM reflection loop) to the `sw implement` pipeline SF-01
established, completing the contract's "…and auto-fix linting errors." Placed **before `run_tests`** so
tests + C01–C08 validate the lint-fixed code; report-only (`CONTINUE` gate) so lint problems never abort
the autonomous run.

### Source changes (2 files)
- **`workflows/implementation/interfaces/cli.py`** — `_build_implement_pipeline` now yields
  `[generate_code, generate_tests, lint_fix, run_tests, validate_code]`; `lint_fix` params
  `{target: src/<stem>.py, max_reflections: 3}`, gate `CONTINUE`. `_report_implementation` gained a
  `lint_fix` branch (auto_fixed / reflections_used / lint_errors_remaining).
- **`core/flow/handlers/lint_fix.py`** — `_find_code_files(context, target)` honors the explicit generated
  target (traversal-guarded) so the Phase-2 LLM reflection can locate the file when `output_dir` is unset;
  a directory or missing target falls back to the legacy glob.

### Test changes
- `tests/unit/core/flow/handlers/test_lint_fix_find_code_files.py` (new, 7)
- `tests/unit/workflows/implementation/test_implement_pipeline.py` (+3: position/params/gate)
- `tests/unit/workflows/implementation/test_implement_reporting.py` (+3: lint report branch)
- `tests/integration/interfaces/cli/test_cli_implement.py` (+4 incl. graceful-failure); `_patch_qa`
  refactored to a single context manager stubbing all three QA handlers
- `tests/e2e/conftest.py` — `stub_implement_qa` extended to stub `LintFixHandler`

## Verification results
| Check | Result |
|-------|--------|
| Unit | **4690 passed**, 15 skipped |
| Integration | **453 passed**, 5 skipped |
| E2E | **144 passed**, 1 skipped |
| **Grand total** | **5287 passed, 0 failures** |
| ruff / mypy (303) / C901 / tach | ✅ all clean |
| file size | 0 errors (cli.py 263) |

## HITL gate decisions
- **Impl-plan Phase 4 (audit):** Q1–Q5 all resolved to (a) — incl. the `_find_code_files` handler
  enhancement (Q1) and placing `lint_fix` **before** `run_tests` (Q2).
- **Dev Phase 2 (task list):** approved (single CB-1).
- **Pre-commit Phase 1–2 (arch + test gap):** no violations; combined findings presented.
- **Pre-commit Phase 3 (implement tests):** user challenged **graceful-failure** coverage → added: lint_fix
  ERROR (LLM crash) absorbed by the CONTINUE gate; lint+tests both fail → exit 1; `_find_code_files`
  project_path-falsy and missing-target fallbacks. Confirmed the CONTINUE gate absorbs `ERROR` as well as
  `FAILED`.

## Scope boundaries
Host mode (no worktree isolation — SF-03); Podman out of scope for the whole feature. Real lint execution
in a sandbox is proven by SF-03's verifiable-proof e2e — so the US-3 base-contract box stays `[ ]`.
