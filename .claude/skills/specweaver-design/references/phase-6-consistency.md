---
description: "Phase 6: Final Consistency Check — FR/NFR completeness, agent handoff, architecture validation, Red/Blue review, and mandatory HITL approval."
---

# Phase 6: Final Consistency Check

After the Design Document is written, evaluate and present the following consistency checks. Do NOT just assert "yes" — provide evidence based on the document you just wrote.

---

6.1. **Open questions**: Are there still open questions or unresolved ambiguities?
     - If yes: list them explicitly with their severity. For each, you MUST provide:
       - Options for resolution
       - Pros / Cons of each option
       - Impact / Consequences of each option
       - Your specific proposal/recommendation
     - If no: state "All design decisions and FRs are fully resolved and unambiguous."

6.1a. **FR/NFR Completeness**: Are ALL Functional Requirements and Non-Functional Requirements explicitly defined?
     - Cross-check against the working definition from Phase 1 — is anything missing?
     - Cross-check against the research findings from Phase 2 — did research reveal requirements not yet captured?
     - Are all NFR thresholds concrete (numbers, not words like "fast" or "good")?
     - If any are missing or vague: list them and propose additions.

6.2. **Agent Handoff Risk**: If a new agent in a new session were to continue starting *only* with the Design Document:
      - Are there possible misunderstandings?
      - Are there open points the new agent would have to guess or assume?
      - Bring up your own critical questions that a fresh agent would stumble on.
      - Would the agent be able to create a complete implementation plan without misinterpreting or forgetting anything?

6.3. **Architecture and future compatibility**: Does the design respect all `context.yaml` dependency rules and support upcoming roadmap features?
     Verify and provide evidence for:
     - Component archetypes (e.g. `cli/` forbids `loom/*`)
     - Compatibility with at least the next 2–3 features on the roadmap
     - Is there an Architectural Switch that wasn't approved?

6.3a. **Re-read ALL `context.yaml` files** for modules that will be touched.
      Confirm the correct placement for every new component. Flag any violations.

6.3b. **Existing feature impact**: Are there already implemented features that should be
      updated or refactored to use this new feature? For each:
      - What is the impact?
      - What is the ROI?
      - Pros / Cons of the refactoring

6.4. **Internal consistency**: Does the design contradict itself anywhere?
     Check that:
     - Union of all sub-feature FR subsets = 100% of top-level FRs
     - Every Sub-Feature has clearly defined inputs and outputs
     - The Execution Order strictly honors the declared dependency graph (DAG)

6.5. **Red/Blue Team Review**: Execute the `specweaver-red-blue-review` skill
     (read `.agents/skills/specweaver-red-blue-review/SKILL.md`) against this design document.
     Focus on: architecture decisions, security boundaries, scalability, and maintainability.
     Run cycles until the continuation thresholds are no longer met (minimum 2 cycles).
     Incorporate any corrections into the design document before presenting to the user.

---

## HITL Gate (Mandatory — Always Fires)

6.6. Present the answers to all checks above to the user, including the Red/Blue Team findings and any corrections made.
     **STOP. Wait for explicit approval before finalizing the design.**

6.7. On approval:
     - Set `Status: APPROVED` in the Design Document header block.
     - Update the **Session Handoff** paragraph in the Design Document
       to name the next concrete step (e.g., "Trigger the implementation-plan skill for SF-1").

> [!CAUTION]
> **HARD GATE:** The design MUST NOT be marked `APPROVED` until the user explicitly approves
> this consistency check. A design with open questions or contradictions will produce
> a broken implementation plan. This gate exists to catch those before any planning begins.

> [!IMPORTANT]
> **CHECKPOINT:** Phase 6 complete. Design Document is APPROVED.
> Inform the user to trigger the implementation-plan skill for the first SF.
