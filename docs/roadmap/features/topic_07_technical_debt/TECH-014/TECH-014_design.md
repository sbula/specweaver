# Design: Fan-Out RunContext Isolation (Concurrent Sub-Run State Corruption)

- **Feature ID**: TECH-014
- **Epic**: Topic 07 (Technical Debt)
- **Status**: DELIVERED 2026-08-12 — see §Delivery. Approach 1 (derived per-sub-run context),
  applied inside `PipelineRunner.run` rather than at each fan-out boundary (user decision).
- **Origin**: Found during INT-US-21 SF-01 CB-2's pre-commit Phase-2 HITL gate (2026-07-25).

## Problem Statement

`OrchestrateComponentsHandler` hands **the same `RunContext` object** to every concurrent
sub-runner (`core/flow/handlers/decompose.py`, `context=context.pipeline_runner._context`), while
`PipelineRunner._execute_loop` writes `run_id`, `step_records` and `pipeline_runner` onto that
context on **every step** (`core/flow/engine/runner.py`, the context-injection block before handler
execution).

With N sub-runs executing concurrently those writes interleave, so a sub-run can observe another
sub-run's `run_id`. **Lineage and telemetry events are therefore attributable to the wrong sub-run
today**, and `step_records` (consumed by handover persistence) is likewise corruptible.

This is a defect in **shipped** code — `C-FLOW-03` (Multi-Spec Fan-Out) is ✅ delivered — not a
missing capability. It is live now, independent of INT-US-21.

## What INT-US-21 did and did not do

INT-US-21 FR-2 added a runner hook that writes `context.plan` / `context.decomposition` at the same
shared object, which **widened the blast radius** to the plan fields. It did **not** create the
defect: `run_id` / `step_records` / `pipeline_runner` were already racing before FR-2 existed.

## Why this is NOT deferred to `C-FLOW-12` / `INT-US-21-SF02`

Considered and explicitly rejected during INT-US-21's CB-2 pre-commit (user decision, 2026-07-25):

1. The add-on is about autonomous DAG *execution* and per-component DAL isolation. Basic context
   hygiene is something it should be able to **assume**, not own.
2. `C-FLOW-12` is unbuilt and sequenced behind `C-EXEC-07`, so gating a live shipped-code defect on
   it would leave corrupt telemetry in place indefinitely.
3. Per the finished-stories-immutable rule, a defect in a delivered story becomes a new story or a
   TECH ticket — never an edit to the delivered entry.

**Should land before `C-FLOW-12`.**

## Candidate Approaches (not yet designed)

1. **Derived per-sub-run context** — give each sub-runner its own context (a copy with sub-run
   identity applied) at the fan-out boundary. Cheapest to reason about; needs care over which
   fields are legitimately shared (settings, adapters) versus per-run (identity, records).
2. **Thread run-scoped state through the call instead of the context** — stop writing `run_id` /
   `step_records` onto `RunContext` at all; pass them as explicit arguments to the handler call.
   Architecturally cleaner and removes the shared-mutable-state class of bug outright, but touches
   every handler signature. Overlaps `TECH-007`'s RunContext god-object finding.
3. **Make the shared identity fields immutable per run** — freeze them after construction so an
   interleaved write fails loudly instead of silently corrupting. A detection mechanism rather than
   a fix; possibly a useful first step.

## Non-Goals (proposed, pending design)

- Redesigning fan-out concurrency or its loop/error bounds (a documented DMZ — see
  `pipeline_engine_guide.md`).
- Per-component DAL-scoped isolation — that is `C-FLOW-12` / `C-EXEC-07` territory.

## Verification the design must specify

A concurrency test asserting **per-sub-run `run_id` attribution** in emitted lineage/telemetry
events. The current defect is invisible to every existing test because nothing runs two sub-runs
concurrently and then checks which run each event was recorded against.

## Delivery, 2026-08-12

### The defect was worse and wider than recorded

**Wider:** the ticket names one fan-out site (`handlers/decompose.py`). There are **four**, across
two handlers — `decompose.py` (the DAG dispatch and the Wave-N deferred-join runner) and
**`handlers/dual_pipeline.py`**, which was never mentioned and dispatches two concurrent
sub-runners over the same shared context by the same `context.run.pipeline_runner._context` route.

**Worse:** the reproduction shows the corruption is **total, not intermittent**. Every single step
of every sub-run observed a sibling's `run_id` after its first `await`. The ticket's "a sub-run
*can* observe another's `run_id`" understates it — under three concurrent sub-runs, essentially
none of them observed their own.

### What `TECH-006` SF-02 did and did not do

`RunHandle` landed, and it narrowed the failure mode without closing it: collapsing the three
racing fields into one frozen model made the rebind a single atomic swap, so a reader can no longer
see a *torn* handle carrying one run's id beside another's records. It can still see the wrong
handle entirely, which is what the reproduction demonstrates.

### Approach and why the fix sits where it does

Approach 1, but applied in `PipelineRunner.run` rather than at each fan-out boundary:

```python
self._context = isolate_sub_run_context(self._context, parent_run_id)
```

`parent_run_id is not None` is exactly "I am a sub-run" — **all four** fan-out sites pass it and
**no** top-level caller does, verified across all 15 `PipelineRunner(...)` construction sites. That
fixes the two sites this ticket never recorded, and any future one, without the per-caller
discipline that had already failed here. The fifteen top-level callers (the API and eight CLI
entrypoints) keep today's semantics, where they hand in a context and read their own reference
back — pinned by its own test, so the discriminator is load-bearing in **both** directions.

The copy is **shallow**: only `run` is rebound per step, so paths, providers and adapters stay
shared by reference as the read-only infrastructure they are.

Two collaborators were checked rather than assumed. The C-EXEC-06 worktree swap in
`runner_utils.py` captures `original = runner._context` **at call time**, which is after the copy,
so its `finally:` restores the sub-run's own context and not the shared one.

`GateEvaluator` retains the *original* context from `__init__`, and that turned out to be
**load-bearing, not a leak**. It reads only `project_path`, and a RESERVE gate is a
*cross-pipeline mutex* keyed `pipeline:<name>` whose lock database resolves to
`project_path / ".specweaver" / "reservations.db"`. Contention exists only while every contender
resolves the same path — and C-EXEC-06 rewrites `project_path` to a per-run worktree. **Re-pointing
the evaluator at `runner._context`, which is the obvious tidy-up, would hand each run a private
database, make every acquire succeed, and delete the mutex with nothing failing and nothing
logged.** Pinned by two tests: one asserting the evaluator keeps its original context, and one
demonstrating that separate databases do not contend, so the reason is visible and not folklore.

### Isolation covers more than the three fields named

The shallow copy isolates **all** per-run state, not only `run` — including the `plan_context`
fields INT-US-21 FR-2 widened the blast radius to. That holds because **no code anywhere in `src/`
mutates a `RunContext` sub-model in place**; every write rebinds the whole sub-model
(`context.plan_context = context.plan_context.model_copy(update=...)`, and the same for `isolation`
and `run`). Verified by search rather than assumed, because a single in-place mutation would defeat
a shallow copy silently.

### Verification

`tests/unit/core/flow/engine/test_fan_out_context_isolation.py` — the concurrency test this
document asked for, asserting **per-sub-run `run_id` attribution** and not merely aggregate
success. Four tests: the attribution claim, the narrower "identity does not move under a running
step" mechanism, a **vacuity guard** (both assert over a collection that would be empty if the
handler never ran — `test-quality.md` pattern 8), and the top-level control.

Confirmed red before and after the repro was adjusted to pass `parent_run_id`, and
**mutation-checked**: with the one-line fix disabled the two attribution tests fail again and the
controls still pass.

### Known boundary, deliberately not closed

`resume()` takes no `parent_run_id` and so never isolates. That is correct today because sub-runs
are always created fresh by fan-out and never resumed — `dual_pipeline` downgrades HITL gates to
auto inside the fan-out precisely so sub-pipelines cannot park, and C-EXEC-06 rejects parking
inside a session outright. **If sub-run resume is ever introduced, this fix does not cover it.**

### Out of scope, surfaced here

This commit hit `TECH-020`'s trap head-on: `runner.py` sits against a **600-line RED threshold**,
and adding the single call line pushed it to 601 and blocked the gate. The rationale therefore
lives in `runner_utils.isolate_sub_run_context`'s docstring rather than as a comment at the call
site — a structural move, not the comment-condensing that `TECH-020` names as the pattern to stop
repeating. The file now sits at **599 of 600**. This is `TECH-020`'s second recorded data point,
and the next contributor still pays with no warning.
