# Task List: C-EXEC-02 SF-2 — Pipeline Engine Integration

- **Implementation Plan**: docs/roadmap/features/topic_06_sandbox/C-EXEC-02/C-EXEC-02_sf2_implementation_plan.md
- **Commit boundaries**: 1 (3 new files, 3 modified — confirmed zero engine changes needed for FR-6/FR-7, just tests proving it)

## Adversarial Test Matrix

| Bucket | Covered by |
|--------|-----------|
| **Happy Path** | `test_success_maps_to_passed`, `test_bash_step_runs_end_to_end`, `test_downstream_step_reads_step_records` |
| **Boundary/Edge Cases** | `test_missing_params_key_not_defaulted_by_handler` (empty `params`, handler doesn't paper over it) |
| **Graceful Degradation** | `test_failure_maps_to_failed` (nonzero exit → `StepStatus.FAILED`, not a crash) |
| **Hostile/Wrong Input** | N/A — justified: `BashActionAtom` (SF-1) already owns all hostile-input handling (path traversal, symlink escape, shell metacharacters, non-string args — all tested there). `BashActionHandler` is a thin, pass-through translation layer with no independent input-validation surface; duplicating those tests here would test the same code path twice, not find new bugs. |

## Tasks (single commit boundary)

- [x] **T1 — `StepAction.BASH`/`StepTarget.SCRIPT`/`VALID_STEP_COMBINATIONS`** (FR-1): Added the two enum values and the combination tuple to `core/flow/engine/models.py`. Also fixed 3 hardcoded count assertions in `test_models.py` (`test_action_count` 12→13, `test_target_count` 10→11, `test_combination_count` 20→21) that would have regressed. 75 tests pass.
- [x] **T2 — `BashActionHandler`** (FR-5): Red → Green → Refactor. New `core/flow/handlers/bash_action.py`, cloning `ValidateTestsHandler`'s exact shape (lazy `_get_atom`, `AtomStatus` → `StepStatus.PASSED`/`FAILED` mapping, `output=result.exports`). Registered in `handlers/registry.py`. 4 tests pass, ruff + mypy clean.
- [x] **T3 — Integration: end-to-end + `step_records` propagation** (FR-1, FR-6): New `tests/integration/core/flow/handlers/test_bash_action_integration.py`, real `PipelineRunner` + real `StepHandlerRegistry` + real script in `tmp_path/.specweaver/scripts/` (inline creation, matching SF-1's own test style — no separate fixture needed). Confirms zero engine changes were required. `test_bash_step_runs_end_to_end`, `test_downstream_step_reads_step_records` pass, ruff + mypy clean.
- [x] **T4 — Integration: router branching** (FR-7): Same test file. Bash step with a `router:` block keyed on `exit_code`, `gate=GateDefinition(on_fail=CONTINUE)` so a FAILED (nonzero exit) step still reaches the router. Each test places its target branch last in the pipeline so the router jump provably *skips* the other branch rather than both running sequentially. `test_router_branches_on_exit_code`, `test_router_branches_on_nonzero_exit` pass, ruff + mypy clean.
- [x] **T5 — Dev guide**: Added `## 12. Native CLI Action Nodes (action: bash)` to `pipeline_engine_guide.md` — YAML example, `params:`-nesting footgun warning, output shape, router `field: exit_code` note, cross-reference to `subprocess_execution.md`. Also updated `subprocess_execution.md`'s now-stale "not yet implemented" note to point at the new section. Doc-only, no TDD cycle.

## Commit Boundary 1 (after T1–T5)

- [x] Run full project test suite (unit + integration + e2e) — 5098 passed, 21 skipped, zero regressions.
- [x] Pre-commit quality gate (`.agents/skills/specweaver-pre-commit/SKILL.md`, all 7 phases + 7.5) — complete.
  - [x] Phase 1 — Architecture verification (clean, zero violations, tach check OK)
  - [x] Phase 2 — Test gap analysis (1 gap found, approved)
  - [x] Phase 3 — Implement missing tests (`test_registry_resolves_bash_script_to_handler`, ruff clean, HITL approved)
  - [x] Phase 4 — Full test suite re-run (unit 4532, integration 428, e2e 139 — 5099 total passed, 0 failed)
  - [x] Phase 5 — Code quality (ruff clean, mypy clean/302 files, C901 clean, file-size 0 errors/30 pre-existing warnings, tach OK)
  - [x] Phase 6 — Documentation (master_story_roadmap.md + capability_matrix.md + topic_06_sandbox.md flipped to ✅/complete; SF-2 impl plan Post-Implementation Notes added; design doc FR-5 `COMPLETED`→`PASSED` wording fixed with footnote; README/user_guides checked, no changes needed; quickstart.md/testing_guide.md/developer_guide.html/architecture_reference.md don't exist in this repo)
  - [x] Phase 7 — Walkthrough artifact (published: https://claude.ai/code/artifact/72f98302-8b4f-4ce9-bac1-8c28acf5df75)
  - [x] Phase 7.5 — Red/Blue adversarial review (2 cycles; 1 HIGH finding — missing `skipif` bash-availability guard on integration tests, fixed matching SF-1's exact precedent; cycle 2 zero new findings, converged)
- [ ] **STOP — HITL commit gate.** Wait for explicit user commit/proceed.
- [ ] After commit: update Design Doc Progress Tracker (`Dev ✅`, `Pre-Commit ✅`, `Committed ✅` for SF-2) and Session Handoff — this completes C-EXEC-02.
