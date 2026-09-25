# INT-US-03 SF-02 — Walkthrough

**Commit boundary:** CB-1 (single) · **Date:** 2026-07-18 · Plan:
[sf02](INT-US-03_sf02_implementation_plan.md)

## Delivered

The `lint_fix` step (ruff auto-fix + LLM reflection loop) in the `sw implement` pipeline — the
contract's "…and auto-fix linting errors." Placed **before `run_tests`** so tests + C01–C08 validate
the lint-fixed code; report-only (`CONTINUE` gate) so lint problems never abort the run.

| File | Change |
|---|---|
| `workflows/implementation/interfaces/cli.py` | `_build_implement_pipeline` yields `[generate_code, generate_tests, lint_fix, run_tests, validate_code]`; `lint_fix` params `{target: src/<stem>.py, max_reflections: 3}`, gate `CONTINUE`. `_report_implementation` gained a `lint_fix` branch (auto_fixed / reflections_used / lint_errors_remaining) |
| `core/flow/handlers/lint_fix.py` | `_find_code_files(context, target)` honors the generated target (traversal-guarded) so Phase-2 reflection finds the file when `output_dir` is unset; a directory or missing target falls back to the legacy glob |

Scope: host mode (isolation is SF-03); Podman out of scope. Real lint execution in a sandbox is
SF-03's proof — the US-3 base-contract box stayed `[ ]` until then.

## Proof

| Test | Cases |
|---|---|
| `tests/unit/core/flow/handlers/test_lint_fix_find_code_files.py` (new) | 7 |
| `tests/unit/workflows/implementation/test_implement_pipeline.py` | +3: position/params/gate |
| `tests/unit/workflows/implementation/test_implement_reporting.py` | +3: lint report branch |
| `tests/integration/interfaces/cli/test_cli_implement.py` | +4 incl. graceful-failure; `_patch_qa` is one context manager stubbing all three QA handlers |
| `tests/e2e/conftest.py` | `stub_implement_qa` also stubs `LintFixHandler` |

Added on the user's graceful-failure challenge: lint_fix ERROR (LLM crash) absorbed by the CONTINUE
gate; lint+tests both fail → exit 1; `_find_code_files` project_path-falsy and missing-target
fallbacks. The CONTINUE gate absorbs `ERROR` as well as `FAILED`.

| Check | Result |
|-------|--------|
| Unit | **4690 passed**, 15 skipped |
| Integration | **453 passed**, 5 skipped |
| E2E | **144 passed**, 1 skipped |
| **Grand total** | **5287 passed, 0 failures** |
| ruff / mypy (303) / C901 / tach | ✅ all clean |
| file size | 0 errors (cli.py 263) |

Approvals: plan audit Q1–Q5 → (a), incl. the `_find_code_files` handler enhancement (Q1) and
`lint_fix` **before** `run_tests` (Q2); single CB-1.
