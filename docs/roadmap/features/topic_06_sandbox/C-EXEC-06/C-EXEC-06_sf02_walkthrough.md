# C-EXEC-06 SF-02 — Walkthrough

**Commit boundary:** CB-1 (single) · **Date:** 2026-07-19 · Plan:
[sf02](C-EXEC-06_sf02_implementation_plan.md)

## Delivered

The **reconcile** — the DAL-C authorization gate. At span end, COMPLETED runs only, the session
worktree is committed onto the session branch and one `strip_merge` writes back **only**
`allowed_paths` (+ the `README.md`/`docs/` hard-block). Fixes `TECH-012` Gap 1 (nothing committed) and
Gap 2 (allow-list not applied).

| File | Change |
|---|---|
| `sandbox/git/core/worktree_ops.py` | `handle_worktree_commit` (stage + commit, skip if clean); `_strip_forbidden_files` extracted, **deletes** stripped *new* files from disk; `handle_strip_merge` gained a `cwd` param, a **merge-failure guard** (dirty real tree → `--abort` + FAILED) and a **post-strip empty check** (all stripped → abort, no noise commit) |
| `sandbox/git/core/atom.py` | `_intent_worktree_commit`; `_intent_strip_merge` passes `self._cwd` |
| `core/flow/engine/runner_utils.py` | reconcile in `execute_run`: COMPLETED-only, `worktree_commit → strip_merge(allowed_paths)`, **raise** on either FAILED (replaces the INT-US-09 behavior of swallowing the failure) |

Out of scope: policy wiring, allow-list population and the multi-step e2e (SF-03).

## Proof

| Test | Cases |
|---|---|
| `tests/unit/sandbox/git/core/git/test_worktree_commit.py` | 4 |
| `tests/integration/core/flow/engine/test_session_reconcile.py` (real git) | 11 — lands-allowed/strips-disallowed, failed-run-skip, strip/commit-fail surfaced, dirty-tree fail-loud, empty-allowed, hard-block, graceful-teardown-on-failure, all-stripped, empty-session, doc_updates-survives |
| `test_atom.py` | intent-set + 2 strip_merge mock sequences updated |

| Check | Result |
|-------|--------|
| Unit | **4703 passed**, 15 skipped |
| Integration | **472 passed**, 5 skipped |
| E2E | **144 passed**, 1 skipped |
| **Grand total** | **5319 passed, 0 failures** |
| ruff / mypy / C901 / tach / file-size | ✅ all clean |

Approvals: plan audit Q1–Q5 → (a).
