# Task List — INT-US-03 SF-02: Lint-Fix Reflection Loop Integration

- **Impl Plan**: docs/roadmap/features/topic_08_integration/INT-US-03/INT-US-03_sf02_implementation_plan.md
- **FR**: FR-2 (lint_fix step: ruff auto-fix + LLM reflection loop, inline report)
- **Commit boundary**: single **CB-1**. Foundation-first (T1 enables T2's LLM-reflection path).
- **(SF-01 task record preserved in git history + walkthrough.)**

## Tasks

- [x] **T1 — `LintFixHandler._find_code_files` honors an explicit target** (FR-2, Audit Q1)
  - src: `src/specweaver/core/flow/handlers/lint_fix.py` (`_find_code_files`, + caller in `execute`)
  - test: `tests/unit/core/flow/handlers/test_lint_fix_handler.py`
  - Behavior: `_find_code_files(context, target=None)` → if `target` resolves (vs `project_path`, inside it) to an existing file → `[file]`; else existing `output_dir.glob("*.py")`. Traversal-guarded. Caller in `execute` passes the resolved `target`.

- [x] **T2 — Insert `lint_fix` step before `run_tests`** (FR-2, Audit Q2/Q3)
  - src: `cli.py` `_build_implement_pipeline` → `[generate_code, generate_tests, lint_fix, run_tests, validate_code]`; `lint_fix` params `{target: src/<stem>.py, max_reflections: 3}`, gate `CONTINUE`.
  - test: `tests/unit/workflows/implementation/test_implement_pipeline.py` — step order/position, params, gate.

- [x] **T3 — Report `lint_fix` outcome** (extends FR-7)
  - src: `cli.py` `_report_implementation` → add `name == "lint_fix"` branch: auto_fixed / reflections_used / lint_errors_remaining (green when 0 remain, yellow otherwise; report-only).
  - test: `tests/unit/workflows/implementation/test_implement_reporting.py`.

- [x] **T4 — Integration + e2e fixtures: stub lint_fix in the loop** (FR-2)
  - test: `tests/integration/interfaces/cli/test_cli_implement.py` — extend `_patch_qa` to also stub `LintFixHandler.execute`; new cases: (happy) lint clean → reported, exit 0; (graceful) lint_fix FAILED (errors remain) → report-only, exit still governed by run_tests.
  - ⚠️ **e2e fixture (Red/Blue):** `tests/e2e/conftest.py` `stub_implement_qa` MUST also stub `LintFixHandler.execute` (else the 5 `sw implement` e2e tests break the same way SF-01's did — real lint on mock code + mock-LLM reflection). Verify in T5.

- [ ] **T5 — Full suite + pre-commit gate (CB-1)**
  - Full unit/integration/e2e; fix any regression project-wide. Run pre-commit skill. HITL commit stop (direct to master).

## Adversarial Test Matrix (per task — 4 buckets)

| Task | Happy | Boundary/Edge | Graceful Degradation | Hostile/Wrong Input |
|------|-------|---------------|----------------------|---------------------|
| T1 | target file exists → `[file]` | no target → output_dir glob (existing behavior kept) | target missing + no output_dir → `[]` (→ "no code files" FAIL path) | `../` traversal target → not resolved outside project |
| T2 | lint_fix present, correct position/params/gate | position: lint_fix index < run_tests index | — (pure builder) | odd/empty stem interpolation |
| T3 | auto_fixed clean → "0 remaining" | reflections used, N remaining → yellow | malformed/empty lint output → defaults, no crash | — |
| T4 | lint clean in loop → exit 0 | lint_fix FAILED → report-only, run continues | run_tests still governs exit | — |

## Progress
- T1–T4 complete (TDD, lint clean). mypy + tach clean on changed src (lint_fix.py, cli.py).
- Full suite: unit 4688 · integration 451 · e2e 144 (5283 passed, 0 failures).
- Pre-commit skill: _running_
  - Phase 1 (architecture): ✅ no violations (tach ✅)
  - Phase 2 (test gap): ✅ combined findings presented
  - Phase 3 (implement tests): ✅ 4 edge cases incl. graceful failure (project_path-falsy, missing-target glob fallback, lint_fix ERROR absorbed by CONTINUE gate, lint+tests both fail → exit 1) — 18 pass, lint clean
  - Phase 4 (full suite): ✅ unit 4690 · integration 453 · e2e 144 (5287 passed, 0 failures)
  - Phase 5 (code quality): ruff ✅ · C901 ✅ · size 0 errors (cli.py 263) · tach ✅ · mypy _running_
  - Phase 5 (code quality): ✅ ruff, C901, size (0 err), tach, mypy (303) all clean
  - Phase 6 (docs): ✅ SF-02 as-built notes + roadmap (US-3 stays 🟡)
  - Phase 7 (walkthrough): ✅ INT-US-03_sf02_walkthrough.md
  - Phase 7.5 (Red/Blue): ✅ no critical findings
  - Phase 8 (commit boundary): ⏸ HITL — awaiting user commit (direct to master)
