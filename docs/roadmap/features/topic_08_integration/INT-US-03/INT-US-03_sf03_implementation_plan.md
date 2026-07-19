# Implementation Plan: Autonomous Implementation Integration — SF-03: Zero-Trust Isolation + Verifiable Proof

- **Feature ID**: INT-US-03
- **Sub-Feature**: SF-03 — Zero-Trust Isolation + Verifiable Proof
- **Design Document**: docs/roadmap/features/topic_08_integration/INT-US-03/INT-US-03_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_08_integration/INT-US-03/INT-US-03_sf03_implementation_plan.md
- **Status**: BLOCKED — depends on the new capability **`C-EXEC-06`** (Per-Run Worktree Isolation) + its
  integration **`INT-US-09-SF05`** (which also resolves `TECH-012`). Direction resolved 2026-07-19:
  **Option B via C** — per-run worktree is a real capability build (`C-EXEC-06`), integrated by
  `INT-US-09-SF05`; SF-03 then re-scopes to *consume* it + thread the policy + deliver the FR-8 e2e proof.
  Do NOT `/dev` SF-03 until `INT-US-09-SF05` is committed.
- **Depends on**: SF-01 ✅, SF-02 ✅, **`C-EXEC-06` + `INT-US-09-SF05`** ⛔ (not yet started)

## Scope (from the Design Document)
Thread the US-9 worktree-isolation policy into the `implement` `RunContext`, carry the generated files
into the `run_tests` worktree (**AD-7 crux**), and deliver the e2e proof that freshly **generated** code runs
QA worktree-bounded + a paired un-isolated control. **FRs owned: FR-5, FR-8.** Depends on SF-01, SF-02
(both committed).

> [!CAUTION]
> **The design (AD-7) flagged this as "may require a short spike." The spike is done, and it found that
> SF-03 as scoped is NOT achievable within the existing INT-US-09 per-step isolation model.** Three
> independent defects in that machinery block the generated→run_tests round-trip; one of them (Gap 3)
> breaks *any* multi-step isolated pipeline regardless of this feature. This plan documents the findings and
> presents the architectural fork; the direction is a HITL decision (Audit Q1) before any code is written.

## Research Notes (Phase 0) — the spike

**The one part that is trivial integration** (mirrors `core/flow/interfaces/cli.py:270-272`): thread the
policy into the implement `RunContext` — `context.enforce_isolation =
load_settings(...).sandbox.enforce_worktree_isolation`. This works today.

**The isolation round-trip is broken.** INT-US-09's `execute_in_sandbox` (`runner_utils.py:151-221`) wraps
**each step** in: `worktree_add` → rebind `output_dir`/`execution_root` to the worktree → `handler.execute`
→ `worktree_sync` → `strip_merge` → `worktree_teardown` (finally). For the implement loop
(`generate_code → generate_tests → lint_fix → run_tests → validate_code`), the generated `src/<stem>.py`
must travel from generate_code's worktree to run_tests' worktree via the real repo. It does not. Three gaps:

- **Gap 1 — nothing commits the worktree's new file onto the `sf-*` branch.** Handlers never commit (grep
  of `core/flow/handlers/` for commit/add: none). `worktree_sync` (`atom.py:427-475`) runs `git fetch` +
  `git rebase main` inside the worktree — which **refuses on a dirty tree** (the uncommitted generated file)
  → `rebase --abort` → returns FAILED, and that result is **discarded** (`runner_utils.py:195`). So the
  generated file is never committed; `strip_merge`'s `git merge sf-*` is a no-op ("No changes to strip",
  `worktree_ops.py:92-98`). The uncommitted file is then destroyed at teardown.
- **Gap 2 — `allowed_paths` does not exist.** `execute_in_sandbox` reads `getattr(context, "allowed_paths",
  [])` (`runner_utils.py:202`), but `RunContext` (`base.py:30-75`) has **no such field** and nothing in
  `src/` ever sets it → always `[]`. In `strip_merge`, `file not in allowed_paths` is then true for every
  file (`worktree_ops.py:107`) → everything is stripped, nothing survives to commit. (Format is a list of
  repo-relative path strings, per `test_atom.py:749`.)
- **Gap 3 — the per-step branch/worktree name is constant per run, and teardown does not delete the
  branch.** Branch `sf-{pipeline}-{task_id}`, path `.worktrees/{task_id}` (`runner_utils.py:163-166`);
  `task_id` is constant across the run. `worktree_add` runs `git worktree add -b <branch> …`
  (`atom.py:402-403`); teardown removes the worktree but **not** the branch (`test_worktree_atoms.py:99`).
  So the **second** isolated step in one run runs `git worktree add -b <existing-branch>` → "branch already
  exists" → fail-closed `RuntimeError` (`runner_utils.py:170-178`). **Any multi-step isolated pipeline
  crashes at step 2 today** — INT-US-09 was only ever exercised with single-step pipelines
  (`test_int_us_09_isolation_e2e.py`, which also commits its probe files up front, `:64-65`, `:134-135`).

**No existing test** proves the generate→commit→run_tests round-trip for uncommitted files, because the
model never commits them.

### External deps: git worktree (existing). No new tool.

## Functional Requirements (this SF)
- **FR-5** — the implement QA loop runs worktree-bounded under the US-9 policy (generated code never
  executed against the real source root).
- **FR-8** — verifiable-proof e2e: freshly **generated** code runs pytest worktree-bounded + un-isolated
  control.

## The architectural fork (Audit Q1 — must be decided before /dev)

| Option | What it means | Pros | Cons |
|--------|---------------|------|------|
| **A — Fix the per-step model in place** | Commit the worktree working-tree onto `sf-*` before sync (Gap 1); add + populate `RunContext.allowed_paths` (Gap 2); make the branch/worktree unique per step or delete the branch at teardown (Gap 3). | Keeps the existing per-step design. | Pollutes the user's git history with an intermediate commit **per step**; complex 3-part change to core isolation machinery; run_tests worktree must re-checkout committed code each step. |
| **B — Per-run (session) worktree mode** *(recommended)* | Add an isolation mode where the **whole** implement loop runs in ONE worktree: create once, all 5 steps operate in it (generated code persists in-tree, lint fixes it in place, pytest runs on it in place), reconcile once at the end via `strip_merge`. | Natural model for one untrusted unit of work; sidesteps Gap 1 (files persist in-tree) and Gap 3 (one worktree); single reconcile ⇒ `allowed_paths` handled once. | New isolation execution mode in the flow engine = **architectural switch** (needs sign-off); larger than "integration"; still needs `allowed_paths` (Gap 2) for the final reconcile. |
| **C — Re-scope: spin the machinery into an INT-US-09 enhancement first** | Gaps 1 & 3 are INT-US-09 **defects** (multi-step isolation is simply broken). Fix them under a new `INT-US-09-SFxx`; INT-US-03 SF-03 then only threads the policy + consumes the fixed mode + ships the e2e proof. | Correct ownership (isolation bugs belong to US-9, not US-3); keeps SF-03 truly integration-scoped. | US-3 base contract stays `[ ]` longer (depends on the new US-9 work landing first). |
| **D — Scope SF-03 down** | Thread the policy + prove only the guarantee that works today (e.g. an isolated single-step `run_tests` over **pre-committed** code, matching the INT-US-09 e2e). | Small, ships now. | Does **not** prove "freshly generated code runs worktree-bounded" (FR-8's real intent) ⇒ the contract's proof is weak/misleading. Not recommended. |

**Recommendation: B (per-run worktree mode), most likely delivered as an INT-US-09 enhancement per C.**
It is the only option that cleanly models "the autonomous implement loop is one unit of untrusted work,"
avoids per-step history pollution, and fixes the latent multi-step defect. Because it adds a new isolation
execution mode to the flow engine, it is an **Architectural Switch requiring explicit approval**, and its
natural home is the US-9 isolation machinery (so pairing B with C — do it as `INT-US-09-SFxx`, then have
INT-US-03 SF-03 consume it — is the cleanest ownership).

## Architecture Verification (Phase 3)
- **CRITICAL — Architectural Switch (unapproved):** every viable option changes core INT-US-09 isolation
  machinery (`runner_utils.execute_in_sandbox`, `worktree_ops`, `git/atom`, and `RunContext`), not just
  `workflows/implementation`. Option B additionally introduces a **new isolation execution mode**. Per the
  design/plan rules this is a hard stop for HITL sign-off (Audit Q1). It also touches `core/config` /
  `core/flow` (relatively stable modules), so the change must be deliberate.
- The only non-switch change is the 1-line `enforce_isolation` threading in the implement CLI — inert on its
  own (default policy off) and safe, but useless until the chosen option lands.

## Audit (Phase 2) — open questions for HITL
| # | Question | Proposal | Severity |
|---|----------|----------|----------|
| Q1 | **Which option (A/B/C/D) for the isolated implement loop?** The per-step model can't carry generated code and breaks on multi-step pipelines (Gaps 1-3). | **B via C** — add a per-run worktree mode as an `INT-US-09` enhancement, then SF-03 consumes it. Requires arch sign-off. | **CRITICAL** |
| Q2 | Should Gap 3 (multi-step isolation crash) be filed/fixed as an INT-US-09 defect regardless of this feature? | Yes — it's a latent bug; any multi-step isolated pipeline hits it. | HIGH |
| Q3 | Add + populate `RunContext.allowed_paths` (Gap 2) — where do the generated paths come from? | From the implement stem (`src/<stem>.py`, `tests/test_<stem>.py`); populated at the composition root or the per-run reconcile. | MEDIUM |
| Q4 | Should `sw implement` default `enforce_isolation` ON (design AD-5, approved) once the mode works? | Yes (AD-5) — but gate it on the chosen option landing so it isn't turned on over a broken path. | MEDIUM |

## Session Handoff
**Current status**: Impl Plan DRAFT — **blocked on Audit Q1 (architectural fork)**. The AD-7 spike proved the
per-step model can't carry generated code (3 gaps documented). No `/dev` until the direction is chosen.
**Next step**: Resolve Q1 at the Phase 4 HITL. If B/C: this likely spawns an `INT-US-09-SFxx` (per-run
worktree) that SF-03 then consumes.
