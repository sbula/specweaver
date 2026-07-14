# Task List: C-EXEC-02 SF-3 — Scaffold, Boundary Config, and Docs

- **Implementation Plan**: docs/roadmap/features/topic_06_sandbox/C-EXEC-02/C-EXEC-02_sf3_implementation_plan.md
- **Commit boundaries**: 1 (small, low-risk sub-feature — 9 modified files, no new source files, clones an existing scaffold pattern exactly)

## Adversarial Test Matrix

| Bucket | Covered by |
|--------|-----------|
| **Happy Path** | `test_creates_scripts_dir_with_readme`, `test_init_creates_scripts_dir` |
| **Boundary/Edge Cases** | N/A — no numeric/size boundaries in this SF (pure filesystem scaffolding, fixed content) |
| **Graceful Degradation** | `test_does_not_overwrite_existing_scripts_readme` (idempotency — scaffold re-run against an already-scaffolded/user-modified project must not clobber it) |
| **Hostile/Wrong Input** | N/A — no user-controlled input reaches this code path (`scaffold_project(project_path)` takes a trusted CLI-resolved path, not YAML/agent-controlled content) |

Two buckets justified as N/A: this SF has no numeric thresholds to probe (Boundary/Edge Cases) and no externally-controlled input surface (Hostile/Wrong Input) — it's fixed-content filesystem scaffolding, unlike SF-1's `BashActionAtom` which processes YAML-sourced script names/args. Consistent with the design doc's own scope note.

## Tasks (single commit boundary)

- [x] **T1 — Scaffold `.specweaver/scripts/`** (FR-10): Red → Green → Refactor. Added `_DEFAULT_SCRIPTS_README` constant + `_scaffold_scripts_dir(sw_dir, created)` helper to `scaffold.py`, cloning `_scaffold_templates()`'s exact structure; wired into `scaffold_project()` right after `_scaffold_templates(sw_dir, created)`. Tests: `test_creates_scripts_dir_with_readme`, `test_does_not_overwrite_existing_scripts_readme`, `test_creates_readme_when_scripts_dir_already_exists` (all in `test_scaffold.py`), `test_init_creates_scripts_dir` (`test_cli_projects.py`). All 82 tests in both files pass (0 regressions), ruff + mypy clean.
- [x] **T2 — `tach.toml` boundary config**: Added `"execution.core"` + `"execution.core.atom.BashActionAtom"` to the `specweaver.sandbox` interface's `expose` array.
- [x] **T3 — `core/flow/context.yaml` boundary config**: Added `- specweaver/sandbox/execution/core` to `consumes:`, grouped with the other `sandbox/*` entries. `tach check` → `[OK] All modules validated!` (verified after T2+T3 together).
- [x] **T4 — `hard_dependency_rules.md` correction**: Replaced the stale `flow` row (Consumes/Forbids columns) with the corrected version.
- [x] **T5 — `ORIGINS.md` correction**: Replaced line 176's Archon-attribution bullet with the corrected text.
- [x] **T6 — `subprocess_execution.md` addition**: One sentence appended to the existing "Engine-Internal Script Execution (BashActionAtom)" section noting the scaffold origin of `.specweaver/scripts/`.
- [x] **T7 — `1_installation_and_setup.md` addition**: One clause appended to §4's scaffolding-artifact list.

## Commit Boundary 1 (after T1–T7)

- [ ] Run full project test suite (unit + integration + e2e) — zero regressions.
- [ ] Pre-commit quality gate (`.agents/skills/specweaver-pre-commit/SKILL.md`, all 7 phases + 7.5).
- [ ] **STOP — HITL commit gate.** Wait for explicit user commit/proceed.
- [ ] After commit: update Design Doc Progress Tracker (`Dev ✅`, `Pre-Commit ✅`, `Committed ✅` for SF-3) and Session Handoff.
