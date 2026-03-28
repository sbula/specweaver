---
description: "Phase 1: Intake — read the feature entry and clarify scope with HITL if needed."
---

> [!IMPORTANT]
> **Autonomy vs. HITL:**
> Read and analyze autonomously. STOP only if the feature description has gaps.
> One targeted question per gap. Never assume or guess.

// turbo-all

# Phase 1: Intake

1.1. Read the feature entry. If referenced by ID, read:
     `docs/proposals/roadmap/phase_3_feature_expansion.md`
     and locate the row for this feature. Also read any linked proposal documents.

1.2. Determine whether all of the following are answerable without guessing:

     - **What** does the feature do? (user-facing behavior — what changes for the user)
     - **Why** does it exist? (the problem it solves — what currently doesn't work or is missing)
     - **Boundaries**: what does it touch? What explicitly does it NOT touch?
     - **Constraints**: performance targets, compatibility requirements, scope limits,
       technology mandates, security requirements.

1.3. If ALL of the above are answerable:
     Write a 3–5 sentence working definition using this format:
     ```
     Feature <ID> adds <capability> to <system component>.
     It solves <problem> by <approach>.
     It interacts with <modules/systems> and does NOT touch <out-of-scope areas>.
     Key constraints: <list constraints or "none stated">.
     ```
     Proceed autonomously to Phase 2.

1.4. If ANY of the above is unclear or missing:
     **STOP — HITL gate.**
     Present a numbered list of targeted questions, one per gap.
     Do NOT guess. Do NOT make assumptions.
     **Wait for answers before proceeding.**

> [!CAUTION]
> **HARD GATE:** If the feature description has gaps, you MUST stop and ask.
> Never start research on a poorly defined feature — the entire design will be wrong.
> A vague working definition produces vague requirements, which produce wrong code.

> [!IMPORTANT]
> **CHECKPOINT:** Phase 1 complete. Working definition written.
> Proceed to Phase 2 (Research).
