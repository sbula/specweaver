# C-INTL-05: Configurable Prompt Render Profiles

- **Feature ID**: C-INTL-05
- **Parent Story**: US-4 (Context-Aware Flow Orchestration)
- **Phase**: Pending
- **Status**: ANALYSIS GATHERED (DRAFT)
- **Priority**: MEDIUM / POST D-INTL-06

## Discovery Context
This feature was escalated from technical debt during the Phase 4 HITL Gate of `D-INTL-06` (Context Hydration & Handover Engine). A deep dive into rule taxonomy and separation revealed that the current `PromptBuilder` (`infrastructure/llm/prompt_builder.py` and `_prompt_render.py`) uses a **hardcoded block render sequence** to maintain a strict semantic hierarchy of injected context.

While this works for the current 11 fixed context block types, it is not scalable. As we add new intelligence features (e.g., Memory Hydration, RAG Retrieval, Context Enrichers), the static assembly function becomes a maintenance bottleneck and an architectural constraint.

## Current Architecture Analysis

The codebase currently has 4 distinct categories of rules injected into prompts, plus various forms of context. The `PromptBuilder` enforces their priority natively by a hardcoded list in `_prompt_render.py:73-80`:

```
1. instructions          ← What to do (role-specific, per-call)
2. dictator-overrides    ← HITL corrections from prior iterations
3. project_metadata      ← Environment context (Python version, OS, archetype)
4. constitution          ← HUMAN RULES (project-wide, non-negotiable)
5. standards             ← MACHINE-OBSERVED PATTERNS (codebase conventions)
6. plan                  ← IMPLEMENTATION BLUEPRINT (architecture, files, tasks)
7. topology              ← MODULE BOUNDARIES (consumes/forbids/archetype)
8. files                 ← Source files (spec, code, contracts)
9. mentioned_files       ← Auto-detected references from prior LLM output
10. context              ← Free-form context blocks (validation_findings, env_context, agent_memory)
11. reminder             ← Reinforcement instruction at the very end
```

**The Architectural Pain Points:**
1. **Hardcoded Monolith:** Adding any new block type requires modifying the core `_prompt_render.py` file, breaking the Open-Closed Principle.
2. **Inflexible Profiles:** Not all workflows need all slots. For example, `FeatureDecomposer` operates at a high module level and does not need `constitution` or `standards`. Currently, this is handled implicitly by callers simply not adding those blocks, but there is no formal way to define a "Minimal Profile" vs a "Full Profile".
3. **Implicit Tiers:** We have conceptually arrived at a 2-Tier Handover model:
    - **Tier 1 (Strict):** Cross-task handover (e.g. `agent_memory`, `constitution`).
    - **Tier 2 (Relaxed):** Intra-task interactive work (e.g. `validation_findings`).
    Currently, these tiers are not reflected natively in the `PromptBuilder`'s API design; they are just grouped together under a generic `<context>` tag.

## Proposed Solution: Configurable Render Pipeline

Instead of a hardcoded string assembly loop, `PromptBuilder` should utilize a **Configurable Pipeline Engine** for prompt rendering. This brings prompt rendering directly into alignment with the pipeline architecture of US-4.

### 1. Enum-Based Block Registry
Define all valid context slots as an Enum with explicit priority, XML tag mapping, and truncation rules.
```python
class PromptSlot(Enum):
    CONSTITUTION = ("constitution", Priority.MANDATORY, Truncation.NONE)
    STANDARDS = ("standards", Priority.HIGH, Truncation.PROPORTIONAL)
    # ...
```

### 2. Render Profiles
Introduce `RenderProfile` definitions that dictate which slots are active and their relative ordering.
- `RenderProfile.FULL`: Used by `Generator`, `Reviewer`.
- `RenderProfile.MINIMAL`: Used by `Arbiter`, `FeatureDecomposer`.
- `RenderProfile.INTERACTIVE`: Used by `Drafter` (Tier 2 rules active, strict rules minimized).

### 3. Tiers as First-Class Citizens
Replace the generic `add_context()` method with explicit tier injections that reflect the 2-Tier standard natively.

## Implementation Placement & Prioritization

*   **Roadmap Story:** `US-4 (Context-Aware Flow Orchestration)` -> `Sub-Story Add-Ons`
*   **Target Domain:** `src/specweaver/infrastructure/llm`
*   **Dependency:** This feature **strictly depends on the completion of D-INTL-06 SF-2 (Prompt Factory)**. The factory is what centralizes prompt assembly. Once the factory is in place, replacing the `PromptBuilder`'s internals becomes a localized, safe change. Without the factory, applying profiles would require touching all 6 workflow modules again.
*   **When to Implement:** After `US-28` is complete. It is not an immediate blocker for current Intelligence features, but it will become a critical blocker for any future RAG or advanced Context Enrichment epics (which require custom prompt formatting and new XML slots).
