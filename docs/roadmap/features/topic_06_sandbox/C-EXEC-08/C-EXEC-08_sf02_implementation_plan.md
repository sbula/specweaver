# Implementation Plan: Project Doc Policy [SF-02: Grant and merge follow it]
- **Feature ID**: C-EXEC-08
- **Sub-Feature**: SF-02 — Grant and merge follow it
- **Design Document**: docs/roadmap/features/topic_06_sandbox/C-EXEC-08/C-EXEC-08_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_06_sandbox/C-EXEC-08/C-EXEC-08_sf02_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-19

**FRs owned**: FR-7, FR-8 · **NFRs**: NFR-2 (and NFR-1, NFR-3 where the run reads the policy) ·
**Depends on**: SF-01 (committed f0ca523e)

## Shape

| Piece | Where | Tag |
|---|---|---|
| `IsolationPolicy.doc_policy: DocPolicy` (default: empty policy = the built-in rules, today's behaviour); each root passes it when it builds the `RunContext` | `core/flow/handlers/run_context.py` | MODIFY |
| The run roots call `load_doc_policy(project_path)` **strictly**: a broken `[docs]` stops the command, naming the line (NFR-1). Outside the best-effort settings block. The API answers `SpecWeaverAPIError(error_code="DOC_POLICY", status_code=500)`, as `_max_runs` does for a broken settings file | `core/flow/interfaces/cli.py` `_build_run_context` (`sw run`, `sw resume`), `interfaces/api/v1/pipelines.py` (both `_apply_isolation` call sites, `:64` gate/resume and `:193` start), `workflows/implementation/interfaces/cli.py` (`sw implement`) | MODIFY |
| `write_verdict(policy, path, step, allowed) -> "keep" \| "propose" \| "strip"` replaces `merge_keeps`, in order: a protected name → `strip`; the root `doc_updates.md` → `keep`; `doc_access` `keep` → `keep`, `refuse` → `propose`; `task` → `keep` when `path_allowed(path, allowed)`, else `strip`. The grant writes only on `keep`; the merge acts on all three — one decider, so FR-8 holds by construction | `sandbox/security.py` | MODIFY (`merge_keeps` removed) |
| `TaskGrant` gains `policy` and `step`; `covers` is `write_verdict(...) == "keep"` | `sandbox/security.py` | MODIFY |
| `ToolDispatcher.create_standard_set(..., doc_policy=, step=)` passes both into the grant | `sandbox/dispatcher.py` | MODIFY |
| `strip_merge` reads `doc_policy` and the step(s) from its context; a doc change refused by a rule becomes a proposal in the root `doc_updates.md` (FR-7, NFR-2) | `sandbox/git/core/worktree_ops.py` | MODIFY |
| Per-step worktree: the merge gets `step_def.name` | `core/flow/engine/sandboxed_execution.py` | MODIFY |
| Session worktree: after **every** step, whatever its result, a snapshot commit carrying the step's name (a `SW-Step: <name>` trailer) — a failed step's leftovers stay its own, not the next step's after a loop-back. The merge reads the trailers of `HEAD..<branch>` and judges a file by every step that changed it: kept only when each step's verdict is `keep`; `propose` when any is `propose`; else `strip`. The reconcile's final commit (changes made outside any step) counts as step `None` (Q1) | `core/flow/engine/step_execution.py`, `session.py`, `worktree_ops.py` | MODIFY |

### What becomes a proposal (FR-7)

Only a change refused **by a doc rule** (`doc_access` → `refuse` from a `human` rule, or a `step`
rule the step is not named in). Not a protected file (`.env`, `context.yaml`, …): its content must
never be copied into a tracked file. Not a file outside the task's list: that is not a doc change,
and it is stripped as today.

Order inside the merge, per refused doc file:
1. read its staged change against `HEAD` (`git diff --cached HEAD -- <file>`), before anything is
   reset;
2. restore or delete the file as today;
3. after the loop, append one section per file to the root `doc_updates.md` (created when absent,
   NFR-2) and stage it. A section is a heading naming the file and the step(s), then the diff in a
   `diff` fence; a deletion shows as one; a binary file is named with "binary change, not shown"
   (Q2).

So a merge whose only change was a refused doc no longer aborts as "nothing merged": it commits
`doc_updates.md`. The run goes on (FR-7): a refusal is never a failure.

## Commit boundaries

| CB | Does | Proves | Red first |
|---|---|---|---|
| CB-1 | policy on the run; strict load at the roots; `write_verdict`; grant and dispatcher take policy and step | FR-8 (grant half), NFR-1 at the roots, NFR-3 | a `[docs]` rule that opens `docs/user_guides/**` still refuses the tool's write; a broken `[docs]` does not stop `sw run` |
| CB-2 | merge follows the policy, with the step; proposals; session attribution (Q1) | FR-7, FR-8 (merge half and agreement), NFR-2 | a refused `README.md` change is lost; `doc_updates.md` stays absent |

| CB | Tier | Test |
|---|---|---|
| CB-1 | unit | `write_verdict`: protected never (a rule naming `.env` too); root `doc_updates.md` always; `docs/doc_updates.md` and `src/my_doc_updates.md` judged like any path (Q3); `open`, `human`, `step` with the named step and another; no rule → the task list |
| CB-1 | integration | the dispatcher built with a project policy: an implementer writes `docs/user_guides/a.md` under `open`; is refused `docs/api/a.md` unless `step` is the named one; is refused `README.md` with no `[docs]` |
| CB-1 | integration | `sw run` and `POST /pipelines/{name}/run` on a project whose `[docs]` is broken stop, naming the file and the line; with no `[docs]`, they run as before |
| CB-2 | integration | real git: `strip_merge` with a policy and a step — the kept doc lands; a refused `README.md` is restored and its diff is in `doc_updates.md`; a refused new file is deleted and is in `doc_updates.md`; `doc_updates.md` absent before → created; a refused `.env` change is stripped and **not** in `doc_updates.md` |
| CB-2 | integration | session run, real git: step `a` writes `docs/api/x.md` (named in the `step` rule), step `b` then edits it → proposed, not kept; a failed step's leftover is judged as that step's |
| CB-2 | integration (FR-8 seam) | one policy, one step, a matrix of paths: what the tool's grant lets the agent write is exactly what the merge keeps |
| CB-2 | e2e | `sw run` of a two-step pipeline, each step `use_worktree: true`: step `update_api_docs` (a `bash` step) writes `docs/api/x.md` under a `step` rule → it lands; step `other` writes `README.md` → `README.md` is unchanged, `doc_updates.md` holds its diff, the run completes |

> [!CAUTION]
> `core.flow` may not import `core.config.bootstrap` (bootstrap depends on `core.flow`: a cycle).
> The interface modules load the policy; `core.flow` only receives it.

> [!NOTE]
> `TaskGrant` is a frozen dataclass and a pydantic `DocPolicy` is not hashable, so `policy` is a
> `field(compare=False)`: it stays out of the generated `__eq__` and `__hash__`.

> [!NOTE]
> A `strip_merge` context with no `doc_policy` uses the empty policy, and with no step uses `None`:
> the built-in rules, today's behaviour. A forgotten wiring is caught by the mutants below, not by
> a crash.

> [!NOTE]
> Accepted: if the merge commit itself fails, the merge is aborted and nothing of it lands — code
> nor proposals; the run fails loudly, as today. An uncommitted edit to the root `doc_updates.md` in
> the real repo is kept and committed with the appended proposals.

## Mutants (into `C-EXEC-08_mutants.json`)

| CB | Neutralise | Killed by |
|---|---|---|
| CB-1 | the grant passes no step; the protected check in `write_verdict`; `refuse` mapped to `strip` instead of `propose`; the root-only `doc_updates.md` check (Q3) | CB-1 unit + integration |
| CB-1 | the roots skip loading the policy | CB-1 root integration |
| CB-2 | the proposal is not written; `doc_updates.md` not created when absent; the per-step merge passes no step; the session judges a file by its last step only; the snapshot taken only after a passed step (Q1) | CB-2 integration + e2e |

## Docs (CB-2)

- `docs/dev_guides/agent_tools_reference.md:45`, `pipeline_engine_guide.md:223,246`,
  `special_patterns_and_adaptations.md:167`: the fixed rule becomes the project's policy.
- The user guide gains "Which docs agents may change": the design's settings example, and where a
  refused change goes (`doc_updates.md`). SF-03 adds blocks to it.

## Research Notes

- `merge_keeps(path, allowed)` (`sandbox/security.py:251-261`) has two callers:
  `TaskGrant.covers` (`security.py:198-202`) and `_strip_forbidden_files`
  (`sandbox/git/core/worktree_ops.py:125-145`). Its `doc_updates.md` check is
  `lowered.endswith("doc_updates.md")`: it also keeps `docs/doc_updates.md` and
  `src/my_doc_updates.md` (Q3).
- Two merges call `strip_merge`: per step (`sandboxed_execution.py:105-113`, knows `step_def`) and per
  run (`session.py:96-104`, once after all steps — it does not know which step changed a file, Q1).
- The step name is on the context while a step runs: `context.run.step_name`
  (`step_execution.py:191-197`), so a handler that builds a dispatcher has it.
- No production handler builds a **writing** dispatcher today: `create_standard_set` is called by
  `review.py:59` and `scenario.py:31`, both read-only. The grant half of FR-8 is therefore proven
  through the dispatcher directly; `C-FLOW-11` is its first production caller.
- The three run roots: `core/flow/interfaces/cli.py:319-330`, `interfaces/api/v1/pipelines.py:133-140`,
  `workflows/implementation/interfaces/cli.py:302`. `apply_isolation_policy` is best-effort by
  contract, so the doc policy is loaded beside it, not inside it.
- `IsolationPolicy` is frozen; replace the attribute with `model_copy(update=...)`.
- Without worktree isolation a `bash` step writes the real repo directly: no merge judges it. That is
  today's behaviour for the `README.md` block too, and outside this design ("Not touched").
- The session merge uses `-X ours`; a parked run keeps its worktree and branch, so per-step commits
  (Q1 A) survive a resume.

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q1 | A session run merges once at the end: whose step decides a file? | a snapshot commit per step names it; a file is kept only when every step that changed it may change it `[agreed 2026-10-19]` |
| Q2 | What does a proposal hold? | per file, a heading with the file and the step, then its diff; a binary file named only `[agreed 2026-10-19]` |
| Q3 | Which `doc_updates.md` always survives? | only the one at the repo root; any other is judged like every path `[agreed 2026-10-19]` |

## Backlog

none
