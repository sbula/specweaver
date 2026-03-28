---
description: Create or audit an implementation plan — research, audit, merge findings, consistency check. Usage - /implementation-plan <path-to-plan>
---

# Implementation Plan Workflow

The user will provide a path to an implementation plan file as an argument after the slash command.
For example: `/implementation-plan docs/proposals/roadmap/phase_3/feature_3_12a_implementation_plan.md`

If no path argument is provided, ask the user which implementation plan to audit.

> [!CAUTION]
> **MANDATORY SEQUENCING — DO NOT SKIP OR REORDER PHASES!**
>
> This workflow has 5 phases that MUST be executed **in strict order**.
> Every phase MUST be completed before moving to the next one.
> The final deliverable is a **single self-contained implementation plan** — no separate audit report.

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
     16. **Import chains** — verify no circular imports are introduced; check module-level vs lazy imports

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
     Trace the full import chain for any cross-module references,
     distinguishing module-level imports from lazy (in-function) imports.

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

## Phase 4: Merge Findings Into Plan

After the user has reviewed, answered, or accepted the audit findings:

4.1. **Update the implementation plan** to incorporate all resolved findings.
     - Findings that changed the design → update the relevant plan sections.
     - Findings that are implementation caveats → add as inline `[!CAUTION]`,
       `[!WARNING]`, or `[!NOTE]` alerts next to the relevant code/section.
     - Findings that are deferred → add to the Backlog section.
     - Findings that are rejected or not applicable → discard.

4.2. **Do NOT create a separate audit report.** The implementation plan must be
     the single self-contained document. Another agent or session must be able
     to pick it up and implement it without needing any other context.

4.3. Present the updated plan to the user for review.

## Phase 5: Final Consistency Check

After the audit findings are merged and the plan is updated, answer these
three questions explicitly. Do NOT just assert "yes" — provide evidence.

5.1. **Open questions**: Are there still any unresolved decisions or ambiguities?
     If yes, list them. If no, state that all decisions are made and documented inline.

5.2. **Architecture and future compatibility**: Does the plan respect all
     `context.yaml` dependency rules? Does it support upcoming features on the
     roadmap (downstream consumers like the next planned feature)? Verify:
     - Import chains (no circular deps)
     - `consumes`/`forbids` rules in all affected modules
     - Compatibility with at least the next 2-3 features on the roadmap

5.3. **Internal consistency**: Does the plan contradict itself anywhere?
     Check that:
     - Every file mentioned in "Proposed Changes" has correct `[NEW]`/`[MODIFY]`/`[DELETE]` tags
     - Every DB migration is reflected in both `_schema.py` AND the affected mixin/database code
     - Every new function/class mentioned in code snippets appears in the verification plan
     - Test names match the code they claim to test

> [!IMPORTANT]
> Present the answers to all three questions to the user and **STOP. Wait for
> approval** before proceeding to implementation.