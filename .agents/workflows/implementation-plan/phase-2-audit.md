---
description: "Phase 2: Audit & Analysis — surface every open question, unresolved decision, and ambiguity across 16 categories. No HITL. Feeds Phase 4."
---

> [!IMPORTANT]
> **This phase is fully autonomous. No HITL.**
> Surface every question. Do NOT answer them here.
> All findings feed into Phase 4's single HITL presentation.

// turbo-all

# Phase 2: Audit & Analysis

2.1. **Identify every single open question, unresolved decision, silent assumption,
     and ambiguity** in the plan. There is NO LIMIT on the number of questions.
     Surface every one you find. Do NOT guess answers. Do NOT assume defaults.
     Just list the questions.

2.2. For each question, provide:
     - **#**: sequential number
     - **Question**: the specific decision or ambiguity
     - **Options**: concrete alternatives (if identifiable)
     - **Impact**: what breaks or gets harder if we pick wrong
     - **Pros/Cons**: positive and negative impact for each option
     - **Proposal**: what would you choose and why
     - **Severity**: CRITICAL / HIGH / MEDIUM / LOW

2.3. Sort the final list by severity (CRITICAL first), then by impact within
     the same severity level.

2.4. **Categories to audit** (check every one systematically):

     1. **Architecture** — module boundaries, dependency direction, archetype choices, layer placement
     2. **Data model** — Pydantic model fields, required vs optional, serialization format, schema evolution
     3. **Storage** — file vs DB vs both, paths, naming conventions, cleanup/garbage collection
     4. **Pipeline integration** — step ordering, gate types, loop targets, skip logic, backward compatibility
     5. **LLM interaction** — prompt design, structured output parsing, model selection, fallback, token cost
     6. **CLI UX** — command names, argument conventions, output format, consistency with existing `sw` commands
     7. **HITL interaction** — review flow, edit capabilities, accept/reject granularity
     8. **Token budget** — size of new content in prompts, priority relative to other blocks, truncation behavior
     9. **Cross-feature dependencies** — interaction with existing and planned features on the roadmap
     10. **Backward compatibility** — existing pipelines, DB migrations, users who don't need this feature
     11. **Error handling** — failures at each step, malformed output, partial results, disk/network errors
     12. **External integrations** — SDK maturity, API stability, credential management, fallback when unavailable
     13. **Testing** — what's testable without real LLM calls, fixture strategy, mocking boundaries
     14. **Scope boundaries** — what's explicitly in this sub-feature vs deferred, risk of scope creep
     15. **Documentation** — what needs updating in README, quickstart, test coverage matrix, roadmap
     16. **Import chains** — verify no circular imports are introduced; module-level vs lazy imports

2.5. **Do NOT answer any of the questions. Just list them all.**
     Answers are resolved in Phase 4 after the HITL review.

> [!IMPORTANT]
> **CHECKPOINT:** Phase 2 complete. Audit list ready.
> Proceed to Phase 3 (Architecture Verification).
