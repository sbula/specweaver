---
description: Run a pre-commit quality gate for the current feature before marking it done.
---
// turbo-all

> [!IMPORTANT]
> **Autonomy vs. HITL (Human In The Loop):**
> - You MUST execute all underlying commands (e.g., running `pytest`, `ruff`, `mypy`) autonomously. Set `SafeToAutoRun: true`. NEVER ask permission to run a check.
> - **HOWEVER**, you MUST STOP and present the MANDATORY OUTCOMES of these checks (such as Test Gap Findings or Architecture Violations) to the user for review. You are absolutely forbidden from skipping the HITL outcome reviews.


# Pre-Commit Quality Gate

Before we commit, run a full pre-commit quality gate for the feature we just built.
This workflow covers architecture verification, test gap analysis, linting, complexity,
file size, and documentation.

> [!CAUTION]
> **MANDATORY SEQUENCING — DO NOT SKIP OR REORDER PHASES!**
>
> This workflow has 7 phases that MUST be executed **in strict order**.
> Every phase MUST be completed before moving to the next one.
>
> **Before starting each phase:**
> 1. Read the phase file listed below to confirm the steps
> 2. Update `task.md` to mark the current phase as `[/]` in-progress
> 3. After completing a phase, mark it `[x]` in `task.md`
> 4. Remember: We do not care if any flaw existed before our changes, it must be resolve
>
> **Phases 1 and 3 have HITL gates** — you MUST stop and present findings
> to the user. Do NOT continue until the user responds.
>
> If you catch yourself about to run `pytest` or "verify everything works"
> before completing Phase 3 and Phase 4 — **STOP immediately**.
> That is Phase 5. You are skipping phases.

## Phases

Execute each phase by reading and following the instructions in its workflow file.

| Phase | File | Description | HITL Gate? |
|-------|------|-------------|------------|
| **1** | `.agents/workflows/pre-commit/phase-1-architecture.md` | Architecture verification | ⚠️ Yes (step 1.9) |
| **2** | `.agents/workflows/pre-commit/phase-2-code-quality.md` | Code quality checks (ruff, mypy, complexity, file size) | No |
| **3** | `.agents/workflows/pre-commit/phase-3-test-gap.md` | Test gap analysis (coverage matrix + test stories) | ⚠️ Yes (step 3.8) |
| **4** | `.agents/workflows/pre-commit/phase-4-implement-tests.md` | Implement missing tests | No |
| **5** | `.agents/workflows/pre-commit/phase-5-test-suite.md` | Run full test suite | No |
| **6** | `.agents/workflows/pre-commit/phase-6-documentation.md` | Documentation updates | No |
| **7** | `.agents/workflows/pre-commit/phase-7-walkthrough.md` | Write walkthrough artifact | No |

> [!IMPORTANT]
> Every bug, lint error, complexity violation, or oversized file MUST be fixed
> regardless of whether it is pre-existing or introduced by this feature.
> No inherited problems are acceptable!

## Phase 8: Commit Boundary (HITL)

> [!CAUTION]
> **HARD STOP REQUIRED:** You MUST NOT proceed past a commit boundary autonomously.

8.1. After Phase 7 completes, the `/pre-commit` gate is finished.
8.2. **STOP execution**. Inform the user that the pre-commit gate is complete.
8.3. **WAIT** for the user to perform the commit or explicitly tell you to proceed. Do absolutely nothing else.