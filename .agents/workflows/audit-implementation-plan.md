---
description: Audit an implementation plan for open questions, assumptions, and ambiguities. Usage - /audit-implementation-plan <path-to-plan>
---

# Audit Implementation Plan

The user will provide a path to an implementation plan file as an argument after the slash command.
For example: `/audit-implementation-plan docs/proposals/roadmap/phase_3/feature_3_6_implementation_plan.md`

If no path argument is provided, ask the user which implementation plan to audit.

## Instructions

1. Read the implementation plan file at the provided path in its entirety. If any link or reference is mentioned, also read these.

2. **Identify every single open question, unresolved decision, silent assumption, and ambiguity** in the plan. There is NO LIMIT on the number of questions. Surface every one you find. Do NOT guess answers. Do NOT assume defaults. Just list the questions.

3. For each question, provide:
   - **#**: sequential number
   - **Question**: the specific decision or ambiguity
   - **Options**: concrete alternatives (if identifiable)
   - **Impact**: what breaks or gets harder if we pick wrong
   - **Severity**: CRITICAL / HIGH / MEDIUM / LOW

4. Sort the final list by severity (CRITICAL first), then by impact within the same severity level.

5. **Categories to audit** (check every one systematically):
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

6. Cross-reference the plan against:
   - The existing codebase architecture (`context.yaml` files, `flow/models.py`, `flow/handlers.py`)
   - The existing pipeline YAMLs (`pipelines/*.yaml`)
   - Patterns established by completed features (e.g., `feature_3_5_implementation_plan.md`)
   - The roadmap (`phase_3_feature_expansion.md`) for downstream feature dependencies
   - The pre-commit quality gate workflow (`.agents/workflows/pre-commit-test-gap.md`)

7. **Do NOT answer any of the questions. Just list them all.**

8. Present the full list to the user and **STOP. Wait for the user to respond** before doing anything else.