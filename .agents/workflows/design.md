---
description: "Feature design workflow. Intake → Research → Feature Detail → Decompose → Document. Produces a self-contained Design Document with Progress Tracker. Usage: /design <feature_id>"
---

> [!CAUTION]
> **STRICT COMPLIANCE MANDATE:**
> 1. **NO INTERNAL MEMORY RELIANCE:** You are STRICTLY FORBIDDEN from relying on your internal training memory for facts, APIs, designs, or code behavior. Explicit research (files, internet, HITL) is a MUST.
> 2. **NO SKIPPING STEPS:** IT IS STRICTLY FORBIDDEN to skip ANY phase, step, or specific checklist item in this workflow, even if a feature seems "trivially simple". You must execute every single instruction exhaustively.

> [!IMPORTANT]
> **Autonomy vs. HITL:**
> Execute all research and analysis autonomously.
> STOP only at the defined HITL gates. Never add extra stops.

// turbo-all

# Design Workflow

```
Usage: /design <feature_id>
```

Output: `docs/proposals/design/phase<X>/<feature_id>_design.md`

> [!CAUTION]
> **MANDATORY SEQUENCING — DO NOT SKIP OR REORDER PHASES.**
>
> This workflow has 5 phases that MUST be executed in strict order.
> Every phase MUST be completed before moving to the next one.
>
> **Before starting each phase:**
> 1. Read the phase file listed below.
> 2. Complete every step in that phase before moving on.
> 3. Never skip a phase, even if the feature seems simple.
>
> **Phases 1, 3, and 5 have HITL gates** — you MUST stop and wait for the user.
> Phase 1 gate fires only if the feature description is ambiguous.
> Phase 3 gates fire on gaps, API conflicts, or architectural switches.
> Phase 5 gate fires always — the design MUST be approved before planning begins.

## Phases

| Phase | File | Description | HITL Gate? |
|-------|------|-------------|------------|
| **1** | `.agents/workflows/design/phase-1-intake.md` | Read feature entry + clarify scope | ⚠️ If unclear |
| **2** | `.agents/workflows/design/phase-2-research.md` | Parallel: codebase + internet research | No |
| **3** | `.agents/workflows/design/phase-3-detail.md` | FR/NFR + API validation + arch alignment | ⚠️ On gap or arch switch |
| **4** | `.agents/workflows/design/phase-4-decompose.md` | Sub-feature breakdown + dependency graph | No |
| **5** | `.agents/workflows/design/phase-5-document.md` | Write design.md + HITL approval | ⚠️ Always |

Execute each phase by reading its file and following the instructions exactly.
