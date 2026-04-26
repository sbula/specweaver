# Design: Interactive Gate Variables (HITL)

- **Feature ID**: 3.26c
- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/phase_3/feature_3.26c/feature_3.26c_design.md

## Feature Overview

Feature 3.26c adds support for strictly isolated human `GateType.HITL` rejections into the generation sequence prompts.
It solves the issue where human feedback is sometimes ignored or outweighed by linter errors in loop-back generation sequences by placing that feedback into a `<dictator-overrides>` XML section with the highest priority weighting ("never truncated").
It interacts with `PromptBuilder` and the Flow Engine's pipeline handlers (`_generation.py`, `_draft.py`, etc.), and does NOT touch the underlying LLM structural adapters themselves.
Key constraints: Must use `<dictator-overrides>` XML section, must grant strict promotional weight above standard linter error findings, and must fit seamlessly within the existing adapter archetype.

## Research Findings

### Codebase Patterns
- `src/specweaver/infrastructure/llm/prompt_builder.py` provides an `add_instructions` and similar methods with token-aware truncation logic based on integer priority levels. Priority 0 is "never truncated".
- `context.feedback` is used by the Flow Engine (`src/specweaver/core/flow/runner.py` and `gates.py`) to pipe output from `loop_back` actions to target steps. By modifying handlers (e.g. `GenerateCodeHandler`), this feedback can be unpacked and directed into the prompt.
- The `RunContext` cleanly isolates feedback state, making the implementation natively compatible with the existing `Flow` routing mechanisms without an architectural switch.

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| standard XML | N/A | Format tags | N/A |

### Blueprint References
None specified in ORIGINS.md directly corresponding to `3.26c` beside the top-level roadmap instruction.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | PromptBuilder dictatorial overrides | System | Inject human feedback into `<dictator-overrides>` XML section at priority 0 | The LLM receives the human feedback mathematically bound to ignore context limits. |
| FR-2 | Feedback extraction | Flow Handlers | Extract HITL rejection remarks from `RunContext.feedback` separately from generic automated errors | Human and Linter errors are distinct streams going into the loop-back code generation. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Archetype Strictness | `llm/` module must remain an adapter and forbid `loom/*`. |
| NFR-2 | Extensibility | `<dictator-overrides>` must be compatible with existing Gemini, OpenAI, Claude adapters implicitly. |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| None | N/A | N/A | Y | Pure text manipulation |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Put `add_dictator_overrides` natively on `PromptBuilder` | Keeps prompt token management strictly within `llm/` archetype. | No |
| AD-2 | Extract feedback inside `GenerateCodeHandler` vs LLM root. | Flow Engine Orchestrators are responsible for bridging cross-domain context, making this perfectly aligned with context passing rules. | No |

## Developer Guides Required

Evaluate if this feature introduces a new sub-system, paradigm, or extension layer that requires a Developer Guide for onboarding engineers.

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| None | No new architecture, just minor capability | ⬜ N/A |

## Sub-Feature Breakdown

Single feature — no decomposition.

### SF-1: Interactive Gate Variables (HITL)
- **Scope**: Extend PromptBuilder and Generation handlers to parse and prioritize HITL remarks over linter outputs.
- **FRs**: [FR-1, FR-2]
- **Inputs**: `RunContext.feedback` dict containing loop-back findings and specifically parked remarks.
- **Outputs**: Properly formatted XML prompt text block to LLM payload.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/phase_3/feature_3.26c/feature_3.26c_implementation_plan.md

## Execution Order

Single feature — no decomposition.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | Interactive Gate Variables | — | ✅ | ✅ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: Implementation Plan APPROVED.
**Next step**: Run `/dev docs/roadmap/phase_3/feature_3.26c/feature_3.26c_sf1_implementation_plan.md`
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜
in any row and resume from there using the appropriate workflow.
