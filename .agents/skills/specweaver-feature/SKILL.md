---
name: specweaver-feature
description: "Drives a feature end to end: precondition gate, design, an implementation plan per
sub-feature, dev and commit per commit boundary, then the closure gate and the finished message.
Resumable from the Progress Tracker in the Design Document. Use when the user says 'feature
<feature_id>', 'implement <feature_id>', 'build <feature_id>', 'work on <feature_id>' or 'start
<feature_id>'."
argument-hint: "<feature_id>"
allowed-tools: Bash(git rev-list *) Bash(echo *)
---

# Feature Lifecycle Skill

```
Trigger: "feature <feature_id>", "implement <feature_id>", "build <feature_id>",
         "work on <feature_id>", "start <feature_id>"
```

This skill orchestrates the complete feature lifecycle from first design to
committed, tested code. It is **fully resumable**: starting it in a new session
automatically continues from where the Progress Tracker shows work stopped.

> [!CAUTION]
> **MANDATORY SEQUENCING — DO NOT SKIP OR REORDER PHASES.**
> Read the Progress Tracker before every decision. Never assume a phase is done.
> Never proceed past a HITL gate without explicit user confirmation.

> [!IMPORTANT]
> **AGENT DIRECTIVE:**
> Execute all research, TDD, and quality checks autonomously.
> STOP only at the explicitly defined HITL gates below: design approval (Phase 1), plan approval
> (Phase 2), the commit boundary that closes a sub-feature (Phase 3), and sign-off (Phase 4).
> Never add extra stops. Never skip a defined gate.
> The Progress Tracker in the Design Document is the single source of truth.
> Always read it at the start of a new session to know where to resume.

Why each rule exists: [references/lessons.md](references/lessons.md).

---

## Phase 0: Precondition Gate (HARD BLOCK — run before anything else)

0.0. **No new feature while commits are unpushed.** Commits on `main` not yet on `origin`:

```
!`git rev-list --count origin/main..HEAD 2>/dev/null || echo "unknown: no origin/main"`
```

If that number is above 0 (or unknown) and this feature is not the one those commits belong to, **STOP** and ask
the user to push first. Fixes to the same feature may go on (`PRINCIPLES.md` §6).

0.1. Verify the story's prerequisites are green **in code**, not just in documents:
```
python scripts/check_story_preconditions.py <STORY-ID>
```

A non-zero exit **blocks the whole feature**. Do not design, plan, or implement; fix the reported
facts, or file each as its own ticket (`specweaver-ticket`) and stop. There is deliberately no
override — an overridable gate becomes a habit. The gate checks the *evidence*: the declared proof
exists, passes and does not skip; every bundled pipeline step resolves to a real handler; no field
documented as "set by X" is unwritten.

## Phase 0b: The (Sub)Story Path List (`ADR-005`)

0b.1. Every (sub)story carries a **path list** — every path through it, one row each, with the
      **seam (N)FRs** the crossing paths generate. It lives in the (sub)story itself. There is no
      separate integration entry and no `INT-US` identifier; `ADR-005` retired the family. If the
      (sub)story you are entering has no list, create it before Phase 1; if it has one, you are
      extending it.

0b.2. Fill the list with every path, one row each, with its owner and status. Ownership is decided by
      **span**:

| Path | Owner | Written when |
|---|---|---|
| One feature can walk it | that feature | inside the feature's own TDD cycle |
| Crosses several features | this (sub)story | now, red, as soon as the interface is defined |
| Touches an interface not yet defined | this (sub)story | now, as `xfail(strict=True)` naming the blocker |

0b.3. **Nothing is deferred to a later entry.** A path whose other side is unbuilt still gets its
      test now, marked `xfail(strict=True)` with the blocker named. It fails today for the right
      reason and turns green loudly when the last related (sub)story lands.
      `check_xfail_blockers.py` fails the marker once its blocker is `✅`.

0b.4. A path a single feature can walk is **never** restated at (sub)story level.

0b.5. The path list is expected to change. A list or a scope that turns out wrong is edited, not
      worked around.

> [!CAUTION]
> **A (sub)story may not go green while any of this is missing** — even when every feature task
> beneath it is green. Feature-level green is not story-level proof.
> `check_delivered_claims.py` enforces it: a green unit holding closed features with no delivered
> contract is a finding.

---

## Phase 1: Design

1.1. Locate the Design Document:
     `docs/roadmap/features/[Topic]/[ID]/[ID]_design.md`

1.2. If it exists and `Status: APPROVED`:
     Read it fully. Extract the sub-feature list and dependency graph.
     Skip to Phase 2. Design is already done.

1.3. If it does not exist or `Status: DRAFT`:
     Invoke the `specweaver-design` skill and execute it in full.
     **STOP at Phase 6 HITL gate.** Wait for user approval.
     On approval: the design doc is written and `Status: APPROVED`.
     Proceed to Phase 2.

---

## Phase 2: Implementation Plans

For each sub-feature in topological execution order (from the Design Document):

2.1. Read the Progress Tracker. Check the `Impl Plan` column for this SF:
     - `✅` → already done. Skip to next SF.
     - `⬜` → not done. Proceed to 2.2.

2.2. Pre-check dependencies:
     All sub-features listed in this SF's `depends_on` must have `Impl Plan ✅`.
     If not → **STOP.** Tell the user which dependency still needs its plan first.

2.3. Invoke the `specweaver-implementation-plan` skill and execute it in full for this SF.
     Output: `docs/roadmap/features/[Topic]/[ID]/[ID]_sf[N]_implementation_plan.md`
     (no `_sf<N>` suffix for non-decomposed features)

2.4. **STOP at Phase 4 HITL gate.** Wait for user response.
2.5. **STOP at Phase 5 HITL gate.** Wait for user approval.
2.6. On approval: Design Document Progress Tracker updated (`Impl Plan ✅`).
     Move to next SF.

Repeat until all sub-features have `Impl Plan ✅`, then proceed to Phase 3.

> [!NOTE]
> Sub-features with no shared dependencies MAY be planned in parallel sessions.
> The Progress Tracker prevents double-work — always check it before starting.

---

## Phase 3: Dev + Pre-Commit + Commit

For each sub-feature in the same topological execution order:

3.1. Read the Progress Tracker. Check `Dev`, `Pre-Commit`, `Committed` for this SF:
     - All `✅` → already done. Skip to next SF.
     - Any `⬜` → proceed to 3.2.

3.2. Pre-check dependencies:
     All sub-features in this SF's `depends_on` must have `Committed ✅`.
     If not → **STOP.** Tell the user which dependency must be committed first.

3.3. Derive the implementation plan path from the Design Document SF section.
     Invoke the `specweaver-dev` skill and execute it in full.

     Inside the dev skill, for **each commit boundary** defined in `.tmp/task.md`:
     - Complete all TDD tasks in this batch autonomously (red → green → refactor).
     - Invoke the `specweaver-pre-commit` skill; every check runs.
     - **Interior boundary:** commit and report in a few lines (tasks, test count, what the gate
       found), then continue `[agreed 2026-08-15]`.
     - **The boundary that closes the sub-feature — HARD STOP (HITL):**
       Inform the user: "Commit boundary N of M for SF-<X> is ready."
       State: tasks included, test count, what's in this commit.
       **WAIT** for the user's acceptance before committing it.

3.4. After the final commit boundary for this SF:
     Update Progress Tracker: `Dev ✅`, `Pre-Commit ✅`, `Committed ✅`.
     Update Session Handoff in Design Document.
     Move to next SF.

Repeat until all sub-features have `Committed ✅`, then proceed to Phase 4.

---

## Phase 4: Completion `[agreed 2026-10-10]`

Only the user says "finished"; until then the feature is "ready for your check"
(`PRINCIPLES.md` §6).

4.1. Verify all Progress Tracker rows are fully `✅`.

4.2. **Closure gate — HARD BLOCK.** Run both. A non-zero exit means the story is NOT finished;
     there is no override:
```
python scripts/check_fr_coverage.py <STORY-ID>
python scripts/tests.py feature <STORY-ID>
```

- The **FR ledger** proves every FR the design declared is owned by an implementation plan *and*
  cited by at least one test file. An uncited FR means either the proof is missing, or the FR was
  silently descoped while the design still claims it. Fix the proof, or delete the row from the
  design's FR table so the descoping is a visible decision.
- **Filing a follow-up ticket does not satisfy this gate.** If an FR is unproven, the story is not
  finished — a new ticket defers the work rather than discharging it. Full contract:
  `.claude/skills/specweaver-ticket/references/closure-contract.md`.
- The **suite** carries the always-on reachability invariants
  (`tests/unit/core/flow/engine/test_handler_reachability.py`): every declared step combination
  resolves to a registered handler, and every bundled pipeline step is executable.

4.3. **Works for real.** The feature ran on a real project with the real tools; one live demo
     command, kept in the design, shows it, and it runs in the nightly real-model run.

4.4. **Docs say what the code does.** Find every related document with
     `grep -rl <ID> docs .agents src` and check each one. Recount the README numbers (tests per
     tier, mutants) in the feature's last commit, before calling it ready.

4.5. **One finished message**, at most 10 lines: the promise; the demo and what it shows; limits
     with decision and date; what was removed; "Sign off?". Then **STOP** and wait.

4.6. **After sign-off:** set Design Document `Status: COMPLETE`, update the Session Handoff and the
     one line in `.agents/STATE.md`, in one commit. End with `Push now: YES`. The user pushes;
     no new feature starts while commits are unpushed.
