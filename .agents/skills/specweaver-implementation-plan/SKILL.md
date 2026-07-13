---
name: specweaver-implementation-plan
description: "Create or audit an implementation plan for a sub-feature. Deep research, audit across 16 categories, architecture verification, Red/Blue team analysis, consistency check. Use when the user asks to create an implementation plan, plan a sub-feature, or prepare for development."
---

# Implementation Plan Skill

```
Trigger: "implementation plan for <feature_id> <sf_id>",
         "plan <feature_id> SF-<N>", "prepare implementation for <feature_id>"
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
> This skill has 6 phases that MUST be executed in strict order.
> Every phase MUST be completed before moving to the next one.
>
> **Before starting each phase:**
> 1. Read the phase file from the `references/` directory listed below.
> 2. Complete every step in that phase before moving on.
>
> **Phases 4 and 5 have HITL gates** — you MUST stop and wait for the user.
> Phase 4: present all audit + arch findings (always fires).
> Phase 5: final consistency approval (always fires).

> [!IMPORTANT]
> **Autonomy vs. HITL:**
> Execute research, audit, and architecture verification autonomously.
> STOP only at the defined HITL gates (Phases 4 and 5). Never bypass them.

> [!CAUTION]
> **CODE DETAIL LIMIT: pseudocode and short snippets only — NEVER a full-fledged class or algorithm.**
>
> An implementation plan may include:
> - Short illustrative snippets (a few lines) showing a signature, a call shape, or one
>   tricky bit of logic worth pinning down (e.g. "reject PATH case-insensitively: `key.upper() == \"PATH\"`").
> - Pseudocode describing the sequence of steps/checks an implementation must perform,
>   and in what order, with the reasoning for that order.
> - Exact signatures pulled from *existing* code being called or subclassed (these are
>   research findings, not authored code — quoting `SubprocessExecutor.execute()`'s real
>   signature is fine; writing out `BashActionAtom`'s entire `run()` body is not).
>
> An implementation plan must NEVER include a complete, ready-to-paste class body,
> a fully worked algorithm, or anything a developer could copy verbatim into the
> source file without doing any of their own implementation work. Writing the real
> code is the **`dev` skill's** job — driven test-first (red → green → refactor) from
> the FRs and test plan this document specifies. A plan that pre-writes the
> implementation defeats TDD (tests get written to match code that already exists in
> the plan, not the other way around) and produces two competing sources of truth that
> drift the moment the `dev` skill's tests force a different shape.
>
> If you catch yourself writing a full method body with every branch fleshed out,
> STOP — collapse it back down to an ordered list of checks/steps (pseudocode) and
> move any signature-level detail into the Research Notes as a cited fact, not
> authored code.

## MCP Tool Guidance

When available, prefer these MCP tools over grep/file-reading:

- **Architecture verification (Phase 3):** Use `codebase-memory` → `get_architecture` and `trace_path` to verify dependency chains and layer boundaries.
- **Identifying existing patterns (Phase 0-1):** Use `codebase-memory` → `search_graph` to find similar implementations in the codebase.
- **API surface validation:** Use `context7` → `get-library-docs` to verify library APIs referenced in the plan are correct.
- **Fall back to grep/file-reading** if MCP tools are unavailable.

## Phases


| Phase | File | Description | HITL Gate? |
|-------|------|-------------|------------|
| **0** | `.agents/skills/specweaver-implementation-plan/references/phase-0-research.md` | Deep codebase + external API + guides research | No |
| **1** | `.agents/skills/specweaver-implementation-plan/references/phase-1-preparation.md` | Read design doc + architecture + cross-ref codebase | No |
| **2** | `.agents/skills/specweaver-implementation-plan/references/phase-2-audit.md` | Identify all open questions across 16 categories | No |
| **3** | `.agents/skills/specweaver-implementation-plan/references/phase-3-architecture.md` | Architecture verification — feeds Phase 4 | No |
| **4** | `.agents/skills/specweaver-implementation-plan/references/phase-4-merge.md` | Present combined findings → HITL → merge into plan | ⚠️ Always |
| **5** | `.agents/skills/specweaver-implementation-plan/references/phase-5-consistency.md` | Consistency + Red/Blue + HITL approval | ⚠️ Always |

**After Phase 5 approval:**
- Mark `Impl Plan ✅` for this SF in the Progress Tracker in the Design Document.
- Update the `Session Handoff` paragraph in the Design Document.
