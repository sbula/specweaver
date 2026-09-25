# C-FLOW-05 — Interactive Gate Variables (HITL)

**Status**: APPROVED · **Phase**: 3 · **Legacy ID**: 3.26c · **Feature ID**: C-FLOW-05

| | |
|---|---|
| Touches | `PromptBuilder`; Flow Engine pipeline handlers (`_generation.py`, `_draft.py`, etc.) |
| Not touched | the LLM structural adapters |

## What it does

Puts human `GateType.HITL` rejection remarks into loop-back generation prompts, in a
`<dictator-overrides>` XML section at the highest priority ("never truncated").

Without it, human feedback in loop-back sequences can be ignored or outweighed by linter errors.

Constraints: must use the `<dictator-overrides>` section; human feedback ranks strictly above
standard linter findings; must fit the existing adapter archetype.

## Architecture

- `src/specweaver/infrastructure/llm/prompt_builder.py` has `add_instructions` and similar methods with
  token-aware truncation by integer priority. Priority 0 is "never truncated".
- `context.feedback` carries `loop_back` output to target steps in the Flow Engine
  (`src/specweaver/core/flow/runner.py` and `gates.py`). Handlers (e.g. `GenerateCodeHandler`) unpack
  it and route it into the prompt.
- `RunContext` isolates feedback state, so this fits the existing `Flow` routing with no architectural
  switch.

External dependencies: none — standard XML tags, pure text manipulation. No `ORIGINS.md` blueprint
for `3.26c` beyond the top-level roadmap instruction.

## Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Put `add_dictator_overrides` on `PromptBuilder` | Keeps prompt token management strictly within the `llm/` archetype. | No |
| AD-2 | Extract feedback inside `GenerateCodeHandler`, not at the LLM root. | Flow Engine orchestrators bridge cross-domain context, per the context-passing rules. | No |

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | PromptBuilder overrides section | System | Inject human feedback into `<dictator-overrides>` XML section at priority 0 | The LLM receives the human feedback, never truncated by context limits. |
| FR-2 | Feedback extraction | Flow Handlers | Extract HITL rejection remarks from `RunContext.feedback` separately from generic automated errors | Human and Linter errors are distinct streams going into the loop-back code generation. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Archetype Strictness | `llm/` module must remain an adapter and forbid `loom/*`. **[proof: arch — tach/lint gate, not pytest]** |
| NFR-2 | Extensibility | `<dictator-overrides>` must work with the existing Gemini, OpenAI, Claude adapters without adapter changes. |

## Sub-features

Single feature — no decomposition. Developer guide: none needed (no new architecture).

| SF | Does | FRs | Inputs → Outputs | Plan |
|----|------|-----|------------------|------|
| SF-01 | Extend `PromptBuilder` and generation handlers to parse HITL remarks and rank them over linter output | FR-1, FR-2 | `RunContext.feedback` (loop-back findings + parked remarks) → XML prompt block in the LLM payload | [sf01](C-FLOW-05_sf01_implementation_plan.md) |

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Interactive Gate Variables | — | ✅ | ✅ | ⬜ | ⬜ | ⬜ |
