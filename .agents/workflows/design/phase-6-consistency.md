---
description: "Phase 6: Final Consistency Check — answer reflection questions and get mandatory HITL approval before design is finalized."
---

> [!CAUTION]
> **NO SHELL COMPOUNDING & NO PIPES**: You are strictly forbidden from combining commands using shell operators (`&&`, `||`, `;`, `|`, `>`) or using inline scripts like `python -c`. The secure sandbox blocks these and demands HITL approval. Execute EACH command as a SEPARATE `run_command` tool call or write a `.py` script and run it.

> [!IMPORTANT]
> **Autonomy vs. HITL:**
> Answer the consistency questions autonomously with evidence.
> The HITL approval gate is MANDATORY and always fires.
> The design MUST NOT be marked APPROVED without explicit user approval here.

// turbo-all

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

6.2. **Agent Handoff Risk**: If a new agent in a new session were to continue starting *only* with the Design Document:
      - Are there possible misunderstandings?
      - Are there open points the new agent would have to guess or assume?
      - Bring up your own critical questions that a fresh agent would stumble on.

6.3. **Architecture and future compatibility**: Does the design respect all `context.yaml` dependency rules and support upcoming roadmap features?
     Verify and provide evidence for:
     - Component archetypes (e.g. `cli/` forbids `loom/*`)
     - Compatibility with at least the next 2–3 features on the roadmap
     - Is there an Architectural Switch that wasn't approved?

6.4. **Internal consistency**: Does the design contradict itself anywhere?
     Check that:
     - Union of all sub-feature FR subsets = 100% of top-level FRs
     - Every Sub-Feature has clearly defined inputs and outputs
     - The Execution Order strictly honors the declared dependency graph (DAG)

---

## HITL Gate (Mandatory — Always Fires)

6.5. Present the answers to all four questions to the user.
     **STOP. Wait for explicit approval before finalizing the design.**

6.6. On approval:
     - Set `Status: APPROVED` in the Design Document header block.
     - Update the **Session Handoff** paragraph in the Design Document
       to name the next concrete step (e.g., "Run `/implementation-plan` for SF-1").

> [!CAUTION]
> **HARD GATE:** The design MUST NOT be marked `APPROVED` until the user explicitly approves
> this consistency check. A design with open questions or contradictions will produce
> a broken implementation plan. This gate exists to catch those before any planning begins.

> [!IMPORTANT]
> **CHECKPOINT:** Phase 6 complete. Design Document is APPROVED.
> Inform the user to run `/implementation-plan <design_doc_path> SF-1`
> or `/feature <feature_id>` to continue.
