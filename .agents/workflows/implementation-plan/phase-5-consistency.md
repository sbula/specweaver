---
description: "Phase 5: Final Consistency Check — answer three evidence-backed questions and get mandatory HITL approval before implementation begins."
---

> [!IMPORTANT]
> **Autonomy vs. HITL:**
> Answer the three questions autonomously with evidence.
> The HITL approval gate is MANDATORY and always fires.
> Implementation MUST NOT begin without explicit user approval here.

// turbo-all

# Phase 5: Final Consistency Check

After all audit findings are merged and the plan is updated, answer these
three questions explicitly. Do NOT just assert "yes" — provide evidence.

---

5.1. **Open questions**: Are there still any unresolved decisions or ambiguities?
     - If yes: list them explicitly with their severity. For each, you MUST provide:
       - Options for resolution
       - Pros / Cons of each option
       - Impact / Consequences of each option
       - Your specific proposal/recommendation
     - If no: state "All decisions are resolved and documented inline in the plan."

5.1a. **Agent Handoff Risk**: If a new agent in a new session were to continue starting *only* with this document:
      - Are there possible misunderstandings?
      - Are there open points the new agent would have to guess or assume?
      - Bring up your own critical questions that a fresh agent would stumble on.

5.2. **Architecture and future compatibility**: Does the plan respect all
     `context.yaml` dependency rules and support upcoming roadmap features?
     Verify and provide evidence for:
     - Import chains (no circular deps introduced)
     - `consumes`/`forbids` rules in all affected modules
     - Compatibility with at least the next 2–3 features on the roadmap

5.3. **Internal consistency**: Does the plan contradict itself anywhere?
     Check that:
     - Every file mentioned in "Proposed Changes" has correct `[NEW]`/`[MODIFY]`/`[DELETE]` tags
     - Every DB migration is reflected in both `_schema.py` AND the affected mixin/database code
     - Every new function/class mentioned in code snippets appears in the verification plan
     - Test names match the code they claim to test

---

## HITL Gate (Mandatory — Always Fires)

5.4. Present the answers to all three questions to the user.
     **STOP. Wait for explicit approval before any implementation begins.**

5.5. On approval:
     - Set `Status: APPROVED` in the impl plan header block.
     - Update the **Progress Tracker** in the Design Document: mark `Impl Plan ✅` for this SF.
     - Update the **Session Handoff** paragraph in the Design Document
       to name the next concrete step (e.g., "Run `/dev` for SF-1 impl plan").

> [!CAUTION]
> **HARD GATE:** Implementation MUST NOT begin until the user explicitly approves
> this consistency check. A plan with open questions or contradictions will produce
> broken or incomplete code. This gate exists to catch those before any code is written.

> [!IMPORTANT]
> **CHECKPOINT:** Phase 5 complete. Implementation plan is APPROVED.
> Inform the user to run `/dev <impl_plan_path>` or continue via `/feature`.
