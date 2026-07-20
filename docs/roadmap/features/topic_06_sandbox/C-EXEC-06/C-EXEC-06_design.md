# Design: Per-Run (Session) Worktree Isolation (C-EXEC-06)

- **Feature ID**: C-EXEC-06
- **Phase**: 6
- **Status**: APPROVED — approved by Steve Bula on 2026-07-19 (AD-1..5 confirmed, incl. the AD-5 architectural switch).
- **DAL**: C (Enterprise Standard)
- **Design Doc**: docs/roadmap/features/topic_06_sandbox/C-EXEC-06/C-EXEC-06_design.md

## Feature Overview

`C-EXEC-06` adds a **per-run (session) worktree isolation mode** to the Flow Engine: a whole untrusted
*span* of pipeline steps runs inside **one** ephemeral git worktree with a **single** end-of-run
reconcile, replacing `D-EXEC-02`'s per-step create/reconcile/teardown for that span. It solves the
`TECH-012` defect — the per-step model is non-functional for multi-step untrusted loops (the 2nd isolated
step crashes on a branch-name collision, the reconcile never commits generated files, and `allowed_paths`
doesn't exist) — so autonomous multi-step untrusted execution (`sw implement`'s generate → lint-fix →
run-tests → validate loop) can finally run worktree-bounded. It touches `core.flow.engine` (a run-level
isolation lifecycle), `sandbox.git.core` (a new `worktree_commit` primitive + reconcile orchestration),
`core.flow.handlers.base` (a new `RunContext.allowed_paths` field), and the composition root (policy +
allow-list population). It does **NOT** touch container isolation (`B-EXEC-01`/`D-EXEC-01`) and does **NOT**
change the existing per-step single-step isolation behavior. **DAL-C** because the single end-of-run
strip-merge is the *sole authorization gate* deciding what generated code lands in the user's real repo.

**Relationships:** this is the **capability build**. `INT-US-09-SF05` integrates it into the US-9 policy;
`INT-US-03 SF-03` consumes it to run `sw implement` sandboxed; it **resolves `TECH-012`**.

## Research Findings

### Codebase Patterns

**The current per-step isolation (`D-EXEC-02` / INT-US-09).** Dispatch is per-step:
`runner.py:321-327` — `if resolve_should_isolate(step_def, context): result = execute_in_sandbox(...)`.
`execute_in_sandbox` (`runner_utils.py:151-221`) wraps ONE step: `worktree_add` → rebind
`output_dir`/`execution_root` to the worktree → `handler.execute` → `worktree_sync` → `strip_merge` →
`worktree_teardown` (finally).

**The three `TECH-012` gaps this feature fixes** (all confirmed in code):
- **Gap 1 (no commit):** handlers never commit; `worktree_sync` (`git/core/atom.py:427-475`) runs
  `git rebase main`, which refuses on the dirty worktree tree, aborts, and returns FAILED — a result
  **discarded** at `runner_utils.py:195`. So `strip_merge`'s `git merge sf-*` is a no-op and the generated
  file is lost at teardown.
- **Gap 2 (no allow-list):** `execute_in_sandbox` reads `getattr(context, "allowed_paths", [])`
  (`runner_utils.py:202`); `RunContext` (`handlers/base.py`) has **no such field** → always `[]` → in
  `strip_merge` (`git/core/worktree_ops.py:107`) every file is stripped.
- **Gap 3 (branch collision):** branch/path are named from the constant run id
  (`sf-{pipeline}-{task_id}`, `.worktrees/{task_id}`, `runner_utils.py:163-166`); teardown removes the
  worktree but **not** the branch → the 2nd isolated step's `git worktree add -b <existing-branch>` fails
  fail-closed.

**Reusable primitives (GitAtom, `git/core/atom.py`):** `worktree_add` (`:385-415`, `git worktree add -b
<branch> <path> HEAD`), `worktree_sync` (`:427-475`, fetch+rebase — *not* a commit), `strip_merge`
(`:477-491` → `worktree_ops.handle_strip_merge`: `git merge -X ours`, strip non-`allowed_paths` +
hard-block `README.md`/`docs/`, then commit surviving hunks), `worktree_teardown`
(`worktree_ops.py:20-64`, resilient remove with a Windows `shutil.rmtree` backoff — but **does not delete
the branch**). `setup_sandbox_caches` (`runner_utils.py`) symlinks `.specweaver`/caches into the worktree.

**Context + composition root:** `RunContext.enforce_isolation` (`base.py:56`, default False) +
`execution_root` (`base.py:57`) already exist; the flow CLI sets the policy from settings
(`flow/interfaces/cli.py:270-272`, `sandbox.enforce_worktree_isolation`). No `allowed_paths` anywhere.

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| git | any | `worktree add/remove`, `branch -D`, `add -A`, `commit`, `merge -X ours` | host |

No new external dependency; per-run isolation is git-worktree only (container-free).

### Blueprint References
Extends the existing Git Worktree Bouncer (`D-EXEC-02`) and the INT-US-09 isolation pattern
(`test_int_us_09_isolation_e2e.py`). No external blueprint.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Session lifecycle | Runner | SHALL, for a run under per-run isolation, create **one** ephemeral worktree (unique branch/path per run) at span start, and tear it down **once** at span end — **including deleting the branch** — in a `finally` (guaranteed even on crash). | No orphaned `.worktrees/` or `sf-*` branches; a run can contain many steps in one worktree (fixes Gap 3). |
| FR-2 | In-session execution binding | Runner | SHALL run **all** steps of the span against the one worktree by rebinding the session workspace root (`project_path`-equivalent + `output_dir` + `execution_root`) to the worktree (AD-3). | Generated code persists in the worktree across steps; untrusted execution (pytest/bash) is worktree-bounded; static QA (lint/validate) operates on the same worktree copy. |
| FR-3 | Commit before reconcile | Runner/GitAtom | SHALL commit the worktree's accumulated working tree onto the session branch (new `worktree_commit` primitive) **before** reconcile. | The generated/modified files exist as commits on `sf-*` so the reconcile can merge them (fixes Gap 1). |
| FR-4 | Authorized reconcile | GitAtom | SHALL perform a **single** end-of-run `strip_merge` that writes back to the real repo **only** paths in `allowed_paths` (plus the existing `README.md`/`docs/` hard-block), and SHALL **surface** (not swallow) any commit/sync/merge failure as a run failure. | Only authorized generated paths land in the user's real branch; a broken reconcile fails loudly, never silently green (fixes Gap 2 + the swallowed failure). |
| FR-5 | `allowed_paths` field | System | SHALL add `RunContext.allowed_paths: list[str]` (repo-relative path strings/globs) and populate it at the composition root (AD-2: the pipeline's generation targets, with a config override). | The reconcile has a real, tight allow-list to authorize against. |
| FR-6 | Fail-closed | Runner | SHALL fail the run with an actionable error if the session worktree cannot be created (e.g. non-git project), and SHALL NOT execute any span step against the real root in that case. | Isolation is never silently skipped when requested. |
| FR-7 | Backward compatibility | System | SHALL keep per-run isolation **opt-in / default-off**, leave the existing per-step single-step isolation path unchanged, and reject/clearly-error a **park (HITL gate) inside an isolated session** (AD-4 v1 non-parking scope). | Zero regression; existing behavior byte-identical when the policy is off. |
| FR-8 | Verifiable proof | Test suite | SHALL provide a **multi-step, freshly-generated-file** e2e: step 1 generates a file, a later step runs pytest on it **worktree-bounded**, the real source root is unmutated until the authorized reconcile, then only `allowed_paths` land back — plus a paired un-isolated control and adversarial reconcile-authorization tests (an out-of-`allowed_paths` write is stripped). | The `TECH-012` coverage gap is closed by a real proof that generated code runs sandboxed end-to-end. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Container-free | Git-worktree only; MUST NOT touch Podman/Docker (`B-EXEC-01`). |
| NFR-2 | No host-execution regression | With the policy off, behavior is byte-identical to today; the per-step path is untouched. |
| NFR-3 | Determinism / no cross-run leak | A fresh worktree per run; no state carried between runs; no orphaned worktrees/branches (guaranteed teardown + branch delete). |
| NFR-4 | DAL-C authorization rigor | The reconcile allow-list is adversarially tested: out-of-`allowed_paths` writes, traversal paths, `README.md`/`docs/` hard-block, and empty allow-list = write-back nothing (never everything). |
| NFR-5 | Windows-safe teardown | Reuse the existing resilient `shutil.rmtree` backoff; branch delete must also succeed cross-platform. |
| NFR-6 | Fail-loud reconcile | A commit/sync/merge failure MUST fail the run (surfaced), never be logged-and-ignored. |
| NFR-7 | Architecture compliance | Lifecycle in `core.flow.engine`; git primitive in `sandbox.git.core`; `allowed_paths` on `RunContext`; `tach`/`ruff`/`mypy --strict` green; ADR-002 (config frozen at composition root) respected. |

## External Dependencies
| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| git | any | worktree/branch/commit/merge | Y | Already used by `D-EXEC-02`. |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | **Whole-run span** (the entire pipeline runs in one worktree). | Matches "one unit of untrusted work" (implement's 5 steps); marked-span deferred until a pipeline mixes trusted/untrusted spans. | No |
| AD-2 | **`allowed_paths` = the pipeline's generation targets** (`src/<stem>.py`, `tests/test_<stem>.py`), with a config override. | Tightest safe default; never "whole diff minus blocklist" (that's the unauthorized-write-back failure). | No |
| AD-3 | **Rebind the session workspace root** to the worktree for all steps (not just `execution_root`). | In per-run mode the worktree *is* the workspace; one consistent tree is simpler and correct (static QA lints the code about to be reconciled). Care: `.specweaver`/DB/cache symlinks. | No |
| AD-4 | **v1 = non-parking spans.** A park (HITL gate) inside an isolated session errors clearly; not supported in v1. | Persisting a worktree across park/resume is a large separate concern; implement has no gates. | No |
| AD-5 | **New per-run isolation execution mode** in the flow engine (+ `RunContext.allowed_paths` + `worktree_commit` primitive). | The whole point of the capability; additive, correct layer, complements `D-EXEC-02`. | **Yes — approved by Steve Bula on 2026-07-19.** |

## ROI Analysis
### Investment Cost
| Item | Effort | Risk |
|------|--------|------|
| Session lifecycle + workspace rebind (SF-01) | Medium | Medium (core runner path) |
| Commit-before-reconcile + authorized strip-merge (SF-02) | Medium | Medium-High (the security gate) |
| Composition-root policy + allow-list + e2e proof (SF-03) | Medium | Low-Medium |

### Returns
| Beneficiary | Benefit | Magnitude |
|-------------|---------|-----------|
| `INT-US-03 SF-03` / US-3 | Unblocks closing the flagship autonomous-implementation epic | High |
| US-17/19/22/24 | All build on autonomous implementation | High (cascading) |
| Zero-trust posture | Multi-step untrusted loops finally run sandboxed; `TECH-012` fixed | High (security) |

### Risk Assessment
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Reconcile authorizes an out-of-bounds write | Low | High | AD-2 tight default + NFR-4 adversarial tests + hard-block |
| Rebinding `project_path` breaks `.specweaver`/DB/cache resolution | Medium | Medium | Reuse `setup_sandbox_caches` symlinks; SF-01 tests cover it |
| Orphaned worktrees/branches on crash | Medium | Medium | Guaranteed `finally` teardown + branch delete (FR-1/NFR-3) |
| Silent data loss (today's swallowed failure) | — | — | FR-4/NFR-6 surface failures |
| Crash-orphaned worktree/branch collides on a same-`run_id` retry | Low | Medium | **[impl note, SF-01]** make create idempotent — prune/delete a stale same-named worktree+branch before `worktree_add`, or add a per-attempt suffix |
| Reconcile runs against a **dirty real working tree** → `git merge` blocks/conflicts | Medium | Medium | **[impl note, SF-02]** decide policy — fail loud (NFR-6) with a clear "commit/stash your changes first" message, or auto-stash; do NOT silently drop |

> [!NOTE]
> **Red/Blue design-review notes carried to the impl plans (not design-blocking):** (1) under AD-3
> `project_path` rebind, `.specweaver`/DB/cache must still resolve to the **real** ones — reuse
> `setup_sandbox_caches` symlinks and verify DB access in SF-01; (2) idempotent worktree/branch create to
> survive a hard crash (kill -9) that skips the `finally` teardown; (3) `run_tests` **loop-back** re-runs
> steps *within* the same session worktree (it is in-session iteration, not a park/resume) — confirmed
> compatible with AD-4's non-parking scope.

### Refactoring Opportunities
| Existing Feature | Current Issue | Benefit from This Feature | Effort |
|-----------------|---------------|---------------------------|--------|
| Per-step `execute_in_sandbox` | Broken for multi-step (`TECH-012`) | Could be deprecated for multi-step in favor of per-run; keep for single-step | Low (follow-up) |

## Developer Guides Required
| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Per-Run Worktree Isolation | Update `pipeline_engine_guide.md §7` (currently documents only per-step isolation) with the session model + `allowed_paths` | ⬜ To be written during Pre-commit |

## Sub-Feature Breakdown

### SF-01: Session Worktree Lifecycle + Context Rebind
- **Scope**: The new run-level isolation mode — create ONE worktree (unique branch/path) at span start, rebind the session workspace root to it for all steps, tear down once (worktree + branch) in a guaranteed `finally`; fail-closed on creation failure; add the `RunContext.allowed_paths` field (unpopulated). No reconcile yet.
- **FRs**: [FR-1, FR-2, FR-5 (field), FR-6, FR-7 (park-guard)]
- **Inputs**: A run flagged for per-run isolation; git repo.
- **Outputs**: All span steps execute in one worktree; generated code persists across steps in-tree; guaranteed cleanup.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_06_sandbox/C-EXEC-06/C-EXEC-06_sf01_implementation_plan.md

### SF-02: Commit-Before-Reconcile + Authorized Strip-Merge
- **Scope**: New `worktree_commit` GitAtom primitive; orchestrate commit → single `strip_merge` (respecting `allowed_paths` + the README/docs hard-block) at span end; **surface** any failure as a run failure (fixes Gap 1, Gap 2 mechanics, and the swallowed failure).
- **FRs**: [FR-3, FR-4]
- **Inputs**: The session worktree from SF-01 with accumulated changes; `allowed_paths`.
- **Outputs**: Only authorized generated paths committed back to the real repo; loud failure on a broken reconcile.
- **Depends on**: SF-01
- **Impl Plan**: docs/roadmap/features/topic_06_sandbox/C-EXEC-06/C-EXEC-06_sf02_implementation_plan.md

### SF-03: Composition-Root Policy + Allow-List Population + Verifiable Proof
- **Scope**: Select per-run isolation via policy (default-off, opt-in); populate `allowed_paths` at the composition root from the pipeline's generation targets (AD-2, with config override); keep per-step single-step isolation unchanged; deliver the multi-step generated-file e2e (FR-8) + NFR-4 adversarial reconcile-authorization tests.
- **FRs**: [FR-5 (populate), FR-7 (policy/default-off), FR-8]
- **Inputs**: SF-01 + SF-02; `SandboxSettings`; pipeline generation targets.
- **Outputs**: Opt-in per-run isolation wired end-to-end; verifiable-proof e2e green.
- **Depends on**: SF-01, SF-02
- **Impl Plan**: docs/roadmap/features/topic_06_sandbox/C-EXEC-06/C-EXEC-06_sf03_implementation_plan.md

## Execution Order
1. **SF-01** — lifecycle + rebind (no deps)
2. **SF-02** — commit-before-reconcile + authorized strip-merge (depends on SF-01)
3. **SF-03** — policy + allow-list + verifiable proof (depends on SF-01, SF-02)

Linear DAG (SF-01 → SF-02 → SF-03); acyclic.

## Progress Tracker
| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Session Worktree Lifecycle + Context Rebind | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | Commit-Before-Reconcile + Authorized Strip-Merge | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-03 | Composition-Root Policy + Allow-List + Verifiable Proof | SF-01, SF-02 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff
**Current status**: Design **APPROVED** (2026-07-19). **SF-01 + SF-02 committed to `main`** — the session
lifecycle AND the authorized reconcile are live (generated code lands back via `allowed_paths`).
**Next step**: SF-03 (composition-root policy + `allowed_paths` population + the multi-step generated-file
e2e proof) — completes `C-EXEC-06`, then `INT-US-09-SF05` → `INT-US-03 SF-03` → US-3 closes.
**If resuming mid-feature**: Read the Progress Tracker; resume at the first ⬜.
