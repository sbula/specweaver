---
description: Audit an implementation plan for open questions, assumptions, and ambiguities. Usage - /audit-implementation-plan <path-to-plan>
---

# Audit Implementation Plan

The user will provide a path to an implementation plan file as an argument after the slash command.
For example: `/audit-implementation-plan docs/proposals/roadmap/phase_3/feature_3_6_implementation_plan.md`

If no path argument is provided, ask the user which implementation plan to audit.

> [!CAUTION]
> **MANDATORY SEQUENCING — DO NOT SKIP OR REORDER PHASES!**
>
> This workflow has 3 phases that MUST be executed **in strict order**.
> Every phase MUST be completed before moving to the next one.

## Phase 1: Preparation

1.1. **Read the architecture reference** in full:
     ```
     docs/architecture/architecture_reference.md
     ```
     Pay special attention to: module map, dependency rules (`consumes`/`forbids`),
     archetypes, Known Boundary Violations, and Anti-Patterns.

1.2. Read the implementation plan file at the provided path in its entirety.
     If any link or reference is mentioned, also read these.

1.3. Cross-reference the plan against:
     - The existing codebase architecture (`context.yaml` files, `flow/models.py`, `flow/handlers.py`)
     - The existing pipeline YAMLs (`pipelines/*.yaml`)
     - Patterns established by completed features (e.g., `feature_3_5_implementation_plan.md`)
     - The roadmap (`phase_3_feature_expansion.md`) for downstream feature dependencies
     - The pre-commit quality gate workflow (`.agents/workflows/pre-commit-test-gap.md`)

## Phase 2: Audit & Analysis

2.1. **Identify every single open question, unresolved decision, silent assumption,
     and ambiguity** in the plan. There is NO LIMIT on the number of questions.
     Surface every one you find. Do NOT guess answers. Do NOT assume defaults.
     Just list the questions.

2.2. For each question, provide:
     - **#**: sequential number
     - **Question**: the specific decision or ambiguity
     - **Options**: concrete alternatives (if identifiable)
     - **Impact**: what breaks or gets harder if we pick wrong
     - **Pros/Cons**: positive and negative impact if we chose this option
     - **Proposal**: what would you chose and why
     - **Severity**: CRITICAL / HIGH / MEDIUM / LOW

2.3. Sort the final list by severity (CRITICAL first), then by impact within
     the same severity level.

2.4. **Categories to audit** (check every one systematically):
     1. **Architecture** — module boundaries, dependency direction, archetype choices, layer placement
     2. **Data model** — Pydantic model fields, what's required vs optional, serialization format, schema evolution
     3. **Storage** — file vs DB vs both, paths, naming conventions, cleanup/garbage collection
     4. **Pipeline integration** — step ordering, gate types, loop targets, skip logic, backward compatibility with existing pipelines
     5. **LLM interaction** — prompt design, structured output parsing, model selection, fallback on parse failure, token cost
     6. **CLI UX** — command names, argument conventions, output format, consistency with existing `sw` commands
     7. **HITL interaction** — review flow, edit capabilities, accept/reject granularity
     8. **Token budget** — size of new content in prompts, priority relative to other blocks, truncation behavior
     9. **Cross-feature dependencies** — interaction with existing and planned features on the roadmap
     10. **Backward compatibility** — existing pipelines, DB migrations, users who don't need/want this feature
     11. **Error handling** — failures at each step, malformed output, partial results, disk/network errors
     12. **External integrations** — SDK maturity, API stability, credential management, fallback when unavailable
     13. **Testing** — what's testable without real LLM calls, fixture strategy, mocking boundaries
     14. **Scope boundaries** — what's explicitly in each sub-phase vs deferred, risk of scope creep
     15. **Documentation** — what needs updating in README, quickstart, test coverage matrix, roadmap

2.5. **Do NOT answer any of the questions. Just list them all.**

## Phase 3: Architecture Verification

3.1. For EACH new or modified module proposed in the plan, verify:
     - **Layer placement**: Does the proposed file live in the correct module per the
       architecture? Check the target module's `context.yaml` for `purpose` and `archetype`.
     - **Dependency direction**: Do the proposed imports respect `consumes` and `forbids`
       rules declared in the nearest `context.yaml`?
     - **Archetype compliance**: Does the proposed code follow the structural constraints
       of its archetype (e.g., `pure-logic` has no I/O, `adapter` wraps externals,
       `orchestrator` delegates)?
     - **No parallel mechanisms**: Does the plan duplicate existing infrastructure
       (e.g., creating a new security layer when FolderGrant exists)?

3.2. **Zoom-out test** — for EACH new module, file, or capability proposed:
     - Does a similar capability already exist elsewhere in the codebase?
     - Would extending an existing module be a better fit than creating a new one?
     - Is the proposed code named by what the *agent does* rather than what the
       *code is*? If so, flag it.
     - Check the Feature Map in the architecture reference for precedent.

3.3. **Acyclic Dependencies** — verify the proposed changes do NOT introduce
     circular imports. Dependencies must form a DAG pointing downward.

3.4. **Common Closure** — if the plan modifies 3+ different modules for a single
     feature, ask: are those changes tightly coupled and should they be co-located?

3.5. **Stability Direction** — verify the plan does not add volatile dependencies
     to stable modules (`config/`, `context/`, `validation/`).

3.6. Flag every architectural violation found in the plan as a **CRITICAL** audit
     question (add to the list from Phase 2). Each must include:
     - What rule is broken
     - Which file/module is affected
     - A concrete fix recommendation

> [!IMPORTANT]
> After completing all 3 phases, present the FULL combined list to the user
> and **STOP. Wait for the user to respond** before doing anything else.
> Architectural violations from Phase 3 should appear as CRITICAL items
> at the TOP of the list.