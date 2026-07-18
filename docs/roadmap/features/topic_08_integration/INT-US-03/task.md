# Task List — INT-US-03 SF-01: Generation → QA Test Loop

- **Impl Plan**: docs/roadmap/features/topic_08_integration/INT-US-03/INT-US-03_sf01_implementation_plan.md
- **FRs**: FR-1 (run_tests), FR-3 (validate_code), FR-4 (targets), FR-6 (loop-back), FR-7 (report+exit)
- **Commit boundaries**: single boundary **CB-1** (cohesive integration; T1 is a backward-compatible prerequisite for T2). Tasks ordered foundation-first.

## Tasks

- [x] **T1 — `ValidateCodeHandler` honors `params["target"]`** (FR-3, FR-4)
  - src: `src/specweaver/core/flow/handlers/validation.py` (`ValidateCodeHandler._find_code_path`)
  - test: `tests/unit/core/flow/handlers/test_validate_code_find_path.py`
  - Behavior: if `step.params.get("target")` → resolve vs `context.project_path`, return if `.exists()`; else fall back to existing `output_dir.glob("*.py")[0]`. No signature change.

- [x] **T2 — Extract + build the extended `implement_spec` pipeline** (FR-1, FR-3, FR-4, FR-6) — coverage_threshold uses handler default (70); `ValidationSettings` has no direct field (Q4 refinement, documented).
  - src: `src/specweaver/workflows/implementation/interfaces/cli.py` — extract a private helper `_build_implement_pipeline(stem, settings)` returning the 4-step pipeline (generate_code, generate_tests, run_tests, validate_code) with gates/params; call it from `implement()`.
  - test: `tests/unit/workflows/implementation/test_implement_pipeline.py` — assert step names/order, `run_tests` loop-back gate (`loop_target="generate_code"`, `max_retries=2`, `condition=ALL_PASSED`), `validate_code` gate `on_fail=CONTINUE`, targets `tests/test_<stem>.py` / `src/<stem>.py`, `coverage=True` + threshold from settings (fallback 70).

- [x] **T3 — Inline QA reporting + QA-aware exit code** (FR-7)
  - src: `cli.py` — rewrite the post-run `step_records` loop; print run_tests (pass/fail/coverage) + validate_code (pass/fail + failed rule_ids); exit 1 iff final status != completed OR run_tests failed after retries; validate_code failure is report-only (never forces exit 1).
  - test: `tests/integration/interfaces/cli/test_cli_implement.py` — new cases with `QARunnerAtom` stubbed (patch `specweaver.sandbox.qa_runner.core.atom.QARunnerAtom`; also stub `ValidateCodeHandler` execution to avoid the heavy validation sub-pipeline): (happy) tests pass → exit 0 + report; (degradation) run_tests fails after retries → exit 1; (report-only) validate_code fails but run passes → exit 0, failure reported.
  - ⚠️ **Red/Blue mechanic to verify in-test:** confirm `OnFailAction.CONTINUE` on `validate_code` leaves the run status `completed` even when that step FAILED. If the runner marks the run failed anyway, the exit-code logic must explicitly key off `run_tests`' result, not just `run_state.status`.

- [x] **T4 — Update existing implement tests to the QA-aware world** (backward-compat, NFR-2)
  - test: `test_cli_implement.py` — `test_implement_generates_files`, `test_implement_spec_suffix_removal`, `test_full_pipeline`: stub `QARunnerAtom` (and `validate_code`) so they assert files created + "Implementation complete" without running real pytest. **`test_full_pipeline` is mandatory** (its mock returns identical text for code+tests → generated "test" collects 0 → would fail QA).

- [ ] **T5 — Full suite + pre-commit gate (CB-1)**
  - Run full `tests/unit`, `tests/integration`, `tests/e2e`; fix any regression project-wide.
  - Run the pre-commit skill (all phases). Then HITL commit stop.

## Adversarial Test Matrix (per task — 4 buckets)

| Task | Happy | Boundary/Edge | Graceful Degradation | Hostile/Wrong Input |
|------|-------|---------------|----------------------|---------------------|
| T1 | `target` set & file exists → returns it | `target` missing → falls back to glob; empty `output_dir` | `target` points at nonexistent file → None (→ "no code file" path) | `../` path-traversal string → not resolved outside project |
| T2 | 4 steps built w/ correct gates/params | odd/nested stem → correct relative targets | settings without `validation.coverage_threshold` → fallback 70 | `None`/empty stem guarded |
| T3 | pass → exit 0 + report | validate_code fail only → exit 0, reported | run_tests fail ×N → loop-back exhausted → exit 1 | malformed/empty QA `output` dict → report degrades, no crash |
| T4 | existing asserts still pass w/ stub | suffix-strip case | — (stubbed) | — (stubbed) |

## Progress
- T1–T4 complete (TDD red→green→refactor, lint clean).
- mypy (changed files): ✅  ·  tach: ✅
- Full unit suite: ✅ 4669 passed, 15 skipped
- Full integration suite: ✅ 449 passed, 5 skipped
- Full e2e suite: 5 regressions found & fixed (implement now runs real QA → mock-generated tests collect 0 → exit 1). Added opt-in `stub_implement_qa` fixture in `tests/e2e/conftest.py`; applied to 5 `sw implement`-based tests (lineage, lifecycle×3, constitution). Re-running full e2e to confirm green.
- Full e2e suite (after fix): ✅ 144 passed, 1 skipped
- Pre-commit skill: _running_
  - Phase 1 (architecture): ✅ no violations (tach ✅, mypy ✅)
  - Phase 2 (test gap): ✅ combined findings presented; 4 unit gaps approved
  - Phase 3 (implement tests): ✅ 8 new unit edge-case tests (coverage-None, coverage-0, malformed/None output, failed-rule listing, elif-not-passed fallback, unknown-passed skip, target+no-project_path, empty-target) — 15 pass, lint clean
  - Phase 4 (full suite): ✅ unit 4677, integration 449, e2e 144 (grand total 5270). 1 pre-existing SQLite-lock flake in graph/lineage (`test_log_artifact_event_concurrent_writes`) — passes in isolation, untouched module, NOT caused by SF-01.
  - Phase 5 (code quality): ✅ ruff, C901, tach, mypy (303 files) all clean; changed files within size limits. Pre-existing RED: `core/flow/engine/runner.py` (606>600) — untouched by SF-01, flagged for user (risky out-of-scope split).
  - Phase 6 (docs): ✅ impl plan Implementation Notes added; master_story_roadmap noted (US-3 stays 🟡, box `[ ]` until SF-03 e2e proof). No arch/guide/README change (CLI surface unchanged, no new pattern).
  - Phase 7 (walkthrough): ✅ `INT-US-03_sf01_walkthrough.md` written
  - Phase 7.5 (Red/Blue on code): ✅ no critical findings (2 minor unreachable/internal notes)
  - **Inherited fixes (per user directive):**
    - runner.py 606→592 (moved `resolve_should_isolate` to runner_utils, re-exported) — file-size gate 0 errors; 750 flow tests pass.
    - lineage SQLite flake fixed (WAL set once at construction + busy_timeout 30s) — 0/20 stress failures; `test_busy_timeout_set` updated.
    - CLAUDE.md convention: commit direct to master, no feature branches.
    - Re-running full suite to confirm project-wide green.
  - Phase 8 (commit boundary): ⏸ HITL — awaiting user commit (direct to master)
