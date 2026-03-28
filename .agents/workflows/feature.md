---
description: "Master feature lifecycle workflow. Orchestrates /design → /implementation-plan (per sub-feature) → /dev (per sub-feature, per commit boundary) → commit. Fully resumable via the Progress Tracker in the Design Document."
---

> [!IMPORTANT]
> **AGENT DIRECTIVE:**
> Execute all research, TDD, and quality checks autonomously.
> STOP only at the explicitly defined HITL gates below.
> Never add extra stops. Never skip a defined gate.
> The Progress Tracker in the Design Document is the single source of truth.
> Always read it at the start of a new session to know where to resume.

// turbo-all

# Feature Lifecycle Workflow

```
Usage:  /feature <feature_id>
```

This workflow orchestrates the complete feature lifecycle from first design to
committed, tested code. It is **fully resumable**: starting it in a new session
automatically continues from where the Progress Tracker shows work stopped.

> [!CAUTION]
> **MANDATORY SEQUENCING — DO NOT SKIP OR REORDER PHASES.**
> Read the Progress Tracker before every decision. Never assume a phase is done.
> Never proceed past a HITL gate without explicit user confirmation.

---

## Phase 1: Design

1.1. Locate the Design Document:
     `docs/proposals/design/phase<X>/<feature_id>_design.md`

1.2. If it exists and `Status: APPROVED`:
     Read it fully. Extract the sub-feature list and dependency graph.
     Skip to Phase 2. Design is already done.

1.3. If it does not exist or `Status: DRAFT`:
     Read `.agents/workflows/design.md` and execute the full `/design` workflow.
     **STOP at Phase 5 HITL gate.** Wait for user approval.
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

2.3. Read `.agents/workflows/implementation-plan.md` and execute the full
     `/implementation-plan` workflow for this SF.
     Output: `docs/proposals/roadmap/phase<X>/<feature_id>_sf<N>_implementation_plan.md`
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
     Read `.agents/workflows/dev.md` and execute the full `/dev` workflow.

     Inside `/dev`, for **each commit boundary** defined in `task.md`:
     - Complete all TDD tasks in this batch autonomously (red → green → refactor).
     - Execute the full `/pre-commit` workflow (phases 1–7).
       **STOP at `/pre-commit` Phase 1 HITL gate** if arch violations found.
       **STOP at `/pre-commit` Phase 3 HITL gate** (test gap — always fires).
     - **COMMIT BOUNDARY — HARD STOP (HITL):**
       Inform the user: "Commit boundary N of M for SF-<X> is ready."
       State: tasks included, test count, what's in this commit.
       **WAIT** for the user to commit or give explicit permission.
       Do NOT proceed to the next task batch until confirmed.

3.4. After the final commit boundary for this SF:
     Update Progress Tracker: `Dev ✅`, `Pre-Commit ✅`, `Committed ✅`.
     Update Session Handoff in Design Document.
     Move to next SF.

Repeat until all sub-features have `Committed ✅`, then proceed to Phase 4.

---

## Phase 4: Completion

4.1. Verify all Progress Tracker rows are fully `✅`.
4.2. Update Design Document `Status: COMPLETE`.
4.3. Update Session Handoff: "Feature complete. Ready for dogfood + merge."
4.4. Inform the user:
     - All commits included in this feature
     - Sub-features delivered
     - Suggested next steps: dogfood, validate, merge
