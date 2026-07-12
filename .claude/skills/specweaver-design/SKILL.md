---
name: specweaver-design
description: "Feature design skill. Intake → Research → Feature Detail → Decompose → Document → Consistency Check. Produces a self-contained Design Document with Progress Tracker. Use when the user asks to design a feature, create a design document, or analyze requirements for a feature."
---

# Design Skill

```
Trigger: "design <feature_id>", "create design for <feature_id>",
         "design document for <feature_id>", "analyze requirements for <feature_id>"
```

Output: `docs/roadmap/features/[Topic]/[ID]/[ID]_design.md`

> [!CAUTION]
> **MANDATORY SEQUENCING — DO NOT SKIP OR REORDER PHASES.**
>
> This skill has 6 phases that MUST be executed in strict order.
> Every phase MUST be completed before moving to the next one.
>
> **Before starting each phase:**
> 1. Read the phase file from the `references/` directory listed below.
> 2. Complete every step in that phase before moving on.
> 3. Never skip a phase, even if the feature seems simple.
>
> **Phases 1, 3, and 6 have HITL gates** — you MUST stop and wait for the user.
> Phase 1 gate fires only if the feature description is ambiguous.
> Phase 3 gates fire on gaps, API conflicts, or architectural switches.
> Phase 6 gate fires always — the design MUST be approved before planning begins.

> [!IMPORTANT]
> **Autonomy vs. HITL:**
> Execute all research and analysis autonomously.
> STOP only at the defined HITL gates. Never add extra stops.

## MCP Tool Guidance

When available, prefer these MCP tools over grep/file-reading for code discovery:

| Tool | When to use | Instead of |
|------|------------|------------|
| `codebase-memory` → `search_graph` | Find functions, classes, routes by name | `grep` across source files |
| `codebase-memory` → `trace_path` | Trace call chains and dependencies | Reading files one-by-one |
| `codebase-memory` → `get_architecture` | Understand module structure | Reading every context.yaml |
| `context7` → `resolve-library-id` + `get-library-docs` | Get correct API syntax for libraries (Pydantic, SQLAlchemy, Typer, etc.) | Guessing from training data |

> If these tools are unavailable (e.g., MCP not configured), fall back to grep/file-reading normally.

## Phases


| Phase | File | Description | HITL Gate? |
|-------|------|-------------|------------|
| **1** | `.agents/skills/specweaver-design/references/phase-1-intake.md` | Read feature entry + clarify scope | ⚠️ If unclear |
| **2** | `.agents/skills/specweaver-design/references/phase-2-research.md` | Parallel: codebase + internet research + ROI | No |
| **3** | `.agents/skills/specweaver-design/references/phase-3-detail.md` | FR/NFR + API validation + arch alignment | ⚠️ On gap or arch switch |
| **4** | `.agents/skills/specweaver-design/references/phase-4-decompose.md` | Sub-feature breakdown + dependency graph | No |
| **5** | `.agents/skills/specweaver-design/references/phase-5-document.md` | Write design.md | No |
| **6** | `.agents/skills/specweaver-design/references/phase-6-consistency.md` | Final checks + Red/Blue + HITL approval | ⚠️ Always |

Execute each phase by reading its file and following the instructions exactly.
