---
description: "Create or audit an implementation plan — research, audit, merge findings, consistency check. Usage - /implementation-plan <design_doc_path> [<sf_id>]"
---

> [!CAUTION]
> **NO SHELL COMPOUNDING & NO PIPES**: You are strictly forbidden from combining commands using shell operators (`&&`, `||`, `;`, `|`, `>`) or using inline scripts like `python -c`. The secure sandbox blocks these and demands HITL approval. Execute EACH command as a SEPARATE `run_command` tool call or write a `.py` script and run it.

> [!CAUTION]
> **STRICT COMPLIANCE MANDATE:**
> 1. **NO INTERNAL MEMORY RELIANCE:** You are STRICTLY FORBIDDEN from relying on your internal training memory for facts, APIs, designs, or code behavior. Explicit research (files, internet, HITL) is a MUST.
> 2. **NO SKIPPING STEPS:** IT IS STRICTLY FORBIDDEN to skip ANY phase, step, or specific checklist item in this workflow, even if a feature seems "trivially simple". You must execute every single instruction exhaustively.
> 3. **USE .tmp FOR SCRATCHPADS:** All temporary files, debug scripts, or generated data must be stored in the project's `.tmp/` directory. Keep the project root clean.

// turbo-all

> [!IMPORTANT]
> **Autonomy vs. HITL:**
> Execute research, audit, and architecture verification autonomously.
> STOP only at the defined HITL gates (Phases 4 and 5). Never bypass them.

# Implementation Plan Workflow

```
Usage: /implementation-plan <design_doc_path> [<sf_id>]
```

**Pre-conditions — HARD STOP if any fail:**
1. The Design Document at `<design_doc_path>` exists and `Status: APPROVED`.
2. If `<sf_id>` is given: all sub-features in its `depends_on` list have `Impl Plan ✅`
   in the Progress Tracker.
3. If `<sf_id>` is omitted and the design has sub-features: ask the user which sub-feature
   to plan. Do NOT plan all sub-features at once.

**Output header block** — write this at the top of every impl plan produced:
```markdown
# Implementation Plan: <Feature Name> [SF-<N>: <Sub-Feature Name>]
- **Feature ID**: <feature_id>
- **Sub-Feature**: SF-<N> — <name>   (omit line if not decomposed)
- **Design Document**: <design_doc_path>
- **Design Section**: §Sub-Feature Breakdown → SF-<N>  (omit line if not decomposed)
- **Implementation Plan**: <this_file_path>
- **Status**: DRAFT | APPROVED
```

> [!CAUTION]
> **MANDATORY SEQUENCING — DO NOT SKIP OR REORDER PHASES.**
>
> This workflow has 6 phases that MUST be executed in strict order.
> Every phase MUST be completed before moving to the next one.
>
> **Before starting each phase:**
> 1. Read the phase file listed below.
> 2. Complete every step in that phase before moving on.
>
> **Phases 4 and 5 have HITL gates** — you MUST stop and wait for the user.
> Phase 4: present all audit + arch findings (always fires).
> Phase 5: final consistency approval (always fires).

## Phases

| Phase | File | Description | HITL Gate? |
|-------|------|-------------|------------|
| **0** | `.agents/workflows/implementation-plan/phase-0-research.md` | Parallel: deep codebase + external API research | No |
| **1** | `.agents/workflows/implementation-plan/phase-1-preparation.md` | Read design doc + architecture + cross-ref codebase | No |
| **2** | `.agents/workflows/implementation-plan/phase-2-audit.md` | Identify all open questions across 16 categories | No |
| **3** | `.agents/workflows/implementation-plan/phase-3-architecture.md` | Architecture verification — feeds Phase 4 | No |
| **4** | `.agents/workflows/implementation-plan/phase-4-merge.md` | Present combined findings → HITL → merge into plan | ⚠️ Always |
| **5** | `.agents/workflows/implementation-plan/phase-5-consistency.md` | Final consistency check + HITL approval | ⚠️ Always |

**After Phase 5 approval:**
- Mark `Impl Plan ✅` for this SF in the Progress Tracker in the Design Document.
- Update the `Session Handoff` paragraph in the Design Document.