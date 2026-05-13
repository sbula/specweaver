# Design: Configurable Prompt Render Profiles

- **Feature ID**: C-INTL-05
- **Parent Story**: US-4 (Context-Aware Flow Orchestration)
- **Phase**: Design
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/features/topic_04_intelligence/C-INTL-05/C-INTL-05_design.md

## Feature Overview

Feature C-INTL-05 adds **configurable prompt render profiles** to the `PromptBuilder` / `_prompt_render.py` layer. It solves the Open-Closed Principle violation in the current hardcoded block render sequence by introducing an **Enum-based slot registry** (`PromptSlot`) and a **`RenderProfile` frozen dataclass** as domain-agnostic _mechanisms_ in `infrastructure/llm/`, while the **named profile constants** (FULL, MINIMAL, INTERACTIVE, ARBITER) encoding workflow orchestration _policy_ are owned by `core/flow/handlers/base.py`. This Mechanism/Policy split follows DDD's strict separation of infrastructure adapters from domain knowledge. The feature interacts with `infrastructure/llm/` and `core/flow/handlers/base.py` and does NOT touch `sandbox/*`, `validation/`, or `config/`. Zero new external dependencies are required.

## Research Findings

### Codebase Patterns

#### Current State — The Hardcoded Pipeline

The rendering pipeline in `_prompt_render.py:73-80` defines 6 ordered tags (`instructions`, `dictator-overrides`, `project_metadata`, `constitution`, `standards`, `plan`) followed by inline handling for `topology`, `file`, `mentioned`, `context`, and `reminder` blocks. This is a total of **11 distinct block types**.

**What already exists and can be reused:**

| Component | File | Reuse Potential |
|-----------|------|-----------------|
| `_ContentBlock` dataclass | `prompt_builder.py:47-61` | ✅ **Extend** — add a `slot: PromptSlot` field alongside existing `kind` |
| `_render_tagged_blocks()` | `_prompt_render.py:35-46` | ✅ **Reuse directly** — generic renderer already parameterized by `kind`/`tag` |
| `render_files()` / `_render_mentioned()` | `_prompt_render.py:17-64` | ✅ **Reuse directly** — already isolated rendering functions |
| `_build_base_prompt()` | `core/flow/handlers/base.py:174-232` | ✅ **Refactor** — the `include_rules` boolean becomes a `RenderProfile` enum |
| Hybrid truncation engine | `prompt_builder.py:501-599` | ✅ **Reuse directly** — priority-based truncation is profile-agnostic |
| `PromptBuilder.clone()` | `prompt_builder.py:89-103` | ✅ **Extend** — clone must also copy profile state |

**Callers that will benefit from profiles (refactoring targets):**

| Caller | Current Pattern | Profile Mapping |
|--------|----------------|-----------------|
| `handlers/draft.py:80-84` | `_build_base_prompt(include_rules=False)` | → `RenderProfile.INTERACTIVE` |
| `handlers/generation.py:150-158` | `_build_base_prompt()` + add plan, topology | → `RenderProfile.FULL` |
| `handlers/review.py:162-168` | `_build_base_prompt()` + add topology | → `RenderProfile.FULL` |
| `handlers/review.py:273-280` | `_build_base_prompt()` for code review | → `RenderProfile.FULL` |
| `handlers/generation.py:252-260` | `_build_base_prompt()` for test gen | → `RenderProfile.FULL` |
| `handlers/generation.py:445-455` | `_build_base_prompt()` for plan | → `RenderProfile.FULL` |
| `handlers/arbiter.py:137-144` | Direct `PromptBuilder()` without rules | → `RenderProfile.ARBITER` |
| `workflows/planning/decomposer.py:90-91` | Direct `PromptBuilder()` + instructions + metadata only | → `RenderProfile.MINIMAL` |

**Key Observation — Redundancy Pattern:**
The `include_rules: bool` parameter in `_build_base_prompt()` is a primitive boolean switch that implicitly encodes "profile selection". This is the exact design smell C-INTL-05 eliminates. Today there are effectively 4 implicit profiles scattered across the codebase:
1. **FULL** — constitution + standards + memory + plan + topology (generators, reviewers)
2. **INTERACTIVE** — metadata + memory, no strict rules (drafter)
3. **MINIMAL** — instructions + metadata only (decomposer, planner)
4. **ARBITER** — instructions + context only, no rules/memory (arbiter)

**Boundary Constraints (from `context.yaml` files):**
- `infrastructure/llm/context.yaml`: archetype `adapter`, consumes `specweaver/config`, forbids `specweaver/sandbox/*`. **Mechanism types** (`PromptSlot` enum, `RenderProfile` dataclass) live here — they are domain-agnostic data structures.
- `core/flow/handlers/` context: archetype `orchestrator`, consumes `specweaver/llm`. **Policy constants** (the 4 named profile instances: `FULL`, `MINIMAL`, `INTERACTIVE`, `ARBITER`) live here — they encode workflow orchestration knowledge about which handlers need which context. This follows the existing IoC pattern (like `skeleton_files` injection).
- `workflows/planning/context.yaml`: archetype `orchestrator`, consumes `specweaver/llm` but does **NOT** consume `specweaver/flow`. The `FeatureDecomposer` must receive a pre-built `PromptBuilder` via DI from its calling handler (`DecomposeFeatureHandler` in `core/flow/handlers/`), NOT call `_build_base_prompt()` itself.
- No new module dependencies are introduced. This is a purely internal refactoring.

#### Refactoring ROI Analysis

| Refactoring Opportunity | Impact | Effort | ROI |
|------------------------|--------|--------|-----|
| **Replace `include_rules: bool` with `RenderProfile` enum** | 🟢 HIGH — eliminates implicit profile encoding, self-documenting code | 🟢 LOW — 7 callsites, mechanical substitution | ⭐⭐⭐⭐⭐ |
| **Extract `ordered_tags` from `render_blocks()` into profile-driven slot ordering** | 🟢 HIGH — OCP-compliant, adding new slots requires zero code changes to renderer | 🟢 LOW — one-time extraction, slot enum carries ordering metadata | ⭐⭐⭐⭐⭐ |
| ~~**Formalize 2-Tier Handover in builder API**~~ | ~~🟡 MEDIUM~~ | ~~🟢 LOW~~ | ❌ DROPPED — DDD audit: tier semantics are domain knowledge, not infrastructure. The profile system already controls tier inclusion via slot membership. No dedicated methods needed. |
| **Remove ad-hoc profile construction in `arbiter.py` and `decomposer.py`** | 🟡 MEDIUM — both bypass `_build_base_prompt()` entirely, creating maintenance islands | 🟡 MEDIUM — Arbiter handler calls `_build_base_prompt(profile=ARBITER)`. Decomposer receives pre-built PromptBuilder via IoC from `DecomposeFeatureHandler` | ⭐⭐⭐⭐ |
| **Future-proof for RAG, Conversation Summarization, and new context sources** | 🟢 HIGH — C-INTL-04 (Conversation Summarization) and B-FLOW-04 (Hybrid RAG) both need new XML slots | 🟢 LOW — just add new `PromptSlot` enum variants, no render code changes | ⭐⭐⭐⭐⭐ |

**Downstream features that directly profit:**
- `C-INTL-04` (Conversation Summarization) — needs a new `summary` slot
- `B-FLOW-04` (Hybrid RAG Orchestration) — needs `rag_context` slot
- `A-INTL-04` (Memory Consolidation) — needs `consolidated_memory` slot
- `D-INTL-04` (Design Questionnaire) — needs `questionnaire_state` slot

### External Tools

| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| Python `enum.Enum` | 3.11+ (stdlib) | Standard Enum with rich attributes | Built-in |
| Pydantic v2 | 2.x (already in `pyproject.toml`) | BaseModel for RenderProfile definitions if needed | Already a dependency |

No new external dependencies. This feature is entirely stdlib + Pydantic-based.

### Blueprint References

**LangChain `ChatPromptTemplate` (2025):** Composition via operator overloading (`+`), `MessagesPlaceholder` for slot injection, `configurable_fields` for runtime swapping. Relevant pattern: treating prompt sections as composable, independently configurable units.

**Aider's Repo Map (2025):** Dynamic context sizing using graph-ranking. Relevant pattern: dynamic budget-based context scaling (already implemented in SpecWeaver's `_compute_auto_scale`). Aider's approach validates our existing proportional truncation strategy.

**DSPy Signatures (2025):** Typed input/output contracts for prompt modules. Relevant pattern: declarative "what goes in" vs "what comes out" specifications. Validates the `PromptSlot` enum approach — each slot is a typed, declared input to the LLM.

### Pros / Cons Analysis

| | Pros | Cons |
|---|------|------|
| **Do It Now** | Eliminates maintenance bottleneck before C-INTL-04 and B-FLOW-04 arrive; reduces technical debt; all callers benefit immediately; self-documenting profile names | Moderate refactoring effort across 7+ callsites; requires careful backwards compatibility |
| **Defer** | No immediate work | Every new context source (RAG, summaries, questionnaire) must modify the hardcoded list again; `include_rules` boolean proliferates further; arbiter/decomposer remain maintenance islands |

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | PromptSlot Enum Registry | `infrastructure/llm/` | Define all valid prompt block slots as a `str` Enum where the string value IS the XML tag name (e.g., `PromptSlot.CONSTITUTION = "constitution"`). This eliminates any implicit `kind ↔ slot` mapping — `block.kind = slot.value` is a direct, type-safe comparison | Adding a new slot requires only a new enum variant; no changes to render logic |
| FR-2 | RenderProfile Mechanism | `infrastructure/llm/` | Define the `RenderProfile` frozen dataclass (mechanism) with `name`, `active_slots`, and `order` fields | Domain-agnostic type definition; contains no workflow-specific knowledge |
| FR-3 | Named Profile Constants (Policy) | `core/flow/handlers/_profiles.py` | Define 4 named profile constants (`FULL`, `MINIMAL`, `INTERACTIVE`, `ARBITER`) that declare which `PromptSlot`s are active and their rendering order | Profile constants encode workflow orchestration policy and live in the orchestrator layer, not infrastructure |
| FR-4 | Profile-Driven Rendering | `_prompt_render.py` | Two-phase rendering: (1) Build-time: `add_*` methods skip inactive slots, so only active blocks are stored in `_blocks`. (2) Render-time: `render_blocks()` accepts the profile's `order: tuple[PromptSlot, ...]` alongside the blocks list and iterates over slots in that sequence, replacing the hardcoded `ordered_tags` list | `render_blocks(blocks, order)` renders blocks in profile-defined sequence |
| FR-5 | PromptBuilder Profile Initialization | `PromptBuilder.__init__()` | Accept an optional `profile: RenderProfile | None` parameter (default `None`). When `None`, all slots are active with current hardcoded ordering. Inactive slot additions emit `logger.debug()`. **I/O-bound `add_*` methods (`add_file`, `add_mentioned_files`) MUST early-return before any disk I/O when the slot is inactive.** Modify `add_context` to accept `slot`. **`PromptBuilder.clone()` MUST explicitly propagate `self._profile` to the new instance** | All `add_*` methods validate slot activity via `_is_slot_active()`. Clones inherit the exact profile state of their parent |
| FR-6 | `_build_base_prompt()` Refactoring | `core/flow/handlers/base.py` | Replace the `include_rules: bool` parameter with `profile: RenderProfile` | All handler callsites pass an explicit profile constant instead of a boolean flag |
| FR-7 | Arbiter Handler Unification | `ArbitrateVerdictHandler` | Replace direct ad-hoc `PromptBuilder()` construction with `_build_base_prompt(profile=ARBITER)` | Arbiter handler flows through the centralized assembly function |
| FR-8 | Decomposer IoC Injection | `DecomposeFeatureHandler` + `FeatureDecomposer` | `DecomposeFeatureHandler` calls `_build_base_prompt(profile=MINIMAL)` and passes the resulting `PromptBuilder` into `FeatureDecomposer.decompose(base_prompt=...)` via DI | Decomposer receives a pre-built PromptBuilder; no illegal `workflows/planning/` → `core/flow/handlers/` dependency |
| FR-9 | Backward Compatibility | All callers | Existing `PromptBuilder()` construction without a profile parameter uses an internal all-slots-active default (no import from `core/flow/`). Emits a deprecation `logger.warning()` to encourage explicit profile adoption | Zero breaking changes for callers that don't opt into profiles. Deprecation path documented |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Performance | Zero measurable latency regression. Enum lookup is O(1). **Critical**: Expensive context gathers MUST be pre-gated by checking `slot in profile.active_slots` to avoid blocking I/O for inactive slots. This applies both to `_build_base_prompt` (DB hydration) AND to `add_*` methods with disk I/O (`add_file`, `add_mentioned_files`) |
| NFR-2 | Architectural Boundary | Mechanism types (`PromptSlot`, `RenderProfile`) in `infrastructure/llm/`. Policy constants (profile instances) in `core/flow/handlers/_profiles.py`. `infrastructure/llm/context.yaml` MUST add `PromptSlot` and `RenderProfile` to the `exposes` list. No new `consumes` or `forbids` entries required |
| NFR-3 | Test Coverage | 70–90% coverage on new code. All 4 profiles must have dedicated unit tests verifying correct slot inclusion/exclusion. Additionally: 2 integration tests verifying profile × truncation interaction (MINIMAL under tight budget, FULL with priority-based slot dropping) |
| NFR-4 | Backward Compatibility | `PromptBuilder()` without profile argument must produce identical output to current behavior |
| NFR-5 | Extensibility | Adding a new prompt slot using **standard tagged block rendering** requires: (a) one new `PromptSlot` enum entry, (b) adding it to relevant profiles. Zero changes to `_prompt_render.py`. Slots requiring **custom rendering logic** (e.g., custom XML attributes, per-item formatting) additionally need a dedicated render function in `_prompt_render.py` |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| Python stdlib `enum` | 3.11+ | str Enum | ✅ | Already using Python 3.13 |
| Pydantic v2 | 2.x | BaseModel (optional) | ✅ | Already in pyproject.toml |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | **Mechanism/Policy Split**: `PromptSlot` enum + `RenderProfile` dataclass (mechanism) live in `infrastructure/llm/`. Named profile constants (policy) live in `core/flow/handlers/_profiles.py` | DDD: infrastructure provides domain-agnostic mechanisms; the orchestrator layer encodes workflow-specific policy. Follows existing IoC pattern (like `skeleton_files` injection). No new `consumes`/`forbids` entries needed — `flow` already consumes `llm` | No |
| AD-2 | `PromptSlot` is a `str` Enum where the string value IS the XML tag name | `PromptSlot.CONSTITUTION = "constitution"`, etc. This makes `block.kind = slot.value` a direct, type-safe comparison — no implicit mapping layer needed. **It does NOT carry sequence metadata.** The `RenderProfile.order` tuple is the sole source of truth for rendering sequence | No |
| AD-3 | `RenderProfile` is a simple frozen dataclass with `name: str`, `active_slots: frozenset[PromptSlot]`, `order: tuple[PromptSlot, ...]` | Immutable by design. The dataclass is domain-agnostic — it knows about slots and ordering, not about workflow semantics | No |
| AD-4 | `_build_base_prompt()` signature changes from `include_rules: bool` to `profile: RenderProfile` with a default of the `FULL` constant | Replaces implicit boolean encoding with self-documenting profile. The old boolean mapped to exactly 2 profiles (FULL vs INTERACTIVE) | No |
| AD-5 | `ArbitrateVerdictHandler` will call `_build_base_prompt(profile=ARBITER)` instead of constructing `PromptBuilder()` ad-hoc | Both `ArbitrateVerdictHandler` and `_build_base_prompt()` live in `core/flow/handlers/`, so this is a legal same-layer refactoring | No |
| AD-6 | `DecomposeFeatureHandler` (in `core/flow/handlers/`) pre-builds the PromptBuilder via `_build_base_prompt(profile=MINIMAL)` and injects it into `FeatureDecomposer.decompose(base_prompt=...)` | DDD IoC: `workflows/planning/` does NOT consume `specweaver/flow`, so the Decomposer cannot call `_build_base_prompt()` directly. The handler (which IS in `flow`) injects the pre-built builder. This follows the established `skeleton_files` and `project_metadata` injection pattern | No |
| AD-7 | **No tier-specific methods** on `PromptBuilder`. The 2-Tier Handover standard is enforced by profile slot membership, not by dedicated `add_tier1/2_context()` methods | DDD: the "2-Tier Handover" is domain knowledge from D-INTL-06. The infrastructure `PromptBuilder` must remain domain-agnostic. Callers use `add_context()` with appropriate priority; the profile controls which slots are rendered | No |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Adding New Prompt Slots | How to add a new PromptSlot enum variant and register it in the appropriate RenderProfiles | ✅ [adding_prompt_slots.md](../../../../dev_guides/adding_prompt_slots.md) |

## Sub-Feature Breakdown

### SF-1: Slot Registry & Profile Mechanism
- **Scope**: Define the `PromptSlot` enum and `RenderProfile` frozen dataclass (mechanism types, with `__post_init__` validation that `order ⊆ active_slots`) in `infrastructure/llm/`. Define the 4 named profile constants (policy) in `core/flow/handlers/_profiles.py`:
  - `FULL`: All slots
  - `MINIMAL`: `{INSTRUCTIONS, METADATA, TOPOLOGY}`
  - `INTERACTIVE`: `{INSTRUCTIONS, DICTATOR_OVERRIDES, METADATA, PLAN, TOPOLOGY, FILE, MENTIONED, CONTEXT, REMINDER, AGENT_MEMORY}` (all slots except `CONSTITUTION` and `STANDARDS`)
  - `ARBITER`: `{INSTRUCTIONS, CONTEXT}`
- **FRs**: [FR-1, FR-2, FR-3, FR-9]
- **Inputs**: Current hardcoded block kinds from `_prompt_render.py`
- **Outputs**: `PromptSlot` enum + `RenderProfile` dataclass in `infrastructure/llm/_prompt_profiles.py`. Profile constants (`FULL`, `MINIMAL`, `INTERACTIVE`, `ARBITER`) in `core/flow/handlers/_profiles.py`
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_04_intelligence/C-INTL-05/C-INTL-05_sf1_implementation_plan.md

### SF-2: Profile-Driven Rendering & Builder Refactoring
- **Scope**: Refactor `PromptBuilder` and `_prompt_render.py` to use profiles for slot selection and rendering order. Refactor `_build_base_prompt()` signature to accept `profile: RenderProfile`.
- **FRs**: [FR-4, FR-5, FR-6]
- **Inputs**: `PromptSlot` enum, `RenderProfile` dataclass, and profile constants from SF-1
- **Outputs**: Profile-aware `PromptBuilder`, profile-driven `render_blocks()`, refactored `_build_base_prompt()`
- **Depends on**: SF-1
- **Impl Plan**: docs/roadmap/features/topic_04_intelligence/C-INTL-05/C-INTL-05_sf2_implementation_plan.md

### SF-3: Caller Migration & Unification
- **Scope**: Migrate all handler callsites to use explicit profiles. Refactor `ArbitrateVerdictHandler` to call `_build_base_prompt(profile=ARBITER)`. Refactor `DecomposeFeatureHandler` to pre-build PromptBuilder and inject into `FeatureDecomposer` via DI.
- **FRs**: [FR-7, FR-8]
- **Inputs**: Refactored `_build_base_prompt()` API from SF-2
- **Outputs**: All 8+ callsites using explicit `RenderProfile` constants. Arbiter handler uses centralized assembly. Decomposer receives pre-built PromptBuilder via IoC.
- **Depends on**: SF-2
- **Impl Plan**: docs/roadmap/features/topic_04_intelligence/C-INTL-05/C-INTL-05_sf3_implementation_plan.md

## Execution Order

1. **SF-1** (no deps — start immediately): Pure data definitions, zero side effects
2. **SF-2** (depends on SF-1): Core refactoring of the render pipeline and builder
3. **SF-3** (depends on SF-2): Mechanical caller migration across all handler files

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------| 
| SF-1 | Slot Registry & Profile Mechanism | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-2 | Profile-Driven Rendering & Builder Refactoring | SF-1 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-3 | Caller Migration & Unification | SF-2 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: SF-2 Pre-Commit Quality Gate Complete.
**Next step**: Run `/implementation-plan` workflow for SF-3.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and resume from there using the appropriate workflow.
