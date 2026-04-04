# Design: Project metadata injection

- **Feature ID**: feature_3_15
- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/proposals/roadmap/phase_3/feature_3_15/feature_3_15_design.md

## Feature Overview

Feature 3.13 adds project metadata injection to the system prompt.
It solves the issue of the LLM lacking specific environmental context by injecting the project name, root archetype, language target (Python/OS version), current date/time, and active configuration settings (like LLM profile and validation thresholds) into the prompt.
It interacts with `PromptBuilder` and the configuration module, and does NOT touch the core LLM adapters or backend dispatch mechanisms.
Key constraints: The generated metadata block must remain concise as to avoid consuming too much of the LLM context window.

## Research Findings

### Codebase Patterns
The `PromptBuilder` class in `src/specweaver/llm/prompt_builder.py` is the centralized place for assembling system prompts. It uses an XML-tagged structure mapping priority levels. We can extend it with an `add_project_metadata()` method and a new `_ContentBlock` for metadata. The active config can be retrieved from `SpecWeaverSettings`, and the project name from the database. Language target and OS info can be obtained via the standard Python `platform` and `sys` modules.

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| Python `platform` / `sys` | Built-in | `python_version()`, `system()` | Built-in |
| datetime | Built-in | `datetime.now()` | Built-in |

### Blueprint References
Inspired by Aider's `get_platform_info()`, which explicitly tells the LLM the operating system, language version, and commit hashes to avoid syntax incompatible with the user's environment.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Build Metadata DTO | PipelineRunner / Config | Create `ProjectMetadata` once per run | A single DTO containing project name, archetype, safe strictly-allowlisted config, OS (`platform`), Python version (`sys.version`), and Date is assembled and attached to the run state. |
| FR-2 | Inject into Prompt | PromptBuilder | Call `.add_project_metadata()` | A `<project_metadata>` XML block is added to the prompt at priority 1 using the pre-assembled DTO. |
| FR-3 | Provide safe config | Flow Handlers | Pass `ProjectMetadata` to `PromptBuilder` | Handlers inject the DTO cleanly without needing to manually fetch project parameters or scrub API keys. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Token Budgeting | The metadata block should be concise (around 100-200 tokens typically). |
| NFR-2 | Stability | Core prompts should not break if a property (like project Name) is temporarily unavailable. |
| NFR-3 | Zero Secret Leakage | The injected config MUST use a strict allowlist. Full Pydantic `model_dump_json()` on `SpecWeaverSettings` is FORBIDDEN as it leaks `api_key` to the LLM backend. |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| Python Standard Lib | 3.11+ | `sys.version_info`, `platform.system` | Y | Standard |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Add `add_project_metadata` directly to `PromptBuilder` | Keeps prompt assembly logic centralized. Avoids creating new modules for simple string interpolation. | No |
| AD-2 | Centralized `ProjectMetadata` DTO | Handlers should not each re-query the DB. `PipelineRunner` creates the DTO once and caches it in the flow context. | No |
| AD-3 | Explicit "Language Target" = Environment | We strictly use OS/Python system version to map the execution environment. We do NOT use this to detect target codebase languages (already covered by Feature 3.5). | No |

## Sub-Feature Breakdown

Single feature — no decomposition.

### SF-1: Metadata Injection implementation
- **Scope**: Extend `PromptBuilder` to accept and format project metadata, and update handlers/orchestrators to provide it.
- **FRs**: [FR-1, FR-2, FR-3]
- **Inputs**: Current `SpecWeaverSettings`, Project name from context, system state.
- **Outputs**: `<project_metadata>` tag within LLM prompt.
- **Depends on**: none
- **Impl Plan**: docs/proposals/roadmap/phase_3/feature_3_15/feature_3_15_sf1_implementation_plan.md

## Execution Order

Single feature.
1. SF-1 (no deps — start immediately)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | Metadata Injection | — | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Current status**: Feature 3.13 COMPLETE and COMMITTED on 2026-03-29.
**Next step**: Proceed to the next feature on the roadmap (`feature_3_16` or `feature_3_17`).
