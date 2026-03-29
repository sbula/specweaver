---
description: "Phase 5: Document — write the fully self-contained Design Document and get mandatory HITL approval before any implementation plan begins."
---

> [!IMPORTANT]
> **Autonomy vs. HITL:**
> Write the document autonomously using the template below.
> The HITL approval gate at the end is MANDATORY and always fires.
> Do NOT run /implementation-plan until the user explicitly approves.

// turbo-all

# Phase 5: Document

---

## Write the Design Document

5.1. Write the Design Document to:
     `docs/proposals/design/phase<X>/<feature_id>_design.md`
     Create the directory if it does not exist.

5.2. The document MUST be fully self-contained. An agent starting a brand-new
     session with zero prior context must be able to:
     - Understand the complete feature and its rationale
     - Find the current status by reading the Progress Tracker
     - Know exactly which workflow to run and with which arguments
     - Continue from where work stopped, without asking anyone

5.3. Use this exact structure. All sections are mandatory.
     (For non-decomposed features, use "Single feature — no decomposition."
     in the Sub-Feature Breakdown and Execution Order sections.)

````markdown
# Design: <Feature Name>

- **Feature ID**: <feature_id>
- **Phase**: <X>
- **Status**: DRAFT
- **Design Doc**: docs/proposals/design/phase<X>/<feature_id>_design.md

## Feature Overview

<3–5 sentence working definition from Phase 1 intake>

## Research Findings

### Codebase Patterns
<What already exists, what can be reused, which modules will be touched,
what boundary rules constrain the design>

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|

### Blueprint References
<Links from ORIGINS.md or other reference implementations, if any>

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | ... | ... | ... | ... |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | ... | ... |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | ... | ... | No |
| AD-2 | ... | ... | Yes — approved by <user> on <date> |

## Sub-Feature Breakdown

*(Use "Single feature — no decomposition." if not split.)*

### SF-1: <Name>
- **Scope**: <one sentence describing this SF's sole responsibility>
- **FRs**: [FR-1, FR-3, FR-7]
- **Inputs**: <what this SF receives — from prior SFs, CLI, DB, files, env>
- **Outputs**: <what this SF produces — for later SFs, the system, or the user>
- **Depends on**: none
- **Impl Plan**: docs/proposals/roadmap/phase<X>/<feature_id>_sf1_implementation_plan.md

### SF-2: <Name>
- **Scope**: ...
- **FRs**: [FR-2, FR-4]
- **Inputs**: ...
- **Outputs**: ...
- **Depends on**: SF-1
- **Impl Plan**: docs/proposals/roadmap/phase<X>/<feature_id>_sf2_implementation_plan.md

## Execution Order

<Topological sort. Note which SFs can run in parallel.>

Example:
1. SF-1 (no deps — start immediately)
2. SF-2 and SF-3 in parallel (both depend only on SF-1)
3. SF-4 (depends on SF-2 and SF-3)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | <name> | — | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-2 | <name> | SF-1 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: Design DRAFT — awaiting HITL approval.
**Next step**: After approval, run:
`/implementation-plan docs/proposals/design/phase<X>/<feature_id>_design.md SF-1`
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜
in any row and resume from there using the appropriate workflow.
````

---

## HITL Gate (Mandatory — Always Fires)

5.4. Before presenting the document to the user, evaluate and present the following critical reflection questions:
     - **Open Questions**: Are there still open questions or unresolved ambiguities? If yes, provide for each:
       - Options for resolution
       - Pros / Cons of each option
       - Impact / Consequences of each option
       - Your specific proposal/recommendation
     - **Agent Handoff Risk**: If a new agent in a new session were to continue starting *only* with this document:
       - Are there possible misunderstandings?
       - Are there open points the new agent would have to guess or assume?
       - Bring up your own critical questions that a fresh agent would stumble on.

5.5. Present the completed Design Document AND your answers to the reflection questions above to the user.
     **STOP. Wait for explicit approval.**
     Do NOT proceed to any implementation plan until the user confirms.

5.6. On approval:
     - Set `Status: APPROVED` in the header block.
     - Update Session Handoff: replace "awaiting HITL approval" with "Design APPROVED on <date>."
     - Save the updated document.

> [!CAUTION]
> **HARD GATE:** The design MUST be explicitly approved before any implementation
> plan begins. A DRAFT design is not sufficient. No exceptions.

> [!IMPORTANT]
> **CHECKPOINT:** Phase 5 complete. Design Document is APPROVED and saved.
> Inform the user to run `/implementation-plan <design_doc_path> SF-1`
> or `/feature <feature_id>` to continue.
